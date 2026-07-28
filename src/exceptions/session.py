"""Session domain exceptions."""

from __future__ import annotations

from typing import Any

from src.exceptions.base import EngineError


class SessionNotInitialized(EngineError):
    """Raised when a requested session state context is missing or uninitialized."""

    error_code = "SESSION_NOT_INITIALIZED"
    severity = "medium"
    recoverable = True

    def __init__(
        self,
        session_id: str,
        *,
        correlation_id: str | None = None,
        internal_details: dict[str, Any] | None = None,
    ) -> None:
        details = internal_details or {}
        details["session_id"] = session_id
        super().__init__(
            f"Session state context uninitialized: {session_id}",
            error_code=self.error_code,
            severity=self.severity,
            recoverable=self.recoverable,
            correlation_id=correlation_id,
            safe_message="Session state context is not initialized.",
            internal_details=details,
        )


class SessionExpired(EngineError):
    """Raised when a session TTL or token budget has expired."""

    error_code = "SESSION_EXPIRED"
    severity = "medium"
    recoverable = False

    def __init__(
        self,
        session_id: str,
        *,
        correlation_id: str | None = None,
        internal_details: dict[str, Any] | None = None,
    ) -> None:
        details = internal_details or {}
        details["session_id"] = session_id
        super().__init__(
            f"Session expired: {session_id}",
            error_code=self.error_code,
            severity=self.severity,
            recoverable=self.recoverable,
            correlation_id=correlation_id,
            safe_message="Your session has expired. Please re-initialize your session.",
            internal_details=details,
        )
