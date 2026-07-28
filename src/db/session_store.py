"""PostgreSQL authoritative session persistence and authorization helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import SessionModel


def utc_now() -> datetime:
    return datetime.now(UTC)


async def sync_session_record_async(
    db: AsyncSession,
    session_id: str,
    tenant_id: str,
    owner_user_id: str,
) -> SessionModel:
    """Create or update a session record in PostgreSQL ensuring tenant and user ownership."""
    query = select(SessionModel).where(SessionModel.id == session_id)
    result = await db.execute(query)
    record = result.scalar_one_or_none()

    if record is None:
        record = SessionModel(
            id=session_id,
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            status="active",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        db.add(record)
    else:
        # Validate existing ownership
        if record.tenant_id != tenant_id or record.owner_user_id != owner_user_id:
            raise KeyError(f"Session {session_id} is owned by another tenant or user")
        record.status = "active"
        record.updated_at = utc_now()

    await db.commit()
    await db.refresh(record)
    return record


async def verify_session_access_async(
    db: AsyncSession,
    session_id: str,
    tenant_id: str,
    owner_user_id: str | None = None,
) -> SessionModel | None:
    """Verify session existence and ownership in PostgreSQL."""
    query = select(SessionModel).where(
        SessionModel.id == session_id,
        SessionModel.tenant_id == tenant_id,
        SessionModel.status == "active",
    )
    if owner_user_id is not None:
        query = query.where(SessionModel.owner_user_id == owner_user_id)

    result = await db.execute(query)
    return result.scalar_one_or_none()


async def list_authorized_sessions_async(
    db: AsyncSession,
    tenant_id: str,
    owner_user_id: str | None = None,
) -> list[str]:
    """List session IDs authorized for a given tenant and optional user."""
    query = select(SessionModel.id).where(
        SessionModel.tenant_id == tenant_id,
        SessionModel.status == "active",
    )
    if owner_user_id is not None:
        query = query.where(SessionModel.owner_user_id == owner_user_id)

    result = await db.execute(query)
    return list(result.scalars().all())


async def burn_session_record_async(
    db: AsyncSession,
    session_id: str,
    tenant_id: str,
    owner_user_id: str | None = None,
) -> bool:
    """Mark session as burned in PostgreSQL."""
    record = await verify_session_access_async(db, session_id, tenant_id, owner_user_id)
    if record is None:
        return False

    record.status = "burned"
    record.burned_at = utc_now()
    record.updated_at = utc_now()
    await db.commit()
    return True
