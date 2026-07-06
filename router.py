"""
router.py — Unified Single Source of Truth for Agent Routing
=============================================================
Pillar 2: Multi-Agent Architecture

Consolidates ALL routing logic that was previously split across
app.py (determine_active_agent) and orchestrator.py (Orchestrator.run).

Usage:
    from router import determine_active_agent, determine_agent_chain
"""

from __future__ import annotations

import re
from typing import Optional

# ── Agent Identity Patterns ─────────────────────────────────────────────────
# Each pattern is (compiled_regex, agent_name)
# Word boundaries (\b) prevent false positives (e.g. "import" in "импортировать")

_AGENT_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Elena — Socratic mentor / senior
    (re.compile(r"\b(elena|елена|ментор|mentor|senior)\b", re.IGNORECASE), "elena"),
    # Chad — vibe coder / junior
    (re.compile(r"\b(chad|чад|джуниор|junior|vibe.?coder)\b", re.IGNORECASE), "chad"),
    # Robert — MLOps / sandbox / validator
    (re.compile(r"\b(robert|роберт|mlops|mlоps|validator|sandbox)\b", re.IGNORECASE), "robert"),
    # Geoffrey — Head of AI / boss
    (re.compile(r"\b(geoffrey|джеффри|джеф|jeff|boss|cto|godfather)\b", re.IGNORECASE), "geoffrey"),
]

# ── Code Detection Patterns ────────────────────────────────────────────────

_CODE_PATTERNS: list[re.Pattern] = [
    re.compile(r"\bimport\b"),
    re.compile(r"\bdf\s*\["),
    re.compile(r"\bpd\."),
    re.compile(r"\bnp\."),
    re.compile(r"```python", re.IGNORECASE),
    re.compile(r"\bdef\s+\w+\s*\("),
    re.compile(r"\bclass\s+\w+"),
]

# ── Russian/Hybrid Code Keywords ───────────────────────────────────────────
# Additional keywords for mixed-language inputs

_RU_CODE_KEYWORDS = [
    "выполни", "запусти", "код", "скрипт",
    "sandbox", "ошибка", "traceback",
]


# ── Public API ──────────────────────────────────────────────────────────────

def _detect_named_agent(text: str) -> Optional[str]:
    """Return agent name if a name keyword matches, else None."""
    for pattern, name in _AGENT_PATTERNS:
        if pattern.search(text):
            return name
    return None


def _contains_code(text: str) -> bool:
    """Return True if the input contains programming code patterns."""
    for p in _CODE_PATTERNS:
        if p.search(text):
            return True
    for kw in _RU_CODE_KEYWORDS:
        if kw in text.lower():
            return True
    return False


def determine_active_agent(user_input: str) -> str:
    """
    Return the SINGLE best agent to handle a given user input.
    Used by the Streamlit UI (app.py) — returns exactly one agent per turn.

    Priority:
        1. Named agent mention (Elena, Chad, Robert, Geoffrey)
        2. Code content → Robert
        3. Default → Elena (Socratic mentor)

    AGENTS.md contract: question/chat text → CHAD → ELENA
    So for default case we return "chad" (Elena follows via determine_agent_chain in orchestrator).
    """
    text = user_input.strip()

    named = _detect_named_agent(text)
    if named:
        return named

    if _contains_code(text):
        return "robert"

    # Default: Elena (Socratic mentor) for general questions
    return "elena"


def determine_agent_chain(user_input: str) -> list[str]:
    """
    Return an ORDERED list of agents that should respond.
    Used by Orchestrator.run() — always returns a single-agent list.

    Rule: Elena is the default. Other agents activate only when explicitly
    named or when code is detected (→ Robert).
    """
    text = user_input.strip()
    named = _detect_named_agent(text)

    if named:
        return [named]
    elif _contains_code(text):
        return ["robert"]
    else:
        return ["elena"]
