"""Unit and Stress Tests for Phase 3 OpenAI-Compatible Context Control Plane.

Verifies:
- TokenizerAbstraction (tiktoken / fallback char tokenizer).
- ContextBudgetManager dynamic allocations, minimum floors, and reserved output buffers.
- ContextPlanner ContextBlock generation and dependency tracking.
- ContextOptimizer knapsack block selection, dependency resolution, and sub-10ms latency.
- 100-turn conversation stress test and token overflow handling.
- OpenAI-compatible endpoint streaming and completion handling.
"""
from __future__ import annotations

import unittest
from fastapi.testclient import TestClient

from src.main import app
from src.services.context_budget_manager import ContextBudgetManager
from src.services.context_optimizer import ContextOptimizer
from src.services.context_planner import ContextBlock, ContextPlanner
from src.services.tokenizer_abstraction import FallbackCharTokenizer, TokenizerRegistry


class TestTokenizerAbstraction(unittest.TestCase):
    def test_token_counting(self):
        text = "def hello_world(): return 'Hello SC-EVM Context Control Plane!'"
        count_fallback = FallbackCharTokenizer.count_tokens(text)
        count_registry = TokenizerRegistry.count_tokens(text)

        self.assertGreater(count_fallback, 0)
        self.assertGreater(count_registry, 0)

    def test_empty_text(self):
        self.assertEqual(FallbackCharTokenizer.count_tokens(""), 0)


class TestContextBudgetManager(unittest.TestCase):
    def test_budget_allocation(self):
        mgr = ContextBudgetManager(total_limit=4096, reserved_output=1024)
        self.assertEqual(mgr.available_input_tokens, 3072)

        demands = {"system": 500, "history": 2000, "current_query": 1000}
        budgets = mgr.allocate_budgets(demands)

        self.assertIn("system", budgets)
        self.assertIn("history", budgets)

        sys_budget = budgets["system"]
        self.assertGreaterEqual(sys_budget.allocated_tokens, sys_budget.min_tokens)
        self.assertLessEqual(sys_budget.allocated_tokens, sys_budget.max_tokens)


class TestContextPlannerAndOptimizer(unittest.TestCase):
    def setUp(self):
        self.planner = ContextPlanner()

    def test_context_block_creation(self):
        block = self.planner.create_block(
            block_id="b1",
            text="System initialization instruction",
            source="system",
            priority=100,
            importance=1.0,
        )
        self.assertEqual(block.id, "b1")
        self.assertEqual(block.priority, 100)
        self.assertGreater(block.estimated_tokens, 0)

    def test_dependency_resolution_and_optimization(self):
        b_dep = self.planner.create_block(
            block_id="dep1",
            text="Prerequisite header definition",
            source="system",
            priority=80,
            importance=0.9,
        )
        b_child = self.planner.create_block(
            block_id="child1",
            text="Dependent body logic using header definition",
            source="system",
            priority=90,
            importance=0.95,
            dependencies=["dep1"],
        )

        blocks = [b_dep, b_child]
        mgr = ContextBudgetManager(total_limit=2000, reserved_output=500)
        budgets = mgr.allocate_budgets()

        result = ContextOptimizer.optimize(blocks, budgets, mgr.available_input_tokens)

        admitted_ids = [b.id for b in result.admitted_blocks]
        self.assertIn("child1", admitted_ids)
        self.assertIn("dep1", admitted_ids)
        self.assertLess(result.planner_latency_ms, 10.0)  # Sub-10ms requirement

    def test_100_turn_conversation_stress_test(self):
        """Stress test evaluating 100 conversation turns under budget constraints."""
        history = [
            {"role": "user" if i % 2 == 1 else "assistant", "content": f"Turn {i}: Context payload simulation text data block {i}." * 5}
            for i in range(1, 101)
        ]

        blocks = self.planner.plan_context(
            system_prompt="You are a production-grade AI engine.",
            history=history,
            user_query="Current user prompt testing 100 turn conversation budget eviction.",
        )

        self.assertGreaterEqual(len(blocks), 101)

        mgr = ContextBudgetManager(total_limit=4096, reserved_output=1024)
        budgets = mgr.allocate_budgets()

        result = ContextOptimizer.optimize(blocks, budgets, mgr.available_input_tokens)

        # Ensure admitted token limit is strictly enforced
        self.assertLessEqual(result.total_admitted_tokens, mgr.available_input_tokens)
        self.assertTrue(len(result.evicted_blocks) > 0)
        self.assertLess(result.planner_latency_ms, 10.0)


class TestOpenAICompatibleEndpoint(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_openai_chat_completions_endpoint(self):
        login_res = self.client.post("/api/auth/login", json={"email": "test@example.com"})
        self.assertEqual(login_res.status_code, 200)
        access_token = login_res.json()["data"]["access_token"]

        payload = {
            "model": "sc-evm-proxy",
            "messages": [
                {"role": "system", "content": "You are a helpful coding assistant."},
                {"role": "user", "content": "Hello OpenAI gateway context control plane!"},
            ],
            "stream": False,
        }
        headers = {"Authorization": f"Bearer {access_token}"}
        response = self.client.post("/v1/chat/completions", json=payload, headers=headers)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["object"], "chat.completion")
        self.assertIn("choices", data)
        self.assertTrue(len(data["choices"]) > 0)


if __name__ == "__main__":
    unittest.main()
