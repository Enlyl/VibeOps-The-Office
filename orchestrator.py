"""
orchestrator.py — Simplified Orchestrator for test backward-compat.
===============================================================
Routes through the unified router.py. Kept for backward compatibility
with test_agents.py and other scripts that import Orchestrator.
"""

from __future__ import annotations

import logging
from typing import Optional
from config import AppConfig, config
from llm_interface import get_mock_response, call_live_gemini_api
from router import determine_agent_chain

logger = logging.getLogger("vibeops.orchestrator")


class Orchestrator:
    """
    Minimal orchestrator — uses router.py for all routing decisions.
    Routes input and returns mock/live responses in order.
    """

    def __init__(self, cfg: Optional[AppConfig] = None):
        self.cfg = cfg or config()

    def run(self, user_input: str, mock_mode: bool = True, **kwargs) -> list[tuple[str, str]]:
        text = user_input.strip()
        agents = determine_agent_chain(text)

        turns: list[tuple[str, str]] = []
        for agent in agents:
            if mock_mode:
                content = get_mock_response(agent)
            else:
                content = call_live_gemini_api(f"Ты — {agent}.", text)
            turns.append((agent, content))
        return turns
