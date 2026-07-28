"""Security and authorization domain exceptions."""

from __future__ import annotations

from typing import Any

from src.exceptions.base import EngineError


class AuthorizationFailure(EngineError):
    """Raised when an operation or role check fails authorization."""

    error_code = "AUTHORIZATION_FAILURE"
    severity = "high"
    recoverable = False

    def __init__(
        self,
        reason: str = "Access denied",
        *,
        correlation_id: str | None = None,
        internal_details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            f"Authorization failure: {reason}",
            error_code=self.error_code,
            severity=self.severity,
            recoverable=self.recoverable,
            correlation_id=correlation_id,
            safe_message="Access denied.",
            internal_details=internal_details,
        )


class SessionRecoveryDenied(EngineError):
    """Raised when session recovery is denied due to owner or tenant mismatch."""

    error_code = "SESSION_RECOVERY_DENIED"
    severity = "high"
    recoverable = False

    def __init__(
        self,
        reason: str = "Session recovery denied",
        *,
        correlation_id: str | None = None,
        internal_details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            f"Session recovery denied: {reason}",
            error_code=self.error_code,
            severity=self.severity,
            recoverable=self.recoverable,
            correlation_id=correlation_id,
            safe_message="Your secure session could not be restored. Please refresh and authenticate again.",
            internal_details=internal_details,
        )


class ContextValidationFailure(EngineError):
    """Raised when security context resolution or validation fails."""

    error_code = "CONTEXT_VALIDATION_FAILURE"
    severity = "high"
    recoverable = False

    def __init__(
        self,
        reason: str = "Invalid security context",
        *,
        correlation_id: str | None = None,
        internal_details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            f"Context validation failure: {reason}",
            error_code=self.error_code,
            severity=self.severity,
            recoverable=self.recoverable,
            correlation_id=correlation_id,
            safe_message="Invalid request security context.",
            internal_details=internal_details,
        )


class DisclosureBlocked(EngineError):
    """Raised when DisclosureGuard blocks unsafe model output."""

    error_code = "DISCLOSURE_BLOCKED"
    severity = "high"
    recoverable = False

    def __init__(
        self,
        reason: str = "Content blocked by disclosure guard",
        *,
        correlation_id: str | None = None,
        internal_details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            f"Disclosure blocked: {reason}",
            error_code=self.error_code,
            severity=self.severity,
            recoverable=self.recoverable,
            correlation_id=correlation_id,
            safe_message="The response contained prohibited information and was blocked.",
            internal_details=internal_details,
        )


class SandboxViolation(EngineError):
    """Raised when a path or operation escapes filesystem sandbox boundaries."""

    error_code = "SANDBOX_VIOLATION"
    severity = "high"
    recoverable = False

    def __init__(
        self,
        message: str = "Requested path escapes session sandbox",
        *,
        correlation_id: str | None = None,
        internal_details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code=self.error_code,
            severity=self.severity,
            recoverable=self.recoverable,
            correlation_id=correlation_id,
            safe_message="Requested operation escapes sandbox boundaries.",
            internal_details=internal_details,
        )


class ContextPolicyViolation(EngineError):
    """Raised when context broker detects internal or forbidden context in public workflow."""

    error_code = "CONTEXT_POLICY_VIOLATION"
    severity = "high"
    recoverable = False

    def __init__(
        self,
        reason: str = "Public chat cannot receive internal context",
        *,
        correlation_id: str | None = None,
        internal_details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            f"Context policy violation: {reason}",
            error_code=self.error_code,
            severity=self.severity,
            recoverable=self.recoverable,
            correlation_id=correlation_id,
            safe_message="Context policy violation.",
            internal_details=internal_details,
        )

