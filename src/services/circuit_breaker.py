"""Circuit Breaker and Resilience Policy Engine for SC-EVM.

Implements CLOSED, OPEN, and HALF_OPEN state transitions, exponential backoff retries,
request timeouts, and automatic provider failover.
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any, Callable, Literal

logger = logging.getLogger("SC-EVM.CircuitBreaker")

StateName = Literal["CLOSED", "OPEN", "HALF_OPEN"]


class CircuitBreakerOpenError(RuntimeError):
    """Raised when an operation is attempted while the circuit breaker is OPEN."""


class CircuitBreaker:
    """Three-state Circuit Breaker (CLOSED, OPEN, HALF_OPEN) with retry policy."""

    def __init__(
        self,
        name: str = "default_provider",
        failure_threshold: int = 3,
        recovery_timeout: float = 5.0,
        max_retries: int = 3,
        base_delay: float = 0.2,
        max_delay: float = 2.0,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

        self._state: StateName = "CLOSED"
        self._failure_count: int = 0
        self._last_failure_time: float = 0.0
        self._success_count: int = 0

    @property
    def state(self) -> StateName:
        if self._state == "OPEN":
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                logger.info(f"CircuitBreaker '{self.name}' transitioning from OPEN to HALF_OPEN")
                self._state = "HALF_OPEN"
                self._success_count = 0
        return self._state

    def record_success(self) -> None:
        """Record successful call execution."""
        if self._state == "HALF_OPEN":
            self._success_count += 1
            if self._success_count >= 2:
                logger.info(f"CircuitBreaker '{self.name}' recovered; transitioning to CLOSED")
                self._state = "CLOSED"
                self._failure_count = 0
        elif self._state == "CLOSED":
            self._failure_count = 0

    def record_failure(self) -> None:
        """Record failed call execution."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == "HALF_OPEN" or self._failure_count >= self.failure_threshold:
            logger.warning(f"CircuitBreaker '{self.name}' tripped to OPEN (failures={self._failure_count})")
            self._state = "OPEN"

    def execute(self, fn: Callable[..., Any], *args: Any, fallback_fn: Callable[..., Any] | None = None, **kwargs: Any) -> Any:
        """Execute a synchronous function wrapped with circuit breaker and retry logic."""
        if self.state == "OPEN":
            if fallback_fn:
                return fallback_fn(*args, **kwargs)
            raise CircuitBreakerOpenError(f"CircuitBreaker '{self.name}' is OPEN")

        last_exception = None
        for attempt in range(1, self.max_retries + 1):
            try:
                result = fn(*args, **kwargs)
                self.record_success()
                return result
            except Exception as e:
                last_exception = e
                self.record_failure()
                if attempt < self.max_retries:
                    delay = min(self.max_delay, self.base_delay * (2 ** (attempt - 1)))
                    jitter = random.uniform(0, 0.1 * delay)
                    time.sleep(delay + jitter)

        if fallback_fn:
            logger.info(f"CircuitBreaker '{self.name}' executing fallback after retries exhaustion")
            return fallback_fn(*args, **kwargs)

        raise last_exception or RuntimeError(f"CircuitBreaker '{self.name}' call failed")

    async def async_execute(self, coro_fn: Callable[..., Any], *args: Any, fallback_fn: Callable[..., Any] | None = None, **kwargs: Any) -> Any:
        """Execute an asynchronous function wrapped with circuit breaker and retry logic."""
        if self.state == "OPEN":
            if fallback_fn:
                if asyncio.iscoroutinefunction(fallback_fn):
                    return await fallback_fn(*args, **kwargs)
                return fallback_fn(*args, **kwargs)
            raise CircuitBreakerOpenError(f"CircuitBreaker '{self.name}' is OPEN")

        last_exception = None
        for attempt in range(1, self.max_retries + 1):
            try:
                result = await coro_fn(*args, **kwargs)
                self.record_success()
                return result
            except Exception as e:
                last_exception = e
                self.record_failure()
                if attempt < self.max_retries:
                    delay = min(self.max_delay, self.base_delay * (2 ** (attempt - 1)))
                    jitter = random.uniform(0, 0.1 * delay)
                    await asyncio.sleep(delay + jitter)

        if fallback_fn:
            logger.info(f"CircuitBreaker '{self.name}' executing async fallback after retries exhaustion")
            if asyncio.iscoroutinefunction(fallback_fn):
                return await fallback_fn(*args, **kwargs)
            return fallback_fn(*args, **kwargs)

        raise last_exception or RuntimeError(f"CircuitBreaker '{self.name}' call failed")

    def reset(self) -> None:
        """Reset circuit breaker to CLOSED state."""
        self._state = "CLOSED"
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0.0
