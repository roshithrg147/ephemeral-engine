"""Public chat workflow policy restricting capability manifest, context, and disclosure boundaries."""

from __future__ import annotations

from dataclasses import dataclass

from src.workflow_policy import WorkflowClass, WorkflowPolicy


@dataclass(frozen=True, slots=True)
class PublicChatPolicy:
    """Policy governing PUBLIC_CHAT and PUBLIC_RESEARCH workflows."""

    @staticmethod
    def get_policy(workflow: WorkflowClass = WorkflowClass.PUBLIC_CHAT) -> WorkflowPolicy:
        return WorkflowPolicy(
            workflow=workflow,
            allowed_tools=frozenset({"conversation"}),
            allowed_context_classifications=frozenset({"PUBLIC", "USER_PROVIDED"}),
            memory_namespace="public",
            allow_internal_disclosure=False,
            allow_code_execution=False,
            approval_required=False,
        )
