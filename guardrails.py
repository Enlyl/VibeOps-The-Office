"""
guardrails.py — VibeOps Output Filter & Semantic Gating
=======================================================
Pillar 6: Evaluation & Guardrails (Safety & Contract Enforcement)
Pillar 7: Token Optimizer (Context Compression)

Implements the rules from Output Filter spec:
- Rule A: Intercept Elena's code blocks (Socratic Guardrail).
- Rule B: Detect destructive code from Chad.
- Rule C: Toxicity checks.
- Token Optimizer: Compresses long history into system facts.
"""

import logging
import re
from typing import List, Tuple, Dict, Any

logger = logging.getLogger("vibeops.guardrails")

_CODE_BLOCK_PATTERN = re.compile(r"```(?:python)?", re.IGNORECASE)
_DESTRUCTIVE_PATTERN = re.compile(r"inplace\s*=\s*True|drop|delete", re.IGNORECASE)
_TOXIC_WORDS = {"stupid", "idiot", "moron", "shut up", "trash"}

def compress_context(memory_turns: List[Any], max_history: int = 10) -> List[str]:
    """
    Pillar 7 (Token Optimizer):
    Checks if the history exceeds max_history. If so, pops the oldest turns
    and compresses them into short system facts to save context window tokens.
    
    Args:
        memory_turns: The short_term list of AgentTurn objects from MemoryContext.
        max_history: The maximum allowed length of the history window.
        
    Returns:
        List of newly generated system facts (strings).
    """
    new_facts = []
    
    while len(memory_turns) > max_history:
        oldest = memory_turns.pop(0)
        
        # Don't compress blocked/rejected turns as they didn't contribute to the valid context
        if oldest.blocked:
            continue
            
        # Create a compressed representation
        content_preview = oldest.content[:60].replace('\n', ' ').strip()
        summary = f"[{oldest.agent_name.upper()}]: {content_preview}..."
        new_facts.append(summary)
        
        logger.info("GUARDRAIL | Token Optimizer compressed turn from %s into a system fact.", oldest.agent_name.upper())
        
    return new_facts

def run_guardrails(turns: List[Any]) -> Tuple[List[Any], Dict[str, bool]]:
    """
    Scans a list of AgentTurn objects and applies post-generation checks.

    Args:
        turns: List of AgentTurn objects to check.

    Returns:
        A tuple: (modified_turns, action_flags)
        action_flags is a dictionary containing triggers for the orchestrator:
            - retry_elena_socratic: True if Elena violated Rule A and must rewrite.
            - force_elena_warning: True if Chad violated Rule B.
    """
    flags = {
        "retry_elena_socratic": False,
        "force_elena_warning": False
    }

    for turn in turns:
        if turn.blocked:
            continue

        # Rule C: Toxicity (applies to all agents)
        if any(w in turn.content.lower() for w in _TOXIC_WORDS):
            turn.blocked = True
            turn.block_reason = "Rule C: Toxicity Guardrail triggered. Offensive language detected."
            logger.warning("GUARDRAIL | %s", turn.block_reason)
            continue

        # Rule B: Chad Destructive Code
        if turn.agent_name == "chad":
            if _DESTRUCTIVE_PATTERN.search(turn.content):
                flags["force_elena_warning"] = True
                logger.warning("GUARDRAIL | Rule B: Chad suggested destructive code. Flagging for Elena to warn.")

        # Rule A: Elena Socratic Guardrail
        if turn.agent_name == "elena":
            if _CODE_BLOCK_PATTERN.search(turn.content):
                turn.blocked = True
                turn.block_reason = "Rule A: Socratic Guardrail triggered. No code blocks allowed from Elena."
                flags["retry_elena_socratic"] = True
                logger.warning("GUARDRAIL | %s (Rollback requested)", turn.block_reason)

    return turns, flags
