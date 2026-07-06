"""
llm_interface.py — VibeOps Gemini API Client
=============================================
Supports text-only and function-calling (MCP tool) flows.
"""

import json
import logging
from typing import Any

from google import genai
from google.genai import types
from config import config

logger = logging.getLogger("vibeops.llm")

_MAX_TOOL_LOOP_TURNS = 5


# ============================================================================
# Module-level helpers (used directly by app.py)
# ============================================================================


def call_live_gemini_api(system_instruction: str, prompt: str) -> str:
    """
    Call the live Gemini API.  One attempt, no retry.
    Raises on any error so the caller can fall back to mock.
    """
    cfg = config()
    client = genai.Client(api_key=cfg.gemini_api_key)
    response = client.models.generate_content(
        model=cfg.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.7,
        ),
    )
    return response.text if response.text else "[Empty response]"


def call_with_tools(
    system_instruction: str,
    prompt: str,
    tool_definitions: list[dict],
    tool_executor: Any,
) -> str:
    """
    Call Gemini with function-declaration tools and run the tool loop.
    `tool_definitions` — list of dicts with 'name', 'description', 'parameters', 'server'.
    `tool_executor` — callable(server, tool_name, args) -> dict (result or error).
    """
    cfg = config()
    client = genai.Client(api_key=cfg.gemini_api_key)

    _ALLOWED_PARAM_KEYS = {"type", "description", "properties", "required", "items", "enum", "default"}

    def _clean_params(params: dict) -> dict:
        if not isinstance(params, dict):
            return {"type": "object", "properties": {}}
        cleaned = {k: v for k, v in params.items() if k in _ALLOWED_PARAM_KEYS}
        cleaned.setdefault("type", "object")
        if "properties" in cleaned:
            for pname, pval in cleaned["properties"].items():
                if isinstance(pval, dict):
                    cleaned["properties"][pname] = _clean_params(pval)
                elif not isinstance(pval, dict):
                    cleaned["properties"][pname] = {"type": "string"}
        return cleaned

    declarations = []
    for fd in tool_definitions:
        declarations.append(
            types.FunctionDeclaration(
                name=fd["name"],
                description=fd.get("description", ""),
                parameters=_clean_params(fd.get("parameters", {})) if fd.get("parameters") else {"type": "object"},
            )
        )

    contents = [types.Content(role="user", parts=[types.Part(text=prompt)])]

    if not declarations:
        response = client.models.generate_content(
            model=cfg.gemini_model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.7,
            ),
        )
        return response.text if response.text else "[Empty response]"

    tool_config = types.Tool(functionDeclarations=declarations)
    history: list[types.Content] = []
    final_text = ""

    for _ in range(_MAX_TOOL_LOOP_TURNS):
        response = client.models.generate_content(
            model=cfg.gemini_model,
            contents=contents + history,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=[tool_config],
                temperature=0.7,
            ),
        )

        if not response.candidates:
            final_text = response.text or "[Empty response]"
            break

        candidate = response.candidates[0]
        if not candidate.content or not candidate.content.parts:
            final_text = response.text or "[Empty response]"
            break

        has_tool_call = any(part.function_call for part in candidate.content.parts)

        if not has_tool_call:
            final_text = "".join(
                p.text for p in candidate.content.parts if p.text
            ) or "[Empty response]"
            break

        for part in candidate.content.parts:
            fc = part.function_call
            if fc is None:
                continue

            tool_name = fc.name
            tool_args = dict(fc.args) if fc.args else {}

            server_name = ""
            for td in tool_definitions:
                if td["name"] == tool_name:
                    server_name = td.get("server", "")
                    break

            result = tool_executor(server_name, tool_name, tool_args)

            history.append(
                types.Content(
                    role="model",
                    parts=[types.Part(function_call=fc)],
                )
            )
            history.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part(
                            function_response=types.FunctionResponse(
                                name=tool_name,
                                response={"content": json.dumps(result, ensure_ascii=False)},
                            )
                        )
                    ],
                )
            )

    return final_text or "[Empty response]"


def get_mock_response(agent: str, workspace_info: str = "") -> str:
    """Return a contextual mock response for the given agent role."""
    ws = workspace_info if workspace_info else "**Workspace**: no data loaded."

    pool = {
        "elena": (
            "🧠 **ELENA:** Interesting problem! Looking at our dataset, "
            f"I see we have some data to work with.\n\n{ws}\n\n"
            "Before jumping into code, let's think conceptually. "
            "What do you notice about the columns and their types? "
            "How would you describe the relationship between the "
            "variables we need to examine?"
        ),
        "elena_429": (
            "🧠 **ELENA (Simulation):** The live API is unavailable, "
            "but we can still think through this together.\n\n"
            f"{ws}\n\nGiven what's in our workspace, "
            "what's your mental model of the data transformation we need?"
        ),
        "chad": (
            "🔥 **CHAD:** Bro, it's simple! Just load the dataset and run "
            "`df.dropna(inplace=True)`, that's what I always use on Stack Overflow!"
        ),
        "robert": (
            "🛠️ **ROBERT:** I've reviewed the request against the available data.\n\n"
            f"{ws}\n\n"
            "The sandbox is ready. If you need code executed, "
            "paste it and I'll run it with full traceback logging."
        ),
        "robert_sandbox_ok": (
            "🛠️ **ROBERT:** The sandbox executed successfully. "
            f"{ws}\n\n"
            "Review the execution output below — it contains stdout, stderr, "
            "and performance metrics from the live run."
        ),
        "robert_429": (
            "🛠️ **ROBERT (Simulation):** Live sandbox API is unavailable. "
            f"{ws}\n\n"
            "I can still discuss the approach. What's the transformation you need?"
        ),
        "chad_429": (
            "🔥 **CHAD (Simulation):** Live API is down, bro! "
            "But the quick fix is always the same — just drop the nulls. "
            "We'll figure out the details when the API is back."
        ),
        "geoffrey": (
            "👔 **GEOFFREY:** Our key business goal is improving analytics "
            "quality and reducing customer churn."
        ),
        "geoffrey_429": (
            "👔 **GEOFFREY (Simulation):** The live API is currently unavailable. "
            "Our business priorities remain unchanged — focus on analytics quality "
            "and customer retention metrics."
        ),
    }
    return pool.get(agent, f"[Mock response for {agent}]")


