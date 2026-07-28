"""Circuit breaker implementation for model providers, databases, and tools."""

from __future__ import annotations

import logging
import time
from enum import StrEnum

from src.exceptions.provider import ModelProviderFailure

logger = logging.getLogger("SC-EVM.RELIABILITY.CIRCUIT_BREAKER")


class CircuitState(StrEnum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """Tracks component failures and trips into OPEN state when failure thresholds are exceeded."""

    def __init__(
        self,
        name: str,
        *,
        failure_threshold: int = 5,
        recovery_time_seconds: float = 60.0,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_time_seconds = recovery_time_seconds

        self.state: CircuitState = CircuitState.CLOSED
        self.failure_timestamps: list[float] = []
        self.last_state_change: float = time.time()
        self.half_open_successes: int = 0

    def allow_request(self) -> bool:
        """Check whether execution is allowed under current circuit breaker state."""
        now = time.time()
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            if now - self.last_state_change >= self.recovery_time_seconds:
                self._transition_to(CircuitState.HALF_OPEN)
                return True
            return False

        if self.state == CircuitState.HALF_OPEN:
            return True

        return True

    def record_success(self) -> None:
        """Record a successful execution."""
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_successes += 1
            if self.half_open_successes >= 2:
                self.failure_timestamps.clear()
                self._transition_to(CircuitState.CLOSED)

    def record_failure(self, exc: Exception | None = None) -> None:
        """Record a failed execution."""
        now = time.time()
        self.failure_timestamps.append(now)

        # Retain failures within window
        cutoff = now - self.recovery_time_seconds
        self.failure_timestamps = [ts for ts in self.failure_timestamps if ts >= cutoff]

        if self.state == CircuitState.CLOSED:
            if len(self.failure_timestamps) >= self.failure_threshold:
                self._transition_to(CircuitState.OPEN)

        elif self.state == CircuitState.HALF_OPEN:
            self._transition_to(CircuitState.OPEN)

    def _transition_to(self, new_state: CircuitState) -> None:
        logger.warning(
            "CircuitBreaker [%s] transitioned state: %s -> %s",
            self.name,
            self.state,
            new_state,
        )
        self.state = new_state
        self.last_state_change = time.time()
        if new_state == CircuitState.HALF_OPEN:
            self.half_open_successes = 0

    def check_or_raise(self, correlation_id: str | None = None) -> None:
        """Check state and raise ModelProviderFailure if circuit is OPEN."""
        if not self.allow_request():
            raise ModelProviderFailure(
                provider=self.name,
                message="MODEL_PROVIDER_TEMPORARILY_DISABLED",
                correlation_id=correlation_id,
                internal_details={
                    "circuit_state": self.state.value,
                    "circuit_name": self.name,
                },
            )


# Global registry for named component circuit breakers
_CIRCUIT_BREAKERS: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_time_seconds: float = 60.0,
) -> CircuitBreaker:
    """Get or create a named CircuitBreaker instance."""
    if name not in _CIRCUIT_BREAKERS:
        _CIRCUIT_BREAKERS[name] = CircuitBreaker(
            name,
            failure_threshold=failure_threshold,
            recovery_time_seconds=recovery_time_seconds,
        )
    return _CIRCUIT_BREAKERS[name]


def reset_all_circuit_breakers() -> None:
    """Reset all circuit breakers (primarily for test harness isolation)."""
    _CIRCUIT_BREAKERS.clear()
