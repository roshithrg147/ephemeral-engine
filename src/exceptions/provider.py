"""Model provider domain exceptions."""

from __future__ import annotations

from typing import Any

from src.exceptions.base import EngineError


class ModelProviderFailure(EngineError):
    """Raised when an LLM model provider API fails or returns an error."""

    error_code = "MODEL_PROVIDER_FAILURE"
    severity = "high"
    recoverable = True

    def __init__(
        self,
        provider: str = "provider",
        message: str = "Model provider request failed",
        *,
        correlation_id: str | None = None,
        internal_details: dict[str, Any] | None = None,
    ) -> None:
        details = internal_details or {}
        details["provider"] = provider
        super().__init__(
            f"Model provider failure [{provider}]: {message}",
            error_code=self.error_code,
            severity=self.severity,
            recoverable=self.recoverable,
            correlation_id=correlation_id,
            safe_message="The AI service is temporarily unavailable. Please retry.",
            internal_details=details,
        )


class ModelTimeout(EngineError):
    """Raised when an LLM model provider request times out."""

    error_code = "MODEL_TIMEOUT"
    severity = "medium"
    recoverable = True

    def __init__(
        self,
        provider: str = "provider",
        timeout_seconds: float = 0.0,
        *,
        correlation_id: str | None = None,
        internal_details: dict[str, Any] | None = None,
    ) -> None:
        details = internal_details or {}
        details.update({"provider": provider, "timeout_seconds": timeout_seconds})
        super().__init__(
            f"Model provider request timed out [{provider}] after {timeout_seconds}s",
            error_code=self.error_code,
            severity=self.severity,
            recoverable=self.recoverable,
            correlation_id=correlation_id,
            safe_message="The request to the AI model timed out. Please try again.",
            internal_details=details,
        )
