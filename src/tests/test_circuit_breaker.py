"""Unit tests for CircuitBreaker state transitions."""

from __future__ import annotations

import unittest

from src.exceptions.provider import ModelProviderFailure
from src.reliability.circuit_breaker import CircuitBreaker, CircuitState


class TestCircuitBreaker(unittest.TestCase):
    def test_circuit_breaker_transitions_to_open_after_threshold(self) -> None:
        breaker = CircuitBreaker("test-provider", failure_threshold=3, recovery_time_seconds=60.0)
        self.assertEqual(breaker.state, CircuitState.CLOSED)
        self.assertTrue(breaker.allow_request())

        breaker.record_failure()
        breaker.record_failure()
        self.assertEqual(breaker.state, CircuitState.CLOSED)

        breaker.record_failure()
        self.assertEqual(breaker.state, CircuitState.OPEN)
        self.assertFalse(breaker.allow_request())

        with self.assertRaises(ModelProviderFailure):
            breaker.check_or_raise()

    def test_circuit_breaker_half_open_recovery(self) -> None:
        breaker = CircuitBreaker("test-provider-2", failure_threshold=2, recovery_time_seconds=0.01)
        breaker.record_failure()
        breaker.record_failure()
        self.assertEqual(breaker.state, CircuitState.OPEN)

        # Allow time for recovery window
        import time
        time.sleep(0.02)

        # First request transitions to HALF_OPEN
        self.assertTrue(breaker.allow_request())
        self.assertEqual(breaker.state, CircuitState.HALF_OPEN)

        breaker.record_success()
        breaker.record_success()
        self.assertEqual(breaker.state, CircuitState.CLOSED)


if __name__ == "__main__":
    unittest.main()
