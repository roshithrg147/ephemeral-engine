"""Base domain exception definition for Ephemeral Engine."""

from __future__ import annotations

import uuid
from typing import Any


class EngineError(Exception):
    """Base exception class for all domain-level Ephemeral Engine errors."""

    error_code: str = "ENGINE_ERROR"
    severity: str = "medium"
    recoverable: bool = False

    def __init__(
        self,
        message: str = "An internal processing error occurred.",
        *,
        error_code: str | None = None,
        severity: str | None = None,
        recoverable: bool | None = None,
        correlation_id: str | None = None,
        safe_message: str | None = None,
        internal_details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        if error_code is not None:
            self.error_code = error_code
        if severity is not None:
            self.severity = severity
        if recoverable is not None:
            self.recoverable = recoverable

        self.correlation_id: str = correlation_id or f"corr-{uuid.uuid4().hex[:12]}"
        self.safe_message: str = safe_message or message
        self.internal_details: dict[str, Any] = internal_details or {}

    def to_safe_dict(self) -> dict[str, Any]:
        """Return a user-safe error dictionary omitting diagnostic details."""
        return {
            "type": "error",
            "code": self.error_code,
            "message": self.safe_message,
            "correlation_id": self.correlation_id,
        }
