import asyncio
import logging
import time
import uuid

from src.agent import MemorySnapshot
from src.telemetry_sink import log_error

try:
    from chromadb.errors import NotFoundError
except ImportError:
    NotFoundError = None


logger = logging.getLogger("SC-EVM.SessionRuntime")
_background_tasks: set[asyncio.Task] = set()


def build_memory_snapshot(record, session_id: str = "") -> MemorySnapshot:
    facts = record.metadata_registry.get("learned_facts", [])
    long_term_context = ""
    if facts:
        long_term_context = (
            "Learned Facts about User:\n" + "\n".join(f"- {fact}" for fact in facts) + "\n"
        )
    return MemorySnapshot(
        session_id=session_id,
        long_term_context=long_term_context,
        short_term_history=list(record.chat_history),
    )


def commit_remembered_facts(record, facts: list[str]) -> None:
    remembered_facts = record.metadata_registry.setdefault("learned_facts", [])
    for fact in facts:
        normalized = fact.strip()
        if not normalized:
            continue
        if any(existing.lower() == normalized.lower() for existing in remembered_facts):
            continue
        remembered_facts.append(normalized)


def create_tracked_task(coro) -> asyncio.Task:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)

    def _complete(completed: asyncio.Task) -> None:
        _background_tasks.discard(completed)
        if completed.cancelled():
            return
        try:
            completed.result()
        except Exception:
            logger.exception("Background task failed")

    task.add_done_callback(_complete)
    return task


async def await_background_tasks() -> None:
    if not _background_tasks:
        return
    logger.info("Awaiting %d pending background tasks...", len(_background_tasks))
    await asyncio.gather(*_background_tasks, return_exceptions=True)


async def get_indexed_documents(record, session_id: str) -> list[str]:
    def _get_documents() -> list[str]:
        res = record.collection.get(where={"session_id": session_id})
        if res and "documents" in res:
            return res["documents"]
        return []

    return await asyncio.to_thread(_get_documents)


async def embed_text(record, text: str) -> list[float]:
    return await asyncio.to_thread(lambda: record.embedding_fn([text])[0])


async def index_interaction(record, session_id: str, index_chunk: str) -> None:
    from src.memory import session_registry

    existing = await session_registry.get_session(session_id)
    if existing is not record:
        logger.info(
            "Background indexing aborted: session was burned or replaced.",
            extra={"session_id": session_id},
        )
        return

    def _sync_indexing_task() -> None:
        vector = record.embedding_fn([index_chunk])[0]
        doc_id = str(uuid.uuid4())
        record.collection.add(
            ids=[doc_id],
            embeddings=[vector],
            documents=[index_chunk],
            metadatas=[{"timestamp": int(time.time()), "session_id": session_id}],
        )

    try:
        await asyncio.to_thread(_sync_indexing_task)
    except Exception as exc:
        if NotFoundError is not None and isinstance(exc, NotFoundError):
            logger.info(
                "Background indexing aborted: Collection deleted (likely by /burn).",
                extra={"session_id": session_id},
            )
            return

        logger.error(
            "Background indexing commit failed",
            extra={"session_id": session_id},
            exc_info=True,
        )
        log_error("api.background_indexing", str(exc))
