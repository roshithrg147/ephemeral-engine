"""Intent Router & Structural Gating Policy for SC-EVM.

Classifies user prompts into distinct intent categories and enforces the gating rule:
Only structural requests (Code lookup, Architecture, Dependency analysis, Refactoring)
may invoke AST graph traversal.
"""
from __future__ import annotations

import re
from typing import Literal

IntentCategory = Literal[
    "Conversation",
    "Question answering",
    "Code lookup",
    "Architecture",
    "Dependency analysis",
    "Refactoring",
]

STRUCTURAL_INTENTS: set[IntentCategory] = {
    "Code lookup",
    "Architecture",
    "Dependency analysis",
    "Refactoring",
}


class IntentRouter:
    """Classifies prompt intent and enforces structural AST gating policy."""

    @staticmethod
    def classify_intent(prompt: str) -> IntentCategory:
        """Classify user prompt into one of the 6 intent categories."""
        if not prompt or not prompt.strip():
            return "Conversation"

        p_lower = prompt.lower()

        # Refactoring intent keywords
        if any(w in p_lower for w in ["refactor", "rename", "restructure", "clean up", "extract function", "extract class"]):
            return "Refactoring"

        # Architecture intent keywords
        if any(w in p_lower for w in ["architecture", "design", "overview", "component diagram", "system flow", "structure", "data flow"]):
            return "Architecture"

        # Dependency analysis intent keywords
        if any(w in p_lower for w in ["dependency", "dependencies", "imports", "imported by", "caller", "called by", "used by", "module tree"]):
            return "Dependency analysis"

        # Code lookup intent keywords
        if any(w in p_lower for w in ["where is", "find class", "find function", "find method", "locate", "definition of", "show code", "search symbol"]):
            return "Code lookup"

        # Question answering intent keywords
        if any(w in p_lower for w in ["how to", "how does", "what is", "why does", "explain", "can you"]):
            return "Question answering"

        # Default conversational intent
        return "Conversation"

    @staticmethod
    def requires_structural_ast(intent: str) -> bool:
        """Enforces gating rule: Only structural requests invoke AST graph traversal."""
        return intent in STRUCTURAL_INTENTS
