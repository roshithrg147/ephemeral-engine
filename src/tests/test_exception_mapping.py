"""Unit tests for domain exception mapping and error handling."""

from __future__ import annotations

import unittest

from src.exceptions.base import EngineError
from src.exceptions.provider import ModelProviderFailure, ModelTimeout
from src.exceptions.security import AuthorizationFailure, SandboxViolation
from src.exceptions.session import SessionNotInitialized
from src.services.error_handlers import SafeErrorMapper


class TestExceptionMapping(unittest.TestCase):
    def test_engine_error_attributes(self) -> None:
        err = EngineError("Internal detail message", safe_message="Safe user message")
        self.assertEqual(err.safe_message, "Safe user message")
        self.assertTrue(err.correlation_id.startswith("corr-"))
        self.assertEqual(
            err.to_safe_dict(),
            {
                "type": "error",
                "code": "ENGINE_ERROR",
                "message": "Safe user message",
                "correlation_id": err.correlation_id,
            },
        )

    def test_session_not_initialized_mapping(self) -> None:
        err = SessionNotInitialized("session-123")
        self.assertTrue(err.recoverable)
        self.assertEqual(err.error_code, "SESSION_NOT_INITIALIZED")
        code, status, msg = SafeErrorMapper.map_exception(err)
        self.assertEqual(code, "SESSION_NOT_INITIALIZED")
        self.assertEqual(status, 404)

    def test_model_provider_failure_mapping(self) -> None:
        err = ModelProviderFailure(provider="nvidia", message="Connection reset")
        self.assertTrue(err.recoverable)
        code, status, msg = SafeErrorMapper.map_exception(err)
        self.assertEqual(code, "MODEL_PROVIDER_FAILURE")
        self.assertEqual(status, 503)

    def test_model_timeout_mapping(self) -> None:
        err = ModelTimeout(provider="nvidia", timeout_seconds=15.0)
        self.assertTrue(err.recoverable)
        code, status, msg = SafeErrorMapper.map_exception(err)
        self.assertEqual(code, "MODEL_TIMEOUT")
        self.assertEqual(status, 504)

    def test_authorization_failure_mapping(self) -> None:
        err = AuthorizationFailure(reason="Missing scope")
        self.assertFalse(err.recoverable)
        code, status, msg = SafeErrorMapper.map_exception(err)
        self.assertEqual(code, "AUTHORIZATION_FAILURE")
        self.assertEqual(status, 403)

    def test_sandbox_violation_mapping(self) -> None:
        err = SandboxViolation("Path escapes sandbox")
        self.assertFalse(err.recoverable)
        code, status, msg = SafeErrorMapper.map_exception(err)
        self.assertEqual(code, "SANDBOX_VIOLATION")
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
