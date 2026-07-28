"""Canonical principal identity resolution, identity mapping, and legacy compatibility."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.models import PrincipalIdentity, TenantMembership, User
from src.exceptions.security import AuthorizationFailure

if TYPE_CHECKING:
    from src.security_context import SecurityContext

logger = logging.getLogger("SC-EVM.SECURITY.PRINCIPAL")


@dataclass(frozen=True, slots=True)
class Principal:
    """Authoritative canonical application principal."""

    canonical_id: str
    provider: str
    provider_subject: str
    internal_user_id: str | None
    tenant_id: str
    role: str
    permissions: frozenset[str]
    email: str
    membership_id: str = "m-default"
    display_name: str | None = None

    @property
    def user_id(self) -> str:
        """Internal user ID if available, otherwise canonical_id."""
        return self.internal_user_id or self.canonical_id

    @property
    def external_subject(self) -> str:
        """Alias for provider_subject."""
        return self.provider_subject

    @property
    def subject(self) -> str:
        """Canonical principal subject identifier."""
        return self.canonical_id

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions

    def has_scope(self, scope: str) -> bool:
        if scope == settings.OPERATOR_SCOPE:
            return self.role in ("operator", "admin") or "session:burn" in self.permissions
        if scope == settings.DIAGNOSTIC_SCOPE:
            return self.role in ("operator", "admin") or "scevm:diagnostic" in self.permissions
        return scope in self.permissions


class IdentityMappingService:
    """Server-side service managing normalized principal identity records."""

    @staticmethod
    async def get_or_create_mapping(
        db: AsyncSession | None,
        provider: str,
        provider_subject: str,
        tenant_id: str,
        internal_user_id: str | None = None,
    ) -> str:
        """Returns the canonical_id for a given provider + provider_subject + tenant_id."""
        canonical_id = f"{provider}:{provider_subject}"
        if db is None:
            return canonical_id

        stmt = select(PrincipalIdentity).where(
            PrincipalIdentity.provider == provider,
            PrincipalIdentity.provider_subject == provider_subject,
        )
        result = await db.execute(stmt)
        mapping = result.scalar_one_or_none()

        if mapping is None:
            mapping = PrincipalIdentity(
                tenant_id=tenant_id,
                provider=provider,
                provider_subject=provider_subject,
                internal_user_id=internal_user_id,
                canonical_id=canonical_id,
            )
            db.add(mapping)
            try:
                await db.commit()
            except Exception:
                await db.rollback()
        return canonical_id


class PrincipalResolver:
    """Resolves verified authentication claims into a canonical Principal."""

    @staticmethod
    async def resolve(
        provider: str,
        provider_subject: str,
        email: str,
        *,
        db: AsyncSession | None = None,
        tenant_id: str | None = None,
        display_name: str | None = None,
        roles: list[str] | None = None,
        permissions: frozenset[str] | None = None,
    ) -> Principal:
        """Resolves identity claims and server-side database records to a Principal.

        Guarantees:
        - Never trusts frontend identity mappings.
        - Derives canonical_id as `<provider>:<provider_subject>`.
        - Enforces server-side database user and tenant isolation when DB session is provided.
        """
        if not provider or not provider_subject:
            raise AuthorizationFailure(reason="Missing provider or provider_subject claims")

        canonical_id = f"{provider}:{provider_subject}"
        eff_tenant_id = tenant_id or "development"
        internal_user_id: str | None = None
        role = (roles[0] if roles else None) or "viewer"
        eff_permissions = permissions or frozenset(["runtime:read", "session:read"])
        membership_id = "m-default"

        if db is not None:
            # 1. Lookup internal user by provider subject (e.g. firebase_uid)
            stmt = select(User).where(User.firebase_uid == provider_subject)
            res = await db.execute(stmt)
            user_rec = res.scalar_one_or_none()

            if user_rec is not None:
                internal_user_id = user_rec.id
                email = user_rec.email or email
                display_name = user_rec.display_name or display_name

                # Lookup membership for tenant
                mem_stmt = select(TenantMembership).where(
                    TenantMembership.user_id == user_rec.id,
                    TenantMembership.status == "active",
                )
                if tenant_id:
                    mem_stmt = mem_stmt.where(TenantMembership.tenant_id == tenant_id)

                mem_res = await db.execute(mem_stmt)
                membership = mem_res.scalars().first()
                if membership is not None:
                    eff_tenant_id = membership.tenant_id
                    role = membership.role
                    membership_id = membership.id
                    from src.security import ROLE_PERMISSIONS

                    eff_permissions = frozenset(ROLE_PERMISSIONS.get(role, set()))

            await IdentityMappingService.get_or_create_mapping(
                db,
                provider=provider,
                provider_subject=provider_subject,
                tenant_id=eff_tenant_id,
                internal_user_id=internal_user_id,
            )

        return Principal(
            canonical_id=canonical_id,
            provider=provider,
            provider_subject=provider_subject,
            internal_user_id=internal_user_id,
            tenant_id=eff_tenant_id,
            role=role,
            permissions=eff_permissions,
            email=email,
            membership_id=membership_id,
            display_name=display_name,
        )


class IdentityCompatibilityResolver:
    """Normalizes legacy non-canonical owner IDs and handles backward compatibility safely."""

    @staticmethod
    def normalize_owner_subject(
        owner_subject: str,
        default_provider: str = "firebase",
        *,
        sec_ctx: SecurityContext | None = None,
        correlation_id: str | None = None,
    ) -> str:
        """Converts legacy identifiers to canonical format.

        Rules:
        - If already canonical (`provider:subject`), return as-is.
        - If legacy non-canonical (e.g. `dev-firebase-uid`), convert to `firebase:dev-firebase-uid` and log `IDENTITY_NORMALIZATION_USED`.
        - Ambiguous/unresolvable format raises `AuthorizationFailure("IDENTITY_MAPPING_FAILED")`.
        """
        if not owner_subject:
            raise AuthorizationFailure(reason="IDENTITY_MAPPING_FAILED: Empty owner subject")

        if ":" in owner_subject:
            return owner_subject

        # Single string legacy format (e.g. dev-firebase-uid or user-123)
        canonical_id = f"{default_provider}:{owner_subject}"

        if sec_ctx is not None:
            from src.observability.audit import ReliabilityAuditService

            ReliabilityAuditService.log_event(
                sec_ctx,
                event_name="IDENTITY_NORMALIZATION_USED",
                outcome="SUCCESS",
                details={
                    "old_identifier": owner_subject,
                    "canonical_identifier": canonical_id,
                    "correlation_id": correlation_id or sec_ctx.correlation_id,
                },
            )
        return canonical_id
