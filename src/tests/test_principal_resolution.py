"""Test suite for Phase 4.5.1 Canonical Principal Identity Resolution."""

from __future__ import annotations

import pytest

from src.db.models import Tenant, TenantMembership, User
from src.db.session import _ensure_fallback_tables, _get_fallback_factory
from src.exceptions.security import AuthorizationFailure, SessionRecoveryDenied
from src.memory import SessionRecord
from src.reliability.recovery_manager import RecoveryManager
from src.security.principal import IdentityCompatibilityResolver, PrincipalResolver
from src.security_context import SecurityContextResolver


@pytest.mark.asyncio
async def test_1_firebase_identity_resolves():
    """TEST 1: Firebase identity resolves to canonical_id 'firebase:user123'."""
    principal = await PrincipalResolver.resolve(
        provider="firebase",
        provider_subject="user123",
        email="user123@example.com",
    )
    assert principal.canonical_id == "firebase:user123"
    assert principal.provider == "firebase"
    assert principal.provider_subject == "user123"
    assert principal.subject == "firebase:user123"


@pytest.mark.asyncio
async def test_2_internal_user_mapping_resolves():
    """TEST 2: Internal user mapping resolves internal_user_id from database."""
    await _ensure_fallback_tables()
    factory = _get_fallback_factory()

    async with factory() as db:
        user = User(
            id="456",
            firebase_uid="user123_db",
            email="user123_db@example.com",
            status="active",
        )
        tenant = Tenant(id="tenant_db_1", identifier="tenant_db_1", name="Tenant DB 1", status="active")
        membership = TenantMembership(id="m_db_1", user_id="456", tenant_id="tenant_db_1", role="operator", status="active")
        db.add_all([user, tenant, membership])
        try:
            await db.commit()
        except Exception:
            await db.rollback()

        principal = await PrincipalResolver.resolve(
            provider="firebase",
            provider_subject="user123_db",
            email="user123_db@example.com",
            tenant_id="tenant_db_1",
            db=db,
        )
        assert principal.canonical_id == "firebase:user123_db"
        assert principal.internal_user_id == "456"
        assert principal.user_id == "456"


@pytest.mark.asyncio
async def test_3_session_recovery_succeeds():
    """TEST 3: Session recovery succeeds when existing owner matches canonical identity."""
    principal = await PrincipalResolver.resolve(
        provider="firebase",
        provider_subject="user123",
        email="user123@example.com",
    )
    sec_ctx = SecurityContextResolver.resolve(principal=principal)

    session = SessionRecord(
        session_id="test-rec-session-3",
        tenant_id="development",
        owner_subject="firebase:user123",
        security_context=None,
    )

    repaired = await RecoveryManager.reinitialize_session(
        session=session,
        session_id="test-rec-session-3",
        tenant_id="development",
        owner_subject="firebase:user123",
        sec_ctx=sec_ctx,
    )
    assert repaired.security_context is not None
    assert repaired.owner_subject == "firebase:user123"


@pytest.mark.asyncio
async def test_4_true_ownership_violation_denied():
    """TEST 4: True ownership violation (firebase:user123 vs firebase:user999) raises SessionRecoveryDenied."""
    owner_principal = await PrincipalResolver.resolve(
        provider="firebase",
        provider_subject="user123",
        email="user123@example.com",
    )

    session = SessionRecord(
        session_id="test-rec-session-4",
        tenant_id="development",
        owner_subject="firebase:user123",
        security_context=SecurityContextResolver.resolve(principal=owner_principal),
    )

    attacker_principal = await PrincipalResolver.resolve(
        provider="firebase",
        provider_subject="user999",
        email="attacker@example.com",
    )
    attacker_ctx = SecurityContextResolver.resolve(principal=attacker_principal)

    with pytest.raises(SessionRecoveryDenied) as exc_info:
        await RecoveryManager.reinitialize_session(
            session=session,
            session_id="test-rec-session-4",
            tenant_id="development",
            owner_subject="firebase:user999",
            sec_ctx=attacker_ctx,
        )

    assert "Owner mismatch" in str(exc_info.value)
    # Confirm no state mutation occurred on original session owner
    assert session.owner_subject == "firebase:user123"


@pytest.mark.asyncio
async def test_5_cross_tenant_attempt_denied():
    """TEST 5: Cross tenant recovery attempt is DENIED."""
    principal = await PrincipalResolver.resolve(
        provider="firebase",
        provider_subject="user123",
        email="user123@example.com",
        tenant_id="TenantA",
    )
    sec_ctx_a = SecurityContextResolver.resolve(principal=principal)

    session = SessionRecord(
        session_id="test-rec-session-5",
        tenant_id="TenantA",
        owner_subject="firebase:user123",
        security_context=sec_ctx_a,
    )

    # Attempt cross-tenant recovery from TenantB
    principal_b = await PrincipalResolver.resolve(
        provider="firebase",
        provider_subject="user123",
        email="user123@example.com",
        tenant_id="TenantB",
    )
    sec_ctx_b = SecurityContextResolver.resolve(principal=principal_b)

    with pytest.raises(SessionRecoveryDenied) as exc_info:
        await RecoveryManager.reinitialize_session(
            session=session,
            session_id="test-rec-session-5",
            tenant_id="TenantB",
            owner_subject="firebase:user123",
            sec_ctx=sec_ctx_b,
        )

    assert "Tenant mismatch" in str(exc_info.value)
    assert session.tenant_id == "TenantA"


@pytest.mark.asyncio
async def test_6_ambiguous_identity_mapping_failed():
    """TEST 6: Empty/unresolvable identity mapping raises AuthorizationFailure (IDENTITY_MAPPING_FAILED)."""
    with pytest.raises(AuthorizationFailure) as exc_info:
        IdentityCompatibilityResolver.normalize_owner_subject("")

    assert "IDENTITY_MAPPING_FAILED" in str(exc_info.value)
