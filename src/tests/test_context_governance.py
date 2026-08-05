"""Deterministic regression test suite for SC-EVM Context Governance.

Validates:
1. ContextBudgetManager source floor guarantees & ceiling caps.
2. Explicit EvictionReasons (EXCEEDS_SOURCE_CEILING, TOTAL_BUDGET_EXHAUSTED, EXPIRED_TTL).
3. GovernanceReport audit logging & policy summary.
4. ContextPlanner.govern_and_assemble end-to-end prompt governance.
"""
from __future__ import annotations

import time
import unittest

from src.services.context_budget_manager import (
    ContextBudgetManager,
    EvictionReason,
    SourceBudget,
)
from src.services.context_optimizer import ContextOptimizer
from src.services.context_planner import ContextBlock, ContextPlanner


class TestContextGovernance(unittest.TestCase):
    def setUp(self):
        self.planner = ContextPlanner()
        self.budget_mgr = ContextBudgetManager(
            total_limit=4096,
            reserved_output=1024,
            source_specs={
                "system": {"min": 100, "max": 500},
                "history": {"min": 200, "max": 1000},
                "current_query": {"min": 100, "max": 500},
                "semantic_memory": {"min": 0, "max": 400},
                "lexical_bm25": {"min": 0, "max": 400},
                "structural_ast": {"min": 0, "max": 400},
            },
        )

    def test_01_source_budget_allocation(self):
        """Verify ContextBudgetManager allocates minimum floors and calculates elastic token limits."""
        demanded = {
            "system": 250,
            "history": 800,
            "current_query": 150,
            "semantic_memory": 600,
        }
        budgets = self.budget_mgr.allocate_budgets(demanded)

        self.assertIn("system", budgets)
        self.assertIn("history", budgets)

        sys_b = budgets["system"]
        self.assertEqual(sys_b.min_tokens, 100)
        self.assertEqual(sys_b.max_tokens, 500)
        self.assertGreaterEqual(sys_b.allocated_tokens, 100)

        sem_b = budgets["semantic_memory"]
        self.assertEqual(sem_b.max_tokens, 400)
        self.assertLessEqual(sem_b.allocated_tokens, 400)

    def test_02_eviction_reason_expired_ttl(self):
        """Verify ContextOptimizer assigns EXPIRED_TTL eviction reason to expired blocks."""
        expired_block = ContextBlock(
            id="exp-1",
            text="Old expired memory",
            source="semantic_memory",
            priority=80,
            importance=0.9,
            expiration=time.time() - 100.0,
            estimated_tokens=50,
        )

        demanded = {"semantic_memory": 50}
        budgets = self.budget_mgr.allocate_budgets(demanded)
        res = ContextOptimizer.optimize(
            blocks=[expired_block],
            source_budgets=budgets,
            total_token_limit=self.budget_mgr.available_input_tokens,
        )

        self.assertEqual(len(res.admitted_blocks), 0)
        self.assertEqual(len(res.evicted_blocks), 1)
        self.assertEqual(len(res.eviction_records), 1)
        rec = res.eviction_records[0]
        self.assertEqual(rec.reason, EvictionReason.EXPIRED_TTL)
        self.assertIn("TTL expired", rec.rationale)

    def test_03_eviction_reason_exceeds_source_ceiling(self):
        """Verify ContextOptimizer assigns EXCEEDS_SOURCE_CEILING when block exceeds source max cap."""
        # semantic_memory max cap is 400 tokens
        block1 = ContextBlock(
            id="sem-large-1",
            text="Large vector candidate text " * 40,
            source="semantic_memory",
            priority=60,
            importance=0.8,
            estimated_tokens=300,
        )
        block2 = ContextBlock(
            id="sem-large-2",
            text="Second large vector candidate text " * 40,
            source="semantic_memory",
            priority=59,
            importance=0.7,
            estimated_tokens=300,
        )

        demanded = {"semantic_memory": 600}
        budgets = self.budget_mgr.allocate_budgets(demanded)

        res = ContextOptimizer.optimize(
            blocks=[block1, block2],
            source_budgets=budgets,
            total_token_limit=self.budget_mgr.available_input_tokens,
        )

        self.assertEqual(len(res.admitted_blocks), 1)
        self.assertEqual(res.admitted_blocks[0].id, "sem-large-1")
        self.assertEqual(len(res.evicted_blocks), 1)
        self.assertEqual(res.evicted_blocks[0].id, "sem-large-2")

        rec = res.eviction_records[0]
        self.assertEqual(rec.reason, EvictionReason.EXCEEDS_SOURCE_CEILING)
        self.assertIn("exceeds source ceiling", rec.rationale)

    def test_04_eviction_reason_total_budget_exhausted(self):
        """Verify ContextOptimizer assigns TOTAL_BUDGET_EXHAUSTED when total input limit is hit."""
        small_limit_mgr = ContextBudgetManager(total_limit=300, reserved_output=100)

        block1 = ContextBlock(
            id="b1",
            text="Block one content",
            source="history",
            priority=90,
            importance=0.9,
            estimated_tokens=150,
        )
        block2 = ContextBlock(
            id="b2",
            text="Block two content",
            source="history",
            priority=85,
            importance=0.8,
            estimated_tokens=100,
        )

        demanded = {"history": 250}
        budgets = small_limit_mgr.allocate_budgets(demanded)

        res = ContextOptimizer.optimize(
            blocks=[block1, block2],
            source_budgets=budgets,
            total_token_limit=small_limit_mgr.available_input_tokens,  # 200 tokens
        )

        self.assertEqual(len(res.admitted_blocks), 1)
        self.assertEqual(res.admitted_blocks[0].id, "b1")
        self.assertEqual(len(res.evicted_blocks), 1)
        self.assertEqual(res.evicted_blocks[0].id, "b2")

        rec = res.eviction_records[0]
        self.assertEqual(rec.reason, EvictionReason.TOTAL_BUDGET_EXHAUSTED)
        self.assertIn("exceeds total input limit", rec.rationale)

    def test_05_govern_and_assemble_prompt(self):
        """Verify ContextPlanner.govern_and_assemble policy execution and GovernanceReport output."""
        sys_prompt = "You are an AI coding assistant."
        history = [
            {"role": "user", "content": "How do I optimize retrieval?"},
            {"role": "assistant", "content": "Use adaptive thresholds and hybrid RRF fusion."},
        ]
        query = "Explain context governance."
        sem_mems = [{"text": "Context governance policy engine", "score": 0.88}]
        lex_items = [{"text": "ContextBudgetManager allocate_budgets", "score": 12.5}]

        assembled_prompt, admitted, report = self.planner.govern_and_assemble(
            system_prompt=sys_prompt,
            history=history,
            user_query=query,
            semantic_memories=sem_mems,
            lexical_items=lex_items,
            total_token_limit=4096,
            reserved_output_tokens=1024,
        )

        self.assertIn("You are an AI coding assistant.", assembled_prompt)
        self.assertIn("Explain context governance.", assembled_prompt)
        self.assertTrue(len(admitted) > 0)

        self.assertEqual(report.total_token_limit, 4096)
        self.assertEqual(report.available_input_tokens, 3072)
        self.assertEqual(report.admitted_block_count, len(admitted))
        self.assertGreater(report.admitted_total_tokens, 0)
        self.assertIn("system", report.tokens_by_source)


if __name__ == "__main__":
    unittest.main()
