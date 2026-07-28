"""Span context and correlation ID tracking for Ephemeral Engine."""

from __future__ import annotations

import contextvars
import uuid
from dataclasses import dataclass, field
from typing import Any

_correlation_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)
_workflow_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "workflow_id", default=None
)


@dataclass
class TraceSpan:
    """Trace span representing an execution block."""

    name: str
    correlation_id: str
    workflow_id: str | None = None
    agent_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def get_current_correlation_id() -> str:
    """Get active correlation ID or generate a new default correlation ID."""
    corr_id = _correlation_id_var.get()
    if not corr_id:
        corr_id = f"corr-{uuid.uuid4().hex[:12]}"
        _correlation_id_var.set(corr_id)
    return corr_id


def set_current_correlation_id(correlation_id: str) -> None:
    """Set the active correlation ID for current context."""
    _correlation_id_var.set(correlation_id)


def get_current_workflow_id() -> str | None:
    """Get current workflow ID."""
    return _workflow_id_var.get()


def set_current_workflow_id(workflow_id: str) -> None:
    """Set current workflow ID."""
    _workflow_id_var.set(workflow_id)
