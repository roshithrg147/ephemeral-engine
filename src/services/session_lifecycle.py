"""Canonical session deletion orchestration and receipts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, Protocol
from uuid import uuid4

from pydantic import BaseModel, Field

from src.memory import MultiTenantSessionRegistry
from src.tools import sandbox_fs


class SandboxStore(Protocol):
    """Filesystem deletion surface required by session lifecycle."""

    def burn_session(
        self,
        session_id: str,
        *,
        tenant_id: str,
        owner_subject: str,
    ) -> sandbox_fs.SandboxBurnResult: ...


class BurnReceipt(BaseModel):
    """One non-secret, machine-verifiable deletion receipt."""

    receipt_id: str
    session_id: str
    status: Literal["deleted", "not_found", "partial_failure"]
    memory_removed: bool
    vector_removed: bool
    sandbox_existed: bool
    sandbox_removed: bool
    errors: list[str] = Field(default_factory=list)
    completed_at: datetime


class SessionLifecycleService:
    """Serialize all session-owned deletion surfaces behind one command."""

    def __init__(
        self,
        registry: MultiTenantSessionRegistry,
        sandbox: SandboxStore = sandbox_fs,
    ) -> None:
        self._registry = registry
        self._sandbox = sandbox

    async def burn(
        self,
        session_id: str,
        *,
        tenant_id: str,
        owner_subject: str,
    ) -> BurnReceipt:
        """Delete registry, vector, and sandbox state under one lifecycle lock."""

        def cleanup_sandbox() -> tuple[bool, bool]:
            outcome = self._sandbox.burn_session(
                session_id,
                tenant_id=tenant_id,
                owner_subject=owner_subject,
            )
            return outcome.existed, outcome.removed

        purge = await self._registry.purge_session(
            session_id,
            tenant_id=tenant_id,
            owner_subject=owner_subject,
            external_cleanup=cleanup_sandbox,
        )
        found = purge.session_found or purge.external_existed
        if not found:
            status: Literal["deleted", "not_found", "partial_failure"] = "not_found"
        elif (
            purge.errors
            or not purge.vector_removed
            or (purge.external_existed and not purge.external_removed)
        ):
            status = "partial_failure"
        else:
            status = "deleted"

        return BurnReceipt(
            receipt_id=str(uuid4()),
            session_id=session_id,
            status=status,
            memory_removed=purge.memory_removed,
            vector_removed=purge.vector_removed,
            sandbox_existed=purge.external_existed,
            sandbox_removed=purge.external_removed,
            errors=list(purge.errors),
            completed_at=datetime.now(UTC),
        )
