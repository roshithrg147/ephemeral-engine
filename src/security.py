"""Authentication, principal extraction, and API security response controls."""

from __future__ import annotations

import asyncio
import hashlib
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
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from src.config import settings

logger = logging.getLogger("SC-EVM.Security")
bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class Principal:
    """Verified caller identity used for ownership and scope decisions."""

    subject: str
    tenant_id: str
    scopes: frozenset[str]

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes


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

    def _decode(self, token: str, key: Any) -> Principal:
        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=list(self.algorithms),
                issuer=self.issuer,
                audience=self.audience,
                leeway=self.clock_skew_seconds,
                options={"require": ["exp", "iat", "sub", "tenant_id"]},
            )
        except (InvalidTokenError, ValueError, TypeError) as exc:
            raise AuthenticationError("invalid_token") from exc

        subject = claims.get("sub")
        tenant_id = claims.get("tenant_id")
        if not isinstance(subject, str) or not subject.strip():
            raise AuthenticationError("invalid_subject")
        if not isinstance(tenant_id, str) or not tenant_id.strip():
            raise AuthenticationError("invalid_tenant")
        return Principal(
            subject=subject,
            tenant_id=tenant_id,
            scopes=_parse_scopes(claims),
        )

    def validate(self, token: str) -> Principal:
        """Validate with an injected synchronous key resolver, primarily for isolated tests."""
        if self._signing_key_resolver is None:
            raise RuntimeError("Use validate_async when resolving keys from JWKS")
        try:
            key = self._signing_key_resolver(token)
        except (InvalidTokenError, ValueError, TypeError) as exc:
            raise AuthenticationError("invalid_token") from exc
        return self._decode(token, key)

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

    async def validate_async(self, token: str) -> Principal:
        key = await self._resolve_signing_key_async(token)
        return self._decode(token, key)


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
    principal_hash = None
    tenant_id = None
    if principal is not None:
        principal_hash = hashlib.sha256(principal.subject.encode("utf-8")).hexdigest()[:16]
        tenant_id = principal.tenant_id
    logger.info(
        "security_decision",
        extra={
            "method": request.method,
            "path": request.url.path,
            "outcome": outcome,
            "reason_code": reason_code,
            "principal_hash": principal_hash,
            "tenant_id": tenant_id,
        },
    )


def _unauthorized(reason_code: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


_FIREBASE_APP_INITIALIZED = False


# Development-mode token management (in-memory)
DEV_ACCESS_TOKEN_TTL = 3600
DEV_REFRESH_TOKEN_TTL = 7 * 24 * 3600
_ISSUED_DEV_TOKENS: dict[str, dict] = {}


def issue_dev_tokens(email: str) -> tuple[str, str]:
    now = time.time()
    access_token = f"development-token-{hashlib.sha256(f'{email}:{now}'.encode('utf-8')).hexdigest()}"
    refresh_token = f"development-refresh-{hashlib.sha256(f'refresh:{email}:{now}'.encode('utf-8')).hexdigest()}"
    _ISSUED_DEV_TOKENS[access_token] = {
        "email": email,
        "issued_at": now,
        "access_expires_at": now + DEV_ACCESS_TOKEN_TTL,
        "refresh_token": refresh_token,
        "refresh_expires_at": now + DEV_REFRESH_TOKEN_TTL,
        "revoked": False,
    }
    return access_token, refresh_token


def _find_by_refresh_token(refresh_token: str) -> tuple[str, dict] | None:
    for at, meta in list(_ISSUED_DEV_TOKENS.items()):
        if meta.get("refresh_token") == refresh_token:
            return at, meta
    return None


def refresh_dev_token(refresh_token: str) -> tuple[str, str] | None:
    pair = _find_by_refresh_token(refresh_token)
    if not pair:
        return None
    access_token, meta = pair
    now = time.time()
    if meta.get("refresh_expires_at", 0) < now or meta.get("revoked"):
        return None
    # rotate tokens
    email = meta.get("email")
    # revoke old access token
    meta["revoked"] = True
    new_access, new_refresh = issue_dev_tokens(email)
    return new_access, new_refresh


def revoke_dev_token(token: str) -> bool:
    # try access token
    meta = _ISSUED_DEV_TOKENS.get(token)
    if meta:
        meta["revoked"] = True
        return True
    # try refresh token
    pair = _find_by_refresh_token(token)
    if pair:
        at, meta = pair
        meta["revoked"] = True
        return True
    return False


def validate_dev_access_token(token: str) -> dict | None:
    meta = _ISSUED_DEV_TOKENS.get(token)
    if not meta or meta.get("revoked"):
        return None
    if meta.get("access_expires_at", 0) < time.time():
        return None
    return meta


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


async def verify_firebase_token_async(token: str) -> Principal:
    """Verify a Firebase ID token using firebase_admin.auth."""
    try:
        from firebase_admin import auth

        _init_firebase_app()
        decoded = await asyncio.to_thread(auth.verify_id_token, token)
    except Exception as exc:
        raise AuthenticationError("invalid_firebase_token") from exc

    subject = decoded.get("uid") or decoded.get("sub")
    tenant_id = decoded.get("tenant_id") or decoded.get("firebase", {}).get("tenant") or subject
    if not isinstance(subject, str) or not subject.strip():
        raise AuthenticationError("invalid_subject")
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        tenant_id = subject

    scopes = _parse_scopes(decoded)
    if not scopes:
        scopes = frozenset({settings.DIAGNOSTIC_SCOPE, settings.OPERATOR_SCOPE})

    return Principal(
        subject=subject,
        tenant_id=tenant_id,
        scopes=scopes,
    )


async def get_current_principal(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> Principal:
    """Resolve development identity or verify production OIDC / Firebase bearer token."""
    if settings.AUTH_MODE == "disabled":
        # If no credentials provided, return default development principal
        if credentials is None or credentials.scheme.lower() != "bearer":
            return Principal(
                subject="development",
                tenant_id="development",
                scopes=frozenset({settings.DIAGNOSTIC_SCOPE, settings.OPERATOR_SCOPE}),
            )

        token = credentials.credentials
        # Handle dev tokens issued by /api/auth/login
        if token.startswith("development-token-") or token.startswith("development-refresh-"):
            meta = validate_dev_access_token(token)
            if not meta:
                log_security_event(request, outcome="denied", reason_code="invalid_token")
                raise _unauthorized("invalid_token")

            principal = Principal(
                subject=f"dev-{meta.get('email')}",
                tenant_id="development",
                scopes=frozenset({settings.DIAGNOSTIC_SCOPE, settings.OPERATOR_SCOPE}),
            )
            log_security_event(request, outcome="allowed", reason_code="authenticated", principal=principal)
            return principal

        # Try verifying as Firebase ID token
        try:
            principal = await verify_firebase_token_async(token)
            log_security_event(request, outcome="allowed", reason_code="authenticated", principal=principal)
            return principal
        except Exception:
            pass

        # In development mode, fallback to development principal if token is unrecognized
        principal = Principal(
            subject="development",
            tenant_id="development",
            scopes=frozenset({settings.DIAGNOSTIC_SCOPE, settings.OPERATOR_SCOPE}),
        )
        log_security_event(request, outcome="allowed", reason_code="authenticated_fallback", principal=principal)
        return principal

    if credentials is None or credentials.scheme.lower() != "bearer":
        log_security_event(request, outcome="denied", reason_code="missing_bearer")
        raise _unauthorized("missing_bearer")

    if settings.AUTH_MODE == "firebase":
        try:
            principal = await verify_firebase_token_async(credentials.credentials)
        except AuthenticationError as exc:
            log_security_event(request, outcome="denied", reason_code=exc.reason_code)
            raise _unauthorized(exc.reason_code) from exc
        log_security_event(
            request,
            outcome="allowed",
            reason_code="authenticated",
            principal=principal,
        )
        return principal

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
        principal = await validator.validate_async(credentials.credentials)
    except AuthenticationError as exc:
        log_security_event(request, outcome="denied", reason_code=exc.reason_code)
        raise _unauthorized(exc.reason_code) from exc

    log_security_event(
        request,
        outcome="allowed",
        reason_code="authenticated",
        principal=principal,
    )
    return principal


def require_scope(request: Request, principal: Principal, scope: str) -> None:
    if principal.has_scope(scope):
        return
    log_security_event(
        request,
        outcome="denied",
        reason_code="insufficient_scope",
        principal=principal,
    )
    raise HTTPException(status_code=403, detail="Insufficient permissions")


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


import re

INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(?:all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"system\s+prompt\s+override", re.IGNORECASE),
    re.compile(r"disregard\s+(?:above|prior)\s+rules", re.IGNORECASE),
    re.compile(r"you\s+are\n+now\s+in\s+DAN\s+mode", re.IGNORECASE),
]


def sanitize_user_input(text: str) -> str:
    """Sanitize user input by stripping control characters and null bytes."""
    if not text or not isinstance(text, str):
        return ""
    # Strip non-printable control characters except newline, tab, carriage return
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)
    return cleaned.strip()


def protect_prompt_assembly(system_prompt: str, user_prompt: str) -> str:
    """Sanitize and assembly-protect system and user prompt pairs against jailbreaks."""
    clean_sys = sanitize_user_input(system_prompt)
    clean_user = sanitize_user_input(user_prompt)

    for pat in INJECTION_PATTERNS:
        clean_user = pat.sub("[REDACTED_INJECTION_ATTEMPT]", clean_user)

    return f"{clean_sys}\n\nUser Prompt:\n{clean_user}"


def protect_context_injection(retrieved_text: str) -> str:
    """Sanitize retrieved memory context to prevent malicious instructions injection."""
    clean_text = sanitize_user_input(retrieved_text)

    for pat in INJECTION_PATTERNS:
        clean_text = pat.sub("[REDACTED_CONTEXT_INJECTION]", clean_text)

    return clean_text
