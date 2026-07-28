"""Maintenance workflow policy authorizing repository tools, internal context, and maintenance memory."""

from __future__ import annotations

from dataclasses import dataclass

from src.workflow_policy import WorkflowClass, WorkflowPolicy


@dataclass(frozen=True, slots=True)
class MaintenancePolicy:
    """Policy governing MAINTENANCE workflow."""

    @staticmethod
    def get_policy() -> WorkflowPolicy:
        return WorkflowPolicy(
            workflow=WorkflowClass.MAINTENANCE,
            allowed_tools=frozenset({
                "conversation",
                "list_files",
                "read_file",
                "save_file",
                "search_repository",
                "run_tests",
            }),
            allowed_context_classifications=frozenset({
                "PUBLIC",
                "USER_PROVIDED",
                "REPOSITORY",
                "MAINTENANCE",
                "INTERNAL",
                "WORKSPACE_FS",
                "MAINTENANCE_MEMORY",
            }),
            memory_namespace="maintenance",
            allow_internal_disclosure=True,
            allow_code_execution=True,
            approval_required=False,
        )
