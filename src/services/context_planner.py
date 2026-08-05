"""Context Planner for SC-EVM Context Control Plane.

Encapsulates all prompt items into formal ContextBlock instances with priority,
importance, retrieval scores, expiration timestamps, dependencies, and token estimates.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from src.services.tokenizer_abstraction import TokenizerRegistry


@dataclass
class ContextBlock:
    id: str
    text: str
    source: str  # system, history, current_query, semantic_memory, lexical_bm25, structural_ast
    priority: int  # 1 (lowest) to 100 (highest)
    importance: float  # 0.0 to 1.0
    retrieval_score: float = 0.0
    expiration: float | None = None  # unix timestamp or turn threshold
    dependencies: list[str] = field(default_factory=list)  # list of prerequisite ContextBlock IDs
    estimated_tokens: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.estimated_tokens and self.text:
            self.estimated_tokens = TokenizerRegistry.count_tokens(self.text)


class ContextPlanner:
    """Constructs, categorizes, and tracks lifecycle of context blocks for a query execution."""

    def __init__(self, model_name: str = ""):
        self.model_name = model_name

    def create_block(
        self,
        block_id: str,
        text: str,
        source: str,
        priority: int = 50,
        importance: float = 0.5,
        retrieval_score: float = 0.0,
        expiration: float | None = None,
        dependencies: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ContextBlock:
        """Create a single ContextBlock with automatic token estimation."""
        tokens = TokenizerRegistry.count_tokens(text, self.model_name)
        return ContextBlock(
            id=block_id,
            text=text,
            source=source,
            priority=priority,
            importance=importance,
            retrieval_score=retrieval_score,
            expiration=expiration,
            dependencies=dependencies or [],
            estimated_tokens=tokens,
            metadata=metadata or {},
        )

    def plan_context(
        self,
        system_prompt: str,
        history: list[dict[str, str]],
        user_query: str,
        semantic_memories: list[dict[str, Any]] | None = None,
        lexical_items: list[dict[str, Any]] | None = None,
        ast_symbols: list[dict[str, Any]] | None = None,
    ) -> list[ContextBlock]:
        """Compile all prompt components into a collection of ContextBlocks."""
        blocks: list[ContextBlock] = []

        # 1. System Prompt (Priority 100, Importance 1.0)
        if system_prompt:
            blocks.append(
                self.create_block(
                    block_id="sys-prompt",
                    text=system_prompt,
                    source="system",
                    priority=100,
                    importance=1.0,
                )
            )

        # 2. Conversation History (Priority 75 to 90 based on recency)
        for idx, turn in enumerate(history, 1):
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if content:
                block_id = f"hist-{idx}-{role}"
                recency_boost = (idx / max(1, len(history))) * 15.0
                blocks.append(
                    self.create_block(
                        block_id=block_id,
                        text=f"{role.capitalize()}: {content}",
                        source="history",
                        priority=int(75 + recency_boost),
                        importance=0.7 + (recency_boost / 50.0),
                    )
                )

        # 3. Current User Query (Priority 95, Importance 1.0)
        if user_query:
            blocks.append(
                self.create_block(
                    block_id="query-curr",
                    text=f"User: {user_query}",
                    source="current_query",
                    priority=95,
                    importance=1.0,
                )
            )

        # 4. Semantic Memory Blocks (Priority 60, Importance derived from distance/score)
        if semantic_memories:
            for idx, mem in enumerate(semantic_memories, 1):
                text = mem.get("text", "")
                score = mem.get("score", 0.5)
                blocks.append(
                    self.create_block(
                        block_id=f"sem-{idx}",
                        text=f"<retrieved_memory>\n{text}\n</retrieved_memory>",
                        source="semantic_memory",
                        priority=60,
                        importance=min(1.0, max(0.1, score)),
                        retrieval_score=score,
                    )
                )

        # 5. Lexical BM25 Blocks (Priority 55)
        if lexical_items:
            for idx, item in enumerate(lexical_items, 1):
                text = item.get("text", "")
                score = item.get("score", 0.5)
                blocks.append(
                    self.create_block(
                        block_id=f"lex-{idx}",
                        text=f"<retrieved_memory>\n{text}\n</retrieved_memory>",
                        source="lexical_bm25",
                        priority=55,
                        importance=min(1.0, max(0.1, score / 10.0)),
                        retrieval_score=score,
                    )
                )

        # 6. Structural AST Symbols (Priority 65 if required)
        if ast_symbols:
            for idx, sym in enumerate(ast_symbols, 1):
                text = sym.get("text", "")
                score = sym.get("score", 0.5)
                blocks.append(
                    self.create_block(
                        block_id=f"ast-{idx}",
                        text=f"<retrieved_memory>\n{text}\n</retrieved_memory>",
                        source="structural_ast",
                        priority=65,
                        importance=min(1.0, max(0.1, score)),
                        retrieval_score=score,
                    )
                )

        return blocks
