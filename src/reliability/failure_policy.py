"""Failure policy definitions for classifying exceptions and fallbacks."""

from __future__ import annotations

import logging
from typing import Any

from src.exceptions.base import EngineError

logger = logging.getLogger("SC-EVM.RELIABILITY.POLICY")


class FailurePolicy:
    """Classifies exceptions into safe public representations and fallback policies."""

    @staticmethod
    def classify_exception(exc: Exception) -> dict[str, Any]:
        """Convert any exception into safe user-facing error properties."""
        if isinstance(exc, EngineError):
            return {
                "code": exc.error_code,
                "message": exc.safe_message,
                "correlation_id": exc.correlation_id,
                "severity": exc.severity,
                "recoverable": exc.recoverable,
            }

        exc_type = type(exc).__name__
        if exc_type == "KeyError" and "Session state context uninitialized" in str(exc):
            return {
                "code": "SESSION_NOT_INITIALIZED",
                "message": "Session state context is not initialized.",
                "correlation_id": "corr-unknown",
                "severity": "medium",
                "recoverable": True,
            }
        if exc_type in ("PermissionError", "AuthenticationError"):
            return {
                "code": "AUTHORIZATION_FAILURE",
                "message": "Access denied.",
                "correlation_id": "corr-unknown",
                "severity": "high",
                "recoverable": False,
            }
        if exc_type in ("ValidationError", "ValueError"):
            return {
                "code": "CONTEXT_VALIDATION_FAILURE",
                "message": "Invalid request payload or context.",
                "correlation_id": "corr-unknown",
                "severity": "medium",
                "recoverable": False,
            }

        return {
            "code": "ERR_INTERNAL_SAFETY",
            "message": "An internal processing error occurred.",
            "correlation_id": "corr-unknown",
            "severity": "high",
            "recoverable": False,
        }
