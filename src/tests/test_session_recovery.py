"""Unit tests for RecoveryManager session state self-healing & recovery policy."""

from __future__ import annotations

import asyncio
import unittest

from src.exceptions.security import AuthorizationFailure, SessionRecoveryDenied
from src.memory import SessionRecord, session_registry
from src.reliability.recovery_manager import RecoveryManager
from src.security import Principal
from src.security_context import SecurityContextResolver


class TestSessionRecovery(unittest.IsolatedAsyncioTestCase):
    async def test_case_1_missing_context_auto_recovery(self) -> None:
        """Case 1: Session exists with missing security_context -> auto-recovers & logs audit."""
        session_id = "rec-case-1-session"
        await session_registry.flush_session(session_id)

        # Create session record without security_context
        record = SessionRecord(session_id, tenant_id="dev-tenant", owner_subject="dev-user")
        record.security_context = None
        session_registry._sessions[session_id] = record

        sec_ctx = SecurityContextResolver.resolve(
            principal=Principal(
                canonical_id="firebase:dev-user",
                provider="firebase",
                provider_subject="dev-user",
                internal_user_id="dev-user",
                tenant_id="dev-tenant",
                membership_id="m-123",
                role="developer",
                permissions=frozenset(["*"]),
                email="dev@example.com",
            )
        )

        repaired = await RecoveryManager.reinitialize_session(
            session=record,
            session_id=session_id,
            tenant_id="dev-tenant",
            owner_subject="dev-user",
            workflow=sec_ctx.workflow.value,
            correlation_id=sec_ctx.correlation_id,
            sec_ctx=sec_ctx,
        )

        self.assertIsNotNone(repaired)
        self.assertEqual(repaired.session_id, session_id)
        self.assertIsNotNone(repaired.security_context)
        self.assertEqual(repaired.security_context.tenant_id, "dev-tenant")

        await session_registry.flush_session(session_id)

    async def test_case_2_wrong_tenant_denied(self) -> None:
        """Case 2: Session exists for tenant-A, request claims tenant-B -> AuthorizationFailure, no repair."""
        session_id = "rec-case-2-session"
        await session_registry.flush_session(session_id)

        record = SessionRecord(session_id, tenant_id="tenant-A", owner_subject="user-123")
        session_registry._sessions[session_id] = record

        sec_ctx = SecurityContextResolver.resolve(
            principal=Principal(
                canonical_id="firebase:user-123",
                provider="firebase",
                provider_subject="user-123",
                internal_user_id="user-123",
                tenant_id="tenant-B",
                membership_id="m-456",
                role="developer",
                permissions=frozenset(["*"]),
                email="user@example.com",
            )
        )

        with self.assertRaises((SessionRecoveryDenied, AuthorizationFailure)) as ctx:
            await RecoveryManager.reinitialize_session(
                session=record,
                session_id=session_id,
                tenant_id="tenant-B",
                owner_subject="user-123",
                sec_ctx=sec_ctx,
            )

        self.assertIn("Tenant mismatch", str(ctx.exception))
        # Ensure original session tenant was NOT modified
        self.assertEqual(record.tenant_id, "tenant-A")

        await session_registry.flush_session(session_id)

    async def test_case_3_unauthenticated_recreation_denied(self) -> None:
        """Case 3: Unauthenticated caller attempting arbitrary session creation is denied."""
        session_id = "rec-case-3-session"
        await session_registry.flush_session(session_id)

        with self.assertRaises((SessionRecoveryDenied, AuthorizationFailure)) as ctx:
            await RecoveryManager.reinitialize_session(
                session=None,
                session_id=session_id,
                tenant_id=None,
                owner_subject=None,
                sec_ctx=None,
            )

        self.assertIn("Unauthenticated or missing identity claims", str(ctx.exception))
        self.assertNotIn(session_id, session_registry._sessions)

    async def test_case_4_concurrent_recovery_idempotency(self) -> None:
        """Case 4: Concurrent requests on missing context trigger only 1 repair."""
        session_id = "rec-case-4-session"
        await session_registry.flush_session(session_id)

        record = SessionRecord(session_id, tenant_id="dev-tenant", owner_subject="dev-user")
        record.security_context = None
        session_registry._sessions[session_id] = record

        sec_ctx = SecurityContextResolver.resolve(
            principal=Principal(
                canonical_id="firebase:dev-user",
                provider="firebase",
                provider_subject="dev-user",
                internal_user_id="dev-user",
                tenant_id="dev-tenant",
                membership_id="m-123",
                role="developer",
                permissions=frozenset(["*"]),
                email="dev@example.com",
            )
        )

        # Run 2 recovery calls concurrently
        task1 = asyncio.create_task(
            RecoveryManager.reinitialize_session(
                session=record,
                session_id=session_id,
                tenant_id="dev-tenant",
                owner_subject="dev-user",
                sec_ctx=sec_ctx,
            )
        )
        task2 = asyncio.create_task(
            RecoveryManager.reinitialize_session(
                session=record,
                session_id=session_id,
                tenant_id="dev-tenant",
                owner_subject="dev-user",
                sec_ctx=sec_ctx,
            )
        )

        res1, res2 = await asyncio.gather(task1, task2)

        self.assertIs(res1, res2)
        self.assertIsNotNone(res1.security_context)

        await session_registry.flush_session(session_id)

    async def test_case_5_owner_boundary_denied(self) -> None:
        """Case 5: Existing session owned by userA, requested by userB -> DENIED, no mutation."""
        session_id = "rec-case-5-session"
        await session_registry.flush_session(session_id)

        record = SessionRecord(session_id, tenant_id="tenant-A", owner_subject="userA")
        session_registry._sessions[session_id] = record

        sec_ctx = SecurityContextResolver.resolve(
            principal=Principal(
                canonical_id="firebase:userB",
                provider="firebase",
                provider_subject="userB",
                internal_user_id="userB",
                tenant_id="tenant-A",
                membership_id="m-789",
                role="developer",
                permissions=frozenset(["*"]),
                email="userb@example.com",
            )
        )

        with self.assertRaises((SessionRecoveryDenied, AuthorizationFailure)) as ctx:
            await RecoveryManager.reinitialize_session(
                session=record,
                session_id=session_id,
                tenant_id="tenant-A",
                owner_subject="userB",
                sec_ctx=sec_ctx,
            )

        self.assertIn("Owner mismatch", str(ctx.exception))
        self.assertEqual(record.owner_subject, "userA")

        await session_registry.flush_session(session_id)

    async def test_case_6_recovery_rehydrates_fresh_public_chat_security_context(self) -> None:
        """Case 6: Recovered session rehydrates with incoming PUBLIC_CHAT security_context, replacing stale MAINTENANCE context."""
        from src.workflow_policy import WorkflowClass

        session_id = "rec-case-6-session"
        await session_registry.flush_session(session_id)

        maint_principal = Principal(
            canonical_id="firebase:user-123",
            provider="firebase",
            provider_subject="user-123",
            internal_user_id="user-123",
            tenant_id="dev-tenant",
            membership_id="m-123",
            role="operator",
            permissions=frozenset(["*"]),
            email="dev@example.com",
        )
        maint_sec_ctx = SecurityContextResolver.resolve(
            principal=maint_principal,
            requested_workflow=WorkflowClass.MAINTENANCE,
        )

        record = SessionRecord(session_id, tenant_id="dev-tenant", owner_subject="firebase:user-123")
        record.security_context = maint_sec_ctx
        session_registry._sessions[session_id] = record

        public_sec_ctx = SecurityContextResolver.resolve(
            principal=maint_principal,
            requested_workflow=WorkflowClass.PUBLIC_CHAT,
        )

        repaired = await RecoveryManager.reinitialize_session(
            session=record,
            session_id=session_id,
            tenant_id="dev-tenant",
            owner_subject="firebase:user-123",
            workflow=public_sec_ctx.workflow.value,
            correlation_id=public_sec_ctx.correlation_id,
            sec_ctx=public_sec_ctx,
        )

        self.assertEqual(repaired.security_context.workflow, WorkflowClass.PUBLIC_CHAT)
        self.assertFalse(repaired.security_context.allow_internal_disclosure())

        await session_registry.flush_session(session_id)


if __name__ == "__main__":
    unittest.main()
