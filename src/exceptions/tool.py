"""Tool execution domain exceptions."""

from __future__ import annotations

from typing import Any

from src.exceptions.base import EngineError


class ToolExecutionFailure(EngineError):
    """Raised when an internal or external tool execution fails."""

    error_code = "TOOL_EXECUTION_FAILURE"
    severity = "medium"
    recoverable = False

    def __init__(
        self,
        tool_name: str,
        reason: str = "Tool execution failed",
        *,
        correlation_id: str | None = None,
        internal_details: dict[str, Any] | None = None,
    ) -> None:
        details = internal_details or {}
        details["tool_name"] = tool_name
        super().__init__(
            f"Tool execution failed [{tool_name}]: {reason}",
            error_code=self.error_code,
            severity=self.severity,
            recoverable=self.recoverable,
            correlation_id=correlation_id,
            safe_message="The requested tool operation could not be completed.",
            internal_details=details,
        )
