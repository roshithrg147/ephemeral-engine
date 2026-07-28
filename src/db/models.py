"""PostgreSQL identity, membership, and session authorization models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, TimestampMixin, generate_uuid_str

UserStatus = Literal["active", "suspended", "inactive"]
TenantStatus = Literal["active", "suspended", "inactive"]
MembershipStatus = Literal["active", "suspended", "inactive"]
RoleName = Literal["viewer", "operator", "admin"]
SessionStatus = Literal["active", "burned", "expired"]


class User(Base, TimestampMixin):
    """Authoritative user record mapped to immutable external identity (firebase_uid)."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'suspended', 'inactive')", name="ck_users_status"),
        Index("idx_users_firebase_uid", "firebase_uid", unique=True),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid_str,
    )
    firebase_uid: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    display_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    memberships: Mapped[list[TenantMembership]] = relationship(
        "TenantMembership",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    sessions: Mapped[list[SessionModel]] = relationship(
        "SessionModel",
        back_populates="owner_user",
        cascade="all, delete-orphan",
    )


class Tenant(Base, TimestampMixin):
    """Authoritative tenant organization boundary."""

    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'suspended', 'inactive')", name="ck_tenants_status"),
        Index("idx_tenants_identifier", "identifier", unique=True),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid_str,
    )
    identifier: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
    )

    memberships: Mapped[list[TenantMembership]] = relationship(
        "TenantMembership",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    sessions: Mapped[list[SessionModel]] = relationship(
        "SessionModel",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )


class TenantMembership(Base, TimestampMixin):
    """Authoritative user-to-tenant relationship and role assignment."""

    __tablename__ = "tenant_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "tenant_id", name="uq_user_tenant_membership"),
        CheckConstraint(
            "role IN ('viewer', 'operator', 'admin')",
            name="ck_tenant_memberships_role",
        ),
        CheckConstraint(
            "status IN ('active', 'suspended', 'inactive')",
            name="ck_tenant_memberships_status",
        ),
        Index("idx_memberships_lookup", "user_id", "tenant_id", "status"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid_str,
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="viewer",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
    )

    user: Mapped[User] = relationship("User", back_populates="memberships")
    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="memberships")


class SessionModel(Base, TimestampMixin):
    """Authoritative session ownership and lifecycle record."""

    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'burned', 'expired')",
            name="ck_sessions_status",
        ),
        Index("idx_sessions_tenant_owner", "tenant_id", "owner_user_id", "status"),
    )

    id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    owner_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
    )
    burned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="sessions")
    owner_user: Mapped[User] = relationship("User", back_populates="sessions")


class PrincipalIdentity(Base, TimestampMixin):
    """Normalized identity mapping connecting provider identity to tenant and internal user."""

    __tablename__ = "principal_identities"
    __table_args__ = (
        UniqueConstraint("provider", "provider_subject", name="uq_principal_provider_subject"),
        UniqueConstraint("tenant_id", "canonical_id", name="uq_principal_tenant_canonical"),
        Index("idx_principal_lookup", "provider", "provider_subject", "tenant_id"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid_str,
    )
    tenant_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    provider_subject: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    internal_user_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
    )
    canonical_id: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        index=True,
    )
