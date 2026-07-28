"""Unit tests for model provider timeout handling."""

from __future__ import annotations

import unittest

from src.exceptions.provider import ModelTimeout
from src.reliability.retry_manager import RetryManager


class TestProviderTimeout(unittest.IsolatedAsyncioTestCase):
    async def test_provider_timeout_exception_properties(self) -> None:
        err = ModelTimeout(provider="nvidia-nim", timeout_seconds=60.0)
        self.assertEqual(err.error_code, "MODEL_TIMEOUT")
        self.assertTrue(err.recoverable)
        self.assertIn("timed out", err.safe_message)

    async def test_provider_timeout_exhausts_retries(self) -> None:
        attempts = 0

        async def timing_out_op() -> None:
            nonlocal attempts
            attempts += 1
            raise ModelTimeout(provider="nvidia-nim", timeout_seconds=1.0)

        with self.assertRaises(ModelTimeout):
            await RetryManager.execute_with_retry(
                timing_out_op,
                delays=(0.01, 0.01),
                operation_name="timing_out_op",
            )
        self.assertEqual(attempts, 3)


if __name__ == "__main__":
    unittest.main()
