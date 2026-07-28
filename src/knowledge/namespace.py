"""Retrieval and graph namespace definitions for workflow isolation."""

from __future__ import annotations

from enum import StrEnum

from src.workflow_policy import WorkflowClass


class RetrievalNamespace(StrEnum):
    """Vector-store namespaces, one per workflow boundary."""

    PUBLIC = "public"
    OPERATOR = "operator"
    MAINTENANCE = "maintenance"
    SECURITY = "security"


class GraphNamespace(StrEnum):
    """Knowledge-graph namespaces, one per workflow boundary."""

    PUBLIC_GRAPH = "public_graph"
    OPERATOR_GRAPH = "operator_graph"
    MAINTENANCE_GRAPH = "maintenance_graph"
    SECURITY_GRAPH = "security_graph"


# Workflow -> allowed retrieval namespaces (read access only).
WORKFLOW_RETRIEVAL_NAMESPACES: dict[WorkflowClass, frozenset[RetrievalNamespace]] = {
    WorkflowClass.PUBLIC_CHAT: frozenset({RetrievalNamespace.PUBLIC}),
    WorkflowClass.PUBLIC_RESEARCH: frozenset({RetrievalNamespace.PUBLIC}),
    WorkflowClass.OPERATOR_READ: frozenset({RetrievalNamespace.OPERATOR}),
    WorkflowClass.MAINTENANCE: frozenset({RetrievalNamespace.MAINTENANCE}),
    WorkflowClass.PRIVILEGED_OPERATION: frozenset(
        {RetrievalNamespace.MAINTENANCE, RetrievalNamespace.OPERATOR}
    ),
}

# Workflow -> allowed graph namespaces.
WORKFLOW_GRAPH_NAMESPACES: dict[WorkflowClass, frozenset[GraphNamespace]] = {
    WorkflowClass.PUBLIC_CHAT: frozenset({GraphNamespace.PUBLIC_GRAPH}),
    WorkflowClass.PUBLIC_RESEARCH: frozenset({GraphNamespace.PUBLIC_GRAPH}),
    WorkflowClass.OPERATOR_READ: frozenset({GraphNamespace.OPERATOR_GRAPH}),
    WorkflowClass.MAINTENANCE: frozenset({GraphNamespace.MAINTENANCE_GRAPH}),
    WorkflowClass.PRIVILEGED_OPERATION: frozenset(
        {GraphNamespace.MAINTENANCE_GRAPH, GraphNamespace.OPERATOR_GRAPH}
    ),
}

# Security graph is NEVER exposed to any normal workflow.
_SECURITY_GRAPH_WORKFLOWS: frozenset[WorkflowClass] = frozenset()


def get_allowed_retrieval_namespaces(workflow: WorkflowClass) -> frozenset[RetrievalNamespace]:
    return WORKFLOW_RETRIEVAL_NAMESPACES.get(workflow, frozenset({RetrievalNamespace.PUBLIC}))


def get_allowed_graph_namespaces(workflow: WorkflowClass) -> frozenset[GraphNamespace]:
    return WORKFLOW_GRAPH_NAMESPACES.get(workflow, frozenset({GraphNamespace.PUBLIC_GRAPH}))
