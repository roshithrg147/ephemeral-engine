"""Metadata validator — enforces classification integrity before retrieval results enter context."""

from __future__ import annotations

import logging

from src.knowledge.metadata import (
    INTERNAL_CLASSIFICATIONS,
    DocumentMetadata,
    classify_source,
)
from src.knowledge.namespace import (
    get_allowed_graph_namespaces,
    get_allowed_retrieval_namespaces,
)
from src.workflow_policy import WorkflowClass

logger = logging.getLogger("SC-EVM.MetadataValidator")


class MetadataValidator:
    """Validates document metadata against workflow policy before retrieval results are used.

    Invariants enforced:
    - INTERNAL sources cannot be downgraded to PUBLIC.
    - Namespace must be within workflow-allowed namespaces.
    - Tenant isolation: document tenant must match requesting tenant.
    - Workflow must be in document's allowed_workflows.
    """

    @classmethod
    def validate(
        cls,
        metadata: DocumentMetadata,
        workflow: WorkflowClass,
        requesting_tenant_id: str,
    ) -> tuple[bool, str]:
        """Return (allowed, reason). Fails closed on any violation."""
        # 1. Tenant isolation
        if metadata.tenant_id != "global" and metadata.tenant_id != requesting_tenant_id:
            return False, f"tenant_mismatch: doc={metadata.tenant_id} req={requesting_tenant_id}"

        # 2. Source classification override — INTERNAL sources always INTERNAL
        mandatory_classification = classify_source(metadata.source_type)
        effective_classification = metadata.classification
        if (
            mandatory_classification in INTERNAL_CLASSIFICATIONS
            and effective_classification not in INTERNAL_CLASSIFICATIONS
        ):
            logger.warning(
                "Classification downgrade attempt blocked: doc=%s source=%s claimed=%s",
                metadata.document_id,
                metadata.source_type,
                effective_classification,
            )
            effective_classification = mandatory_classification

        # 3. Workflow allowed for this document
        if workflow.value not in metadata.allowed_workflows:
            return False, f"workflow_not_authorized: workflow={workflow} doc={metadata.document_id}"

        # 4. PUBLIC_CHAT cannot receive INTERNAL-classified documents
        if workflow == WorkflowClass.PUBLIC_CHAT and effective_classification in INTERNAL_CLASSIFICATIONS:
            return False, f"classification_forbidden: workflow=PUBLIC_CHAT classification={effective_classification}"

        # 5. PUBLIC_RESEARCH cannot receive INTERNAL-classified documents
        if workflow == WorkflowClass.PUBLIC_RESEARCH and effective_classification in INTERNAL_CLASSIFICATIONS:
            return False, f"classification_forbidden: workflow=PUBLIC_RESEARCH classification={effective_classification}"

        return True, "ok"

    @classmethod
    def validate_namespace(
        cls,
        namespace: str,
        workflow: WorkflowClass,
    ) -> tuple[bool, str]:
        """Validate that a retrieval namespace is allowed for the workflow."""
        allowed = get_allowed_retrieval_namespaces(workflow)
        allowed_values = {ns.value for ns in allowed}
        if namespace not in allowed_values:
            return False, f"namespace_not_allowed: namespace={namespace} workflow={workflow}"
        return True, "ok"

    @classmethod
    def validate_graph_namespace(
        cls,
        graph_namespace: str,
        workflow: WorkflowClass,
    ) -> tuple[bool, str]:
        """Validate that a graph namespace is allowed for the workflow."""
        allowed = get_allowed_graph_namespaces(workflow)
        allowed_values = {ns.value for ns in allowed}
        if graph_namespace not in allowed_values:
            return False, f"graph_namespace_not_allowed: graph={graph_namespace} workflow={workflow}"
        return True, "ok"
