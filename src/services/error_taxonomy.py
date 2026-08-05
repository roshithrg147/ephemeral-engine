"""Machine-readable Runtime Error Taxonomy for SC-EVM Resilience.

Defines fine-grained error codes and exception wrappers to eliminate silent failures
and ensure deterministic observability and machine-driven recovery.
"""
from __future__ import annotations

from enum import Enum
from typing import Any


class RuntimeErrorCode(str, Enum):
    # Model / Provider Errors
    EMBEDDING_TIMEOUT = "EMBEDDING_TIMEOUT"
    PROVIDER_RATE_LIMIT = "PROVIDER_RATE_LIMIT"
    PROVIDER_OUTAGE = "PROVIDER_OUTAGE"
    UNKNOWN_PROVIDER = "UNKNOWN_PROVIDER"

    # Vector & Retrieval Failures
    VECTOR_STORE_FAILURE = "VECTOR_STORE_FAILURE"
    BM25_FAILURE = "BM25_FAILURE"
    AST_FAILURE = "AST_FAILURE"

    # Context & Planning Failures
    PROMPT_ASSEMBLY_FAILURE = "PROMPT_ASSEMBLY_FAILURE"
    TOKEN_BUDGET_EXCEEDED = "TOKEN_BUDGET_EXHAUSTED"

    # Streaming & Lifecycle Failures
    STREAM_INTERRUPTED = "STREAM_INTERRUPTED"
    SESSION_RECOVERY_FAILED = "SESSION_RECOVERY_FAILED"
    STORAGE_PERSISTENCE_FAILED = "STORAGE_PERSISTENCE_FAILED"

    # System / Generic
    CIRCUIT_OPEN = "CIRCUIT_OPEN"
    UNEXPECTED_RUNTIME_ERROR = "UNEXPECTED_RUNTIME_ERROR"


class ResilientRuntimeError(Exception):
    """Machine-readable exception wrapper carrying structured diagnostic context."""

    def __init__(
        self,
        code: RuntimeErrorCode,
        message: str,
        *,
        provider: str | None = None,
        http_status: int = 500,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.provider = provider
        self.http_status = http_status
        self.context = context or {}
        self.cause = cause

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_code": self.code.value,
            "message": self.message,
            "provider": self.provider,
            "http_status": self.http_status,
            "context": self.context,
        }
