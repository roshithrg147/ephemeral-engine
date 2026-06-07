import asyncio
from typing import Dict, List, Any
from pydantic import BaseModel, Field

class MemoryRegistrationRecord(BaseModel):
    """Pydantic V2 schema tracking tenant session data including chat history, metadata registry, and confidence anchors."""
    session_id: str
    chat_history: List[Dict[str, str]] = Field(default_factory=list)
    metadata_registry: Dict[str, Any] = Field(default_factory=dict)
    confidence_anchors: List[Dict[str, Any]] = Field(default_factory=list)

class MultiTenantSessionRegistry:
    """Thread-safe, async-safe, volatile memory registry container tracking active sessions strictly in-memory."""
    
    def __init__(self) -> None:
        self._global_lock: asyncio.Lock = asyncio.Lock()
        self._session_locks: Dict[str, asyncio.Lock] = {}
        self._sessions: Dict[str, MemoryRegistrationRecord] = {}

    async def get_session_lock(self, session_id: str) -> asyncio.Lock:
        """Retrieves or creates a unique asyncio.Lock for the requested session ID under a global lock."""
        async with self._global_lock:
            if session_id not in self._session_locks:
                self._session_locks[session_id] = asyncio.Lock()
            return self._session_locks[session_id]

    async def initialize_session(self, session_id: str) -> MemoryRegistrationRecord:
        """Allocates resources and registers a session_id if it does not already exist."""
        async with self._global_lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = MemoryRegistrationRecord(session_id=session_id)
                if session_id not in self._session_locks:
                    self._session_locks[session_id] = asyncio.Lock()
            return self._sessions[session_id]

    async def append_message(self, session_id: str, role: str, content: str) -> None:
        """Appends a dialogue turn to the session's chat history under the session's sub-lock."""
        session_lock = await self.get_session_lock(session_id)
        async with session_lock:
            # Ensure session is initialized
            await self.initialize_session(session_id)
            record = self._sessions[session_id]
            record.chat_history.append({"role": role, "content": content})

    async def get_history(self, session_id: str) -> List[Dict[str, str]]:
        """Retrieves conversation history for a specific session ID under its sub-lock."""
        session_lock = await self.get_session_lock(session_id)
        async with session_lock:
            await self.initialize_session(session_id)
            return list(self._sessions[session_id].chat_history)

    async def flush_session(self, session_id: str) -> None:
        """Purges active sessions and locks from memory, ensuring zero persistent disk residue."""
        async with self._global_lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
            if session_id in self._session_locks:
                del self._session_locks[session_id]
