"""Operator read workflow policy providing read-only system access."""

from __future__ import annotations

from dataclasses import dataclass

from src.workflow_policy import WorkflowClass, WorkflowPolicy


@dataclass(frozen=True, slots=True)
class OperatorPolicy:
    """Policy governing OPERATOR_READ workflow."""

    @staticmethod
    def get_policy() -> WorkflowPolicy:
        return WorkflowPolicy(
            workflow=WorkflowClass.OPERATOR_READ,
            allowed_tools=frozenset({"conversation", "list_files", "read_file"}),
            allowed_context_classifications=frozenset({"PUBLIC", "USER_PROVIDED", "INTERNAL"}),
            memory_namespace="operator",
            allow_internal_disclosure=False,
            allow_code_execution=False,
            approval_required=False,
        )
