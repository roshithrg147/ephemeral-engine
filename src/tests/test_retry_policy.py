"""Unit tests for RetryManager backoff and filtering policy."""

from __future__ import annotations

import unittest

from src.exceptions.provider import ModelTimeout
from src.exceptions.security import SandboxViolation
from src.reliability.retry_manager import RetryManager


class TestRetryPolicy(unittest.IsolatedAsyncioTestCase):
    async def test_retryable_exception_retries_and_succeeds(self) -> None:
        attempts = 0

        async def failing_op() -> str:
            nonlocal attempts
            attempts += 1
            if attempts < 2:
                raise ModelTimeout(provider="test", timeout_seconds=1.0)
            return "success"

        result = await RetryManager.execute_with_retry(
            failing_op,
            delays=(0.01, 0.02),
            operation_name="test_op",
        )
        self.assertEqual(result, "success")
        self.assertEqual(attempts, 2)

    async def test_non_retryable_exception_fails_immediately(self) -> None:
        attempts = 0

        async def security_op() -> None:
            nonlocal attempts
            attempts += 1
            raise SandboxViolation("Path escape")

        with self.assertRaises(SandboxViolation):
            await RetryManager.execute_with_retry(
                security_op,
                delays=(0.01, 0.02),
                operation_name="security_op",
            )
        self.assertEqual(attempts, 1)


if __name__ == "__main__":
    unittest.main()
