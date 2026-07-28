"""Retrieval Security Gateway — the single mandatory entry point for all retrieval.

No code may call vector_db.search(), graph.search(), or embedding_store.query()
outside this module. All retrieval passes through RetrievalGateway.retrieve().

Flow:
  User Query
    -> Security Context
    -> Query Intent Classification
    -> Retrieval Policy Decision
    -> Namespace Filtering
    -> Vector / Graph Search (with pre-query metadata filters)
    -> Post-retrieval Metadata Validation
    -> Context Broker validation
    -> LLM
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from src.context_broker import ContextBroker, ContextItem
from src.knowledge.metadata import Classification
from src.knowledge.namespace import RetrievalNamespace, get_allowed_graph_namespaces
from src.retrieval.audit import RetrievalAuditEvent, RetrievalAuditLogger
from src.retrieval.filters import RetrievalFilter
from src.retrieval.intent import QueryIntent, QueryIntentClassifier
from src.retrieval.policy import RetrievalPolicyEngine
from src.retrieval.trace import ContextTrace, make_trace_entry_from_context_item
from src.security_context import SecurityContext
from src.workflow_policy import WorkflowClass

logger = logging.getLogger("SC-EVM.RetrievalGateway")


@dataclass(slots=True)
class RetrievalRequest:
    """Input to the retrieval gateway."""

    query: str
    sec_ctx: SecurityContext
    top_k: int = 3
    # Optional: caller may hint a namespace; gateway validates and may override.
    requested_namespace: str = ""
    # Optional: caller may hint a graph namespace.
    requested_graph_namespace: str = ""


@dataclass(slots=True)
class RetrievalResult:
    """Output from the retrieval gateway — only policy-cleared context items."""

    context_items: list[ContextItem] = field(default_factory=list)
    query_intent: QueryIntent = QueryIntent.NORMAL_INFORMATION_REQUEST
    retrieval_blocked: bool = False
    blocked_reason: str = ""
    documents_blocked: int = 0
    # Provenance trace — every admitted item is recorded here.
    # ModelInputFirewall reads this before context enters the prompt.
    trace: ContextTrace | None = None


class RetrievalGateway:
    """Secure gateway for all retrieval operations.

    All retrieval MUST go through retrieve(). Direct calls to the underlying
    vector store or graph are forbidden outside this class.
    """

    def __init__(
        self,
        vector_store: Any | None = None,
        graph_store: Any | None = None,
    ) -> None:
        # Injected at runtime; None means no backend available (safe default).
        self._vector_store = vector_store
        self._graph_store = graph_store

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        """Execute a policy-enforced retrieval.

        Returns empty context on any policy violation (fail closed).
        """
        sec_ctx = request.sec_ctx
        workflow = sec_ctx.workflow
        tenant_id = sec_ctx.tenant_id
        principal_id = sec_ctx.canonical_principal_id
        correlation_id = sec_ctx.correlation_id

        # ── Step 0: Initialise provenance trace ───────────────────────────────
        trace = ContextTrace(
            correlation_id=correlation_id,
            workflow=workflow.value,
            principal_id=principal_id,
            query_intent="PENDING",
        )

        # ── Step 1: Query Intent Classification ──────────────────────────────
        intent = QueryIntentClassifier.classify(request.query)
        trace.query_intent = intent.value

        # ── Step 2: Block retrieval for sensitive intents on public workflows ─
        is_public_workflow = workflow in (WorkflowClass.PUBLIC_CHAT, WorkflowClass.PUBLIC_RESEARCH)
        if is_public_workflow and QueryIntentClassifier.retrieval_blocked_for_public(intent):
            RetrievalAuditLogger.log_intent_block(
                correlation_id=correlation_id,
                workflow=workflow.value,
                principal_id=principal_id,
                query_intent=intent.value,
            )
            trace.add_blocked(
                reason=f"intent_blocked: {intent}",
                source_type="query_intent_classifier",
                namespace="none",
            )
            return RetrievalResult(
                query_intent=intent,
                retrieval_blocked=True,
                blocked_reason=f"intent_blocked_for_public_workflow: {intent}",
                trace=trace,
            )

        # ── Step 3: Retrieval Policy Decision ────────────────────────────────
        policy = RetrievalPolicyEngine.get_policy(workflow)
        if not policy.retrieval_enabled:
            return RetrievalResult(
                query_intent=intent,
                retrieval_blocked=True,
                blocked_reason="retrieval_disabled_for_workflow",
                trace=trace,
            )

        # ── Step 4: Namespace Validation ─────────────────────────────────────
        allowed_namespaces = policy.allowed_namespaces
        effective_namespace: RetrievalNamespace

        if request.requested_namespace:
            try:
                requested_ns = RetrievalNamespace(request.requested_namespace)
            except ValueError:
                RetrievalAuditLogger.log_namespace_violation(
                    correlation_id=correlation_id,
                    workflow=workflow.value,
                    principal_id=principal_id,
                    requested_namespace=request.requested_namespace,
                    reason="unknown_namespace",
                )
                return RetrievalResult(
                    query_intent=intent,
                    retrieval_blocked=True,
                    blocked_reason=f"unknown_namespace: {request.requested_namespace}",
                )
            if requested_ns not in allowed_namespaces:
                RetrievalAuditLogger.log_namespace_violation(
                    correlation_id=correlation_id,
                    workflow=workflow.value,
                    principal_id=principal_id,
                    requested_namespace=request.requested_namespace,
                    reason="namespace_not_allowed_for_workflow",
                )
                trace.add_blocked(
                    reason=f"namespace_not_allowed: {request.requested_namespace}",
                    source_type="namespace_validator",
                    namespace=request.requested_namespace,
                )
                return RetrievalResult(
                    query_intent=intent,
                    retrieval_blocked=True,
                    blocked_reason=f"namespace_not_allowed: {request.requested_namespace}",
                    trace=trace,
                )
            effective_namespace = requested_ns
        else:
            # Default to first allowed namespace (lowest privilege)
            effective_namespace = next(iter(allowed_namespaces))

        # ── Step 5: Vector Search with pre-query metadata filter ─────────────
        raw_results: list[dict[str, Any]] = []
        if self._vector_store is not None:
            pre_filter = RetrievalFilter.build_vector_filter(workflow, tenant_id)
            try:
                raw_results = self._vector_store.query(
                    query_text=request.query,
                    n_results=request.top_k,
                    where=pre_filter,
                    namespace=effective_namespace.value,
                )
            except Exception:
                logger.exception("Vector store query failed; failing closed")
                raw_results = []

        # ── Step 6: Graph Search with namespace isolation ────────────────────
        graph_results: list[dict[str, Any]] = []
        if self._graph_store is not None and request.requested_graph_namespace:
            allowed_graphs = get_allowed_graph_namespaces(workflow)
            allowed_graph_values = {ns.value for ns in allowed_graphs}
            if request.requested_graph_namespace not in allowed_graph_values:
                RetrievalAuditLogger.log_namespace_violation(
                    correlation_id=correlation_id,
                    workflow=workflow.value,
                    principal_id=principal_id,
                    requested_namespace=request.requested_graph_namespace,
                    reason="graph_namespace_not_allowed",
                )
                # Fail closed — no graph results
            else:
                graph_filter = RetrievalFilter.build_graph_filter(workflow, tenant_id)
                try:
                    graph_results = self._graph_store.query(
                        query_text=request.query,
                        n_results=request.top_k,
                        where=graph_filter,
                        namespace=request.requested_graph_namespace,
                    )
                except Exception:
                    logger.exception("Graph store query failed; failing closed")
                    graph_results = []

        # ── Step 7: Post-retrieval Metadata Validation ───────────────────────
        all_raw = raw_results + graph_results
        cleared_items: list[ContextItem] = []
        blocked_count = 0
        classification_failures: list[str] = []

        for raw in all_raw:
            meta = raw.get("metadata", {})
            allowed, reason = RetrievalFilter.is_result_allowed(meta, workflow, tenant_id)
            if not allowed:
                blocked_count += 1
                classification_failures.append(reason)
                RetrievalAuditLogger.log_retrieval_blocked(
                    correlation_id=correlation_id,
                    workflow=workflow.value,
                    principal_id=principal_id,
                    blocked_source=meta.get("source_type", "UNKNOWN"),
                    reason=reason,
                    query_intent=intent.value,
                )
                trace.add_blocked(
                    reason=reason,
                    source_type=meta.get("source_type", "UNKNOWN"),
                    namespace=meta.get("namespace", ""),
                )
                continue

            # Build ContextItem
            content = raw.get("content", raw.get("document", ""))
            if not content:
                continue

            item = ContextItem(
                content=content,
                source=meta.get("source_type", "retrieved"),
                classification=meta.get("classification", Classification.PUBLIC.value),
                tenant_id=meta.get("tenant_id", tenant_id),
                allowed_workflows=frozenset({workflow}),
                trust_status="untrusted",
            )
            cleared_items.append(item)
            # Record provenance for every admitted item
            trace.add_entry(
                make_trace_entry_from_context_item(
                    item=item,
                    namespace=meta.get("namespace", effective_namespace.value),
                    injecting_component="RetrievalGateway",
                    policy_rule=f"workflow={workflow.value} classification={item.classification}",
                    workflow=workflow.value,
                )
            )

        # ── Step 8: Context Broker Validation ────────────────────────────────
        if cleared_items:
            try:
                ContextBroker.validate_context_for_workflow(sec_ctx, cleared_items)
            except Exception as exc:
                RetrievalAuditLogger.log_context_broker_rejection(
                    correlation_id=correlation_id,
                    workflow=workflow.value,
                    principal_id=principal_id,
                    reason=str(exc),
                )
                # Fail closed — reject all context, clear trace entries
                blocked_count += len(cleared_items)
                for entry in trace.entries:
                    trace.add_blocked(
                        reason=f"context_broker_rejection: {exc}",
                        source_type=entry.source_type,
                        namespace=entry.namespace,
                        document_id=entry.document_id,
                    )
                trace.entries.clear()
                cleared_items = []

        # ── Step 9: Audit ────────────────────────────────────────────────────
        audit_event = RetrievalAuditEvent(
            correlation_id=correlation_id,
            workflow=workflow.value,
            principal_id=principal_id,
            query_intent=intent.value,
            namespace_requested=effective_namespace.value,
            documents_returned=len(cleared_items),
            documents_blocked=blocked_count,
            classification_failures=classification_failures,
        )
        RetrievalAuditLogger.log_event(audit_event)

        logger.info("RETRIEVAL_TRACE %s", trace.summary_line())

        return RetrievalResult(
            context_items=cleared_items,
            query_intent=intent,
            retrieval_blocked=False,
            documents_blocked=blocked_count,
            trace=trace,
        )
