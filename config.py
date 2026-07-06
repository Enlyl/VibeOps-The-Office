"""
config.py — VibeOps Secure Configuration Loader
================================================
Pillar 8: Security & Secrets Management

Loads all secrets exclusively from the `.env` file via environment variables.
API keys are NEVER hardcoded. This module is the single entry point for
configuration access across the entire VibeOps system.

Usage:
    from config import get_config
    cfg = get_config()
    print(cfg.gemini_model)   # safe: non-sensitive
    # cfg.gemini_api_key      # available but never logged
"""

import os
import sys
import logging
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Logging — deliberately does NOT log secret values
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ENV_FILE = Path(__file__).parent / ".env"

# Default model per Output Filter v2 spec
DEFAULT_MODEL: str = "gemini-3.1-flash-lite"

# Token budget per Pillar 7
TOKEN_LIMIT: int = 1_000_000

# Short-term memory window per Pillar 5
MEMORY_WINDOW: int = 10

# Sandbox timeout per Pillar 4
SANDBOX_TIMEOUT_SECONDS: int = 10

# MCP read-only workspace paths per Pillar 3
MCP_DIRTY_DATA_PATH: str = "./workspace/dirty_data.csv"
MCP_MODEL_DOCS_PATH: str = "./workspace/model_docs.md"


# ---------------------------------------------------------------------------
# Config Dataclass
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class AppConfig:
    """
    Immutable application configuration loaded from environment variables.

    Attributes:
        gemini_api_key:         Gemini API key — loaded from GEMINI_API_KEY env var.
                                Never log or print this value.
        gemini_model:           Active Gemini model identifier.
        token_limit:            Hard token budget for the active context window.
        memory_window:          Number of messages kept in short-term memory.
        sandbox_timeout:        Max execution time (seconds) for LocalPythonSandbox.
        mcp_dirty_data_path:    Read-only MCP path to the raw dataset.
        mcp_model_docs_path:    Read-only MCP path to model documentation.
    """
    gemini_api_key: str
    gemini_model: str = DEFAULT_MODEL
    token_limit: int = TOKEN_LIMIT
    memory_window: int = MEMORY_WINDOW
    sandbox_timeout: int = SANDBOX_TIMEOUT_SECONDS
    mcp_dirty_data_path: str = MCP_DIRTY_DATA_PATH
    mcp_model_docs_path: str = MCP_MODEL_DOCS_PATH

    def __repr__(self) -> str:
        """Safe repr — masks the API key to prevent accidental log leakage."""
        masked_key = f"{self.gemini_api_key[:6]}...{self.gemini_api_key[-4:]}" \
            if len(self.gemini_api_key) > 10 else "***"
        return (
            f"AppConfig("
            f"gemini_api_key='{masked_key}', "
            f"gemini_model='{self.gemini_model}', "
            f"token_limit={self.token_limit}, "
            f"memory_window={self.memory_window}, "
            f"sandbox_timeout={self.sandbox_timeout}s"
            f")"
        )


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------
def _load_env() -> None:
    """
    Load environment variables from the .env file.

    Raises:
        FileNotFoundError: If the .env file does not exist.
    """
    if not ENV_FILE.exists():
        logger.warning(
            ".env file not found at '%s'. "
            "Falling back to system environment variables. "
            "Create a .env file from .env.example for local development.",
            ENV_FILE,
        )
    else:
        load_dotenv(dotenv_path=ENV_FILE, override=False)
        logger.debug(".env loaded from '%s'", ENV_FILE)


def _require_env(key: str) -> str:
    """
    Retrieve a required environment variable by key.

    Args:
        key: The name of the environment variable.

    Returns:
        The string value of the environment variable.

    Raises:
        SystemExit: If the variable is missing or empty, logs a CRITICAL
                    error and exits to prevent the system from running
                    without a valid API key.
    """
    value = os.getenv(key, "").strip()
    if not value:
        logger.critical(
            "FATAL: Required environment variable '%s' is not set. "
            "Add it to your .env file and restart. Exiting.",
            key,
        )
        sys.exit(1)
    return value


def get_config() -> AppConfig:
    """
    Build and return the immutable AppConfig for the VibeOps system.

    Loads secrets from environment variables (via .env) and validates
    that all required keys are present before returning configuration.

    Returns:
        AppConfig: A frozen dataclass instance with all system settings.

    Example:
        >>> cfg = get_config()
        >>> cfg.gemini_model
        'gemini-2.5-flash-lite'
    """
    _load_env()

    api_key = _require_env("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL", DEFAULT_MODEL).strip()

    config = AppConfig(
        gemini_api_key=api_key,
        gemini_model=model,
    )

    logger.info("Configuration loaded: %s", config)  # safe: __repr__ masks the key
    return config


# ---------------------------------------------------------------------------
# Singleton accessor (optional convenience)
# ---------------------------------------------------------------------------
_config_cache: AppConfig | None = None


def config() -> AppConfig:
    """
    Return a cached singleton AppConfig instance.

    Subsequent calls return the same object without re-reading the .env file.

    Returns:
        AppConfig: The shared application configuration instance.
    """
    global _config_cache
    if _config_cache is None:
        _config_cache = get_config()
    return _config_cache
