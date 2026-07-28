"""Retry manager for controlled execution retries with exponential backoff."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from src.exceptions.base import EngineError

logger = logging.getLogger("SC-EVM.RELIABILITY.RETRY")

T = TypeVar("T")

DEFAULT_BACKOFF_DELAYS = (0.5, 2.0, 5.0)


class RetryManager:
    """Executes asynchronous operations with controlled retries and exponential backoff."""

    @staticmethod
    def is_retryable(exc: Exception) -> bool:
        """Determine if an exception is retryable based on security and error policy."""
        if isinstance(exc, EngineError):
            return exc.recoverable
        exc_name = type(exc).__name__
        if exc_name in (
            "AuthorizationFailure",
            "ContextValidationFailure",
            "DisclosureBlocked",
            "SandboxViolation",
            "PermissionError",
            "ValueError",
        ):
            return False
        return True

    @classmethod
    async def execute_with_retry(
        cls,
        operation: Callable[[], Awaitable[T]],
        *,
        delays: tuple[float, ...] = DEFAULT_BACKOFF_DELAYS,
        operation_name: str = "operation",
        correlation_id: str | None = None,
    ) -> T:
        """Execute operation with retries.

        If non-retryable exception occurs, fails fast immediately.
        """
        last_exception: Exception | None = None
        total_attempts = len(delays) + 1

        for attempt in range(1, total_attempts + 1):
            try:
                return await operation()
            except Exception as exc:
                last_exception = exc
                if not cls.is_retryable(exc):
                    logger.warning(
                        "Operation [%s] failed with non-retryable exception (%s)",
                        operation_name,
                        type(exc).__name__,
                        extra={"correlation_id": correlation_id, "attempt": attempt},
                    )
                    raise

                if attempt > len(delays):
                    logger.error(
                        "Operation [%s] exhausted all %d retry attempts",
                        operation_name,
                        total_attempts,
                        extra={"correlation_id": correlation_id},
                    )
                    raise

                delay = delays[attempt - 1]
                logger.warning(
                    "Operation [%s] failed (attempt %d/%d); retrying in %.2fs. Error: %s",
                    operation_name,
                    attempt,
                    total_attempts,
                    delay,
                    exc,
                    extra={"correlation_id": correlation_id},
                )
                await asyncio.sleep(delay)

        if last_exception:
            raise last_exception
        raise RuntimeError(f"Operation {operation_name} failed without exception")
