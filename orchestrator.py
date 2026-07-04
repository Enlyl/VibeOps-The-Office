"""
orchestrator.py — Simplified Orchestrator for test backward-compat.
"""

from __future__ import annotations

import logging
import re
from typing import Optional
from config import AppConfig, config
from llm_interface import get_mock_response, call_live_gemini_api

logger = logging.getLogger("vibeops.orchestrator")

# ── Simple routing patterns ────────────────────────────────────────────────

_NAME_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(elena|елена|ментор|mentor|senior)\b", re.IGNORECASE), "elena"),
    (re.compile(r"\b(chad|чад|джуниор|junior|vibe.?coder)\b", re.IGNORECASE), "chad"),
    (re.compile(r"\b(robert|роберт|mlops|mlоps|validator)\b", re.IGNORECASE), "robert"),
    (re.compile(r"\b(geoffrey|джеффри|boss|cto)\b", re.IGNORECASE), "geoffrey"),
]

_CODE_PATTERNS = [
    re.compile(r"\bimport\b"),
    re.compile(r"\bdf\s*\["),
    re.compile(r"\bpd\."),
    re.compile(r"\bnp\."),
    re.compile(r"```python", re.IGNORECASE),
    re.compile(r"\bdef\s+\w+\s*\("),
    re.compile(r"\w+\s*=\s*.+"),
]


def _detect_named_agent(text: str) -> Optional[str]:
    for pattern, name in _NAME_PATTERNS:
        if pattern.search(text):
            return name
    return None


def _contains_code(text: str) -> bool:
    for p in _CODE_PATTERNS:
        if p.search(text):
            return True
    return False


# ── Simple Orchestrator ────────────────────────────────────────────────────


class Orchestrator:
    """Minimal orchestrator — routes input and returns mock/live responses."""

    def __init__(self, cfg: Optional[AppConfig] = None):
        self.cfg = cfg or config()

    def run(self, user_input: str, mock_mode: bool = True, **kwargs) -> list[tuple[str, str]]:
        text = user_input.strip()
        named = _detect_named_agent(text)

        if named == "elena":
            agents = ["elena"]
        elif named == "chad":
            agents = ["chad"]
            if mock_mode and "inplace" in get_mock_response("chad"):
                agents.append("elena")
        elif named == "robert":
            agents = ["robert"]
        elif named == "geoffrey":
            agents = ["geoffrey"]
        elif _contains_code(text):
            agents = ["robert"]
        else:
            agents = ["chad", "elena"]

        turns: list[tuple[str, str]] = []
        for agent in agents:
            if mock_mode:
                content = get_mock_response(agent)
            else:
                content = call_live_gemini_api(f"Ты — {agent}.", text)
            turns.append((agent, content))
        return turns
