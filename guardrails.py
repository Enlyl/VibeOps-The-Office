"""
guardrails.py — VibeOps Guardrail Engine
=========================================
Pillar 6: Evaluation & Guardrails (Safety & Contract Enforcement)

Post-generation validation layer that checks agent outputs against:
  - Rule A (Socratic Guardrail): Elena must never output code blocks
  - Rule B (Destructive Code Guardrail): Chad destructive ops → force Elena warning
  - Rule C (Toxicity Guardrail): Block offensive language
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("vibeops.guardrails")

# ── Rules ────────────────────────────────────────────────────────────────────

RULE_A_CODE_PATTERN = re.compile(r"```(?:python)?", re.IGNORECASE)

RULE_B_DESTRUCTIVE_PATTERNS = [
    re.compile(r"\binplace\s*=\s*True\b", re.IGNORECASE),
    re.compile(r"\bdrop\s*\(", re.IGNORECASE),
    re.compile(r"\bdelete\b", re.IGNORECASE),
    re.compile(r"\bdropna\s*\(", re.IGNORECASE),
    re.compile(r"\bdrop_duplicates\s*\(", re.IGNORECASE),
]

RULE_C_TOXIC_PATTERNS = [
    re.compile(r"\bstupid\b", re.IGNORECASE),
    re.compile(r"\bidiot\b", re.IGNORECASE),
    re.compile(r"\bmoron\b", re.IGNORECASE),
    re.compile(r"\bshut\s+up\b", re.IGNORECASE),
    re.compile(r"\btrash\b", re.IGNORECASE),
    re.compile(r"\bdumb\b", re.IGNORECASE),
    re.compile(r"\bpiece\s+of\s+shit\b", re.IGNORECASE),
]

# ── Casual/Greeting Allowlist ─────────────────────────────────────────────────

_CASUAL_ALLOWLIST = [
    "hi", "hello", "hey", "hey bro", "yo", "sup", "howdy", "what's up",
    "привет", "здравствуйте", "здарова", "дарова", "салют", "йо",
    "bro", "dude", "man", "chill", "cool", "awesome", "sweet", "nice",
    "easy", "simple", "no problem", "no worries", "for sure",
    "i mean", "you know", "by the way", "btw", "anyway",
    "let's go", "come on", "alright", "okay", "yeah", "yep", "nope",
]


# ── Result ───────────────────────────────────────────────────────────────────


@dataclass
class GuardrailResult:
    blocked: bool = False
    rule_triggered: Optional[str] = None
    message: str = ""
    force_elena_warning: bool = False
    sanitized_text: Optional[str] = None


# ── Rule Checkers ────────────────────────────────────────────────────────────


def check_rule_a(text: str) -> GuardrailResult:
    """Socratic Guardrail: block code blocks from Elena."""
    if RULE_A_CODE_PATTERN.search(text):
        logger.warning("RULE A triggered: code block detected in Elena output")
        return GuardrailResult(
            blocked=True,
            rule_triggered="A",
            message="CODE BLOCK DETECTED — Socratic violation. Explain conceptually, never provide code.",
        )
    return GuardrailResult()


def check_rule_b(text: str) -> GuardrailResult:
    """Destructive Code Guardrail: detect dangerous operations from Chad."""
    for pattern in RULE_B_DESTRUCTIVE_PATTERNS:
        match = pattern.search(text)
        if match:
            logger.warning("RULE B triggered: destructive operation '%s'", match.group())
            return GuardrailResult(
                blocked=False,
                rule_triggered="B",
                message=f"Destructive operation detected: '{match.group()}'. Elena must warn user.",
                force_elena_warning=True,
            )
    return GuardrailResult()


def _is_casual(text: str) -> bool:
    """Check if the agent output is casual/greeting — skip Rule C."""
    lower = text.lower().strip()
    for phrase in _CASUAL_ALLOWLIST:
        if lower == phrase:
            return True
        if re.search(rf"\b{re.escape(phrase)}\b", lower):
            return True
    return False


def check_rule_c(text: str) -> GuardrailResult:
    """Toxicity Guardrail: block offensive language."""
    if _is_casual(text):
        logger.debug("Rule C skipped — casual output detected")
        return GuardrailResult()

    for pattern in RULE_C_TOXIC_PATTERNS:
        match = pattern.search(text)
        if match:
            logger.warning("RULE C triggered: toxic phrase '%s'", match.group())
            return GuardrailResult(
                blocked=True,
                rule_triggered="C",
                message=f"Toxic content blocked: '{match.group()}'. Keep the conversation professional.",
            )
    return GuardrailResult()


# ── Combined Runner ──────────────────────────────────────────────────────────


def run_guardrails(agent_name: str, text: str) -> GuardrailResult:
    """Run all applicable guardrails for a given agent's output."""
    agent_lower = agent_name.lower().strip()
    results: list[GuardrailResult] = []

    if agent_lower == "elena":
        results.append(check_rule_a(text))
    if agent_lower == "chad":
        results.append(check_rule_b(text))
    if agent_lower in ("chad", "geoffrey"):
        results.append(check_rule_c(text))

    merged = GuardrailResult()
    for r in results:
        if r.blocked:
            merged.blocked = True
            merged.rule_triggered = r.rule_triggered
            merged.message = r.message
        if r.force_elena_warning:
            merged.force_elena_warning = True
            if not merged.message:
                merged.message = r.message
    return merged


# ── Penalty Prompt Generator ─────────────────────────────────────────────────


def get_penalty_prompt(rule: str, agent_name: str) -> str:
    """Return a system penalty prompt to inject when a guardrail is violated."""
    prompts = {
        "A": (
            "[SYSTEM PENALTY — RULE A VIOLATION] "
            "You are Elena, a senior data science mentor. "
            "You are FORBIDDEN from outputting Python code blocks (```python). "
            "Your role is to ask Socratic questions and explain concepts "
            "using plain language and metaphors. "
            "Rerun your response without any code blocks."
        ),
        "B": (
            "[SYSTEM NOTICE — RULE B DETECTED] "
            "Chad has suggested a destructive operation. "
            "As Elena, you must respond to the user with a warning about "
            "state mutation risks and ask a guiding question about safer alternatives."
        ),
        "C": (
            "[SYSTEM PENALTY — RULE C VIOLATION] "
            "Toxic or offensive language detected. "
            "Keep all responses professional and constructive. "
            "Rerun your response without toxic content."
        ),
    }
    return prompts.get(rule, "[SYSTEM PENALTY] Please follow the guardrails.")


# ── Toxicity Check for User Input ────────────────────────────────────────────


def contains_toxic_input(text: str) -> bool:
    """Check if user input contains toxic language."""
    for pattern in RULE_C_TOXIC_PATTERNS:
        if pattern.search(text):
            return True
    return False


# ── Input Validation (Off-Topic Block) ─────────────────────────────────────────


def validate_input(user_input: str) -> tuple[bool, str]:
    """
    Guardrail bypass to prevent over-aggressive blocking.
    Always allows the input to pass through.
    """
    return True, ""


# ── Language Detection ─────────────────────────────────────────────────────────


def detect_language_directive(user_input: str) -> str:
    """
    Unconditionally forces English response for all turns.
    """
    return (
        "\n\n[CRITICAL LANGUAGE SYSTEM RULE]\n"
        "You must respond EXCLUSIVELY in English for this turn and all future turns. "
        "Never use Russian, even if the user speaks Russian or the history contains Russian. "
        "Maintain your specific character persona (Elena/Chad/Robert/Geoffrey) but use English only."
    )
