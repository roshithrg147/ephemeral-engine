"""Memory gateway enforcing namespace boundaries, tenant isolation, and memory payload governance."""

from __future__ import annotations

import logging
import re
from typing import Any

from src.security_context import SecurityContext
from src.workflow_policy import WorkflowClass

logger = logging.getLogger("SC-EVM.MemoryGateway")

_FILE_INVENTORY_PATTERN = re.compile(
    r"(?i)(\b(src/|engine-dashboard/|app/|lib/|\.py|\.tsx|\.ts|\.json|\.env)\b|file inventory|directory structure)",
    re.IGNORECASE,
)


class MemoryGateway:
    """Gateway controlling memory reads and writes per security context and namespace boundary."""

    @staticmethod
    def get_namespace(sec_ctx: SecurityContext) -> str:
        return sec_ctx.workflow_policy.memory_namespace

    @classmethod
    def sanitize_remember_facts(cls, sec_ctx: SecurityContext, facts: list[str]) -> list[str]:
        """Sanitize facts before storing into long-term memory."""
        if not facts:
            return []

        clean_facts: list[str] = []
        for fact in facts:
            if not isinstance(fact, str) or not fact.strip():
                continue

            cleaned = fact.strip()

            # Rule: Under PUBLIC_CHAT or PUBLIC_RESEARCH, block file paths/inventories from public memory
            if sec_ctx.workflow in (WorkflowClass.PUBLIC_CHAT, WorkflowClass.PUBLIC_RESEARCH):
                if _FILE_INVENTORY_PATTERN.search(cleaned):
                    logger.warning(
                        "Blocked internal repository inventory from public memory storage",
                        extra={"fact_snippet": cleaned[:40], "user_id": sec_ctx.user_id},
                    )
                    continue

            clean_facts.append(cleaned)

        return clean_facts

    @classmethod
    def filter_memory_for_read(
        cls, sec_ctx: SecurityContext, memory_items: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Filter retrieved memory items to match active security context namespace and tenant."""
        target_namespace = cls.get_namespace(sec_ctx)
        filtered: list[dict[str, Any]] = []

        for item in memory_items:
            item_tenant = item.get("tenant_id", sec_ctx.tenant_id)
            item_namespace = item.get("namespace", "public")

            if item_tenant != sec_ctx.tenant_id:
                continue

            # In PUBLIC_CHAT / PUBLIC_RESEARCH, strictly block maintenance/operator/privileged/security-audit namespace memories
            if sec_ctx.workflow in (WorkflowClass.PUBLIC_CHAT, WorkflowClass.PUBLIC_RESEARCH):
                if item_namespace != "public" or item_namespace.startswith(("maintenance", "operator", "privileged", "security-audit")):
                    logger.warning(
                        "Denied non-public memory namespace access under public workflow",
                        extra={"requested_namespace": item_namespace, "workflow": sec_ctx.workflow.value},
                    )
                    continue

            if item_namespace == target_namespace or item_namespace == "public":
                filtered.append(item)

        return filtered
