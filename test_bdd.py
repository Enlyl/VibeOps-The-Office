"""
test_bdd.py — BDD Contract Validation Tests
=============================================
Pillar 9: BDD Specification Compliance

Implements the Gherkin scenarios from vibeops_simulation.feature
as executable pytest tests. Each scenario maps to the current live code.

Run:  python -m pytest test_bdd.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from router import determine_active_agent, determine_agent_chain
from guardrails import run_guardrails


# ── Helpers ─────────────────────────────────────────────────────────────────

GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"


def test_route_code_to_robert():
    """Scenario: Route user code request through Robert"""
    text = "import pandas as pd\ndf = pd.read_csv('dirty_data.csv')\ndf['age'].mean()"
    agent = determine_active_agent(text)
    assert agent == "robert", f"Expected robert, got {agent}"
    chain = determine_agent_chain(text)
    assert chain == ["robert"], f"Expected [robert], got {chain}"
    print(f"  {GREEN}✓ Code → Robert{RESET}")

def test_route_russian_code_to_robert():
    """Russian code keywords route to Robert"""
    text = "выполни код: import pandas"
    agent = determine_active_agent(text)
    assert agent == "robert", f"Expected robert, got {agent}"
    print(f"  {GREEN}✓ Russian code keywords → Robert{RESET}")


def test_route_general_question_to_elena():
    """Scenario: Default route is Elena (single agent)"""
    text = "что такое дисбаланс классов?"
    agent = determine_active_agent(text)
    assert agent == "elena", f"Expected elena for default, got {agent}"
    chain = determine_agent_chain(text)
    assert chain == ["elena"], f"Expected [elena], got {chain}"
    print(f"  {GREEN}✓ General question → Elena default{RESET}")


def test_route_named_agent_directly():
    """Scenario: Route named agent mention directly"""
    text = "Geoffrey, какая наша бизнес-цель?"
    agent = determine_active_agent(text)
    assert agent == "geoffrey", f"Expected geoffrey, got {agent}"
    chain = determine_agent_chain(text)
    assert chain == ["geoffrey"], f"Expected [geoffrey], got {chain}"
    print(f"  {GREEN}✓ Named Geoffrey → Geoffrey only{RESET}")


def test_rule_a_socratic_guardrail():
    """Scenario: Enforce Rule A (Socratic Guardrail) on Elena"""
    # Elena output with code block
    text = "Here's the code: ```python\nprint('hello')\n```"
    result = run_guardrails("elena", text)
    assert result.blocked, "Rule A should block Elena code blocks"
    assert result.rule_triggered == "A", f"Expected Rule A, got {result.rule_triggered}"
    print(f"  {GREEN}✓ Rule A blocks Elena code{RESET}")


def test_rule_b_destructive_warning():
    """Scenario: Enforce Rule B (Destructive Code warning) on Chad"""
    text = "Just do df.dropna(inplace=True) bro"
    result = run_guardrails("chad", text)
    assert result.force_elena_warning, "Rule B should force Elena warning"
    assert not result.blocked, "Rule B should NOT block, only warn"
    print(f"  {GREEN}✓ Rule B flags inplace={RESET}")


def test_rule_c_toxicity_block():
    """Scenario: Enforce Rule C (Toxicity filter) on any agent"""
    text = "This is stupid work"
    result = run_guardrails("chad", text)
    assert result.blocked, "Rule C should block toxic output"
    assert result.rule_triggered == "C", f"Expected Rule C, got {result.rule_triggered}"
    print(f"  {GREEN}✓ Rule C blocks toxicity{RESET}")


def test_elena_named_directly():
    """Named Elena routes to Elena only"""
    text = "Елена, объясни кросс-валидацию"
    agent = determine_active_agent(text)
    assert agent == "elena", f"Expected elena, got {agent}"
    chain = determine_agent_chain(text)
    assert chain == ["elena"], f"Expected [elena], got {chain}"
    print(f"  {GREEN}✓ Elena named → Elena only{RESET}")


def test_robert_code_with_import():
    """Code with import routes to Robert"""
    text = "import pandas as pd\ndf = pd.read_csv('data.csv')"
    agent = determine_active_agent(text)
    assert agent == "robert", f"Expected robert for import, got {agent}"
    chain = determine_agent_chain(text)
    assert chain == ["robert"], f"Expected [robert], got {chain}"
    print(f"  {GREEN}✓ import → Robert{RESET}")


def test_orchestrator_matches_router():
    """Orchestrator.run() uses same routing as determine_agent_chain"""
    from orchestrator import Orchestrator
    orch = Orchestrator()
    for prompt, expected_first in [
        ("Что такое градиентный спуск?", "elena"),
        ("import numpy as np", "robert"),
        ("Chad, дай код", "chad"),
        ("Elena, объясни", "elena"),
    ]:
        turns = orch.run(prompt, mock_mode=True)
        assert turns, f"No turns for: {prompt}"
        actual = turns[0][0]
        assert actual == expected_first, (
            f"Orchestrator first agent for '{prompt[:30]}': "
            f"expected {expected_first}, got {actual}"
        )
    print(f"  {GREEN}✓ Orchestrator routing matches router{RESET}")


def test_no_geoffrey_for_general_question():
    """Geoffrey should NOT respond to general questions"""
    text = "как работать с пропусками в данных?"
    chain = determine_agent_chain(text)
    assert "geoffrey" not in chain, f"Geoffrey should not be in chain: {chain}"
    print(f"  {GREEN}✓ Geoffrey not in general question chain{RESET}")


def test_rule_c_casual_exception():
    """Casual/greeting output should NOT trigger Rule C"""
    casual_outputs = [
        "🔥 **CHAD:** Bro, it's simple! Just load the dataset and run `df.dropna(inplace=True)`, that's what I always use on Stack Overflow!",
        "Hey bro, what's up?",
        "Yo, simple fix for that!",
        "Hi there! Let me help you with that.",
        "Привет! Давай разберемся с данными.",
    ]
    for output in casual_outputs:
        result = run_guardrails("chad", output)
        assert not result.blocked, f"Rule C should NOT block casual output: '{output[:50]}...'"
    print(f"  {GREEN}✓ Rule C casual exception works{RESET}")


def test_rule_c_still_blocks_toxic():
    """Actual toxic output should still be blocked"""
    result = run_guardrails("chad", "You are an idiot")
    assert result.blocked
    assert result.rule_triggered == "C"
    print(f"  {GREEN}✓ Rule C still blocks actual toxicity{RESET}")
