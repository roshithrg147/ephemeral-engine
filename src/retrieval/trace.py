"""Context trace — per-item provenance record for every piece of context entering the model.

Every ContextItem that passes through the retrieval gateway gets a ContextTraceEntry
recording exactly:
  - what it is (document_id, content_hash)
  - where it came from (source_type, namespace, injecting_component)
  - which policy allowed it (workflow, classification, policy_rule)
  - when it was admitted (timestamp)

A ContextTrace aggregates all entries for a single request and is attached to
RetrievalResult. The ModelInputFirewall reads the trace before the prompt is built.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(slots=True)
class ContextTraceEntry:
    """Provenance record for a single context item admitted to the model."""

    # Identity
    document_id: str          # content_hash of the ContextItem
    content_preview: str      # first 80 chars — never full content

    # Origin
    source_type: str          # SourceType value or free-form for legacy paths
    namespace: str            # RetrievalNamespace value
    injecting_component: str  # e.g. "RetrievalGateway", "ContextBroker.pending_queue"

    # Policy decision
    workflow: str             # WorkflowClass value
    classification: str       # Classification value
    policy_rule: str          # human-readable rule that admitted this item
    tenant_id: str

    # Timing
    admitted_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict:
        return {
            "document_id": self.document_id,
            "content_preview": self.content_preview,
            "source_type": self.source_type,
            "namespace": self.namespace,
            "injecting_component": self.injecting_component,
            "workflow": self.workflow,
            "classification": self.classification,
            "policy_rule": self.policy_rule,
            "tenant_id": self.tenant_id,
            "admitted_at": self.admitted_at,
        }


@dataclass(slots=True)
class ContextTrace:
    """Full provenance trace for a single retrieval request.

    Attached to RetrievalResult and passed to ModelInputFirewall.
    """

    correlation_id: str
    workflow: str
    principal_id: str
    query_intent: str
    entries: list[ContextTraceEntry] = field(default_factory=list)
    blocked_entries: list[dict] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def add_entry(self, entry: ContextTraceEntry) -> None:
        self.entries.append(entry)

    def add_blocked(self, reason: str, source_type: str, namespace: str, document_id: str = "") -> None:
        self.blocked_entries.append(
            {
                "document_id": document_id,
                "source_type": source_type,
                "namespace": namespace,
                "reason": reason,
                "blocked_at": datetime.now(UTC).isoformat(),
            }
        )

    @property
    def admitted_count(self) -> int:
        return len(self.entries)

    @property
    def blocked_count(self) -> int:
        return len(self.blocked_entries)

    def to_audit_dict(self) -> dict:
        """Serialise for audit log — no raw content, only provenance."""
        return {
            "correlation_id": self.correlation_id,
            "workflow": self.workflow,
            "principal_id": self.principal_id,
            "query_intent": self.query_intent,
            "admitted_count": self.admitted_count,
            "blocked_count": self.blocked_count,
            "entries": [e.to_dict() for e in self.entries],
            "blocked_entries": self.blocked_entries,
            "created_at": self.created_at,
        }

    def summary_line(self) -> str:
        """Single-line summary for structured logging."""
        return (
            f"ContextTrace correlation={self.correlation_id} "
            f"workflow={self.workflow} intent={self.query_intent} "
            f"admitted={self.admitted_count} blocked={self.blocked_count}"
        )


def make_trace_entry_from_context_item(
    item,  # ContextItem — avoid circular import
    namespace: str,
    injecting_component: str,
    policy_rule: str,
    workflow: str,
) -> ContextTraceEntry:
    """Build a ContextTraceEntry from a ContextItem without importing ContextItem directly."""
    preview = (item.content[:80] + "…") if len(item.content) > 80 else item.content
    # Strip newlines from preview to keep audit logs single-line
    preview = preview.replace("\n", " ").replace("\r", "")
    return ContextTraceEntry(
        document_id=item.content_hash,
        content_preview=preview,
        source_type=item.source,
        namespace=namespace,
        injecting_component=injecting_component,
        workflow=workflow,
        classification=item.classification,
        policy_rule=policy_rule,
        tenant_id=item.tenant_id,
    )
