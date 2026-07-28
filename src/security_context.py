"""Immutable security context produced from verified backend identity and policy."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from fastapi import Request

from src.security import AuthenticationError, Principal
from src.workflow_policy import WorkflowClass, WorkflowPolicy, WorkflowPolicyEngine


@dataclass(frozen=True, slots=True)
class SecurityContext:
    """Immutable, server-side security context attached to an authorized request pipeline."""

    principal: Principal
    workflow_policy: WorkflowPolicy
    correlation_id: str

    @property
    def workflow(self) -> WorkflowClass:
        return self.workflow_policy.workflow

    @property
    def tenant_id(self) -> str:
        return self.principal.tenant_id

    @property
    def canonical_principal_id(self) -> str:
        return self.principal.canonical_id

    @property
    def user_id(self) -> str:
        return self.principal.user_id

    @property
    def role(self) -> str:
        return self.principal.role

    def is_tool_allowed(self, tool_name: str) -> bool:
        return tool_name in self.workflow_policy.allowed_tools

    def allow_internal_disclosure(self) -> bool:
        return self.workflow_policy.allow_internal_disclosure


class SecurityContextResolver:
    """Server-side resolver constructing immutable SecurityContext."""

    @staticmethod
    def resolve(
        principal: Principal | None,
        request: Request | None = None,
        requested_workflow: str | WorkflowClass | None = None,
        requested_intent: str | None = None,
    ) -> SecurityContext:
        if principal is None:
            from src.config import settings
            from src.security import ROLE_PERMISSIONS

            if settings.AUTH_MODE == "disabled":
                principal = Principal(
                    canonical_id="firebase:dev-firebase-uid",
                    provider="firebase",
                    provider_subject="dev-firebase-uid",
                    internal_user_id="dev-user-id",
                    tenant_id="development",
                    membership_id="dev-membership-id",
                    role="operator",
                    permissions=frozenset(ROLE_PERMISSIONS["operator"]),
                    email="dev@ephemeral-engine.local",
                )
            else:
                raise AuthenticationError("invalid_security_context_identity")

        correlation_id = (
            request.headers.get("x-correlation-id")
            if request and hasattr(request, "headers")
            else f"corr-{uuid4().hex[:12]}"
        )

        header_workflow = (
            request.headers.get("x-workflow-class")
            if request and hasattr(request, "headers")
            else None
        )
        target_workflow = requested_workflow or header_workflow

        policy = WorkflowPolicyEngine.resolve_workflow(
            principal=principal,
            requested_workflow=target_workflow,
            requested_intent=requested_intent,
        )

        return SecurityContext(
            principal=principal,
            workflow_policy=policy,
            correlation_id=correlation_id or f"corr-{uuid4().hex[:12]}",
        )
