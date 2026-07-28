"""Workflow classification, security policies, and workflow policy engine."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from src.security import Principal


class WorkflowClass(StrEnum):
    PUBLIC_CHAT = "PUBLIC_CHAT"
    PUBLIC_RESEARCH = "PUBLIC_RESEARCH"
    OPERATOR_READ = "OPERATOR_READ"
    MAINTENANCE = "MAINTENANCE"
    PRIVILEGED_OPERATION = "PRIVILEGED_OPERATION"


@dataclass(frozen=True, slots=True)
class WorkflowPolicy:
    """Policy definition for an authorized workflow execution boundary."""

    workflow: WorkflowClass
    allowed_roles: frozenset[str]
    allowed_context_sources: frozenset[str]
    allowed_tools: frozenset[str]
    allowed_resources: frozenset[str]
    allowed_effects: frozenset[str]
    approval_required: bool
    memory_namespace: str
    credential_scope: str
    max_duration_seconds: int
    allow_internal_disclosure: bool


WORKFLOW_POLICIES: dict[WorkflowClass, WorkflowPolicy] = {
    WorkflowClass.PUBLIC_CHAT: WorkflowPolicy(
        workflow=WorkflowClass.PUBLIC_CHAT,
        allowed_roles=frozenset({"viewer", "operator", "admin"}),
        allowed_context_sources=frozenset({"public_model_knowledge", "user_prompt", "public_memory"}),
        allowed_tools=frozenset({"none"}),
        allowed_resources=frozenset({"public"}),
        allowed_effects=frozenset({"read_public"}),
        approval_required=False,
        memory_namespace="public",
        credential_scope="none",
        max_duration_seconds=30,
        allow_internal_disclosure=False,
    ),
    WorkflowClass.PUBLIC_RESEARCH: WorkflowPolicy(
        workflow=WorkflowClass.PUBLIC_RESEARCH,
        allowed_roles=frozenset({"viewer", "operator", "admin"}),
        allowed_context_sources=frozenset({"public_model_knowledge", "public_web", "arxiv", "pubmed"}),
        allowed_tools=frozenset({"none", "search_public"}),
        allowed_resources=frozenset({"public_web"}),
        allowed_effects=frozenset({"read_public"}),
        approval_required=False,
        memory_namespace="public",
        credential_scope="none",
        max_duration_seconds=60,
        allow_internal_disclosure=False,
    ),
    WorkflowClass.OPERATOR_READ: WorkflowPolicy(
        workflow=WorkflowClass.OPERATOR_READ,
        allowed_roles=frozenset({"operator", "admin"}),
        allowed_context_sources=frozenset({"operational_metrics", "session_status", "system_health"}),
        allowed_tools=frozenset({"none", "get_metrics", "list_sessions"}),
        allowed_resources=frozenset({"telemetry", "session_metadata"}),
        allowed_effects=frozenset({"read_operational"}),
        approval_required=False,
        memory_namespace="operator",
        credential_scope="read_only",
        max_duration_seconds=60,
        allow_internal_disclosure=False,
    ),
    WorkflowClass.MAINTENANCE: WorkflowPolicy(
        workflow=WorkflowClass.MAINTENANCE,
        allowed_roles=frozenset({"operator", "admin"}),
        allowed_context_sources=frozenset({"workspace_fs", "vector_memory", "session_history"}),
        allowed_tools=frozenset({"none", "list_files", "read_file", "save_file"}),
        allowed_resources=frozenset({"session_sandbox", "authorized_workspace"}),
        allowed_effects=frozenset({"read_sandbox", "write_sandbox"}),
        approval_required=False,
        memory_namespace="maintenance",
        credential_scope="workspace_scoped",
        max_duration_seconds=300,
        allow_internal_disclosure=True,
    ),
    WorkflowClass.PRIVILEGED_OPERATION: WorkflowPolicy(
        workflow=WorkflowClass.PRIVILEGED_OPERATION,
        allowed_roles=frozenset({"admin"}),
        allowed_context_sources=frozenset({"workspace_fs", "system_config"}),
        allowed_tools=frozenset({"none", "list_files", "read_file", "save_file", "run_command", "burn_session"}),
        allowed_resources=frozenset({"system", "session_sandbox"}),
        allowed_effects=frozenset({"destructive", "execute_command"}),
        approval_required=True,
        memory_namespace="security_audit",
        credential_scope="admin_scoped",
        max_duration_seconds=300,
        allow_internal_disclosure=True,
    ),
}


class WorkflowPolicyEngine:
    """Server-side policy engine selecting and enforcing authorized workflow boundaries."""

    @staticmethod
    def get_policy(workflow: str | WorkflowClass) -> WorkflowPolicy:
        if isinstance(workflow, str):
            try:
                workflow = WorkflowClass(workflow.upper())
            except ValueError:
                return WORKFLOW_POLICIES[WorkflowClass.PUBLIC_CHAT]
        return WORKFLOW_POLICIES.get(workflow, WORKFLOW_POLICIES[WorkflowClass.PUBLIC_CHAT])

    @staticmethod
    def resolve_workflow(
        principal: Principal,
        requested_workflow: str | WorkflowClass | None = None,
        requested_intent: str | None = None,
    ) -> WorkflowPolicy:
        """Select the stricter authorized workflow. Never allow model elevation."""
        target: WorkflowClass = WorkflowClass.PUBLIC_CHAT

        if requested_workflow is not None:
            if isinstance(requested_workflow, str):
                try:
                    target = WorkflowClass(requested_workflow.upper())
                except ValueError:
                    target = WorkflowClass.PUBLIC_CHAT
            else:
                target = requested_workflow
        elif requested_intent in ("file", "code_edit", "maintenance"):
            target = WorkflowClass.MAINTENANCE
        elif requested_intent in ("command", "burn", "privileged"):
            target = WorkflowClass.PRIVILEGED_OPERATION
        elif requested_intent in ("metrics", "status"):
            target = WorkflowClass.OPERATOR_READ
        elif requested_intent in ("research", "web"):
            target = WorkflowClass.PUBLIC_RESEARCH

        policy = WORKFLOW_POLICIES.get(target, WORKFLOW_POLICIES[WorkflowClass.PUBLIC_CHAT])

        # Security check: Validate principal role against allowed roles for policy
        if principal.role not in policy.allowed_roles:
            # Fall back to PUBLIC_CHAT if role is not allowed for requested workflow
            return WORKFLOW_POLICIES[WorkflowClass.PUBLIC_CHAT]

        # Security check: Maintenance or Privileged Operations require operator/admin role
        if policy.workflow in (WorkflowClass.MAINTENANCE, WorkflowClass.PRIVILEGED_OPERATION):
            if not (principal.role in ("operator", "admin") or principal.has_permission("session:create")):
                return WORKFLOW_POLICIES[WorkflowClass.PUBLIC_CHAT]

        return policy
