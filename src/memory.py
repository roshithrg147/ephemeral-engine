import asyncio
import hashlib
import json
import logging
import os
import tempfile
import threading
import time
import weakref
from collections.abc import Callable, Iterable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection
from filelock import FileLock, Timeout

from src.config import settings

# Telemetry sink for audit compliance
try:
    from telemetry_sink import log_error, log_interaction
except ImportError:
    from src.telemetry_sink import log_error, log_interaction


class SessionLock:
    """
    A session-scoped async lock.
    Supports 'async with' directly as an exclusive write lock.
    The read-lock API is retained for compatibility but uses the same mutex.
    """

    def __init__(self):
        self.write_lock = asyncio.Lock()

    async def __aenter__(self):
        """Acquires the exclusive write lock."""
        await self.acquire_write()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Releases the exclusive write lock."""
        self.release_write()

    async def acquire_write(self):
        await self.write_lock.acquire()

    def release_write(self):
        self.write_lock.release()

    async def acquire_read(self):
        await self.write_lock.acquire()

    def release_read(self):
        self.write_lock.release()

    def read_lock(self):
        """Returns a context manager for concurrent reads."""
        return _SessionReadLock(self)


class _SessionReadLock:
    """Helper context manager class for reading."""

    def __init__(self, lock: SessionLock):
        self.lock = lock

    async def __aenter__(self):
        await self.lock.acquire_read()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.lock.release_read()


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SC-EVM.Memory")

DEFAULT_MEMORY_PATH = os.path.expanduser("~/.assistant_memory.json")
SESSION_TTL_SECONDS = settings.GC_TTL_SECONDS
SESSION_GC_INTERVAL_SECONDS = settings.GC_INTERVAL_SECONDS
MAX_ACTIVE_SESSIONS = settings.MAX_ACTIVE_SESSIONS
_runtime_lock = threading.Lock()
_shared_chroma_client: ClientAPI | None = None
_shared_embedding_fn = None
_calibrated_threshold: float | None = None


def _get_shared_chroma_client() -> ClientAPI:
    global _shared_chroma_client
    if _shared_chroma_client is None:
        with _runtime_lock:
            if _shared_chroma_client is None:
                _shared_chroma_client = chromadb.EphemeralClient()
    return _shared_chroma_client


def _get_shared_embedding_function():
    global _shared_embedding_fn
    if _shared_embedding_fn is None:
        with _runtime_lock:
            if _shared_embedding_fn is None:
                from chromadb.utils import embedding_functions

                _shared_embedding_fn = embedding_functions.ONNXMiniLM_L6_V2()
    return _shared_embedding_fn


def warm_memory_runtime() -> None:
    """Load local vector runtime assets before the service reports ready."""
    _get_shared_chroma_client()
    _get_shared_embedding_function()(["SC-EVM runtime readiness"])


def _ensure_memory_structure(data: dict[str, Any]) -> dict[str, Any]:
    if "user_profile" not in data:
        data["user_profile"] = {}
    if "learned_facts" not in data:
        data["learned_facts"] = []
    if "interaction_stats" not in data:
        data["interaction_stats"] = {
            "total_queries": 0,
            "first_seen": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat(),
        }
    return data


def checksum_history(history: list[dict[str, str]]) -> str:
    """Returns a stable checksum for a session history payload."""
    canonical = json.dumps(history, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class StateManifest:
    session_id: str
    history_checksum: str
    message_count: int
    generated_at: float

    @classmethod
    def from_history(cls, session_id: str, history: list[dict[str, str]]) -> "StateManifest":
        return cls(
            session_id=session_id,
            history_checksum=checksum_history(history),
            message_count=len(history),
            generated_at=time.time(),
        )

    def validate(self, history: list[dict[str, str]]) -> bool:
        return self.message_count == len(history) and self.history_checksum == checksum_history(
            history
        )


@dataclass(frozen=True, slots=True)
class SessionPurgeResult:
    """Serialized purge outcome across registry, vector, and external state."""

    session_found: bool
    memory_removed: bool
    vector_removed: bool
    external_existed: bool
    external_removed: bool
    errors: tuple[str, ...]


class ManifestedHistory(list):
    """List that refreshes a session manifest whenever history is mutated."""

    def __init__(
        self, on_change: Callable[[], None], initial: Iterable[dict[str, str]] | None = None
    ):
        super().__init__(initial or [])
        self._on_change = on_change

    def _changed(self) -> None:
        self._on_change()

    def append(self, item: dict[str, str]) -> None:
        super().append(item)
        self._changed()

    def extend(self, items: Iterable[dict[str, str]]) -> None:
        super().extend(items)
        self._changed()

    def insert(self, index: int, item: dict[str, str]) -> None:
        super().insert(index, item)
        self._changed()

    def pop(self, index: int = -1):
        item = super().pop(index)
        self._changed()
        return item

    def clear(self) -> None:
        super().clear()
        self._changed()

    def __setitem__(self, index, value) -> None:
        super().__setitem__(index, value)
        self._changed()

    def __delitem__(self, index) -> None:
        super().__delitem__(index)
        self._changed()


class MemoryManager:
    """Legacy singleton memory for daemon usage (Not used in the new MultiTenant Web API)."""

    def __init__(self, memory_file_path: str | None = None, *, tenant_id: str = "development", owner_subject: str = "development"):
        if memory_file_path is None or memory_file_path == DEFAULT_MEMORY_PATH:
            safe_tenant = "".join(c if c.isalnum() else "_" for c in tenant_id)[:20]
            safe_owner = "".join(c if c.isalnum() else "_" for c in owner_subject)[:40]
            self.memory_file_path = os.path.expanduser(f"~/.ephemeral-engine/memory/{safe_tenant}/{safe_owner}/memory.json")
        else:
            self.memory_file_path = memory_file_path
        self.lock_file = f"{self.memory_file_path}.lock"
        self.short_term_history: list[dict[str, str]] = []
        self.long_term_data: dict[str, Any] = {
            "user_profile": {},
            "learned_facts": [],
            "interaction_stats": {
                "total_queries": 0,
                "first_seen": datetime.now().isoformat(),
                "last_seen": datetime.now().isoformat(),
            },
        }
        self.load_long_term_memory()

    def load_long_term_memory(self) -> None:
        """Loads persistent long-term memory from the JSON file."""
        if os.path.exists(self.memory_file_path):
            try:
                with FileLock(self.lock_file, timeout=5):
                    with open(self.memory_file_path, encoding="utf-8") as f:
                        self.long_term_data = _ensure_memory_structure(json.load(f))
            except Exception as e:
                logger.error(
                    "Persistent memory load failed; defaults retained",
                    extra={"memory_file_path": self.memory_file_path},
                    exc_info=True,
                )
                log_error("memory.load_long_term_memory", str(e))
        else:
            self.save_long_term_memory()

    def _persist_long_term_memory(self) -> bool:
        try:
            directory = os.path.dirname(self.memory_file_path) or "."
            os.makedirs(directory, exist_ok=True)
            with FileLock(self.lock_file, timeout=5):
                descriptor, temporary_path = tempfile.mkstemp(
                    prefix=".memory-", suffix=".tmp", dir=directory
                )
                try:
                    with os.fdopen(descriptor, "w", encoding="utf-8") as memory_file:
                        json.dump(self.long_term_data, memory_file, indent=2, ensure_ascii=False)
                        memory_file.flush()
                        os.fsync(memory_file.fileno())
                    os.replace(temporary_path, self.memory_file_path)
                finally:
                    if os.path.exists(temporary_path):
                        os.remove(temporary_path)
            return True
        except Timeout:
            logger.error(
                "CRITICAL: Could not acquire lock for memory file. Skipping write to prevent corruption."
            )
            log_error("memory.save_long_term_memory.lock_timeout", self.memory_file_path)
        except Exception as e:
            logger.error("CRITICAL: Persistent memory failure", exc_info=True)
            log_error("memory.save_long_term_memory", str(e))
        return False

    def save_long_term_memory(self) -> None:
        """Saves persistent long-term memory to the JSON file."""
        self._persist_long_term_memory()

    # --- Short term Memory API ---

    def add_interaction(self, user_message: str, assistant_response: str) -> None:
        """Adds a complete turn to the short-term conversation history."""
        self.short_term_history.extend(
            [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": assistant_response},
            ]
        )
        stats = self.long_term_data["interaction_stats"]
        stats["total_queries"] += 1
        stats["last_seen"] = datetime.now().isoformat()
        self.save_long_term_memory()

    def get_short_term_history(self) -> list[dict[str, str]]:
        """Returns the conversation history."""
        return self.short_term_history

    def clear_short_term_history(self) -> None:
        """Clears current session conversation history."""
        self.short_term_history = []

    # --- Long term Memory API ---

    def add_fact(self, fact: str) -> bool:
        """Appends a new fact to learned_facts list if it's not already present."""
        fact = fact.strip()
        if not fact:
            return False

        facts = self.long_term_data["learned_facts"]
        if any(f.lower() == fact.lower() for f in facts):
            return False

        facts.append(fact)
        self.save_long_term_memory()
        return True

    def remove_fact(self, index: int) -> bool:
        """Removes a learned fact by its index."""
        facts = self.long_term_data["learned_facts"]
        if 0 <= index < len(facts):
            facts.pop(index)
            self.save_long_term_memory()
            return True
        return False

    def update_profile(self, key: str, value: str) -> None:
        """Updates user profile attributes (e.g. name, preferences)."""
        self.long_term_data["user_profile"][key] = value
        self.save_long_term_memory()

    def get_long_term_context(self) -> str:
        """Generates a text summary of the long term memory to inject as system prompt context."""
        profile_parts = [f"- {k}: {v}" for k, v in self.long_term_data["user_profile"].items()]
        facts_parts = [f"- {fact}" for fact in self.long_term_data["learned_facts"]]

        summary = ""
        if profile_parts:
            summary += "User Profile Context:\n" + "\n".join(profile_parts) + "\n\n"
        if facts_parts:
            summary += "Learned Facts about User:\n" + "\n".join(facts_parts) + "\n\n"

        return summary


class SessionRecord:
    """
    Volatile state container for a single microservice tenant session.
    Encapsulates memory-confined storage configurations.
    """

    def __init__(
        self,
        session_id: str,
        *,
        tenant_id: str = "development",
        owner_subject: str = "development",
    ):
        self.session_id: str = session_id
        self.tenant_id: str = tenant_id
        self.owner_subject: str = owner_subject
        self.last_accessed: float = time.time()
        self.chat_history: list[dict[str, str]] = []
        
        safe_tenant = "".join(c if c.isalnum() else "_" for c in self.tenant_id)[:20]
        safe_session = "".join(c if c.isalnum() else "_" for c in self.session_id)[:40]
        self.collection_name = f"t_{safe_tenant}_s_{safe_session}"
        
        self.chroma_client = chromadb.EphemeralClient()
        from chromadb.utils import embedding_functions
        try:
            self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=settings.CHROMA_EMBEDDING_MODEL
            )
        except (ImportError, ValueError, Exception):
            self.embedding_fn = _get_shared_embedding_function()
        self.collection: Collection = self.chroma_client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
        
        from src.thresholds import get_engine

        engine = get_engine()
        try:
            base_thresh = engine.calibrate_from_anchors(
                embedding_model=settings.CHROMA_EMBEDDING_MODEL,
                repository=None,
                session_id=session_id,
                embedding_fn=self.embedding_fn,
                positive_anchors=settings.RETRIEVAL_POSITIVE_ANCHORS,
                negative_anchors=settings.RETRIEVAL_NEGATIVE_ANCHORS,
            )
        except Exception:
            base_thresh = None

        self.metadata_registry: dict[str, Any] = {
            "pending_commit_buffer": [],
            "base_threshold": float(base_thresh) if base_thresh is not None else None,
            "development_phase": settings.DEVELOPMENT_PHASE,
            "token_budget": settings.SESSION_TOKEN_BUDGET,
        }
        
        self.refresh_manifest()
        logger.info(
            f"Initialized volatile vector collection space for tenant session: {session_id}"
        )

    def refresh_manifest(self) -> StateManifest:
        self.state_manifest = StateManifest.from_history(self.session_id, self.chat_history)
        return self.state_manifest

    def validate_manifest(self) -> bool:
        if not hasattr(self, "state_manifest") or self.state_manifest is None:
            self.refresh_manifest()
        return self.state_manifest.validate(self.chat_history)


class MultiTenantSessionRegistry:
    """
    Thread-safe concurrency container managing lifecycle state transitions
    across independent memory-mapped tenant profiles.
    """

    def __init__(self):
        self._sessions: dict[str, SessionRecord] = {}
        self._locks: weakref.WeakValueDictionary[str, SessionLock] = weakref.WeakValueDictionary()
        self._gc_task: asyncio.Task | None = None

    def get_session_lock(self, session_id: str) -> SessionLock:
        """
        Retrieves or initializes an atomic lock bound exclusively to the tenant session context.
        """
        lock = self._locks.get(session_id)
        if lock is None:
            lock = SessionLock()
            self._locks[session_id] = lock
        return lock

    def list_session_ids(
        self,
        *,
        tenant_id: str | None = None,
        owner_subject: str | None = None,
        include_tenant: bool = False,
    ) -> list[str]:
        """Return sessions visible to an owner or tenant-scoped operator."""
        if tenant_id is None:
            return list(self._sessions.keys())
        return [
            session_id
            for session_id, session in self._sessions.items()
            if session.tenant_id == tenant_id
            and (include_tenant or session.owner_subject == owner_subject)
        ]

    def _touch_session(self, session: SessionRecord) -> SessionRecord:
        session.last_accessed = time.time()
        return session

    def _get_session_unlocked(self, session_id: str) -> SessionRecord | None:
        return self._sessions.get(session_id)

    @staticmethod
    def _assert_owner(
        session: SessionRecord,
        *,
        tenant_id: str | None,
        owner_subject: str | None,
    ) -> None:
        if tenant_id is None and owner_subject is None:
            return
        if session.tenant_id != tenant_id:
            raise KeyError(f"Session state context uninitialized: {session.session_id}")
        if owner_subject is not None and session.owner_subject != owner_subject:
            raise KeyError(f"Session state context uninitialized: {session.session_id}")

    @asynccontextmanager
    async def _session_scope(
        self,
        session_id: str,
        *,
        create: bool = False,
        tenant_id: str | None = None,
        owner_subject: str | None = None,
    ):
        lock = self.get_session_lock(session_id)
        async with lock:
            session = self._get_session_unlocked(session_id)
            if session is None:
                if not create:
                    raise KeyError(f"Session state context uninitialized: {session_id}")
                await self._evict_capacity_pressure(exclude_session_id=session_id)
                session = SessionRecord(
                    session_id,
                    tenant_id=tenant_id or "development",
                    owner_subject=owner_subject or "development",
                )
                self._sessions[session_id] = session

            self._assert_owner(
                session,
                tenant_id=tenant_id,
                owner_subject=owner_subject,
            )
            session = self._touch_session(session)
            self._guard_session_state(session)
            yield session

    async def initialize_session(
        self,
        session_id: str,
        *,
        tenant_id: str | None = None,
        owner_subject: str | None = None,
    ) -> SessionRecord:
        """
        Dynamically initializes an isolated, memory-confined session profile for a user.
        Uses exclusive write lock.
        """
        async with self._session_scope(
            session_id,
            create=True,
            tenant_id=tenant_id,
            owner_subject=owner_subject,
        ) as session:
            return session

    @asynccontextmanager
    async def session_operation(
        self,
        session_id: str,
        *,
        create: bool = False,
        tenant_id: str | None = None,
        owner_subject: str | None = None,
    ):
        """Hold a session's lifecycle lock for one complete logical operation."""
        async with self._session_scope(
            session_id,
            create=create,
            tenant_id=tenant_id,
            owner_subject=owner_subject,
        ) as session:
            yield session

    async def get_session(
        self,
        session_id: str,
        *,
        tenant_id: str | None = None,
        owner_subject: str | None = None,
    ) -> SessionRecord | None:
        """
        Fetches an existing session profile without forcing side-effect mutations.
        Uses exclusive lock to ensure safe read.
        """
        try:
            async with self._session_scope(
                session_id,
                tenant_id=tenant_id,
                owner_subject=owner_subject,
            ) as session:
                return session
        except KeyError:
            return None

    async def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        *,
        tenant_id: str | None = None,
        owner_subject: str | None = None,
    ) -> None:
        """
        Appends a verified conversation log directly to the tenant's history buffer.
        Uses exclusive write lock.
        """
        async with self._session_scope(
            session_id,
            tenant_id=tenant_id,
            owner_subject=owner_subject,
        ) as session:
            session.chat_history.append({"role": role, "content": content})
            while len(session.chat_history) > settings.MAX_HISTORY_TURNS:
                session.chat_history.pop(0)
            session.refresh_manifest()
            # Log to immutable telemetry sink
            log_interaction(session_id, role, content, tenant_id=session.tenant_id, owner_subject=session.owner_subject)

    async def flush_session(
        self,
        session_id: str,
        *,
        tenant_id: str | None = None,
        owner_subject: str | None = None,
    ) -> bool:
        """
        Removes application access to the isolated session record and deletes
        its ephemeral collection. This does not guarantee physical RAM erasure.
        Uses exclusive write lock.
        """
        result = await self.purge_session(
            session_id,
            tenant_id=tenant_id,
            owner_subject=owner_subject,
        )
        return result.memory_removed

    async def purge_session(
        self,
        session_id: str,
        *,
        tenant_id: str | None = None,
        owner_subject: str | None = None,
        external_cleanup: Callable[[], tuple[bool, bool]] | None = None,
    ) -> SessionPurgeResult:
        """Serialize deletion of registry, vector, and injected external state."""
        lock = self.get_session_lock(session_id)
        async with lock:
            errors: list[str] = []
            session = self._sessions.get(session_id)
            if session is not None:
                self._assert_owner(
                    session,
                    tenant_id=tenant_id,
                    owner_subject=owner_subject,
                )
                self._sessions.pop(session_id)

            vector_removed = session is None
            if session is not None:
                try:
                    session.chroma_client.delete_collection(session.collection.name)
                    vector_removed = True
                except Exception as exc:
                    logger.warning(
                        "Error purging vector space for session",
                        extra={"session_id": session_id},
                        exc_info=True,
                    )
                    log_error("memory.purge_session.delete_collection", str(exc))
                    errors.append("vector_delete_failed")

            external_existed = False
            external_removed = False
            if external_cleanup is not None:
                try:
                    external_existed, external_removed = external_cleanup()
                except Exception:
                    logger.exception(
                        "External session cleanup failed",
                        extra={"session_id": session_id},
                    )
                    errors.append("external_delete_failed")

            if session is not None:
                logger.info(
                    "Programmatic session purge completed",
                    extra={"session_id": session_id},
                )
            return SessionPurgeResult(
                session_found=session is not None,
                memory_removed=session is not None,
                vector_removed=vector_removed,
                external_existed=external_existed,
                external_removed=external_removed,
                errors=tuple(errors),
            )

    def _assert_state_integrity(self, session: SessionRecord) -> None:
        if session.validate_manifest():
            return

        logger.critical(
            "Session state manifest checksum mismatch",
            extra={"session_id": session.session_id},
        )
        log_error("memory.state_manifest.mismatch", session.session_id)
        session.refresh_manifest()
        raise RuntimeError(f"Session state manifest mismatch: {session.session_id}")

    def _guard_session_state(self, session: SessionRecord) -> SessionRecord:
        self._assert_state_integrity(session)
        return session

    async def validate_session_state(self, session_id: str) -> StateManifest:
        async with self._session_scope(session_id) as session:
            return session.state_manifest

    async def refresh_session_manifest(self, session_id: str) -> StateManifest:
        async with self._session_scope(session_id) as session:
            return session.refresh_manifest()

    async def _evict_capacity_pressure(self, exclude_session_id: str | None = None) -> None:
        if len(self._sessions) < MAX_ACTIVE_SESSIONS:
            return

        candidates = [
            (sid, session.last_accessed)
            for sid, session in self._sessions.items()
            if sid != exclude_session_id
        ]
        candidates.sort(key=lambda item: item[1])

        overflow_count = len(self._sessions) - MAX_ACTIVE_SESSIONS + 1
        for sid, _ in candidates[: max(1, overflow_count)]:
            await self.flush_session(sid)
            logger.warning(
                "Evicted session under capacity pressure",
                extra={"session_id": sid, "max_active_sessions": MAX_ACTIVE_SESSIONS},
            )

    async def _ttl_garbage_collector(self):
        """Background daemon to harvest abandoned session footprints."""
        while True:
            await asyncio.sleep(SESSION_GC_INTERVAL_SECONDS)
            current_time = time.time()
            to_flush = [
                sid
                for sid, session in list(self._sessions.items())
                if current_time - session.last_accessed > SESSION_TTL_SECONDS
            ]

            for sid in to_flush:
                try:
                    await self.flush_session(sid)
                    logger.info(
                        "TTL GC successfully harvested abandoned session",
                        extra={"session_id": sid, "ttl_seconds": SESSION_TTL_SECONDS},
                    )
                except Exception as e:
                    logger.error(
                        "TTL GC failed to flush session",
                        extra={"session_id": sid},
                        exc_info=True,
                    )
                    log_error("memory.ttl_gc.flush_session", str(e))

    async def start_daemons(self):
        """Starts background service daemons for session maintenance."""
        if self._gc_task and not self._gc_task.done():
            return
        self._gc_task = asyncio.create_task(self._ttl_garbage_collector())

    async def stop_daemons(self) -> None:
        """Stops background service daemons without leaking pending tasks."""
        task = self._gc_task
        self._gc_task = None
        if task is None or task.done():
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


# Export unified runtime access container
session_registry = MultiTenantSessionRegistry()
