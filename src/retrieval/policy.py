"""Retrieval policy — per-workflow rules for what may be retrieved."""

from __future__ import annotations

from dataclasses import dataclass

from src.knowledge.metadata import INTERNAL_CLASSIFICATIONS, Classification
from src.knowledge.namespace import RetrievalNamespace
from src.workflow_policy import WorkflowClass


@dataclass(frozen=True, slots=True)
class RetrievalPolicy:
    """Immutable retrieval policy for a workflow."""

    workflow: WorkflowClass
    allowed_namespaces: frozenset[RetrievalNamespace]
    allowed_classifications: frozenset[Classification]
    forbidden_classifications: frozenset[Classification]
    requires_approval: bool
    retrieval_enabled: bool


# Canonical per-workflow retrieval policies.
_RETRIEVAL_POLICIES: dict[WorkflowClass, RetrievalPolicy] = {
    WorkflowClass.PUBLIC_CHAT: RetrievalPolicy(
        workflow=WorkflowClass.PUBLIC_CHAT,
        allowed_namespaces=frozenset({RetrievalNamespace.PUBLIC}),
        allowed_classifications=frozenset({Classification.PUBLIC, Classification.USER_PROVIDED}),
        forbidden_classifications=INTERNAL_CLASSIFICATIONS,
        requires_approval=False,
        retrieval_enabled=True,
    ),
    WorkflowClass.PUBLIC_RESEARCH: RetrievalPolicy(
        workflow=WorkflowClass.PUBLIC_RESEARCH,
        allowed_namespaces=frozenset({RetrievalNamespace.PUBLIC}),
        allowed_classifications=frozenset({Classification.PUBLIC, Classification.USER_PROVIDED}),
        forbidden_classifications=INTERNAL_CLASSIFICATIONS,
        requires_approval=False,
        retrieval_enabled=True,
    ),
    WorkflowClass.OPERATOR_READ: RetrievalPolicy(
        workflow=WorkflowClass.OPERATOR_READ,
        allowed_namespaces=frozenset({RetrievalNamespace.OPERATOR}),
        allowed_classifications=frozenset({Classification.CONFIDENTIAL}),
        forbidden_classifications=frozenset(
            {Classification.INTERNAL, Classification.REPOSITORY, Classification.WORKSPACE}
        ),
        requires_approval=False,
        retrieval_enabled=True,
    ),
    WorkflowClass.MAINTENANCE: RetrievalPolicy(
        workflow=WorkflowClass.MAINTENANCE,
        allowed_namespaces=frozenset({RetrievalNamespace.MAINTENANCE}),
        allowed_classifications=frozenset(
            {
                Classification.INTERNAL,
                Classification.REPOSITORY,
                Classification.WORKSPACE,
                Classification.MAINTENANCE_MEMORY,
            }
        ),
        forbidden_classifications=frozenset(),
        requires_approval=False,
        retrieval_enabled=True,
    ),
    WorkflowClass.PRIVILEGED_OPERATION: RetrievalPolicy(
        workflow=WorkflowClass.PRIVILEGED_OPERATION,
        allowed_namespaces=frozenset({RetrievalNamespace.MAINTENANCE, RetrievalNamespace.OPERATOR}),
        allowed_classifications=frozenset(
            {
                Classification.INTERNAL,
                Classification.REPOSITORY,
                Classification.WORKSPACE,
                Classification.MAINTENANCE_MEMORY,
                Classification.CONFIDENTIAL,
            }
        ),
        forbidden_classifications=frozenset(),
        requires_approval=True,
        retrieval_enabled=True,
    ),
}


class RetrievalPolicyEngine:
    """Resolves and enforces retrieval policy for a workflow."""

    @staticmethod
    def get_policy(workflow: WorkflowClass) -> RetrievalPolicy:
        """Return the retrieval policy for the workflow. Fails closed to PUBLIC_CHAT policy."""
        return _RETRIEVAL_POLICIES.get(workflow, _RETRIEVAL_POLICIES[WorkflowClass.PUBLIC_CHAT])

    @staticmethod
    def is_classification_allowed(
        workflow: WorkflowClass,
        classification: Classification,
    ) -> bool:
        policy = RetrievalPolicyEngine.get_policy(workflow)
        if classification in policy.forbidden_classifications:
            return False
        return classification in policy.allowed_classifications

    @staticmethod
    def is_namespace_allowed(
        workflow: WorkflowClass,
        namespace: RetrievalNamespace,
    ) -> bool:
        policy = RetrievalPolicyEngine.get_policy(workflow)
        return namespace in policy.allowed_namespaces
