"""Privileged admin workflow policy authorizing full administrative actions and tool execution."""

from __future__ import annotations

from dataclasses import dataclass

from src.workflow_policy import WorkflowClass, WorkflowPolicy


@dataclass(frozen=True, slots=True)
class PrivilegedPolicy:
    """Policy governing PRIVILEGED_ADMIN workflow."""

    @staticmethod
    def get_policy() -> WorkflowPolicy:
        return WorkflowPolicy(
            workflow=WorkflowClass.PRIVILEGED_ADMIN,
            allowed_tools=frozenset({
                "conversation",
                "list_files",
                "read_file",
                "save_file",
                "run_command",
                "burn_session",
            }),
            allowed_context_classifications=frozenset({
                "PUBLIC",
                "USER_PROVIDED",
                "INTERNAL",
                "CONFIDENTIAL",
                "RESTRICTED",
                "REPOSITORY",
                "MAINTENANCE",
                "WORKSPACE_FS",
                "MAINTENANCE_MEMORY",
            }),
            memory_namespace="privileged",
            allow_internal_disclosure=True,
            allow_code_execution=True,
            approval_required=True,
        )
