import asyncio
import concurrent.futures
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any, Literal

from fastapi import FastAPI, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.agent import AgentOrchestrator
from src.config import settings
from src.memory import session_registry, warm_memory_runtime
from src.sc_evm import SCEVMEngine
from src.services.error_handlers import GlobalExceptionHandler
from src.services.model_connector import ModelConnector
from src.services.prompt_manager import PromptManager
from src.services.session_runtime import (
    await_background_tasks,
    build_memory_snapshot,
    commit_remembered_facts,
    create_tracked_task,
    embed_text,
    get_indexed_documents,
    index_interaction,
)
from src.telemetry_sink import log_error

# Instantiate a global instance of SCEVMEngine containing the NVIDIA client
sc_evm_engine = SCEVMEngine()
prompt_manager = PromptManager()
logger = logging.getLogger("SC-EVM.API")

_ORCHESTRATOR: Any | None = None
_ORCHESTRATOR_LOCK: asyncio.Lock = asyncio.Lock()
_ORCHESTRATION_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=settings.MAX_WORKER_THREADS,
    thread_name_prefix="sc-evm-orchestration",
)


async def run_orchestrator(orchestrator: AgentOrchestrator, memory_snapshot: Any, prompt: str):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _ORCHESTRATION_EXECUTOR,
        orchestrator.generate_response,
        memory_snapshot,
        prompt,
    )


async def get_orchestrator() -> AgentOrchestrator:
    global _ORCHESTRATOR
    if _ORCHESTRATOR is None:
        async with _ORCHESTRATOR_LOCK:
            if _ORCHESTRATOR is None:
                _ORCHESTRATOR = AgentOrchestrator(model_connector=ModelConnector())
    return _ORCHESTRATOR


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event manager for startup diagnostics and graceful shutdown."""
    logger.info("Verifying local NVIDIA API key configuration...")
    key = settings.NVIDIA_API_KEY or settings.NVIDIA_API_KEY_KIWI or settings.NVIDIA_API_KEY_QWEN
    if key:
        logger.info("Local NVIDIA connection verification: SUCCESSFUL.")
    else:
        logger.warning("Local NVIDIA connection verification: FAILED (API Key missing).")
    logger.info("Warming local memory runtime...")
    await asyncio.to_thread(warm_memory_runtime)
    await session_registry.start_daemons()
    try:
        yield
    finally:
        await session_registry.stop_daemons()
        await await_background_tasks()
        from src.clients import NVIDIA_NIM_Client

        await NVIDIA_NIM_Client.aclose()
        logger.info("SC-EVM shutdown complete.")


app = FastAPI(title="State-Cached Ephemeral Vector Memory (SC-EVM) Microservice", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(Exception, GlobalExceptionHandler.handle)


@app.get("/")
async def get_health():
    """Health check endpoint for the SC-EVM backend."""
    return {"status": "online", "message": "SC-EVM Backend Engine Running"}


# --- Ingestion Contracts / Schemas ---

SessionId = Annotated[
    str,
    Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$"),
]
PromptText = Annotated[str, Field(min_length=1, max_length=100_000)]


class SessionInitRequest(BaseModel):
    session_id: SessionId


class ChatMessageInput(BaseModel):
    session_id: SessionId
    role: Literal["user", "assistant", "system"]
    content: PromptText


class ExecutionQueryRequest(BaseModel):
    session_id: SessionId
    prompt: PromptText
    graphify_enabled: bool = True
    diagnostic_mode: bool = False


class StandardResponseEnvelope(BaseModel):
    status: str
    message: str
    data: Any | None = None


# --- Network Interface Controllers ---


@app.get("/api/session/list", response_model=StandardResponseEnvelope)
async def list_sessions() -> StandardResponseEnvelope:
    """Retrieves a list of all active session IDs."""
    try:
        session_ids = session_registry.list_session_ids()
        return StandardResponseEnvelope(
            status="success", message="Sessions listed successfully", data=session_ids
        )
    except Exception as e:
        logger.exception("Failed to list sessions")
        raise HTTPException(status_code=500, detail="Failed to list sessions") from e


@app.post("/api/session/initialize", response_model=StandardResponseEnvelope)
async def initialize_session(body: SessionInitRequest) -> StandardResponseEnvelope:
    """Invokes the session_registry.initialize_session lifecycle logic."""
    try:
        await session_registry.initialize_session(body.session_id)
        return StandardResponseEnvelope(
            status="success", message=f"Session {body.session_id} initialized successfully"
        )
    except Exception as e:
        logger.exception("Failed to initialize session", extra={"session_id": body.session_id})
        raise HTTPException(status_code=500, detail="Failed to initialize session") from e


@app.post("/api/session/message", response_model=StandardResponseEnvelope)
async def append_message(body: ChatMessageInput) -> StandardResponseEnvelope:
    """Manually synchronizes conversational entries under session-specific sub-locks."""
    try:
        await session_registry.append_message(body.session_id, body.role, body.content)
        return StandardResponseEnvelope(
            status="success", message="Message successfully appended to session history"
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail="Session not found") from e
    except Exception as e:
        logger.exception("Failed to append message", extra={"session_id": body.session_id})
        raise HTTPException(status_code=500, detail="Failed to append message") from e


@app.delete("/api/session/burn/{session_id}", response_model=StandardResponseEnvelope)
async def burn_session(
    session_id: Annotated[
        str, Path(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    ],
) -> StandardResponseEnvelope:
    """Completely purges the volatile RAM footprint and ChromaDB collection for a session."""
    try:
        await session_registry.flush_session(session_id)
        return StandardResponseEnvelope(
            status="success", message=f"Session {session_id} successfully flushed from memory"
        )
    except Exception as e:
        logger.exception("Failed to flush session", extra={"session_id": session_id})
        raise HTTPException(status_code=500, detail="Failed to flush session") from e


@app.get("/api/session/history/{session_id}", response_model=StandardResponseEnvelope)
async def get_session_history(
    session_id: Annotated[
        str, Path(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    ],
) -> StandardResponseEnvelope:
    """Retrieves conversation history for a specific session ID."""
    try:
        record = await session_registry.get_session(session_id)
        if not record:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        return StandardResponseEnvelope(
            status="success", message="History retrieved successfully", data=record.chat_history
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to retrieve history", extra={"session_id": session_id})
        raise HTTPException(status_code=500, detail="Failed to retrieve history") from e


@app.get("/api/session/memory/{session_id}", response_model=StandardResponseEnvelope)
async def get_session_memory(
    session_id: Annotated[
        str, Path(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    ],
) -> StandardResponseEnvelope:
    """Retrieves index contents and metadata registry for a session."""
    try:
        record = await session_registry.get_session(session_id)
        if not record:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        try:
            docs = await get_indexed_documents(record, session_id)
        except Exception as e:
            logger.error(
                "Failed to fetch indexed documents from collection",
                extra={"session_id": session_id},
                exc_info=True,
            )
            log_error("api.session_memory.collection_get", str(e))
            docs = []

        return StandardResponseEnvelope(
            status="success",
            message="Memory data retrieved successfully",
            data={
                "pending_commit_buffer": record.metadata_registry.get("pending_commit_buffer", []),
                "base_threshold": record.metadata_registry.get(
                    "base_threshold", settings.RETRIEVAL_BASE_DISTANCE_THRESHOLD
                ),
                "token_budget": record.metadata_registry.get(
                    "token_budget", settings.SESSION_TOKEN_BUDGET
                ),
                "indexed_documents": docs,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to retrieve memory", extra={"session_id": session_id})
        raise HTTPException(status_code=500, detail="Failed to retrieve memory") from e


async def sse_query_generator(
    session_id: str, prompt: str, graphify_enabled: bool = True, diagnostic_mode: bool = False
) -> AsyncIterator[str]:
    """Generates server-sent events for query reformulation, context retrieval, and response content streams."""
    async with session_registry.session_operation(session_id, create=True) as record:
        async for event in _sse_query_generator_locked(
            record,
            session_id,
            prompt,
            graphify_enabled,
            diagnostic_mode,
        ):
            yield event


async def _sse_query_generator_locked(
    record: Any,
    session_id: str,
    prompt: str,
    graphify_enabled: bool,
    diagnostic_mode: bool,
) -> AsyncIterator[str]:
    """Run one complete query while the session lifecycle lock is held."""
    history = list(record.chat_history)
    memory_snapshot = build_memory_snapshot(record)
    memory_anchors = record.metadata_registry.get(
        "learned_facts", []
    ) + record.metadata_registry.get("pending_commit_buffer", [])
    pending_mems = list(record.metadata_registry.get("pending_commit_buffer", []))
    base_threshold = record.metadata_registry.get(
        "base_threshold", settings.RETRIEVAL_BASE_DISTANCE_THRESHOLD
    )

    try:
        docs = await get_indexed_documents(record, session_id)
    except Exception as e:
        logger.error(
            "Failed to fetch metadata documents from collection",
            extra={"session_id": session_id},
            exc_info=True,
        )
        log_error("api.sse.metadata_collection_get", str(e))
        docs = []
    tokens_saved = sum(len(d) // 4 for d in docs) * 2

    yield f"event: metadata\ndata: {json.dumps({'tokensSaved': tokens_saved, 'memoryAnchors': memory_anchors})}\n\n"

    # 2. Query Reformulation using NVIDIA NIM Qwen model
    rewrite_usage = None
    try:
        reformulation_res = await sc_evm_engine.run_query_reformulation_async(prompt, history)
        if len(reformulation_res) == 3:
            search_vector_query, grounded_llm_prompt, rewrite_usage = reformulation_res
        else:
            search_vector_query, grounded_llm_prompt = reformulation_res
            rewrite_usage = None
    except Exception as e:
        logger.error(
            "Query reformulation failed; falling back to raw prompt",
            extra={"session_id": session_id},
            exc_info=True,
        )
        log_error("api.sse.query_reformulation", str(e))
        search_vector_query = prompt
        grounded_llm_prompt = prompt

    yield f"event: query_reformulation\ndata: {json.dumps({'search_vector_query': search_vector_query, 'grounded_llm_prompt': grounded_llm_prompt})}\n\n"

    # 3. Retrieve Context & Apply Parallel Context Fusion
    context_str = ""
    try:
        # Generate query vector locally using the session's ONNX embedding function
        query_vector = await embed_text(record, search_vector_query)

        # Evaluate context using parallel retrieval from Vector DB and Graphify
        context_str = await sc_evm_engine.evaluate_query_context(
            query_vector=query_vector,
            collection=record.collection,
            session_id=session_id,
            base_threshold=base_threshold,
            entity_id=search_vector_query,
            graphify_enabled=graphify_enabled,
        )
    except Exception as e:
        logger.error(
            "Parallel context retrieval failed",
            extra={"session_id": session_id},
            exc_info=True,
        )
        log_error("api.sse.context_retrieval", str(e))

    if settings.DIAGNOSTIC_MODE or diagnostic_mode:
        yield f"event: retrieved_context\ndata: {json.dumps([context_str])}\n\n"

    # 4. Synthesize context blocks and execute primary reasoning stream
    context_list = []
    if context_str:
        context_list.append(context_str)

    # Merge volatile in-memory buffer interceptors (mapped to metadata_registry keys)
    for pending in pending_mems:
        context_list.append(
            f"<retrieved_memory>\n[Pending Active Queue Context (Unindexed)]:\n{pending}\n</retrieved_memory>"
        )

    context_str = "\n\n".join(context_list)

    # 4. Invoke Dual-LLM Agent Orchestrator to generate response and actions
    orchestrator = await get_orchestrator()

    # Build augmented prompt for the orchestrator, passing SC-EVM context
    augmented_prompt = prompt_manager.build_augmented_prompt(
        context_str=context_str, grounded_llm_prompt=grounded_llm_prompt
    )

    full_response_text = ""
    action_payload = {"type": "none"}
    refined_response = None
    generation_succeeded = False

    try:
        refined_response = await run_orchestrator(orchestrator, memory_snapshot, augmented_prompt)
        commit_remembered_facts(record, refined_response.remember)

        full_response_text = refined_response.text
        generation_succeeded = True

        # Format action payload
        action_payload = _build_action_payload(refined_response.action)
        if action_payload:
            full_response_text, action_type, payload = _apply_phase_gate(
                record,
                full_response_text,
                action_payload["type"],
                action_payload["payload"],
            )

            action_payload = {"type": action_type, "payload": payload}

        # Staged response delivery: Yield the complete staged response content in a single event without delay
        yield f"event: response_content\ndata: {json.dumps(full_response_text)}\n\n"

        # Yield action payload over SSE
        yield f"event: action\ndata: {json.dumps(action_payload)}\n\n"

        # Compile and yield the detailed cost accounting usage report
        from src.clients import get_model_price

        rewrite_record = []
        if rewrite_usage:
            rewrite_record.append(
                {
                    "measurement_type": "exact",
                    "provider": "nvidia",
                    "model": settings.MODEL_2_CORE,
                    "tokenizer": None,
                    "input_tokens": rewrite_usage.get("prompt_tokens"),
                    "output_tokens": rewrite_usage.get("completion_tokens"),
                    "cached_tokens": None,
                    "retry_usage": None,
                    "missing_reason": None,
                    "price_table_version": "v1.0",
                    "calculated_cost": (rewrite_usage.get("prompt_tokens", 0) / 1000.0)
                    * get_model_price(settings.MODEL_2_CORE)["input_1k"]
                    + (rewrite_usage.get("completion_tokens", 0) / 1000.0)
                    * get_model_price(settings.MODEL_2_CORE)["output_1k"],
                }
            )
        else:
            rewrite_record.append(
                {
                    "measurement_type": "estimate",
                    "provider": "nvidia",
                    "model": settings.MODEL_2_CORE,
                    "tokenizer": None,
                    "input_tokens": len(prompt) // 4,
                    "output_tokens": len(search_vector_query + grounded_llm_prompt) // 4,
                    "cached_tokens": None,
                    "retry_usage": None,
                    "missing_reason": "exact usage not returned by provider",
                    "price_table_version": "v1.0",
                    "calculated_cost": None,
                }
            )

        usage_report = rewrite_record + (
            refined_response.usage_records
            if refined_response and refined_response.usage_records
            else []
        )
        yield f"event: usage_report\ndata: {json.dumps(usage_report)}\n\n"

        # Yield legacy token usage estimates for backward compatibility
        m1_tokens = (len(prompt) + len(search_vector_query) + len(grounded_llm_prompt)) // 4 + 150
        m2_tokens = (len(augmented_prompt) + len(full_response_text)) // 4 + 250
        yield f"event: token_usage\ndata: {json.dumps({'m1': m1_tokens, 'm2': m2_tokens})}\n\n"

        # Yield intent for analytics
        if refined_response:
            yield f"event: intent\ndata: {json.dumps(refined_response.intent)}\n\n"

    except Exception as e:
        logger.error(
            "Agent response generation failed",
            extra={"session_id": session_id},
            exc_info=True,
        )
        log_error("api.sse.agent_generation", str(e))
        yield f"event: error\ndata: {json.dumps('Response generation failed')}\n\n"

    yield "event: done\ndata: [DONE]\n\n"

    # 5. Synchronize memory dialogue state
    if not generation_succeeded:
        return
    record.chat_history.append({"role": "user", "content": prompt})
    record.chat_history.append({"role": "assistant", "content": full_response_text})
    while len(record.chat_history) > settings.MAX_HISTORY_TURNS:
        record.chat_history.pop(0)
    record.refresh_manifest()

    # 6. Non-blocking asynchronous vector database ingestion task allocation
    index_chunk = f"User: {prompt}\nAssistant: {full_response_text}"
    create_tracked_task(index_interaction(record, session_id, index_chunk))


@app.post("/api/agent/query")
async def agent_query(body: ExecutionQueryRequest) -> StreamingResponse:
    """Evaluates query routing, updates registers, and yields Server-Sent Events."""
    return StreamingResponse(
        sse_query_generator(
            body.session_id, body.prompt, body.graphify_enabled, body.diagnostic_mode
        ),
        media_type="text/event-stream",
    )


class DualLLMRequest(BaseModel):
    session_id: SessionId
    prompt: PromptText


def _build_action_payload(action: Any) -> dict[str, Any] | None:
    if not action:
        return None

    payload = None
    if action.payload:
        payload = {
            "command": action.payload.command,
            "prompt": action.payload.prompt,
            "file_path": action.payload.file_path,
            "file_content": action.payload.file_content,
        }

    return {
        "type": action.type,
        "payload": payload,
    }


def _apply_phase_gate(
    record: Any,
    response_text: str,
    action_type: str,
    payload: dict[str, Any] | None,
) -> tuple[str, str, dict[str, Any] | None]:
    current_phase = record.metadata_registry.get("development_phase")
    if sc_evm_engine.check_phase_gate(current_phase, action_type, payload):
        return response_text, action_type, payload

    response_text += (
        "\n\n[SYSTEM: Action blocked by Phase Gate (Not ready for this stage of development)]"
    )
    return response_text, "none", None


@app.post("/api/dual-llm/process")
async def dual_llm_process(body: DualLLMRequest) -> StandardResponseEnvelope:
    """Directly triggers the Dual-LLM Orchestrator reasoning pass."""
    try:
        async with session_registry.session_operation(body.session_id, create=True) as record:
            memory_snapshot = build_memory_snapshot(record)
            orchestrator = await get_orchestrator()
            result = await run_orchestrator(orchestrator, memory_snapshot, body.prompt)
            commit_remembered_facts(record, result.remember)

            action_payload = _build_action_payload(result.action)
            if action_payload:
                result.text, action_type, payload = _apply_phase_gate(
                    record,
                    result.text,
                    action_payload["type"],
                    action_payload["payload"],
                )
                action_payload = {
                    "type": action_type,
                    "payload": payload,
                }

            return StandardResponseEnvelope(
                status="success",
                message="Dual-LLM pass complete",
                data={
                    "text": result.text,
                    "intent": result.intent,
                    "action": action_payload,
                },
            )
    except Exception as e:
        logger.exception("Dual-LLM processing failed", extra={"session_id": body.session_id})
        raise HTTPException(status_code=500, detail="Dual-LLM processing failed") from e
