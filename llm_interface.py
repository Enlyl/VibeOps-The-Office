"""
llm_interface.py — VibeOps Gemini API Client
=============================================
"""

import logging
from google import genai
from google.genai import types
from config import config

logger = logging.getLogger("vibeops.llm")


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
        "robert_429": (
            "🛠️ **ROBERT (Simulation):** Live sandbox API is unavailable. "
            f"{ws}\n\n"
            "I can still discuss the approach. What's the transformation you need?"
        ),
        "geoffrey": (
            "👔 **GEOFFREY:** Our key business goal is improving analytics "
            "quality and reducing customer churn."
        ),
    }
    return pool.get(agent, f"[Mock response for {agent}]")


# ============================================================================
# LLMClient class (backward-compat — used by test_agents.py)
# ============================================================================


class LLMClient:
    """Simplified client — delegates to module-level helpers."""

    def __init__(self):
        self.cfg = config()
        self.client = genai.Client(api_key=self.cfg.gemini_api_key)
        self.model_name = self.cfg.gemini_model

    def generate_agent_response(
        self,
        agent_name: str,
        system_instruction: str,
        prompt_text: str,
        tools: list = None,
    ) -> str:
        """One-shot: try live API, fall back to mock on any error."""
        try:
            return call_live_gemini_api(system_instruction, prompt_text)
        except Exception as e:
            logger.warning("LLM_INTERFACE | Live call failed, falling back to mock: %s", e)
            return get_mock_response(agent_name)


class MockLLMClient:
    """Mock client — always returns local responses (used by test_agents.py)."""

    def generate_agent_response(
        self,
        agent_name: str,
        system_instruction: str,
        prompt_text: str,
        tools: list = None,
    ) -> str:
        return get_mock_response(agent_name)