"""Structured security audit service recording security context, policy decisions, and tool checks."""

from __future__ import annotations

import logging
from typing import Any

from src.security_context import SecurityContext

logger = logging.getLogger("SC-EVM.SecurityAudit")


class SecurityAuditService:
    """Audit logger recording security decisions without leaking sensitive payloads."""

    @classmethod
    def log_decision(
        cls,
        sec_ctx: SecurityContext,
        action_type: str,
        decision: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        metadata = metadata or {}
        sanitized_meta = {
            k: v
            for k, v in metadata.items()
            if k not in ("secret", "key", "password", "token", "file_content", "prompt")
        }

        audit_entry = {
            "correlation_id": sec_ctx.correlation_id,
            "tenant_id": sec_ctx.tenant_id,
            "user_id": sec_ctx.user_id,
            "role": sec_ctx.role,
            "workflow": sec_ctx.workflow.value,
            "action_type": action_type,
            "decision": decision,
            "metadata": sanitized_meta,
        }

        logger.info("SECURITY_AUDIT: %s", audit_entry)
