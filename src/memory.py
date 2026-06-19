import os
import json
import asyncio
import logging
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Any, Optional
import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection

class SessionLock:
    """
    A custom reader-writer lock with writer preference.
    Supports 'async with' directly as an exclusive write lock.
    Exposes 'read_lock()' context manager for concurrent reads.
    """
    def __init__(self):
        self.write_lock = asyncio.Lock()
        self.num_readers = 0
        self.readers_done = asyncio.Event()
        self.readers_done.set()
        self.pending_writers = 0

    async def __aenter__(self):
        """Acquires the exclusive write lock."""
        await self.acquire_write()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Releases the exclusive write lock."""
        self.release_write()

    async def acquire_write(self):
        self.pending_writers += 1
        await self.write_lock.acquire()
        await self.readers_done.wait()

    def release_write(self):
        self.pending_writers -= 1
        self.write_lock.release()

    async def acquire_read(self):
        # If write lock is held or a writer is waiting, wait for the write lock
        if self.write_lock.locked() or self.pending_writers > 0:
            async with self.write_lock:
                pass
        self.num_readers += 1
        self.readers_done.clear()

    def release_read(self):
        self.num_readers -= 1
        if self.num_readers == 0:
            self.readers_done.set()

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

class MemoryManager:
    """Manages short-term (session) and long-term (persistent file) memory for the assistant."""

    def __init__(self, memory_file_path: str = DEFAULT_MEMORY_PATH):
        self.memory_file_path = memory_file_path
        self.short_term_history: List[Dict[str, str]] = []
        self.long_term_data: Dict[str, Any] = {
            "user_profile": {},
            "learned_facts": [],
            "interaction_stats": {
                "total_queries": 0,
                "first_seen": datetime.now().isoformat(),
                "last_seen": datetime.now().isoformat()
            }
        }
        self.load_long_term_memory()

    def load_long_term_memory(self) -> None:
        """Loads persistent long-term memory from the JSON file."""
        if os.path.exists(self.memory_file_path):
            try:
                with open(self.memory_file_path, "r", encoding="utf-8") as f:
                    self.long_term_data = json.load(f)
                # Ensure structure is sound
                if "user_profile" not in self.long_term_data:
                    self.long_term_data["user_profile"] = {}
                if "learned_facts" not in self.long_term_data:
                    self.long_term_data["learned_facts"] = []
                if "interaction_stats" not in self.long_term_data:
                    self.long_term_data["interaction_stats"] = {
                        "total_queries": 0,
                        "first_seen": datetime.now().isoformat(),
                        "last_seen": datetime.now().isoformat()
                    }
            except Exception as e:
                # If corrupt or error, keep defaults
                pass
        else:
            self.save_long_term_memory()

    def save_long_term_memory(self) -> None:
        """Saves persistent long-term memory to the JSON file."""
        try:
            # Ensure folder exists
            os.makedirs(os.path.dirname(self.memory_file_path), exist_ok=True)
            with open(self.memory_file_path, "w", encoding="utf-8") as f:
                json.dump(self.long_term_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            # Silently ignore write failures if permissions are lacking
            pass

    # --- Short term Memory API ---

    def add_interaction(self, user_message: str, assistant_response: str) -> None:
        """Adds a complete turn to the short-term conversation history."""
        self.short_term_history.append({"role": "user", "content": user_message})
        self.short_term_history.append({"role": "assistant", "content": assistant_response})

        # Update metrics
        stats = self.long_term_data["interaction_stats"]
        stats["total_queries"] += 1
        stats["last_seen"] = datetime.now().isoformat()
        self.save_long_term_memory()

    def get_short_term_history(self) -> List[Dict[str, str]]:
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
        # Simple deduplication check (case-insensitive)
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
        profile_parts = []
        for k, v in self.long_term_data["user_profile"].items():
            profile_parts.append(f"- {k}: {v}")

        facts_parts = []
        for fact in self.long_term_data["learned_facts"]:
            facts_parts.append(f"- {fact}")

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
    def __init__(self, session_id: str):
        self.session_id: str = session_id
        self.chat_history: List[Dict[str, str]] = []
        self.metadata_registry: Dict[str, Any] = {
            "pending_commit_buffer": [],
            "base_threshold": 0.52,
            "token_budget": 2500
        }
        # Initialize isolated, memory-mapped storage engine
        from chromadb.utils import embedding_functions
        self.chroma_client: ClientAPI = chromadb.EphemeralClient()
        self.embedding_fn = embedding_functions.ONNXMiniLM_L6_V2()
        self.collection: Collection = self.chroma_client.get_or_create_collection(
            name=f"session_{session_id}",
            embedding_function=self.embedding_fn
        )
        logger.info(f"Initialized volatile vector collection space for tenant session: {session_id}")


class MultiTenantSessionRegistry:
    """
    Thread-safe concurrency container managing lifecycle state transitions
    across independent memory-mapped tenant profiles.
    """
    def __init__(self):
        self._sessions: Dict[str, SessionRecord] = {}
        self.locks: defaultdict[str, SessionLock] = defaultdict(SessionLock)
        self._locks = self.locks  # Maintain compatibility
        self._global_lock: asyncio.Lock = asyncio.Lock()

    async def get_session_lock(self, session_id: str) -> SessionLock:
        """
        Retrieves or initializes an atomic lock bound exclusively to the tenant session context.
        """
        return self.locks[session_id]

    async def initialize_session(self, session_id: str) -> SessionRecord:
        """
        Dynamically initializes an isolated, memory-confined session profile for a user.
        Uses exclusive write lock.
        """
        async with self.locks[session_id]:
            if session_id not in self._sessions:
                self._sessions[session_id] = SessionRecord(session_id)
            return self._sessions[session_id]

    async def get_session(self, session_id: str) -> Optional[SessionRecord]:
        """
        Fetches an existing session profile without forcing side-effect mutations.
        Uses concurrent read lock.
        """
        async with self.locks[session_id].read_lock():
            return self._sessions.get(session_id)

    async def append_message(self, session_id: str, role: str, content: str) -> None:
        """
        Appends a verified conversation log directly to the tenant's history buffer.
        Uses exclusive write lock.
        """
        async with self.locks[session_id]:
            if session_id in self._sessions:
                self._sessions[session_id].chat_history.append({"role": role, "content": content})
            else:
                raise KeyError(f"Session state context uninitialized: {session_id}")

    async def flush_session(self, session_id: str) -> bool:
        """
        Forces a physical memory purge of the isolated session record.
        Wipes the ephemeral client allocation completely.
        Uses exclusive write lock.
        """
        async with self.locks[session_id]:
            async with self._global_lock:
                if session_id in self._sessions:
                    # Wipe memory structures explicitly
                    session = self._sessions[session_id]
                    try:
                        session.chroma_client.delete_collection(f"session_{session_id}")
                    except Exception as e:
                        logger.warning(f"Error purging vector space for session {session_id}: {e}")

                    del self._sessions[session_id]
                    if session_id in self.locks:
                        del self.locks[session_id]
                    logger.info(f"Programmatic /burn executed successfully. Purged space for: {session_id}")
                    return True
                return False

# Export unified runtime access container
session_registry = MultiTenantSessionRegistry()
