"""
mcp_manager.py — MCP Server Manager for VibeOps
================================================
Launches MCP server processes, connects via stdio transport,
and exposes tools as callable functions for the Gemini API tool loop.
"""

import asyncio
import atexit
import json
import logging
import threading
from pathlib import Path
from typing import Any

from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession
from mcp.types import Tool as McpTool, CallToolResult

logger = logging.getLogger("vibeops.mcp")

_CONFIG_PATH = Path(__file__).parent / "mcp_config.json"

_MCP_SERVER_TIMEOUT: float = 20.0


def _load_config() -> dict[str, Any]:
    if not _CONFIG_PATH.exists():
        logger.warning("MCP config not found at '%s'", _CONFIG_PATH)
        return {}
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("mcpServers", {})


class MCPClient:
    """Wraps a single MCP server process and its session."""

    def __init__(self, server_name: str, params: StdioServerParameters):
        self.server_name = server_name
        self.params = params
        self.session: ClientSession | None = None
        self._read_stream = None
        self._write_stream = None
        self._stdio_ctx = None

    async def start(self):
        self._stdio_ctx = stdio_client(self.params)
        self._read_stream, self._write_stream = await self._stdio_ctx.__aenter__()
        self.session = ClientSession(self._read_stream, self._write_stream)
        await self.session.__aenter__()
        await self.session.initialize()

    async def stop(self):
        if self._stdio_ctx:
            try:
                await self._stdio_ctx.__aexit__(None, None, None)
            except BaseException:
                pass
            self._stdio_ctx = None
        if self.session:
            try:
                await self.session.__aexit__(None, None, None)
            except BaseException:
                pass
            self.session = None

    async def list_tools(self) -> list[McpTool]:
        if not self.session:
            return []
        result = await self.session.list_tools()
        return result.tools

    async def call_tool(self, name: str, arguments: dict | None = None) -> CallToolResult:
        if not self.session:
            raise RuntimeError(f"MCP server '{self.server_name}' is not connected")
        return await self.session.call_tool(name, arguments or {})


class MCPManager:
    """Manages multiple MCP server connections and provides a unified tool interface."""

    def __init__(self):
        self._clients: dict[str, MCPClient] = {}
        self._started = False

    async def start_all(self):
        servers = _load_config()
        if not servers:
            logger.info("No MCP servers configured.")
            return

        for name, cfg in servers.items():
            try:
                client = MCPClient(
                    server_name=name,
                    params=StdioServerParameters(
                        command=cfg["command"],
                        args=cfg.get("args", []),
                        env=cfg.get("env"),
                    ),
                )
                await asyncio.wait_for(client.start(), timeout=_MCP_SERVER_TIMEOUT)
                self._clients[name] = client
                tools = await client.list_tools()
                tool_names = [t.name for t in tools]
                logger.info("MCP server '%s' connected. Tools: %s", name, tool_names)
            except Exception as e:
                logger.warning("MCP server '%s' failed to start: %s", name, e)

        self._started = True

    async def stop_all(self):
        for name, client in self._clients.items():
            try:
                await client.stop()
                logger.info("MCP server '%s' stopped.", name)
            except BaseException as e:
                logger.warning("MCP server '%s' stop error: %s", name, e)
        self._clients.clear()
        self._started = False

    async def get_all_tools(self) -> list[dict]:
        """Return all tools as Gemini-compatible function declarations."""
        all_tools = []
        for server_name, client in self._clients.items():
            if not client.session:
                continue
            try:
                tools = await client.list_tools()
                for t in tools:
                    fd = {
                        "name": t.name,
                        "description": t.description or "",
                        "parameters": t.inputSchema or {"type": "object", "properties": {}},
                        "server": server_name,
                    }
                    all_tools.append(fd)
            except Exception as e:
                logger.warning("Failed listing tools for '%s': %s", server_name, e)
        return all_tools

    async def call_tool(self, server: str, name: str, arguments: dict | None = None) -> dict:
        """Call a tool on a specific MCP server."""
        client = self._clients.get(server)
        if not client:
            return {"error": f"Server '{server}' not connected."}
        try:
            result = await client.call_tool(name, arguments or {})
            parts = []
            for content in result.content:
                if hasattr(content, "text"):
                    parts.append(content.text)
                else:
                    parts.append(str(content))
            return {"result": "\n".join(parts)}
        except Exception as e:
            logger.error("Tool call '%s/%s' failed: %s", server, name, e)
            return {"error": str(e)}

    @property
    def is_ready(self) -> bool:
        return self._started and len(self._clients) > 0


# ============================================================================
# Sync wrappers (for Streamlit / non-async contexts)
# ============================================================================

_manager_instance: MCPManager | None = None


def get_mcp_manager() -> MCPManager:
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = MCPManager()
    return _manager_instance


async def initialize_mcp():
    manager = get_mcp_manager()
    await manager.start_all()
    return manager


async def shutdown_mcp():
    manager = get_mcp_manager()
    await manager.stop_all()


# Dedicated background event loop for MCP operations.
# This avoids issues with Streamlit/Tornado event loops and
# ensures MCP sessions persist across sync calls.
_MCP_LOOP: asyncio.AbstractEventLoop | None = None
_MCP_LOOP_THREAD: threading.Thread | None = None


_MCP_SHUTTING_DOWN = False


def _ensure_mcp_loop():
    """Start a daemon background thread with its own event loop."""
    global _MCP_LOOP, _MCP_LOOP_THREAD
    if _MCP_SHUTTING_DOWN:
        return None
    if _MCP_LOOP is not None and not _MCP_LOOP.is_closed():
        return _MCP_LOOP
    _MCP_LOOP = asyncio.new_event_loop()
    _MCP_LOOP_THREAD = threading.Thread(
        target=_MCP_LOOP.run_forever,
        daemon=True,
        name="mcp-event-loop",
    )
    _MCP_LOOP_THREAD.start()
    return _MCP_LOOP


def _run_async(coro):
    """Schedule a coroutine on the dedicated MCP event loop and wait for the result."""
    loop = _ensure_mcp_loop()
    if loop is None:
        return None
    return asyncio.run_coroutine_threadsafe(coro, loop).result()


def _stop_mcp_loop():
    """Shut down the background MCP event loop."""
    global _MCP_LOOP, _MCP_LOOP_THREAD, _MCP_SHUTTING_DOWN
    _MCP_SHUTTING_DOWN = True
    loop = _MCP_LOOP
    thread = _MCP_LOOP_THREAD
    if loop is not None and not loop.is_closed():
        loop.call_soon_threadsafe(loop.stop)
    if thread is not None and thread is not threading.current_thread():
        thread.join(timeout=5)
    if loop is not None and not loop.is_closed():
        try:
            loop.close()
        except RuntimeError:
            pass
    _MCP_LOOP = None
    _MCP_LOOP_THREAD = None


# Suppress harmless anyio cancel-scope warnings during shutdown
import warnings
warnings.filterwarnings("ignore", message=".*cancel scope.*different task.*")
warnings.filterwarnings("ignore", message=".*unhandled errors in a TaskGroup.*")

# Register MCP loop cleanup on process exit
atexit.register(_stop_mcp_loop)


def initialize_mcp_sync():
    """Synchronous wrapper — blocks until MCP servers are ready."""
    return _run_async(initialize_mcp())


def shutdown_mcp_sync():
    """Synchronous wrapper — stops all MCP servers."""
    _run_async(shutdown_mcp())


def get_all_tools_sync() -> list[dict]:
    """Synchronous wrapper for Streamlit — returns tool declarations."""
    manager = get_mcp_manager()
    if not manager.is_ready:
        return []
    return _run_async(manager.get_all_tools())


def call_tool_sync(server: str, name: str, arguments: dict | None = None) -> dict:
    """Synchronous wrapper for calling a tool — for Streamlit."""
    manager = get_mcp_manager()
    return _run_async(manager.call_tool(server, name, arguments))
