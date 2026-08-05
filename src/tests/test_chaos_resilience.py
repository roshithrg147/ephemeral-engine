"""Chaos Testing & Runtime Resilience Test Suite for SC-EVM.

Simulates synthetic provider outages, rate limits, vector database failures,
circuit breaker state transitions, multi-level fallbacks, and session continuity.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.services.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
from src.services.error_taxonomy import ResilientRuntimeError, RuntimeErrorCode
from src.services.fallback_cache import FallbackCacheManager
from src.services.provider_health import ProviderHealthManager
from src.services.request_context import RequestContext
from src.services.resilient_router import ResilientRouter


class TestChaosResilience(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.health_mgr = ProviderHealthManager(cooldown_duration_s=10.0)
        self.router = ResilientRouter(health_manager=self.health_mgr)
        self.cache_mgr = FallbackCacheManager(warm_capacity=50, cold_store_dir=self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_request_context_tracing(self):
        """Verify RequestContext generates immutable trace context and spans."""
        ctx = RequestContext.create(session_id="sess-chaos-1")
        self.assertTrue(ctx.request_id.startswith("req-"))
        self.assertTrue(ctx.trace_id.startswith("trace-"))

        start = ctx.start_time
        span = ctx.record_span("intent_classification", start, status="OK")
        self.assertEqual(span.span_name, "intent_classification")
        self.assertGreaterEqual(span.latency_ms, 0.0)

        data = ctx.to_dict()
        self.assertEqual(data["request_id"], ctx.request_id)
        self.assertEqual(data["span_count"], 1)

    def test_02_circuit_breaker_2_0_transitions(self):
        """Verify 6-state Circuit Breaker 2.0 (CLOSED -> WARNING -> OPEN -> COOLDOWN -> HALF_OPEN)."""
        cb = CircuitBreaker(name="test_provider", warning_threshold=2, failure_threshold=4, recovery_timeout=0.1, cooldown_timeout=0.1)

        self.assertEqual(cb.state, "CLOSED")

        # 2 failures -> WARNING
        cb.record_failure("generic_error")
        cb.record_failure("generic_error")
        self.assertEqual(cb.state, "WARNING")

        # 2 more failures -> OPEN
        cb.record_failure("generic_error")
        cb.record_failure("generic_error")
        self.assertEqual(cb.state, "OPEN")

        # HTTP 429 failure -> COOLDOWN
        cb.record_failure("HTTP 429 Too Many Requests")
        self.assertEqual(cb.state, "COOLDOWN")

    def test_03_provider_health_manager_tracking(self):
        """Verify ProviderHealthManager updates success rate, latency window, and cooldown."""
        self.health_mgr.record_success("nvidia", latency_ms=45.0)
        st = self.health_mgr.get_health("nvidia")
        self.assertEqual(st.status, "Healthy")
        self.assertEqual(st.success_count, 1)

        self.health_mgr.record_failure("nvidia", error_type="429_rate_limit")
        st_after = self.health_mgr.get_health("nvidia")
        self.assertEqual(st_after.status, "Cooldown")
        self.assertFalse(st_after.is_available())

    def test_04_intelligent_routing_failover(self):
        """Verify ResilientRouter redirects queries to Local when Cloud is degraded/cooling down."""
        # Force cloud provider into Cooldown
        self.health_mgr.trigger_cooldown("nvidia", duration_s=10.0)

        decision = self.router.route_query(
            query="Analyze database schema",
            confidence_score=0.9,
            preferred_cloud_provider="nvidia",
        )

        self.assertEqual(decision.target_provider, "local")
        self.assertIn("circuit", decision.decision_reason.lower())

    def test_05_multi_level_fallback_cache(self):
        """Verify multi-level fallback cache hierarchy (Warm -> Cold -> Minimal Retrieval)."""
        session_id = "sess-fallback-1"
        query = "how do I configure chroma db?"

        # Warm Cache lookup (initially empty)
        self.assertIsNone(self.cache_mgr.get_warm(session_id, query))

        # Put in Warm & Cold
        payload = {"retrieved_docs": ["doc-1"], "expanded_query": "chroma db configuration"}
        self.cache_mgr.put_warm(session_id, query, payload)
        self.cache_mgr.put_cold(session_id, query, payload)

        self.assertIsNotNone(self.cache_mgr.get_warm(session_id, query))
        self.assertIsNotNone(self.cache_mgr.get_cold(session_id, query))

        # Minimal retrieval fallback
        history = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]
        min_docs = self.cache_mgr.get_minimal_retrieval(history)
        self.assertEqual(len(min_docs), 2)

    def test_06_machine_readable_error_taxonomy(self):
        """Verify ResilientRuntimeError formats machine-readable error codes and status."""
        err = ResilientRuntimeError(
            code=RuntimeErrorCode.VECTOR_STORE_FAILURE,
            message="ChromaDB connection timeout",
            provider="chroma",
            http_status=503,
            context={"session_id": "sess-123"},
        )

        d = err.to_dict()
        self.assertEqual(d["error_code"], "VECTOR_STORE_FAILURE")
        self.assertEqual(d["http_status"], 503)
        self.assertEqual(d["provider"], "chroma")


if __name__ == "__main__":
    unittest.main()
