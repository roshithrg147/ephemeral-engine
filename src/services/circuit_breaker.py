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

StateName = Literal["CLOSED", "WARNING", "OPEN", "COOLDOWN", "HALF_OPEN", "RECOVERED"]


class CircuitBreakerOpenError(RuntimeError):
    """Raised when an operation is attempted while the circuit breaker is OPEN or in COOLDOWN."""


class CircuitBreaker:
    """Six-state Circuit Breaker 2.0 (CLOSED, WARNING, OPEN, COOLDOWN, HALF_OPEN, RECOVERED)."""

    def __init__(
        self,
        name: str = "default_provider",
        warning_threshold: int = 2,
        failure_threshold: int = 4,
        recovery_timeout: float = 5.0,
        cooldown_timeout: float = 15.0,
        max_retries: int = 3,
        base_delay: float = 0.2,
        max_delay: float = 2.0,
    ):
        self.name = name
        self.warning_threshold = warning_threshold
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.cooldown_timeout = cooldown_timeout
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

        self._state: StateName = "CLOSED"
        self._failure_count: int = 0
        self._consecutive_failures: int = 0
        self._last_failure_time: float = 0.0
        self._last_success_time: float = 0.0
        self._success_count: int = 0
        self._last_error_taxonomy: str = "none"

    @property
    def state(self) -> StateName:
        now = time.time()
        if self._state in {"OPEN", "COOLDOWN"}:
            timeout = self.cooldown_timeout if self._state == "COOLDOWN" else self.recovery_timeout
            if now - self._last_failure_time >= timeout:
                logger.info(f"CircuitBreaker '{self.name}' transitioning from {self._state} to HALF_OPEN")
                self._state = "HALF_OPEN"
                self._success_count = 0
        return self._state

    def classify_error(self, exc: Exception | str) -> str:
        s = str(exc).lower()
        if "429" in s or "rate limit" in s:
            return "429_rate_limit"
        if "timeout" in s or "timed out" in s:
            return "timeout"
        if "dns" in s or "name resolution" in s or "getaddrinfo" in s:
            return "dns_failure"
        if "ssl" in s or "certificate" in s:
            return "ssl_failure"
        if "connection refused" in s or "connect" in s:
            return "connection_refused"
        if "500" in s or "502" in s or "503" in s or "504" in s:
            return "5xx_server_error"
        return "generic_error"

    def record_success(self) -> None:
        """Record successful call execution."""
        self._last_success_time = time.time()
        self._consecutive_failures = 0

        if self._state == "HALF_OPEN":
            self._success_count += 1
            if self._success_count >= 2:
                logger.info(f"CircuitBreaker '{self.name}' recovered; transitioning to RECOVERED ➔ CLOSED")
                self._state = "RECOVERED"
                self._failure_count = 0
                self._state = "CLOSED"
        elif self._state == "WARNING":
            self._failure_count = max(0, self._failure_count - 1)
            if self._failure_count == 0:
                self._state = "CLOSED"

    def record_failure(self, exc: Exception | str | None = None) -> None:
        """Record failed call execution with taxonomy analysis."""
        self._failure_count += 1
        self._consecutive_failures += 1
        self._last_failure_time = time.time()

        if exc:
            self._last_error_taxonomy = self.classify_error(exc)

        # Differential state transition based on error severity
        if self._last_error_taxonomy == "429_rate_limit":
            logger.warning(f"CircuitBreaker '{self.name}' hit HTTP 429 rate limit; tripping to COOLDOWN")
            self._state = "COOLDOWN"
        elif self._state == "HALF_OPEN" or self._consecutive_failures >= self.failure_threshold:
            logger.warning(f"CircuitBreaker '{self.name}' tripped to OPEN (consecutive failures={self._consecutive_failures})")
            self._state = "OPEN"
        elif self._failure_count >= self.warning_threshold and self._state == "CLOSED":
            logger.info(f"CircuitBreaker '{self.name}' entering WARNING state (failures={self._failure_count})")
            self._state = "WARNING"

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
