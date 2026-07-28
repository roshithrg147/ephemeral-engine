"""Retrieval audit — structured events for all retrieval decisions."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger("SC-EVM.RetrievalAudit")

# Fields that must never appear in audit logs
_FORBIDDEN_AUDIT_FIELDS = frozenset(
    {"secret", "key", "password", "token", "api_key", "content", "source_code", "file_content", "prompt"}
)


@dataclass(slots=True)
class RetrievalAuditEvent:
    """Structured audit record for a retrieval decision."""

    correlation_id: str
    workflow: str
    principal_id: str
    query_intent: str
    namespace_requested: str
    documents_returned: int
    documents_blocked: int
    classification_failures: list[str] = field(default_factory=list)
    event_type: str = "RETRIEVAL_DECISION"
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    blocked_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": self.event_type,
            "correlation_id": self.correlation_id,
            "workflow": self.workflow,
            "principal_id": self.principal_id,
            "query_intent": self.query_intent,
            "namespace_requested": self.namespace_requested,
            "documents_returned": self.documents_returned,
            "documents_blocked": self.documents_blocked,
            "classification_failures": self.classification_failures,
            "blocked_reason": self.blocked_reason,
            "timestamp": self.timestamp,
        }


class RetrievalAuditLogger:
    """Logs retrieval audit events without leaking sensitive content."""

    @classmethod
    def log_retrieval_blocked(
        cls,
        correlation_id: str,
        workflow: str,
        principal_id: str,
        blocked_source: str,
        reason: str,
        query_intent: str = "UNKNOWN",
    ) -> None:
        event = {
            "event": "RETRIEVAL_POLICY_BLOCK",
            "correlation_id": correlation_id,
            "workflow": workflow,
            "principal_id": principal_id,
            "blocked_source": blocked_source,
            "reason": reason,
            "query_intent": query_intent,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        logger.warning("RETRIEVAL_AUDIT: %s", event)

    @classmethod
    def log_intent_block(
        cls,
        correlation_id: str,
        workflow: str,
        principal_id: str,
        query_intent: str,
    ) -> None:
        event = {
            "event": "RETRIEVAL_INTENT_BLOCK",
            "correlation_id": correlation_id,
            "workflow": workflow,
            "principal_id": principal_id,
            "query_intent": query_intent,
            "reason": "retrieval_disabled_for_sensitive_intent",
            "timestamp": datetime.now(UTC).isoformat(),
        }
        logger.warning("RETRIEVAL_AUDIT: %s", event)

    @classmethod
    def log_event(cls, event: RetrievalAuditEvent) -> None:
        logger.info("RETRIEVAL_AUDIT: %s", event.to_dict())

    @classmethod
    def log_namespace_violation(
        cls,
        correlation_id: str,
        workflow: str,
        principal_id: str,
        requested_namespace: str,
        reason: str,
    ) -> None:
        event = {
            "event": "RETRIEVAL_NAMESPACE_VIOLATION",
            "correlation_id": correlation_id,
            "workflow": workflow,
            "principal_id": principal_id,
            "requested_namespace": requested_namespace,
            "reason": reason,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        logger.warning("RETRIEVAL_AUDIT: %s", event)

    @classmethod
    def log_context_broker_rejection(
        cls,
        correlation_id: str,
        workflow: str,
        principal_id: str,
        reason: str,
    ) -> None:
        event = {
            "event": "CONTEXT_BROKER_REJECTION",
            "correlation_id": correlation_id,
            "workflow": workflow,
            "principal_id": principal_id,
            "reason": reason,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        logger.warning("RETRIEVAL_AUDIT: %s", event)
