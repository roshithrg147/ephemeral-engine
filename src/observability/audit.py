"""Reliability and security audit event logger."""

from __future__ import annotations

import json
import logging
from typing import Any

from src.security_audit import SecurityAuditService
from src.security_context import SecurityContext
from src.telemetry_sink import log_error

logger = logging.getLogger("SC-EVM.OBSERVABILITY.AUDIT")


class ReliabilityAuditService:
    """Records security and reliability decisions without disclosing secrets or prompts."""

    @staticmethod
    def log_event(
        sec_ctx: SecurityContext,
        event_name: str,
        outcome: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Record a structured reliability/security audit event."""
        meta = details or {}
        SecurityAuditService.log_decision(sec_ctx, event_name, outcome, meta)

        if outcome in ("FAILED", "DENIED", "ERROR"):
            log_error(
                f"audit.{event_name}",
                json.dumps(
                    {
                        "correlation_id": sec_ctx.correlation_id,
                        "tenant_id": sec_ctx.tenant_id,
                        "user_id": sec_ctx.user_id,
                        "event_name": event_name,
                        "outcome": outcome,
                    }
                ),
            )
