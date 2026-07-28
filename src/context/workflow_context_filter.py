"""WorkflowContextFilter enforcing classification, source, and context boundary assertions per workflow."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.exceptions.security import ContextPolicyViolation
from src.workflow_policy import WorkflowClass

if TYPE_CHECKING:
    from src.context_broker import ContextItem
    from src.security_context import SecurityContext


class WorkflowContextFilter:
    """Validates context items against security context workflow boundaries."""

    FORBIDDEN_PUBLIC_CLASSIFICATIONS: frozenset[str] = frozenset({
        "INTERNAL",
        "CONFIDENTIAL",
        "RESTRICTED",
        "REPOSITORY",
        "MAINTENANCE",
        "WORKSPACE_FS",
        "MAINTENANCE_MEMORY",
    })

    ALLOWED_PUBLIC_CLASSIFICATIONS: frozenset[str] = frozenset({
        "PUBLIC",
        "USER_PROVIDED",
    })

    @classmethod
    def validate_and_filter_context(
        cls, sec_ctx: SecurityContext, context_items: list[ContextItem]
    ) -> list[ContextItem]:
        """Validate all context items for policy compliance under sec_ctx.workflow.

        Raises ContextPolicyViolation if forbidden classified context is present in PUBLIC_CHAT.
        """
        workflow = sec_ctx.workflow

        valid_items: list[ContextItem] = []
        for item in context_items:
            classification_upper = item.classification.upper()

            if workflow in (WorkflowClass.PUBLIC_CHAT, WorkflowClass.PUBLIC_RESEARCH):
                if (
                    classification_upper in cls.FORBIDDEN_PUBLIC_CLASSIFICATIONS
                    or classification_upper not in cls.ALLOWED_PUBLIC_CLASSIFICATIONS
                ):
                    raise ContextPolicyViolation(
                        f"Context classification '{item.classification}' from source '{item.source}' "
                        f"is strictly forbidden under workflow {workflow.value}",
                        correlation_id=sec_ctx.correlation_id,
                    )
            valid_items.append(item)

        return valid_items
