"""Workflow domain exceptions."""

from __future__ import annotations

from typing import Any

from src.exceptions.base import EngineError


class WorkflowExecutionFailure(EngineError):
    """Raised when an internal workflow execution fails."""

    error_code = "WORKFLOW_EXECUTION_FAILURE"
    severity = "high"
    recoverable = False

    def __init__(
        self,
        workflow: str = "default",
        reason: str = "Workflow failed",
        *,
        correlation_id: str | None = None,
        internal_details: dict[str, Any] | None = None,
    ) -> None:
        details = internal_details or {}
        details["workflow"] = workflow
        super().__init__(
            f"Workflow execution failure [{workflow}]: {reason}",
            error_code=self.error_code,
            severity=self.severity,
            recoverable=self.recoverable,
            correlation_id=correlation_id,
            safe_message="Workflow execution encountered an error.",
            internal_details=details,
        )


class RateLimitExceeded(EngineError):
    """Raised when a request or workflow rate limit is exceeded."""

    error_code = "RATE_LIMIT_EXCEEDED"
    severity = "medium"
    recoverable = True

    def __init__(
        self,
        resource: str = "api",
        *,
        correlation_id: str | None = None,
        internal_details: dict[str, Any] | None = None,
    ) -> None:
        details = internal_details or {}
        details["resource"] = resource
        super().__init__(
            f"Rate limit exceeded for resource: {resource}",
            error_code=self.error_code,
            severity=self.severity,
            recoverable=self.recoverable,
            correlation_id=correlation_id,
            safe_message="Too many requests. Please slow down and try again later.",
            internal_details=details,
        )
