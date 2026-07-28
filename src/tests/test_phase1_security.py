"""Comprehensive Phase 1 Authentication Gateway and Authorization Foundation unit and integration tests."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src import security as security_module
from src.config import Settings, settings
from src.db import session as db_session_module
from src.db.base import Base
from src.db.models import Tenant, TenantMembership, User
from src.db.session import async_sessionmaker
from src.main import app
from src.security import (
    AuthenticationError,
    ExternalIdentity,
    Principal,
    PrincipalResolver,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


async def _create_test_session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return factory, engine


# --- 1. Database Model & Constraint Tests ---


@pytest.mark.asyncio
async def test_database_schema_and_constraints() -> None:
    session_factory, engine = await _create_test_session_factory()
    try:
        async with session_factory() as db:
            user = User(
                id=str(uuid4()),
                firebase_uid="uid-100",
                email="user100@example.com",
                display_name="User 100",
                status="active",
            )
            tenant = Tenant(
                id=str(uuid4()),
                identifier="tenant-100",
                name="Tenant 100",
                status="active",
            )
            db.add_all([user, tenant])
            await db.commit()

            membership = TenantMembership(
                id=str(uuid4()),
                user_id=user.id,
                tenant_id=tenant.id,
                role="viewer",
                status="active",
            )
            db.add(membership)
            await db.commit()

            user_id_val = user.id
            tenant_id_val = tenant.id

            # Verify unique constraint on firebase_uid
            duplicate_user = User(
                id=str(uuid4()),
                firebase_uid="uid-100",
                email="dup@example.com",
                status="active",
            )
            db.add(duplicate_user)
            with pytest.raises(DBAPIError):
                await db.commit()
            await db.rollback()

            # Verify unique constraint on (user_id, tenant_id)
            duplicate_membership = TenantMembership(
                id=str(uuid4()),
                user_id=user_id_val,
                tenant_id=tenant_id_val,
                role="operator",
                status="active",
            )
            db.add(duplicate_membership)
            with pytest.raises(DBAPIError):
                await db.commit()
    finally:
        await engine.dispose()


# --- 2. Admission Policy & PrincipalResolver Tests ---


@pytest.mark.asyncio
async def test_admission_policy_and_principal_resolution() -> None:
    session_factory, engine = await _create_test_session_factory()
    try:
        async with session_factory() as db:
            user_active = User(
                id=str(uuid4()),
                firebase_uid="fb-active-user",
                email="active@example.com",
                status="active",
            )
            user_inactive = User(
                id=str(uuid4()),
                firebase_uid="fb-inactive-user",
                email="inactive@example.com",
                status="inactive",
            )
            tenant_a = Tenant(
                id=str(uuid4()),
                identifier="tenant-a",
                name="Tenant A",
                status="active",
            )
            tenant_b = Tenant(
                id=str(uuid4()),
                identifier="tenant-b",
                name="Tenant B",
                status="active",
            )
            tenant_inactive = Tenant(
                id=str(uuid4()),
                identifier="tenant-inc",
                name="Tenant Inactive",
                status="inactive",
            )
            db.add_all([user_active, user_inactive, tenant_a, tenant_b, tenant_inactive])
            await db.commit()

            # Membership for active user in Tenant A
            mem_a = TenantMembership(
                id=str(uuid4()),
                user_id=user_active.id,
                tenant_id=tenant_a.id,
                role="viewer",
                status="active",
            )
            db.add(mem_a)
            await db.commit()

            # Case A: Un-provisioned identity fails admission (403 closed)
            ext_unprovisioned = ExternalIdentity(uid="fb-unknown", email="unknown@example.com")
            with pytest.raises(AuthenticationError, match="account_not_admitted"):
                await PrincipalResolver.resolve_principal_async(db, ext_unprovisioned)

            # Case B: Inactive user fails admission
            ext_inactive = ExternalIdentity(uid="fb-inactive-user", email="inactive@example.com")
            with pytest.raises(AuthenticationError, match="account_not_admitted"):
                await PrincipalResolver.resolve_principal_async(db, ext_inactive)

            # Case C: Single active membership resolves deterministically
            ext_active = ExternalIdentity(uid="fb-active-user", email="active@example.com")
            principal = await PrincipalResolver.resolve_principal_async(db, ext_active)
            assert principal.user_id == user_active.id
            assert principal.tenant_id == tenant_a.id
            assert principal.role == "viewer"
            assert principal.has_permission("session:read")
            assert not principal.has_permission("session:create")

            # Case D: Multiple active memberships with explicit selection
            mem_b = TenantMembership(
                id=str(uuid4()),
                user_id=user_active.id,
                tenant_id=tenant_b.id,
                role="operator",
                status="active",
            )
            db.add(mem_b)
            await db.commit()

            # Ambiguous selection without X-Tenant-ID fails closed
            with pytest.raises(AuthenticationError, match="ambiguous_tenant_selection"):
                await PrincipalResolver.resolve_principal_async(db, ext_active)

            # Valid explicit selection resolves to requested tenant
            principal_b = await PrincipalResolver.resolve_principal_async(
                db, ext_active, requested_tenant_id=tenant_b.id
            )
            assert principal_b.tenant_id == tenant_b.id
            assert principal_b.role == "operator"
            assert principal_b.has_permission("session:create")
            assert principal_b.has_permission("session:burn")

            # Selection of tenant without membership fails
            with pytest.raises(AuthenticationError, match="tenant_membership_denied"):
                await PrincipalResolver.resolve_principal_async(
                    db, ext_active, requested_tenant_id=tenant_inactive.id
                )
    finally:
        await engine.dispose()


# --- 3. Role and Permission Policy Tests ---


def test_role_permission_matrix() -> None:
    viewer_principal = Principal(
        canonical_id="firebase:sub-1",
        provider="firebase",
        provider_subject="sub-1",
        internal_user_id="u-1",
        tenant_id="t-1",
        membership_id="m-1",
        role="viewer",
        permissions=frozenset({"runtime:read", "session:list", "session:read"}),
        email="viewer@example.com",
    )
    operator_principal = Principal(
        canonical_id="firebase:sub-2",
        provider="firebase",
        provider_subject="sub-2",
        internal_user_id="u-2",
        tenant_id="t-1",
        membership_id="m-2",
        role="operator",
        permissions=frozenset(
            {
                "runtime:read",
                "session:list",
                "session:read",
                "session:create",
                "session:query",
                "request:cancel",
                "session:burn",
            }
        ),
        email="operator@example.com",
    )

    assert viewer_principal.has_permission("session:read")
    assert not viewer_principal.has_permission("session:create")
    assert not viewer_principal.has_permission("session:burn")

    assert operator_principal.has_permission("session:create")
    assert operator_principal.has_permission("session:burn")
    assert not operator_principal.has_permission("membership:manage")


# --- 4. Integration Tests & API Endpoint Authorization ---


@pytest.mark.asyncio
async def test_api_endpoint_authorization_and_tenant_isolation(monkeypatch) -> None:
    session_factory, engine = await _create_test_session_factory()
    try:
        monkeypatch.setattr(settings, "AUTH_MODE", "firebase")
        monkeypatch.setattr(db_session_module, "get_async_session_factory", lambda: session_factory)

        # Populate test database
        async with session_factory() as db:
            user_alice = User(
                id=str(uuid4()),
                firebase_uid="uid-alice",
                email="alice@example.com",
                status="active",
            )
            user_bob = User(
                id=str(uuid4()),
                firebase_uid="uid-bob",
                email="bob@example.com",
                status="active",
            )
            tenant_alpha = Tenant(
                id=str(uuid4()),
                identifier="tenant-alpha",
                name="Alpha Corp",
                status="active",
            )
            tenant_beta = Tenant(
                id=str(uuid4()),
                identifier="tenant-beta",
                name="Beta Corp",
                status="active",
            )
            db.add_all([user_alice, user_bob, tenant_alpha, tenant_beta])
            await db.commit()

            # Alice is operator in Alpha
            mem_alice = TenantMembership(
                id=str(uuid4()),
                user_id=user_alice.id,
                tenant_id=tenant_alpha.id,
                role="operator",
                status="active",
            )
            # Bob is viewer in Beta
            mem_bob = TenantMembership(
                id=str(uuid4()),
                user_id=user_bob.id,
                tenant_id=tenant_beta.id,
                role="viewer",
                status="active",
            )
            db.add_all([mem_alice, mem_bob])
            await db.commit()

        # Mock Firebase token verification
        async def fake_verify_firebase_identity(token: str) -> ExternalIdentity:
            if token == "token-alice":
                return ExternalIdentity(uid="uid-alice", email="alice@example.com")
            if token == "token-bob":
                return ExternalIdentity(uid="uid-bob", email="bob@example.com")
            raise AuthenticationError("invalid_firebase_token")

        monkeypatch.setattr(
            security_module, "verify_firebase_identity_async", fake_verify_firebase_identity
        )

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Missing Bearer Token -> 401 Unauthorized
            res_no_auth = await client.get("/api/session/list")
            assert res_no_auth.status_code == 401

            # 2. Invalid Bearer Token -> 401 Unauthorized
            res_bad_token = await client.get(
                "/api/session/list", headers={"Authorization": "Bearer invalid"}
            )
            assert res_bad_token.status_code == 401

            # 3. Alice (operator, Alpha) initializes session -> 200 OK
            alice_headers = {"Authorization": "Bearer token-alice"}
            res_init = await client.post(
                "/api/session/initialize",
                json={"session_id": "sess-alpha-1"},
                headers=alice_headers,
            )
            assert res_init.status_code == 200

            # 4. Alice lists sessions -> sees sess-alpha-1
            res_alice_list = await client.get("/api/session/list", headers=alice_headers)
            assert res_alice_list.status_code == 200
            assert "sess-alpha-1" in res_alice_list.json()["data"]

            # 5. Bob (viewer, Beta) attempts to view Alice's session history -> 404 (non-enumeration)
            bob_headers = {"Authorization": "Bearer token-bob"}
            res_bob_history = await client.get(
                "/api/session/history/sess-alpha-1", headers=bob_headers
            )
            assert res_bob_history.status_code == 404

            # 6. Bob (viewer) attempts to burn Alice's session -> 403 Forbidden (viewer lacks session:burn)
            res_bob_burn = await client.delete(
                "/api/session/burn/sess-alpha-1", headers=bob_headers
            )
            assert res_bob_burn.status_code == 403

            # 7. Alice (operator) burns her session -> 200 OK
            res_alice_burn = await client.delete(
                "/api/session/burn/sess-alpha-1", headers=alice_headers
            )
            assert res_alice_burn.status_code == 200
    finally:
        await engine.dispose()


# --- 5. Production Guardrail Tests ---


def test_production_disabled_auth_fails_closed() -> None:
    with pytest.raises(ValueError, match="AUTH_MODE=oidc or AUTH_MODE=firebase"):
        Settings(_env_file=None, DEPLOYMENT_MODE="production", AUTH_MODE="disabled")
