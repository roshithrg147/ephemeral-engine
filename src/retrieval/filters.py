"""Vector database metadata filters — pre-query filters applied before retrieval executes."""

from __future__ import annotations

from typing import Any

from src.retrieval.policy import RetrievalPolicyEngine
from src.workflow_policy import WorkflowClass


class RetrievalFilter:
    """Builds metadata filter dicts for vector store queries.

    Filters are applied AT QUERY TIME — never retrieve-then-filter.
    """

    @classmethod
    def build_vector_filter(cls, workflow: WorkflowClass, tenant_id: str) -> dict[str, Any]:
        """Return a ChromaDB-compatible where-clause filter for the workflow.

        Enforces:
        - Only allowed classifications
        - Only allowed workflows
        - Tenant isolation
        """
        policy = RetrievalPolicyEngine.get_policy(workflow)
        allowed_classifications = [c.value for c in policy.allowed_classifications]
        allowed_namespaces = [ns.value for ns in policy.allowed_namespaces]

        return {
            "$and": [
                {"classification": {"$in": allowed_classifications}},
                {"allowed_workflows": {"$contains": workflow.value}},
                {"namespace": {"$in": allowed_namespaces}},
                {"tenant_id": {"$in": [tenant_id, "global"]}},
            ]
        }

    @classmethod
    def build_graph_filter(cls, workflow: WorkflowClass, tenant_id: str) -> dict[str, Any]:
        """Return a filter for knowledge graph queries."""
        from src.knowledge.namespace import get_allowed_graph_namespaces

        allowed_graphs = [ns.value for ns in get_allowed_graph_namespaces(workflow)]
        return {
            "graph_namespace": {"$in": allowed_graphs},
            "tenant_id": {"$in": [tenant_id, "global"]},
        }

    @classmethod
    def is_result_allowed(
        cls,
        result_metadata: dict[str, Any],
        workflow: WorkflowClass,
        tenant_id: str,
    ) -> tuple[bool, str]:
        """Post-retrieval validation of a single result's metadata.

        Defense-in-depth: even if the pre-query filter fails, this blocks leakage.
        """
        policy = RetrievalPolicyEngine.get_policy(workflow)
        allowed_classifications = {c.value for c in policy.allowed_classifications}
        allowed_namespaces = {ns.value for ns in policy.allowed_namespaces}

        # Tenant check
        doc_tenant = result_metadata.get("tenant_id", "")
        if doc_tenant not in (tenant_id, "global"):
            return False, f"tenant_mismatch: doc={doc_tenant}"

        # Classification check
        doc_classification = result_metadata.get("classification", "INTERNAL")
        if doc_classification not in allowed_classifications:
            return False, f"classification_forbidden: {doc_classification}"

        # Namespace check
        doc_namespace = result_metadata.get("namespace", "")
        if doc_namespace not in allowed_namespaces:
            return False, f"namespace_forbidden: {doc_namespace}"

        # Workflow authorization check
        doc_allowed_workflows = result_metadata.get("allowed_workflows", [])
        if isinstance(doc_allowed_workflows, str):
            doc_allowed_workflows = [doc_allowed_workflows]
        if workflow.value not in doc_allowed_workflows:
            return False, f"workflow_not_in_allowed: {workflow}"

        return True, "ok"
