"""Database connection and session factory management with resilient test/fallback support."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config import settings
from src.db.base import Base

logger = logging.getLogger("SC-EVM.DB")

_async_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None
_fallback_engine: AsyncEngine | None = None
_fallback_factory: async_sessionmaker[AsyncSession] | None = None
_fallback_tables_created: bool = False


def get_async_engine(db_url: str | None = None) -> AsyncEngine:
    global _async_engine
    if db_url is not None:
        return create_async_engine(db_url, echo=False, future=True)
    if _async_engine is None:
        url = settings.get_async_database_url()
        _async_engine = create_async_engine(url, echo=False, future=True)
    return _async_engine


def get_async_session_factory(engine: AsyncEngine | None = None) -> async_sessionmaker[AsyncSession]:
    global _async_session_factory
    if engine is not None:
        return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    if _async_session_factory is None:
        eng = get_async_engine()
        _async_session_factory = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
    return _async_session_factory


def _get_fallback_factory() -> async_sessionmaker[AsyncSession]:
    global _fallback_engine, _fallback_factory
    if _fallback_factory is None:
        _fallback_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False, future=True)
        _fallback_factory = async_sessionmaker(_fallback_engine, class_=AsyncSession, expire_on_commit=False)
    return _fallback_factory


async def _ensure_fallback_tables() -> None:
    global _fallback_tables_created
    import src.db.models  # noqa: F401

    _get_fallback_factory()
    if not _fallback_tables_created and _fallback_engine is not None:
        async with _fallback_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        _fallback_tables_created = True
        _fallback_tables_created = True


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    factory = get_async_session_factory()
    try:
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    except (OSError, DBAPIError, OperationalError) as exc:
        logger.warning(
            "Primary PostgreSQL engine connection failed (%s); using in-memory test database fallback",
            exc,
        )
        fallback_factory = _get_fallback_factory()
        await _ensure_fallback_tables()
        async with fallback_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise


async def create_tables_async(engine: AsyncEngine | None = None) -> None:
    eng = engine or get_async_engine()
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables_async(engine: AsyncEngine | None = None) -> None:
    eng = engine or get_async_engine()
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
