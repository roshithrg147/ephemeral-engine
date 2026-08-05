"""Context Budget Manager for SC-EVM.

Implements dynamic token allocation supporting minimum floors, maximum ceilings,
reserved output token buffers, and elastic remaining token distribution.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, NamedTuple


class EvictionReason(str, Enum):
    EXCEEDS_SOURCE_CEILING = "EXCEEDS_SOURCE_CEILING"
    TOTAL_BUDGET_EXHAUSTED = "TOTAL_BUDGET_EXHAUSTED"
    EXPIRED_TTL = "EXPIRED_TTL"
    UNRESOLVED_DEPENDENCY = "UNRESOLVED_DEPENDENCY"
    LOW_IMPORTANCE_PRUNING = "LOW_IMPORTANCE_PRUNING"


class EvictionRecord(NamedTuple):
    block_id: str
    source: str
    reason: EvictionReason
    rationale: str
    estimated_tokens: int


class SourceBudget(NamedTuple):
    source_name: str
    min_tokens: int
    max_tokens: int
    allocated_tokens: int


class GovernanceReport(NamedTuple):
    total_token_limit: int
    available_input_tokens: int
    admitted_block_count: int
    admitted_total_tokens: int
    evicted_block_count: int
    evicted_total_tokens: int
    eviction_records: list[EvictionRecord]
    tokens_by_source: dict[str, int]
    policy_summary: str


class ContextBudgetManager:
    """Manages dynamic token budget allocation across context sources."""

    def __init__(
        self,
        total_limit: int = 8192,
        reserved_output: int = 2048,
        source_specs: dict[str, dict[str, int]] | None = None,
    ):
        self.total_limit = total_limit
        self.reserved_output = reserved_output
        self.available_input_tokens = max(0, total_limit - reserved_output)

        # Default source specification bounds (min_tokens, max_tokens)
        self.source_specs = source_specs or {
            "system": {"min": 200, "max": 1024},
            "history": {"min": 300, "max": 3072},
            "current_query": {"min": 200, "max": 2048},
            "semantic_memory": {"min": 0, "max": 2048},
            "lexical_bm25": {"min": 0, "max": 1536},
            "structural_ast": {"min": 0, "max": 1536},
        }

    def allocate_budgets(
        self, demanded_tokens: dict[str, int] | None = None
    ) -> dict[str, SourceBudget]:
        """Compute dynamic token allocation across all context sources.

        1. Reserves minimum floors for required sources.
        2. Distributes elastic remaining budget proportionally based on demand.
        """
        demands = demanded_tokens or {}
        allocations: dict[str, int] = {}
        min_total = 0

        # Step 1: Allocate minimum floors
        for source, spec in self.source_specs.items():
            min_floor = min(spec["min"], demands.get(source, spec["min"]))
            allocations[source] = min_floor
            min_total += min_floor

        remaining_budget = max(0, self.available_input_tokens - min_total)

        # Step 2: Elastic allocation based on source demand exceeding minimum floor
        excess_demands: dict[str, int] = {}
        total_excess_demand = 0

        for source, spec in self.source_specs.items():
            current_alloc = allocations[source]
            max_allowed = spec["max"]
            demand = demands.get(source, max_allowed)
            needed = max(0, min(demand, max_allowed) - current_alloc)
            if needed > 0:
                excess_demands[source] = needed
                total_excess_demand += needed

        if total_excess_demand > 0 and remaining_budget > 0:
            for source, needed in excess_demands.items():
                ratio = needed / total_excess_demand
                additional = int(remaining_budget * ratio)
                allocations[source] = min(
                    self.source_specs[source]["max"], allocations[source] + additional
                )

        return {
            source: SourceBudget(
                source_name=source,
                min_tokens=self.source_specs.get(source, {}).get("min", 0),
                max_tokens=self.source_specs.get(source, {}).get("max", self.available_input_tokens),
                allocated_tokens=allocations.get(source, 0),
            )
            for source in self.source_specs
        }
