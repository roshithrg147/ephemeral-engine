"""Registry of agent capability definitions and workflow authorization metadata."""

from __future__ import annotations

from dataclasses import dataclass

from src.workflow_policy import WorkflowClass


@dataclass(frozen=True, slots=True)
class CapabilityDefinition:
    name: str
    description: str
    allowed_workflows: frozenset[WorkflowClass]


ALL_CAPABILITIES: dict[str, CapabilityDefinition] = {
    "conversation": CapabilityDefinition(
        name="conversation",
        description="General conversational interaction and concept explanation",
        allowed_workflows=frozenset({
            WorkflowClass.PUBLIC_CHAT,
            WorkflowClass.PUBLIC_RESEARCH,
            WorkflowClass.OPERATOR_READ,
            WorkflowClass.MAINTENANCE,
            WorkflowClass.PRIVILEGED_OPERATION,
        }),
    ),
    "general_reasoning": CapabilityDefinition(
        name="general_reasoning",
        description="General reasoning and analysis based on user-provided input",
        allowed_workflows=frozenset({
            WorkflowClass.PUBLIC_CHAT,
            WorkflowClass.PUBLIC_RESEARCH,
            WorkflowClass.OPERATOR_READ,
            WorkflowClass.MAINTENANCE,
            WorkflowClass.PRIVILEGED_OPERATION,
        }),
    ),
    "list_files": CapabilityDefinition(
        name="list_files",
        description="List files in session sandbox workspace",
        allowed_workflows=frozenset({
            WorkflowClass.OPERATOR_READ,
            WorkflowClass.MAINTENANCE,
            WorkflowClass.PRIVILEGED_OPERATION,
        }),
    ),
    "read_file": CapabilityDefinition(
        name="read_file",
        description="Read file content from session sandbox workspace",
        allowed_workflows=frozenset({
            WorkflowClass.OPERATOR_READ,
            WorkflowClass.MAINTENANCE,
            WorkflowClass.PRIVILEGED_OPERATION,
        }),
    ),
    "save_file": CapabilityDefinition(
        name="save_file",
        description="Write text file to session sandbox workspace",
        allowed_workflows=frozenset({
            WorkflowClass.MAINTENANCE,
            WorkflowClass.PRIVILEGED_OPERATION,
        }),
    ),
    "search_repository": CapabilityDefinition(
        name="search_repository",
        description="Perform AST/vector repository search",
        allowed_workflows=frozenset({
            WorkflowClass.MAINTENANCE,
            WorkflowClass.PRIVILEGED_OPERATION,
        }),
    ),
    "run_tests": CapabilityDefinition(
        name="run_tests",
        description="Execute unit and integration tests",
        allowed_workflows=frozenset({
            WorkflowClass.MAINTENANCE,
            WorkflowClass.PRIVILEGED_OPERATION,
        }),
    ),
    "run_command": CapabilityDefinition(
        name="run_command",
        description="Execute administrative shell command",
        allowed_workflows=frozenset({
            WorkflowClass.PRIVILEGED_OPERATION,
        }),
    ),
    "burn_session": CapabilityDefinition(
        name="burn_session",
        description="Permanently destroy session sandbox filesystem",
        allowed_workflows=frozenset({
            WorkflowClass.PRIVILEGED_OPERATION,
        }),
    ),
}
