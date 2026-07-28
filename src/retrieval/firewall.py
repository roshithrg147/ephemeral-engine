"""Model Input Firewall — final validation gate before context reaches the LLM.

Principle: "Do not ask why the model revealed it. Ask why the model received it."

The firewall sits between ContextBroker.filter_and_wrap_context() and
prompt_manager.build_augmented_prompt(). It:

1. Validates every ContextTraceEntry against the workflow policy.
2. Rejects the entire context payload if any entry violates policy.
3. Emits a structured audit event for every decision.
4. Never passes untraceable context — if there is no trace, context is rejected.

The firewall does NOT replace retrieval-layer filtering. It is the final
safety net that makes the retrieval trace the authoritative record.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from src.knowledge.metadata import INTERNAL_CLASSIFICATIONS, Classification
from src.retrieval.audit import RetrievalAuditLogger
from src.retrieval.trace import ContextTrace, ContextTraceEntry
from src.security_context import SecurityContext
from src.workflow_policy import WorkflowClass

logger = logging.getLogger("SC-EVM.ModelInputFirewall")


@dataclass(slots=True)
class FirewallDecision:
    """Result of a firewall inspection."""

    allowed: bool
    violations: list[str]
    admitted_entries: list[ContextTraceEntry]
    correlation_id: str
    workflow: str

    @property
    def context_clean(self) -> bool:
        return self.allowed and not self.violations


class ModelInputFirewall:
    """Validates the assembled context trace before it enters the model prompt.

    Usage:
        decision = ModelInputFirewall.inspect(sec_ctx, trace)
        if not decision.allowed:
            context_str = ""   # fail closed
    """

    @classmethod
    def inspect(cls, sec_ctx: SecurityContext, trace: ContextTrace | None) -> FirewallDecision:
        """Inspect the context trace and return a firewall decision.

        Fails closed: if trace is None or any entry violates policy, context is rejected.
        """
        correlation_id = sec_ctx.correlation_id
        workflow = sec_ctx.workflow

        # No trace = untraceable context = reject
        if trace is None:
            cls._log_violation(
                sec_ctx,
                "UNTRACEABLE_CONTEXT",
                "Context has no provenance trace. Rejecting.",
            )
            return FirewallDecision(
                allowed=False,
                violations=["no_trace"],
                admitted_entries=[],
                correlation_id=correlation_id,
                workflow=workflow.value,
            )

        # Empty context is always safe
        if not trace.entries:
            return FirewallDecision(
                allowed=True,
                violations=[],
                admitted_entries=[],
                correlation_id=correlation_id,
                workflow=workflow.value,
            )

        violations: list[str] = []
        admitted: list[ContextTraceEntry] = []

        for entry in trace.entries:
            ok, reason = cls._validate_entry(entry, workflow, sec_ctx.tenant_id)
            if ok:
                admitted.append(entry)
            else:
                violations.append(f"entry={entry.document_id} reason={reason}")
                cls._log_violation(sec_ctx, "ENTRY_POLICY_VIOLATION", reason, entry)

        if violations:
            # Any violation = reject entire context payload (fail closed)
            RetrievalAuditLogger.log_retrieval_blocked(
                correlation_id=correlation_id,
                workflow=workflow.value,
                principal_id=sec_ctx.canonical_principal_id,
                blocked_source="model_input_firewall",
                reason=f"firewall_violations: {violations}",
                query_intent=trace.query_intent,
            )
            return FirewallDecision(
                allowed=False,
                violations=violations,
                admitted_entries=[],
                correlation_id=correlation_id,
                workflow=workflow.value,
            )

        logger.info(
            "FIREWALL_PASS correlation=%s workflow=%s admitted=%d",
            correlation_id,
            workflow.value,
            len(admitted),
        )
        return FirewallDecision(
            allowed=True,
            violations=[],
            admitted_entries=admitted,
            correlation_id=correlation_id,
            workflow=workflow.value,
        )

    @classmethod
    def _validate_entry(
        cls,
        entry: ContextTraceEntry,
        workflow: WorkflowClass,
        tenant_id: str,
    ) -> tuple[bool, str]:
        """Validate a single trace entry against the workflow policy."""
        from src.retrieval.policy import RetrievalPolicyEngine

        # Tenant isolation
        if entry.tenant_id not in (tenant_id, "global"):
            return False, f"tenant_mismatch: entry={entry.tenant_id} req={tenant_id}"

        # Classification check
        try:
            classification = Classification(entry.classification)
        except ValueError:
            return False, f"unknown_classification: {entry.classification}"

        if not RetrievalPolicyEngine.is_classification_allowed(workflow, classification):
            return False, f"classification_forbidden: {entry.classification} workflow={workflow}"

        # PUBLIC_CHAT / PUBLIC_RESEARCH: hard block on any INTERNAL-equivalent classification
        if workflow in (WorkflowClass.PUBLIC_CHAT, WorkflowClass.PUBLIC_RESEARCH):
            if classification in INTERNAL_CLASSIFICATIONS:
                return False, f"internal_classification_in_public_workflow: {entry.classification}"

        # Namespace check
        from src.retrieval.policy import RetrievalPolicyEngine

        policy = RetrievalPolicyEngine.get_policy(workflow)
        allowed_ns_values = {ns.value for ns in policy.allowed_namespaces}
        if entry.namespace and entry.namespace not in allowed_ns_values:
            return False, f"namespace_forbidden: {entry.namespace} workflow={workflow}"

        return True, "ok"

    @classmethod
    def _log_violation(
        cls,
        sec_ctx: SecurityContext,
        event_type: str,
        reason: str,
        entry: ContextTraceEntry | None = None,
    ) -> None:
        record: dict = {
            "event": f"FIREWALL_{event_type}",
            "correlation_id": sec_ctx.correlation_id,
            "workflow": sec_ctx.workflow.value,
            "principal_id": sec_ctx.canonical_principal_id,
            "reason": reason,
        }
        if entry:
            record["document_id"] = entry.document_id
            record["source_type"] = entry.source_type
            record["namespace"] = entry.namespace
            record["classification"] = entry.classification
        logger.warning("MODEL_INPUT_FIREWALL: %s", record)
