"""Structured logger for Ephemeral Engine correlation and context tracing."""

from __future__ import annotations

import logging
from typing import Any


class StructuredLogger:
    """Utility wrapper for creating loggers with structured context context metadata."""

    def __init__(self, name: str) -> None:
        self._logger = logging.getLogger(name)

    def info(
        self,
        event: str,
        *,
        correlation_id: str | None = None,
        workflow_id: str | None = None,
        agent_id: str | None = None,
        tool_call_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        ctx = self._build_extra(correlation_id, workflow_id, agent_id, tool_call_id, extra)
        self._logger.info(event, extra=ctx)

    def warning(
        self,
        event: str,
        *,
        correlation_id: str | None = None,
        workflow_id: str | None = None,
        agent_id: str | None = None,
        tool_call_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        ctx = self._build_extra(correlation_id, workflow_id, agent_id, tool_call_id, extra)
        self._logger.warning(event, extra=ctx)

    def error(
        self,
        event: str,
        *,
        correlation_id: str | None = None,
        workflow_id: str | None = None,
        agent_id: str | None = None,
        tool_call_id: str | None = None,
        exc_info: bool = False,
        extra: dict[str, Any] | None = None,
    ) -> None:
        ctx = self._build_extra(correlation_id, workflow_id, agent_id, tool_call_id, extra)
        self._logger.error(event, extra=ctx, exc_info=exc_info)

    @staticmethod
    def _build_extra(
        correlation_id: str | None,
        workflow_id: str | None,
        agent_id: str | None,
        tool_call_id: str | None,
        extra: dict[str, Any] | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = extra or {}
        if correlation_id:
            payload["correlation_id"] = correlation_id
        if workflow_id:
            payload["workflow_id"] = workflow_id
        if agent_id:
            payload["agent_id"] = agent_id
        if tool_call_id:
            payload["tool_call_id"] = tool_call_id
        return payload
