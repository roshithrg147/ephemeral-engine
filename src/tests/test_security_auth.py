from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Request

from src import security as security_module
from src.config import Settings, settings
from src.main import app
from src.memory import session_registry
from src.security import AuthenticationError, OIDCJWTValidator, Principal, get_current_principal


def _production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "DEPLOYMENT_MODE": "production",
        "AUTH_MODE": "oidc",
        "OIDC_ISSUER": "https://identity.example.com",
        "OIDC_AUDIENCE": "scevm-api",
        "OIDC_JWKS_URL": "https://identity.example.com/.well-known/jwks.json",
        "CORS_ORIGINS": ["https://app.example.com"],
        "DIAGNOSTIC_MODE": False,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_production_configuration_fails_closed() -> None:
    with pytest.raises(ValueError, match="AUTH_MODE=oidc"):
        Settings(_env_file=None, DEPLOYMENT_MODE="production", AUTH_MODE="disabled")

    with pytest.raises(ValueError, match="explicit HTTPS origins"):
        _production_settings(CORS_ORIGINS=["http://localhost:3000"])

    with pytest.raises(ValueError, match="DIAGNOSTIC_MODE must be disabled"):
        _production_settings(DIAGNOSTIC_MODE=True)

    assert _production_settings().AUTH_MODE == "oidc"


def test_oidc_validator_accepts_required_claims_and_rejects_expired_token() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    validator = OIDCJWTValidator(
        issuer="https://identity.example.com",
        audience="scevm-api",
        jwks_url="https://identity.example.com/.well-known/jwks.json",
        algorithms=("RS256",),
        clock_skew_seconds=0,
        jwks_cache_seconds=300,
        signing_key_resolver=lambda _token: public_key,
    )
    now = datetime.now(UTC)
    claims = {
        "iss": "https://identity.example.com",
        "aud": "scevm-api",
        "sub": "user-1",
        "tenant_id": "tenant-1",
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(minutes=5),
        "scope": "scevm:diagnostic profile",
    }
    token = jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "test-key"})

    principal = validator.validate(token)

    assert principal.subject == "user-1"
    assert principal.tenant_id == "tenant-1"
    assert principal.has_scope("scevm:diagnostic")

    expired = jwt.encode(
        {**claims, "iat": now - timedelta(minutes=10), "exp": now - timedelta(minutes=5)},
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )
    with pytest.raises(AuthenticationError, match="invalid_token"):
        validator.validate(expired)


def test_oidc_validator_fetches_and_caches_jwks() -> None:
    async def run() -> None:
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
        public_jwk.update({"kid": "key-1", "alg": "RS256", "use": "sig"})
        fetch_count = 0

        async def fetch_jwks(url: str) -> dict[str, object]:
            nonlocal fetch_count
            assert url == "https://identity.example.com/.well-known/jwks.json"
            fetch_count += 1
            return {"keys": [public_jwk]}

        validator = OIDCJWTValidator(
            issuer="https://identity.example.com",
            audience="scevm-api",
            jwks_url="https://identity.example.com/.well-known/jwks.json",
            algorithms=("RS256",),
            clock_skew_seconds=0,
            jwks_cache_seconds=300,
            jwks_fetcher=fetch_jwks,
        )
        now = datetime.now(UTC)
        token = jwt.encode(
            {
                "iss": "https://identity.example.com",
                "aud": "scevm-api",
                "sub": "user-1",
                "tenant_id": "tenant-1",
                "iat": now,
                "nbf": now,
                "exp": now + timedelta(minutes=5),
            },
            private_key,
            algorithm="RS256",
            headers={"kid": "key-1"},
        )

        assert (await validator.validate_async(token)).subject == "user-1"
        assert (await validator.validate_async(token)).subject == "user-1"
        assert fetch_count == 1

        unknown_key_token = jwt.encode(
            {
                "iss": "https://identity.example.com",
                "aud": "scevm-api",
                "sub": "user-1",
                "tenant_id": "tenant-1",
                "iat": now,
                "exp": now + timedelta(minutes=5),
            },
            private_key,
            algorithm="RS256",
            headers={"kid": "unknown-key"},
        )
        for _ in range(2):
            with pytest.raises(AuthenticationError, match="unknown_signing_key"):
                await validator.validate_async(unknown_key_token)
        assert fetch_count == 1

    asyncio.run(run())


def test_api_requires_bearer_token_in_oidc_mode(monkeypatch) -> None:
    async def run() -> httpx.Response:
        monkeypatch.setattr(settings, "AUTH_MODE", "oidc")
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/api/session/list")

    response = asyncio.run(run())

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid authentication credentials"}
    assert response.headers["www-authenticate"] == "Bearer"


def test_api_accepts_verified_bearer_identity(monkeypatch) -> None:
    class FakeValidator:
        async def validate_async(self, token: str) -> Principal:
            assert token == "valid-token"
            return Principal(subject="user-1", tenant_id="tenant-1", scopes=frozenset())

    async def run() -> httpx.Response:
        monkeypatch.setattr(settings, "AUTH_MODE", "oidc")
        monkeypatch.setattr(security_module, "get_oidc_validator", lambda *_args: FakeValidator())
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(
                "/api/session/list",
                headers={"Authorization": "Bearer valid-token"},
            )

    response = asyncio.run(run())

    assert response.status_code == 200
    assert response.json()["data"] == []


def test_firebase_auth_mode_verification(monkeypatch) -> None:
    async def fake_verify_firebase(token: str) -> Principal:
        if token == "valid-fb-token":
            return Principal(subject="fb-user-123", tenant_id="fb-tenant-abc", scopes=frozenset())
        raise AuthenticationError("invalid_firebase_token")

    async def run() -> None:
        monkeypatch.setattr(settings, "AUTH_MODE", "firebase")
        monkeypatch.setattr(security_module, "verify_firebase_token_async", fake_verify_firebase)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            res_denied = await client.get("/api/session/list")
            res_allowed = await client.get(
                "/api/session/list",
                headers={"Authorization": "Bearer valid-fb-token"},
            )

        assert res_denied.status_code == 401
        assert res_allowed.status_code == 200
        assert res_allowed.json()["data"] == []

    asyncio.run(run())


def test_session_ownership_and_diagnostic_scope_are_enforced(monkeypatch) -> None:
    async def run() -> None:
        monkeypatch.setattr(settings, "AUTH_MODE", "oidc")
        session_id = f"security-{uuid4().hex}"
        operator_burn_session_id = f"security-operator-{uuid4().hex}"

        async def test_principal(request: Request) -> Principal:
            scopes = frozenset(filter(None, request.headers.get("x-test-scopes", "").split()))
            return Principal(
                subject=request.headers.get("x-test-subject", "anonymous"),
                tenant_id=request.headers.get("x-test-tenant", "tenant-a"),
                scopes=scopes,
            )

        app.dependency_overrides[get_current_principal] = test_principal
        transport = httpx.ASGITransport(app=app)
        alice = {"x-test-subject": "alice", "x-test-tenant": "tenant-a"}
        bob = {"x-test-subject": "bob", "x-test-tenant": "tenant-a"}
        cross_tenant_operator = {
            "x-test-subject": "operator",
            "x-test-tenant": "tenant-b",
            "x-test-scopes": settings.OPERATOR_SCOPE,
        }
        tenant_operator = {
            "x-test-subject": "operator",
            "x-test-tenant": "tenant-a",
            "x-test-scopes": settings.OPERATOR_SCOPE,
        }

        try:
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                created = await client.post(
                    "/api/session/initialize",
                    json={"session_id": session_id},
                    headers=alice,
                )
                operator_burn_created = await client.post(
                    "/api/session/initialize",
                    json={"session_id": operator_burn_session_id},
                    headers=alice,
                )
                denied_history = await client.get(f"/api/session/history/{session_id}", headers=bob)
                denied_memory = await client.get(f"/api/session/memory/{session_id}", headers=bob)
                denied_message = await client.post(
                    "/api/session/message",
                    json={"session_id": session_id, "role": "user", "content": "denied"},
                    headers=bob,
                )
                operator_history = await client.get(
                    f"/api/session/history/{session_id}", headers=tenant_operator
                )
                alice_list = await client.get("/api/session/list", headers=alice)
                bob_list = await client.get("/api/session/list", headers=bob)
                tenant_operator_list = await client.get(
                    "/api/session/list", headers=tenant_operator
                )
                cross_tenant_list = await client.get(
                    "/api/session/list", headers=cross_tenant_operator
                )
                denied_diagnostics = await client.post(
                    "/api/agent/query",
                    json={
                        "session_id": session_id,
                        "prompt": "Do not call provider",
                        "diagnostic_mode": True,
                    },
                    headers=bob,
                )
                denied_query = await client.post(
                    "/api/agent/query",
                    json={
                        "session_id": session_id,
                        "prompt": "Do not call provider",
                        "diagnostic_mode": False,
                    },
                    headers=bob,
                )
                denied_dual_llm = await client.post(
                    "/api/dual-llm/process",
                    json={"session_id": session_id, "prompt": "Do not call provider"},
                    headers=bob,
                )
                denied_burn = await client.delete(f"/api/session/burn/{session_id}", headers=bob)
                denied_sandbox_burn = await client.post(
                    f"/api/session/burn/{session_id}", headers=bob
                )
                denied_cross_tenant_burn = await client.delete(
                    f"/api/session/burn/{session_id}", headers=cross_tenant_operator
                )
                operator_burn = await client.delete(
                    f"/api/session/burn/{operator_burn_session_id}", headers=tenant_operator
                )
                allowed_burn = await client.delete(f"/api/session/burn/{session_id}", headers=alice)

            assert created.status_code == 200
            assert operator_burn_created.status_code == 200
            assert denied_history.status_code == 404
            assert denied_memory.status_code == 404
            assert denied_message.status_code == 404
            assert operator_history.status_code == 404
            assert alice_list.json()["data"] == [session_id, operator_burn_session_id]
            assert bob_list.json()["data"] == []
            assert tenant_operator_list.json()["data"] == [
                session_id,
                operator_burn_session_id,
            ]
            assert cross_tenant_list.json()["data"] == []
            assert denied_diagnostics.status_code == 403
            assert denied_query.status_code == 404
            assert denied_dual_llm.status_code == 404
            assert denied_burn.status_code == 404
            assert denied_sandbox_burn.status_code == 404
            assert denied_cross_tenant_burn.status_code == 404
            assert operator_burn.status_code == 200
            assert allowed_burn.status_code == 200
        finally:
            app.dependency_overrides.pop(get_current_principal, None)
            await session_registry.flush_session(session_id)
            await session_registry.flush_session(operator_burn_session_id)

    asyncio.run(run())


def test_security_headers_are_present() -> None:
    async def run() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/")

    response = asyncio.run(run())

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
