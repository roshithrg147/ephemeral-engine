"""Authentication, principal extraction, PostgreSQL identity resolution, and API security response controls."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Any

import httpx
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWK
from jwt.exceptions import InvalidTokenError, PyJWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from src.config import settings
from src.db.models import Tenant, TenantMembership, User
from src.security.principal import IdentityMappingService, Principal

logger = logging.getLogger("SC-EVM.Security")
bearer_scheme = HTTPBearer(auto_error=False)

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "viewer": {
        "runtime:read",
        "session:list",
        "session:read",
    },
    "operator": {
        "runtime:read",
        "session:list",
        "session:read",
        "session:create",
        "session:query",
        "request:cancel",
        "session:burn",
    },
    "admin": {
        "runtime:read",
        "session:list",
        "session:read",
        "session:create",
        "session:query",
        "request:cancel",
        "session:burn",
        "membership:read",
        "membership:manage",
    },
}


@dataclass(frozen=True, slots=True)
class ExternalIdentity:
    """Verified external identity from identity provider (e.g. Firebase UID)."""

    uid: str
    email: str
    display_name: str | None = None


class AuthenticationError(Exception):
    """Internal authentication failure carrying only a safe reason code."""

    def __init__(self, reason_code: str):
        super().__init__(reason_code)
        self.reason_code = reason_code


def _parse_scopes(claims: dict[str, Any]) -> frozenset[str]:
    values: set[str] = set()
    scope = claims.get("scope")
    if isinstance(scope, str):
        values.update(item for item in scope.split() if item)
    scp = claims.get("scp")
    if isinstance(scp, str):
        values.update(item for item in scp.split() if item)
    elif isinstance(scp, list):
        values.update(item for item in scp if isinstance(item, str) and item)
    return frozenset(values)


class PrincipalResolver:
    """Resolves an external verified identity against PostgreSQL to construct a Principal."""

    @staticmethod
    async def resolve_principal_async(
        db: AsyncSession,
        external_identity: ExternalIdentity,
        requested_tenant_id: str | None = None,
    ) -> Principal:
        # Step 1: Query User in PostgreSQL by immutable firebase_uid
        query_user = select(User).where(
            User.firebase_uid == external_identity.uid,
            User.status == "active",
        )
        user_result = await db.execute(query_user)
        user = user_result.scalar_one_or_none()

        if user is None:
            # Bootstrap development user & tenant in non-production mode for dev compatibility
            if external_identity.uid == "dev-firebase-uid" and settings.DEPLOYMENT_MODE != "production":
                user = User(
                    id="dev-user-id",
                    firebase_uid="dev-firebase-uid",
                    email="dev@ephemeral-engine.local",
                    display_name="Development User",
                    status="active",
                )
                tenant = Tenant(
                    id="development",
                    identifier="development",
                    name="Development Tenant",
                    status="active",
                )
                membership = TenantMembership(
                    id="dev-membership-id",
                    user_id=user.id,
                    tenant_id=tenant.id,
                    role="operator",
                    status="active",
                )
                db.add_all([user, tenant, membership])
                try:
                    await db.commit()
                except Exception:
                    await db.rollback()
            else:
                raise AuthenticationError("account_not_admitted")

        # Re-query user & active memberships
        query_user = select(User).where(
            User.firebase_uid == external_identity.uid,
            User.status == "active",
        )
        user_result = await db.execute(query_user)
        user = user_result.scalar_one_or_none()
        if user is None:
            raise AuthenticationError("account_not_admitted")

        # Step 2: Query active memberships for the user
        query_memberships = (
            select(TenantMembership, Tenant)
            .join(Tenant, TenantMembership.tenant_id == Tenant.id)
            .where(
                TenantMembership.user_id == user.id,
                TenantMembership.status == "active",
                Tenant.status == "active",
            )
        )
        membership_result = await db.execute(query_memberships)
        active_memberships = membership_result.all()

        if not active_memberships:
            raise AuthenticationError("no_active_membership")

        # Step 3: Apply Tenant Selection Policy
        selected_membership: TenantMembership | None = None
        selected_tenant: Tenant | None = None

        if requested_tenant_id and requested_tenant_id.strip():
            target = requested_tenant_id.strip()
            for mem, ten in active_memberships:
                if ten.id == target or ten.identifier == target:
                    selected_membership = mem
                    selected_tenant = ten
                    break
            if selected_membership is None:
                raise AuthenticationError("tenant_membership_denied")
        else:
            if len(active_memberships) == 1:
                selected_membership, selected_tenant = active_memberships[0]
            else:
                raise AuthenticationError("ambiguous_tenant_selection")

        # Step 4: Resolve permissions from assigned role
        role = selected_membership.role
        permissions = frozenset(ROLE_PERMISSIONS.get(role, set()))
        provider = "firebase" if settings.AUTH_MODE in ("firebase", "disabled") else "oidc"
        provider_subject = external_identity.uid
        canonical_id = f"{provider}:{provider_subject}"

        await IdentityMappingService.get_or_create_mapping(
            db,
            provider=provider,
            provider_subject=provider_subject,
            tenant_id=selected_tenant.id,
            internal_user_id=user.id,
        )

        return Principal(
            canonical_id=canonical_id,
            provider=provider,
            provider_subject=provider_subject,
            internal_user_id=user.id,
            tenant_id=selected_tenant.id,
            membership_id=selected_membership.id,
            role=role,
            permissions=permissions,
            email=user.email,
            display_name=user.display_name,
        )


class OIDCJWTValidator:
    """Validate OIDC access tokens against issuer JWKS and required claims."""

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        jwks_url: str,
        algorithms: tuple[str, ...],
        clock_skew_seconds: int,
        jwks_cache_seconds: int,
        jwks_min_refresh_seconds: int = 30,
        signing_key_resolver: Callable[[str], Any] | None = None,
        jwks_fetcher: Callable[[str], Awaitable[dict[str, Any]]] | None = None,
    ) -> None:
        self.issuer = issuer
        self.audience = audience
        self.jwks_url = jwks_url
        self.algorithms = algorithms
        self.clock_skew_seconds = clock_skew_seconds
        self.jwks_cache_seconds = jwks_cache_seconds
        self.jwks_min_refresh_seconds = jwks_min_refresh_seconds
        self._signing_key_resolver = signing_key_resolver
        self._jwks_fetcher = jwks_fetcher
        self._cached_keys: dict[str, Any] = {}
        self._cache_expires_at = 0.0
        self._last_refresh_at = 0.0
        self._cache_lock = asyncio.Lock()

    def _decode_identity(self, token: str, key: Any) -> ExternalIdentity:
        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=list(self.algorithms),
                issuer=self.issuer,
                audience=self.audience,
                leeway=self.clock_skew_seconds,
                options={"require": ["exp", "iat", "sub"]},
            )
        except (InvalidTokenError, ValueError, TypeError) as exc:
            raise AuthenticationError("invalid_token") from exc

        subject = claims.get("sub")
        email = claims.get("email") or f"{subject}@example.com"
        name = claims.get("name")
        if not isinstance(subject, str) or not subject.strip():
            raise AuthenticationError("invalid_subject")
        return ExternalIdentity(uid=subject, email=email, display_name=name)

    def validate_identity(self, token: str) -> ExternalIdentity:
        if self._signing_key_resolver is None:
            raise RuntimeError("Use validate_identity_async when resolving keys from JWKS")
        try:
            key = self._signing_key_resolver(token)
        except (InvalidTokenError, ValueError, TypeError) as exc:
            raise AuthenticationError("invalid_token") from exc
        return self._decode_identity(token, key)

    async def _refresh_keys(self) -> None:
        try:
            if self._jwks_fetcher is not None:
                payload = await self._jwks_fetcher(self.jwks_url)
            else:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(self.jwks_url)
                    response.raise_for_status()
                    payload = response.json()
            raw_keys = payload.get("keys") if isinstance(payload, dict) else None
            if not isinstance(raw_keys, list):
                raise ValueError("JWKS keys must be a list")
            parsed_keys = {}
            for item in raw_keys:
                if not isinstance(item, dict) or not isinstance(item.get("kid"), str):
                    continue
                if item.get("use") not in (None, "sig"):
                    continue
                key_ops = item.get("key_ops")
                if isinstance(key_ops, list) and "verify" not in key_ops:
                    continue
                if item.get("alg") not in (None, *self.algorithms):
                    continue
                parsed_keys[item["kid"]] = PyJWK.from_dict(item).key
            if not parsed_keys:
                raise ValueError("JWKS contains no keyed signing material")
        except (httpx.HTTPError, PyJWTError, KeyError, ValueError, TypeError) as exc:
            raise AuthenticationError("jwks_unavailable") from exc

        now = time.monotonic()
        self._cached_keys = parsed_keys
        self._last_refresh_at = now
        self._cache_expires_at = now + self.jwks_cache_seconds

    async def _resolve_signing_key_async(self, token: str) -> Any:
        if self._signing_key_resolver is not None:
            return self._signing_key_resolver(token)
        try:
            header = jwt.get_unverified_header(token)
        except InvalidTokenError as exc:
            raise AuthenticationError("invalid_token") from exc
        algorithm = header.get("alg")
        key_id = header.get("kid")
        if algorithm not in self.algorithms or not isinstance(key_id, str) or not key_id:
            raise AuthenticationError("invalid_token")

        async with self._cache_lock:
            now = time.monotonic()
            cache_expired = now >= self._cache_expires_at
            unknown_key_refresh_due = (
                key_id not in self._cached_keys
                and now - self._last_refresh_at >= self.jwks_min_refresh_seconds
            )
            if cache_expired or unknown_key_refresh_due:
                await self._refresh_keys()
            key = self._cached_keys.get(key_id)
        if key is None:
            raise AuthenticationError("unknown_signing_key")
        return key

    async def validate_identity_async(self, token: str) -> ExternalIdentity:
        key = await self._resolve_signing_key_async(token)
        return self._decode_identity(token, key)


@lru_cache(maxsize=4)
def get_oidc_validator(
    issuer: str,
    audience: str,
    jwks_url: str,
    algorithms: tuple[str, ...],
    clock_skew_seconds: int,
    jwks_cache_seconds: int,
    jwks_min_refresh_seconds: int,
) -> OIDCJWTValidator:
    return OIDCJWTValidator(
        issuer=issuer,
        audience=audience,
        jwks_url=jwks_url,
        algorithms=algorithms,
        clock_skew_seconds=clock_skew_seconds,
        jwks_cache_seconds=jwks_cache_seconds,
        jwks_min_refresh_seconds=jwks_min_refresh_seconds,
    )


def log_security_event(
    request: Request,
    *,
    outcome: str,
    reason_code: str,
    principal: Principal | None = None,
) -> None:
    """Log a sanitized security decision. Never log raw tokens or authorization headers."""
    user_id = None
    tenant_id = None
    if principal is not None:
        user_id = principal.user_id
        tenant_id = principal.tenant_id
    logger.info(
        "security_decision",
        extra={
            "method": request.method,
            "path": request.url.path,
            "outcome": outcome,
            "reason_code": reason_code,
            "user_id": user_id,
            "tenant_id": tenant_id,
        },
    )


def _unauthorized(reason_code: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _forbidden(reason_code: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied",
    )


_FIREBASE_APP_INITIALIZED = False


def _init_firebase_app() -> None:
    global _FIREBASE_APP_INITIALIZED
    if _FIREBASE_APP_INITIALIZED:
        return
    import os

    import firebase_admin
    from firebase_admin import credentials

    if not firebase_admin._apps:
        if settings.FIREBASE_CREDENTIALS_PATH and os.path.exists(
            settings.FIREBASE_CREDENTIALS_PATH
        ):
            cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
            firebase_admin.initialize_app(
                cred,
                {"projectId": settings.FIREBASE_PROJECT_ID}
                if settings.FIREBASE_PROJECT_ID
                else None,
            )
        else:
            options = (
                {"projectId": settings.FIREBASE_PROJECT_ID}
                if settings.FIREBASE_PROJECT_ID
                else None
            )
            firebase_admin.initialize_app(options=options)
    _FIREBASE_APP_INITIALIZED = True


async def verify_firebase_identity_async(token: str) -> ExternalIdentity:
    """Verify a Firebase ID token using firebase_admin.auth to extract external identity."""
    try:
        from firebase_admin import auth

        _init_firebase_app()
        decoded = await asyncio.to_thread(auth.verify_id_token, token)
    except Exception as exc:
        raise AuthenticationError("invalid_firebase_token") from exc

    subject = decoded.get("uid") or decoded.get("sub")
    email = decoded.get("email") or f"{subject}@example.com"
    name = decoded.get("name")
    if not isinstance(subject, str) or not subject.strip():
        raise AuthenticationError("invalid_subject")

    return ExternalIdentity(uid=subject, email=email, display_name=name)


async def verify_firebase_token_async(token: str) -> ExternalIdentity:
    """Legacy helper returning ExternalIdentity for backward compatibility."""
    return await verify_firebase_identity_async(token)


async def get_current_principal(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> Principal:
    """FastAPI dependency resolving external identity against PostgreSQL to produce internal Principal."""
    # Production guardrail: AUTH_MODE=disabled must fail closed in production
    if settings.DEPLOYMENT_MODE == "production" and settings.AUTH_MODE == "disabled":
        log_security_event(request, outcome="denied", reason_code="invalid_production_auth_config")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Production authentication configuration error",
        )

    requested_tenant_id = request.headers.get("x-tenant-id")

    from src.db.session import (
        _ensure_fallback_tables,
        _get_fallback_factory,
        get_async_session_factory,
    )

    try:
        factory = get_async_session_factory()
        async with factory() as db:
            await db.execute(select(1))
    except Exception:
        factory = _get_fallback_factory()
        await _ensure_fallback_tables()

    async with factory() as db:
        if settings.AUTH_MODE == "disabled":
            dev_identity = ExternalIdentity(
                uid="dev-firebase-uid",
                email="dev@ephemeral-engine.local",
                display_name="Development User",
            )
            try:
                principal = await PrincipalResolver.resolve_principal_async(
                    db, dev_identity, requested_tenant_id
                )
                log_security_event(
                    request,
                    outcome="allowed",
                    reason_code="dev_authenticated",
                    principal=principal,
                )
                return principal
            except AuthenticationError as exc:
                log_security_event(request, outcome="denied", reason_code=exc.reason_code)
                raise _forbidden(exc.reason_code) from exc

        if credentials is None or credentials.scheme.lower() != "bearer":
            log_security_event(request, outcome="denied", reason_code="missing_bearer")
            raise _unauthorized("missing_bearer")

        external_identity: ExternalIdentity
        if settings.AUTH_MODE == "firebase":
            try:
                external_identity = await verify_firebase_identity_async(credentials.credentials)
            except AuthenticationError as exc:
                log_security_event(request, outcome="denied", reason_code=exc.reason_code)
                raise _unauthorized(exc.reason_code) from exc
        else:
            validator = get_oidc_validator(
                settings.OIDC_ISSUER,
                settings.OIDC_AUDIENCE,
                settings.OIDC_JWKS_URL,
                settings.OIDC_JWT_ALGORITHMS,
                settings.OIDC_CLOCK_SKEW_SECONDS,
                settings.OIDC_JWKS_CACHE_SECONDS,
                settings.OIDC_JWKS_MIN_REFRESH_SECONDS,
            )
            try:
                external_identity = await validator.validate_identity_async(credentials.credentials)
            except AuthenticationError as exc:
                log_security_event(request, outcome="denied", reason_code=exc.reason_code)
                raise _unauthorized(exc.reason_code) from exc

        try:
            principal = await PrincipalResolver.resolve_principal_async(
                db, external_identity, requested_tenant_id
            )
        except AuthenticationError as exc:
            log_security_event(request, outcome="denied", reason_code=exc.reason_code)
            raise _forbidden(exc.reason_code) from exc

        log_security_event(
            request,
            outcome="allowed",
            reason_code="authenticated",
            principal=principal,
        )
        return principal


def require_permission(request: Request, principal: Principal, permission: str) -> None:
    """Enforce explicit permission check against the resolved Principal."""
    if principal.has_permission(permission):
        return
    log_security_event(
        request,
        outcome="denied",
        reason_code="insufficient_permission",
        principal=principal,
    )
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def require_scope(request: Request, principal: Principal, scope: str) -> None:
    """Backward compatible scope check mapping to permission policy."""
    if principal.has_scope(scope):
        return
    log_security_event(
        request,
        outcome="denied",
        reason_code="insufficient_scope",
        principal=principal,
    )
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add conservative browser-facing security headers to every API response."""

    async def dispatch(self, request: Request, call_next: Callable[..., Any]) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        if settings.DEPLOYMENT_MODE == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
