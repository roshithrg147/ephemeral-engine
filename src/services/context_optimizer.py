"""Context Optimizer for SC-EVM.

Solves optimal context block selection deterministically using priority,
importance, dependency resolution, and dynamic source token budgets in < 10 ms.
"""
from __future__ import annotations

import time
from typing import NamedTuple

from src.services.context_budget_manager import EvictionReason, EvictionRecord, SourceBudget
from src.services.context_planner import ContextBlock


class OptimizationResult(NamedTuple):
    admitted_blocks: list[ContextBlock]
    evicted_blocks: list[ContextBlock]
    eviction_records: list[EvictionRecord]
    total_admitted_tokens: int
    total_evicted_tokens: int
    planner_latency_ms: float
    tokens_by_source: dict[str, int]


class ContextOptimizer:
    """Solves deterministic context selection with dependency resolution and budget enforcement."""

    @staticmethod
    def optimize(
        blocks: list[ContextBlock],
        source_budgets: dict[str, SourceBudget],
        total_token_limit: int,
    ) -> OptimizationResult:
        start_time = time.perf_counter()

        now = time.time()
        active_blocks: list[ContextBlock] = []
        evicted_blocks: list[ContextBlock] = []
        eviction_records: list[EvictionRecord] = []
        total_evicted_tokens = 0

        # Step 1: Filter out expired blocks
        for b in blocks:
            if b.expiration is not None and b.expiration <= now:
                evicted_blocks.append(b)
                total_evicted_tokens += b.estimated_tokens
                eviction_records.append(
                    EvictionRecord(
                        block_id=b.id,
                        source=b.source,
                        reason=EvictionReason.EXPIRED_TTL,
                        rationale=f"Context block TTL expired at {b.expiration} (current time {now:.1f})",
                        estimated_tokens=b.estimated_tokens,
                    )
                )
            else:
                active_blocks.append(b)

        # Index blocks by ID for dependency resolution
        block_map = {b.id: b for b in active_blocks}

        # Step 2: Compute composite rank score
        def block_rank(b: ContextBlock) -> float:
            return (b.priority * 10.0) + (b.importance * 100.0) + (b.retrieval_score * 50.0)

        sorted_blocks = sorted(active_blocks, key=block_rank, reverse=True)

        admitted_blocks: list[ContextBlock] = []
        admitted_ids: set[str] = set()

        tokens_by_source: dict[str, int] = {src: 0 for src in source_budgets}
        total_admitted_tokens = 0

        # Step 3: Greedy Knapsack Selection with Dependency Resolution & Policy Rules
        for block in sorted_blocks:
            if block.id in admitted_ids:
                continue

            # Resolve dependencies first
            dep_blocks = [
                block_map[dep_id]
                for dep_id in block.dependencies
                if dep_id in block_map and dep_id not in admitted_ids
            ]
            all_candidate_blocks = dep_blocks + [block]

            req_tokens_by_source: dict[str, int] = {}
            total_req_tokens = 0

            for cand in all_candidate_blocks:
                src = cand.source
                req_tokens_by_source[src] = req_tokens_by_source.get(src, 0) + cand.estimated_tokens
                total_req_tokens += cand.estimated_tokens

            # Check budget constraints
            can_admit = True
            evict_reason = EvictionReason.TOTAL_BUDGET_EXHAUSTED
            evict_rationale = ""

            if total_admitted_tokens + total_req_tokens > total_token_limit:
                can_admit = False
                evict_reason = EvictionReason.TOTAL_BUDGET_EXHAUSTED
                evict_rationale = (
                    f"Adding block ({total_req_tokens} tokens) exceeds total input limit "
                    f"({total_admitted_tokens + total_req_tokens} > {total_token_limit})"
                )

            if can_admit:
                for src, req in req_tokens_by_source.items():
                    budget = source_budgets.get(src)
                    if budget:
                        current = tokens_by_source.get(src, 0)
                        if current + req > budget.max_tokens:
                            can_admit = False
                            evict_reason = EvictionReason.EXCEEDS_SOURCE_CEILING
                            evict_rationale = (
                                f"Adding block to source '{src}' ({current + req} tokens) "
                                f"exceeds source ceiling ({budget.max_tokens} tokens)"
                            )
                            break

            if can_admit:
                for cand in all_candidate_blocks:
                    admitted_blocks.append(cand)
                    admitted_ids.add(cand.id)
                    tokens_by_source[cand.source] = (
                        tokens_by_source.get(cand.source, 0) + cand.estimated_tokens
                    )
                    total_admitted_tokens += cand.estimated_tokens
            else:
                if block not in evicted_blocks:
                    evicted_blocks.append(block)
                    total_evicted_tokens += block.estimated_tokens
                    eviction_records.append(
                        EvictionRecord(
                            block_id=block.id,
                            source=block.source,
                            reason=evict_reason,
                            rationale=evict_rationale,
                            estimated_tokens=block.estimated_tokens,
                        )
                    )

        # Restore original prompt order for admitted blocks
        order_map = {b.id: idx for idx, b in enumerate(blocks)}
        admitted_blocks.sort(key=lambda b: order_map.get(b.id, 9999))

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        return OptimizationResult(
            admitted_blocks=admitted_blocks,
            evicted_blocks=evicted_blocks,
            eviction_records=eviction_records,
            total_admitted_tokens=total_admitted_tokens,
            total_evicted_tokens=total_evicted_tokens,
            planner_latency_ms=latency_ms,
            tokens_by_source=tokens_by_source,
        )
