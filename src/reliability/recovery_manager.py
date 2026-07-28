"""Session recovery manager for self-healing session state contexts."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from src.memory import SessionRecord
from src.observability.audit import ReliabilityAuditService
from src.security_context import SecurityContext

logger = logging.getLogger("SC-EVM.RELIABILITY.RECOVERY")


class RecoveryManager:
    """Detects invalid or missing session states and safely attempts self-healing recovery."""

    _recovery_locks: dict[str, asyncio.Lock] = {}

    @classmethod
    async def reinitialize_session(
        cls,
        session: SessionRecord | None,
        session_id: str,
        *,
        tenant_id: str | None = None,
        owner_subject: str | None = None,
        workflow: str | None = None,
        correlation_id: str | None = None,
        sec_ctx: SecurityContext | None = None,
    ) -> SessionRecord:
        """Idempotent self-healing session context reinitialization.

        Guarantees:
        - Validates tenant and owner boundaries. Mismatches raise AuthorizationFailure (recovery denied).
        - Idempotent: checks per-session recovery lock to avoid duplicate audit logs under concurrent requests.
        - Policy validation: does not recreate arbitrary sessions if caller lacks authenticated identity claims.
        - Rebinds typed security_context field on SessionRecord.
        - Emits structured SESSION_RECOVERY audit events.
        """
        lock = cls._recovery_locks.setdefault(session_id, asyncio.Lock())
        async with lock:
            from src.exceptions.security import SessionRecoveryDenied
            from src.security.principal import IdentityCompatibilityResolver

            effective_tenant = tenant_id or (sec_ctx.tenant_id if sec_ctx else "development")
            effective_corr_id = (
                correlation_id or (sec_ctx.correlation_id if sec_ctx else "corr-recovery")
            )
            requested_owner_raw = owner_subject or (
                sec_ctx.canonical_principal_id if sec_ctx else "firebase:development"
            )
            requested_owner_canonical = (
                sec_ctx.canonical_principal_id
                if sec_ctx
                else IdentityCompatibilityResolver.normalize_owner_subject(
                    requested_owner_raw,
                    correlation_id=effective_corr_id,
                )
            )

            if session is not None:
                # 1. Tenant boundary validation
                if tenant_id is not None and session.tenant_id != tenant_id:
                    if sec_ctx:
                        ReliabilityAuditService.log_event(
                            sec_ctx,
                            event_name="SESSION_RECOVERY_DENIED",
                            outcome="DENIED",
                            details={
                                "session_id": session_id,
                                "reason": "tenant_mismatch",
                                "existing_tenant": session.tenant_id,
                                "requested_tenant": tenant_id,
                                "correlation_id": effective_corr_id,
                            },
                        )
                    raise SessionRecoveryDenied(
                        reason="Tenant mismatch",
                        correlation_id=effective_corr_id,
                    )

                # 2. Owner boundary validation with canonical identity normalization
                existing_owner_canonical = IdentityCompatibilityResolver.normalize_owner_subject(
                    session.owner_subject,
                    sec_ctx=sec_ctx,
                    correlation_id=effective_corr_id,
                )

                if existing_owner_canonical != requested_owner_canonical:
                    if sec_ctx:
                        ReliabilityAuditService.log_event(
                            sec_ctx,
                            event_name="SESSION_RECOVERY_DENIED",
                            outcome="DENIED",
                            details={
                                "session_id": session_id,
                                "reason": "owner_mismatch",
                                "existing_owner": session.owner_subject,
                                "existing_owner_canonical": existing_owner_canonical,
                                "requested_owner": requested_owner_canonical,
                                "correlation_id": effective_corr_id,
                            },
                        )
                    raise SessionRecoveryDenied(
                        reason="Owner mismatch",
                        correlation_id=effective_corr_id,
                    )

                # 3. Idempotency check & security context rehydration
                if (
                    session.security_context is not None
                    and session.tenant_id == effective_tenant
                    and session.owner_subject == requested_owner_canonical
                    and (sec_ctx is None or session.security_context.workflow == sec_ctx.workflow)
                ):
                    return session

                # 4. Perform session state context repair and workflow boundary rehydration
                session.tenant_id = effective_tenant
                session.owner_subject = requested_owner_canonical
                if sec_ctx:
                    session.security_context = sec_ctx
                else:
                    from src.security_context import SecurityContextResolver
                    from src.workflow_policy import WorkflowClass
                    wf_target = WorkflowClass(workflow) if workflow else WorkflowClass.PUBLIC_CHAT
                    session.security_context = SecurityContextResolver.create_ephemeral(
                        tenant_id=effective_tenant,
                        canonical_principal_id=requested_owner_canonical,
                        workflow=wf_target,
                    )

                if sec_ctx:
                    ReliabilityAuditService.log_event(
                        sec_ctx,
                        event_name="IDENTITY_RESOLVED",
                        outcome="SUCCESS",
                        details={
                            "canonical_id": requested_owner_canonical,
                            "correlation_id": effective_corr_id,
                        },
                    )
                    ReliabilityAuditService.log_event(
                        sec_ctx,
                        event_name="SESSION_RECOVERY_SUCCESS",
                        outcome="SUCCESS",
                        details={
                            "session_id": session_id,
                            "reason": "missing_security_context",
                            "result": "success",
                            "correlation_id": effective_corr_id,
                        },
                    )
                logger.info(
                    "Self-healing session context repaired successfully",
                    extra={
                        "session_id": session_id,
                        "tenant_id": effective_tenant,
                        "owner_subject": requested_owner_canonical,
                        "correlation_id": effective_corr_id,
                    },
                )
                return session

            # If session is None (missing in memory):
            # Policy validation: deny arbitrary recreation if missing authenticated tenant/owner identity
            if tenant_id is None and owner_subject is None and sec_ctx is None:
                raise SessionRecoveryDenied(
                    reason="Unauthenticated or missing identity claims",
                    correlation_id=effective_corr_id,
                )

            new_session = SessionRecord(
                session_id=session_id,
                tenant_id=effective_tenant,
                owner_subject=requested_owner_canonical,
                security_context=sec_ctx,
            )

            if sec_ctx:
                ReliabilityAuditService.log_event(
                    sec_ctx,
                    event_name="SESSION_RECOVERED",
                    outcome="SUCCESS",
                    details={
                        "session_id": session_id,
                        "reason": "missing_session_recreated",
                        "result": "success",
                        "correlation_id": effective_corr_id,
                    },
                )

            logger.info(
                "Self-healing session created under policy validation",
                extra={
                    "session_id": session_id,
                    "tenant_id": effective_tenant,
                    "owner_subject": requested_owner_canonical,
                    "correlation_id": effective_corr_id,
                },
            )
            return new_session

    @staticmethod
    async def recover_session(
        session_id: str,
        sec_ctx: SecurityContext,
        *,
        internal_details: dict[str, Any] | None = None,
    ) -> SessionRecord:
        """Attempt safe self-healing recovery for an uninitialized session."""
        return await RecoveryManager.reinitialize_session(
            session=None,
            session_id=session_id,
            tenant_id=sec_ctx.tenant_id,
            owner_subject=sec_ctx.canonical_principal_id,
            workflow=sec_ctx.workflow.value,
            correlation_id=sec_ctx.correlation_id,
            sec_ctx=sec_ctx,
        )
