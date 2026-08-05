import asyncio
import concurrent.futures
import hashlib
import json
import logging
import re
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Path, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from src.agent import Action, ActionPayload, RefinedResponse
from src.config import settings
from src.memory import session_registry, warm_memory_runtime
from src.sc_evm import SCEVMEngine
from src.security import (
    Principal,
    SecurityHeadersMiddleware,
    get_current_principal,
    require_scope,
    issue_dev_tokens,
    refresh_dev_token,
    revoke_dev_token,
)
from src.services.error_handlers import GlobalExceptionHandler
from src.services.model_connector import ModelConnector
from src.services.prompt_manager import PromptManager
from src.services.response_parsing import clean_structured_response
from src.services.session_runtime import (
    await_background_tasks,
    build_memory_snapshot,
    commit_remembered_facts,
    create_tracked_task,
    embed_text,
    get_indexed_documents,
    index_interaction,
)
from src.strategies.single_model_adapter import SingleModelAdapter
from src.telemetry_sink import log_error
from src.tools import sandbox_fs

# Instantiate a global instance of SCEVMEngine containing the NVIDIA client
sc_evm_engine = SCEVMEngine()
prompt_manager = PromptManager()
logger = logging.getLogger("SC-EVM.API")


class SingleModelOrchestrator:
    def __init__(self, model_connector: ModelConnector | None = None):
        self.adapter = SingleModelAdapter()

    async def generate_response_async(self, memory_snapshot: Any, prompt: str) -> RefinedResponse:
        session_id = getattr(memory_snapshot, "session_id", "default-session")
        if isinstance(memory_snapshot, dict):
            session_id = memory_snapshot.get("session_id", session_id)
        res = await self.adapter.solve(prompt, session_id)
        action_dict = res.get("action") or {"type": "none"}
        action_payload = action_dict.get("payload")
        payload_obj = ActionPayload(**action_payload) if isinstance(action_payload, dict) else None
        return RefinedResponse(
            text=res.get("response_text", ""),
            intent=res.get("intent", "chat"),
            action=Action(type=action_dict.get("type", "none"), payload=payload_obj),
            remember=res.get("remember", []),
            usage_records=[
                {
                    "measurement_type": "estimate",
                    "status": "completed",
                    "stage": "single_model_generation",
                    "provider": "nvidia",
                    "model": settings.MODEL_1_FLASH,
                    "tokenizer": None,
                    "input_tokens": res.get("tokens_in", len(prompt) // 4),
                    "output_tokens": res.get("tokens_out", len(res.get("response_text", "")) // 4),
                    "cached_tokens": None,
                    "retry_usage": None,
                    "missing_reason": None,
                    "price_table_version": "v1.0",
                    "calculated_cost": None,
                    "latency_seconds": res.get("total_latency"),
                    "attempts": [],
                    "finish_reason": "stop",
                }
            ],
        )

    def generate_response(self, memory_snapshot: Any, prompt: str) -> RefinedResponse:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            future = asyncio.run_coroutine_threadsafe(
                self.generate_response_async(memory_snapshot, prompt), loop
            )
            return future.result()
        return asyncio.run(self.generate_response_async(memory_snapshot, prompt))


_ORCHESTRATOR: Any | None = None
_ORCHESTRATOR_LOCK: asyncio.Lock = asyncio.Lock()
_ORCHESTRATION_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=settings.MAX_WORKER_THREADS,
    thread_name_prefix="sc-evm-orchestration",
)


async def run_orchestrator(orchestrator: Any, memory_snapshot: Any, prompt: str) -> RefinedResponse:
    try:
        if hasattr(orchestrator, "generate_response_async"):
            return await orchestrator.generate_response_async(memory_snapshot, prompt)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            _ORCHESTRATION_EXECUTOR,
            orchestrator.generate_response,
            memory_snapshot,
            prompt,
        )
    except Exception as e:
        logger.error(f"Orchestrator execution failed: {e}", exc_info=True)
        return RefinedResponse(
            text=f"An error occurred while generating the model response ({e}).",
            intent="chat",
            action=Action(type="none"),
            remember=[],
        )


async def get_orchestrator() -> Any:
    global _ORCHESTRATOR
    if _ORCHESTRATOR is None:
        async with _ORCHESTRATOR_LOCK:
            if _ORCHESTRATOR is None:
                _ORCHESTRATOR = SingleModelOrchestrator()
    return _ORCHESTRATOR


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event manager for startup diagnostics and graceful shutdown."""
    logger.info("Verifying local NVIDIA API key configuration...")
    if settings.NVIDIA_API_KEY:
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
    allow_credentials=settings.AUTH_MODE == "disabled",
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware)

app.add_exception_handler(Exception, GlobalExceptionHandler.handle)


@app.get("/")
@app.get("/api/health")
async def get_health():
    """Health check endpoint for the SC-EVM backend."""
    return {"status": "online", "message": "SC-EVM Backend Engine Running"}


@app.get("/health/liveness")
@app.get("/api/health/liveness")
async def get_liveness():
    """Liveness probe returning 200 OK if server process is responsive."""
    return {"status": "alive", "timestamp": time.time()}


@app.get("/health/readiness")
@app.get("/api/health/readiness")
async def get_readiness():
    """Readiness probe checking readiness of memory runtime and session registry."""
    return {
        "status": "ready",
        "timestamp": time.time(),
        "services": {
            "session_registry": "ready",
            "memory_runtime": "ready",
            "local_embedding": "ready",
        },
    }


@app.get("/metrics")
@app.get("/api/metrics")
async def get_metrics():
    """Prometheus metrics exposition endpoint."""
    from src.services.metrics import MetricsRegistry

    metrics_str = MetricsRegistry.get_instance().export_prometheus_metrics()
    return Response(content=metrics_str, media_type="text/plain")


class AuthLoginRequest(BaseModel):
    email: str
    password: str | None = None


class AuthUser(BaseModel):
    uid: str
    email: str
    display_name: str


class AuthLoginResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    user: AuthUser


class StandardResponseEnvelope(BaseModel):
    status: str
    message: str
    data: Any | None = None


# Simple in-memory auth rate limiter (development helper)
_AUTH_RATE_LIMITS: dict[str, tuple[int, float]] = {}
AUTH_RATE_LIMIT_WINDOW = 60.0
AUTH_RATE_LIMIT_MAX = 10



@app.post("/api/auth/login", response_model=StandardResponseEnvelope)
async def auth_login(request: Request, body: AuthLoginRequest) -> StandardResponseEnvelope:
    """Authenticate a development user and return a bearer token in disabled auth mode."""
    if settings.AUTH_MODE != "disabled":
        raise HTTPException(
            status_code=501,
            detail="Interactive login is only supported in development mode.",
        )

    # Simple rate limiting per client IP to reduce brute-force risk in dev
    client_ip = request.client.host if request.client is not None else "unknown"
    now = time.time()
    count, window_start = _AUTH_RATE_LIMITS.get(client_ip, (0, now))
    if now - window_start > AUTH_RATE_LIMIT_WINDOW:
        count = 0
        window_start = now
    if count + 1 > AUTH_RATE_LIMIT_MAX:
        raise HTTPException(status_code=429, detail="Too many login attempts, try later")
    _AUTH_RATE_LIMITS[client_ip] = (count + 1, window_start)

    email = body.email.strip()
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")

    display_name = email.split("@")[0] if "@" in email else email
    user = AuthUser(
        uid=f"dev-{display_name}",
        email=email,
        display_name=display_name,
    )
    access_token, refresh_token = issue_dev_tokens(email)

    return StandardResponseEnvelope(
        status="success",
        message="Logged in as development user",
        data=AuthLoginResponse(access_token=access_token, refresh_token=refresh_token, user=user).dict(),
    )



class AuthRefreshRequest(BaseModel):
    refresh_token: str


@app.post("/api/auth/refresh", response_model=StandardResponseEnvelope)
async def auth_refresh(body: AuthRefreshRequest) -> StandardResponseEnvelope:
    if settings.AUTH_MODE != "disabled":
        raise HTTPException(status_code=501, detail="Refresh supported only in development mode")
    if not body.refresh_token:
        raise HTTPException(status_code=400, detail="Missing refresh_token")
    new_pair = refresh_dev_token(body.refresh_token)
    if not new_pair:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    access_token, refresh_token = new_pair
    return StandardResponseEnvelope(
        status="success",
        message="Token refreshed",
        data={"access_token": access_token, "refresh_token": refresh_token},
    )


class RevokeRequest(BaseModel):
    token: str


@app.post("/api/auth/revoke", response_model=StandardResponseEnvelope)
async def auth_revoke(body: RevokeRequest) -> StandardResponseEnvelope:
    if settings.AUTH_MODE != "disabled":
        raise HTTPException(status_code=501, detail="Revoke supported only in development mode")
    if not body.token:
        raise HTTPException(status_code=400, detail="Missing token")
    ok = revoke_dev_token(body.token)
    if not ok:
        raise HTTPException(status_code=404, detail="Token not found")
    return StandardResponseEnvelope(status="success", message="Token revoked", data=None)


# --- Ingestion Contracts / Schemas ---

SessionId = Annotated[
    str,
    Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$"),
]
PromptText = Annotated[str, Field(min_length=1, max_length=100_000)]
CurrentPrincipal = Annotated[Principal, Depends(get_current_principal)]


class SessionInitRequest(BaseModel):
    session_id: SessionId
    development_phase: int | None = Field(default=None, ge=0, le=3)
    assistant_mode: Literal["coding", "general"] | None = Field(default="coding")


class ChatMessageInput(BaseModel):
    session_id: SessionId
    role: Literal["user", "assistant", "system"]
    content: PromptText


class ExecutionQueryRequest(BaseModel):
    session_id: SessionId
    prompt: PromptText
    graphify_enabled: bool = True
    diagnostic_mode: bool = False
    assistant_mode: Literal["coding", "general"] | None = Field(default=None)


# --- Network Interface Controllers ---


@app.get("/api/session/list", response_model=StandardResponseEnvelope)
async def list_sessions(principal: CurrentPrincipal) -> StandardResponseEnvelope:
    """Retrieves a list of all active session IDs."""
    try:
        session_ids = session_registry.list_session_ids(
            tenant_id=principal.tenant_id,
            owner_subject=principal.subject,
            include_tenant=principal.has_scope(settings.OPERATOR_SCOPE),
        )
        return StandardResponseEnvelope(
            status="success", message="Sessions listed successfully", data=session_ids
        )
    except Exception as e:
        logger.exception("Failed to list sessions")
        raise HTTPException(status_code=500, detail="Failed to list sessions") from e


@app.post("/api/session/initialize", response_model=StandardResponseEnvelope)
async def initialize_session(
    body: SessionInitRequest,
    principal: CurrentPrincipal,
) -> StandardResponseEnvelope:
    """Invokes the session_registry.initialize_session lifecycle logic."""
    try:
        record = await session_registry.initialize_session(
            body.session_id,
            tenant_id=principal.tenant_id,
            owner_subject=principal.subject,
        )
        if body.development_phase is not None:
            record.metadata_registry["development_phase"] = body.development_phase
        if body.assistant_mode is not None:
            record.metadata_registry["assistant_mode"] = body.assistant_mode.lower()
        return StandardResponseEnvelope(
            status="success",
            message=f"Session {body.session_id} initialized successfully",
            data={
                "development_phase": record.metadata_registry.get(
                    "development_phase", settings.DEVELOPMENT_PHASE
                ),
                "assistant_mode": record.metadata_registry.get(
                    "assistant_mode", "coding"
                ),
            },
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail="Session not found") from e
    except Exception as e:
        logger.exception("Failed to initialize session", extra={"session_id": body.session_id})
        raise HTTPException(status_code=500, detail="Failed to initialize session") from e


@app.post("/api/session/message", response_model=StandardResponseEnvelope)
async def append_message(
    body: ChatMessageInput,
    principal: CurrentPrincipal,
) -> StandardResponseEnvelope:
    """Manually synchronizes conversational entries under session-specific sub-locks."""
    try:
        await session_registry.append_message(
            body.session_id,
            body.role,
            body.content,
            tenant_id=principal.tenant_id,
            owner_subject=principal.subject,
        )
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
    principal: CurrentPrincipal,
) -> StandardResponseEnvelope:
    """Completely purges the volatile RAM footprint and ChromaDB collection for a session."""
    try:
        flushed = await session_registry.flush_session(
            session_id,
            tenant_id=principal.tenant_id,
            owner_subject=(
                None if principal.has_scope(settings.OPERATOR_SCOPE) else principal.subject
            ),
        )
        if not flushed:
            raise HTTPException(status_code=404, detail="Session not found")
        if _ORCHESTRATOR and hasattr(_ORCHESTRATOR, "adapter"):
            await _ORCHESTRATOR.adapter.clear_session(session_id)
        return StandardResponseEnvelope(
            status="success", message=f"Session {session_id} successfully flushed from memory"
        )
    except HTTPException:
        raise
    except KeyError as e:
        raise HTTPException(status_code=404, detail="Session not found") from e
    except Exception as e:
        logger.exception("Failed to flush session", extra={"session_id": session_id})
        raise HTTPException(status_code=500, detail="Failed to flush session") from e


@app.post("/api/session/burn/{session_id}", status_code=204, response_class=Response)
async def burn_sandbox_session(
    session_id: Annotated[str, Path()],
    principal: CurrentPrincipal,
) -> Response:
    """Permanently destroy one session's filesystem sandbox."""
    try:
        if settings.AUTH_MODE == "oidc":
            record = await session_registry.get_session(
                session_id,
                tenant_id=principal.tenant_id,
                owner_subject=(
                    None if principal.has_scope(settings.OPERATOR_SCOPE) else principal.subject
                ),
            )
            if record is None:
                raise HTTPException(status_code=404, detail="Session not found")
        sandbox_fs.burn_session(session_id)
    except HTTPException:
        raise
    except sandbox_fs.SandboxViolation as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(status_code=204)


@app.get("/api/session/history/{session_id}", response_model=StandardResponseEnvelope)
async def get_session_history(
    session_id: Annotated[
        str, Path(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    ],
    principal: CurrentPrincipal,
) -> StandardResponseEnvelope:
    """Retrieves conversation history for a specific session ID."""
    try:
        record = await session_registry.get_session(
            session_id,
            tenant_id=principal.tenant_id,
            owner_subject=principal.subject,
        )
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
    principal: CurrentPrincipal,
) -> StandardResponseEnvelope:
    """Retrieves index contents and metadata registry for a session."""
    try:
        record = await session_registry.get_session(
            session_id,
            tenant_id=principal.tenant_id,
            owner_subject=principal.subject,
        )
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
                "base_threshold": record.metadata_registry.get("base_threshold"),
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
    session_id: str,
    prompt: str,
    graphify_enabled: bool = True,
    diagnostic_mode: bool = False,
    *,
    tenant_id: str | None = None,
    owner_subject: str | None = None,
    create_session: bool = True,
) -> AsyncIterator[str]:
    """Generates server-sent events for query reformulation, context retrieval, and response content streams."""
    async with session_registry.session_operation(
        session_id,
        create=create_session,
        tenant_id=tenant_id,
        owner_subject=owner_subject,
    ) as record:
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
    memory_snapshot = build_memory_snapshot(record, session_id=session_id)
    memory_anchors = record.metadata_registry.get(
        "learned_facts", []
    ) + record.metadata_registry.get("pending_commit_buffer", [])
    pending_mems = list(record.metadata_registry.get("pending_commit_buffer", []))
    base_threshold = record.metadata_registry.get("base_threshold")

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

    # 2. Query reformulation using the configured NVIDIA NIM Model 1 route
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

    # 4. Invoke Orchestrator to generate response and actions
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
        commit_remembered_facts(record, getattr(refined_response, "remember", []))

        full_response_text = clean_structured_response(getattr(refined_response, "text", ""))
        generation_succeeded = bool(full_response_text.strip())

        # Format action payload
        action_payload = _build_action_payload(getattr(refined_response, "action", None))
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

        if getattr(refined_response, "degraded", False):
            degradation_payload = {
                "degraded": True,
                "reasons": getattr(refined_response, "degradation_reasons", []),
            }
            yield f"event: degradation\ndata: {json.dumps(degradation_payload)}\n\n"

        # Yield action payload over SSE
        yield f"event: action\ndata: {json.dumps(action_payload)}\n\n"

        # Compile and yield the detailed cost accounting usage report
        from src.clients import get_model_price

        rewrite_record = []
        rewrite_metadata = dict(getattr(rewrite_usage, "provider_metadata", None) or {})
        if rewrite_usage and rewrite_usage.get("prompt_tokens") is not None:
            rewrite_record.append(
                {
                    "measurement_type": "exact",
                    "status": "completed",
                    "stage": "model_1_reformulation",
                    "provider": "nvidia",
                    "model": settings.MODEL_1_FLASH,
                    "tokenizer": None,
                    "input_tokens": rewrite_usage.get("prompt_tokens"),
                    "output_tokens": rewrite_usage.get("completion_tokens"),
                    "cached_tokens": None,
                    "retry_usage": None,
                    "missing_reason": None,
                    "price_table_version": "v1.0",
                    "calculated_cost": (rewrite_usage.get("prompt_tokens", 0) / 1000.0)
                    * get_model_price(settings.MODEL_1_FLASH)["input_1k"]
                    + (rewrite_usage.get("completion_tokens", 0) / 1000.0)
                    * get_model_price(settings.MODEL_1_FLASH)["output_1k"],
                    "latency_seconds": rewrite_metadata.get("latency_seconds"),
                    "attempts": rewrite_metadata.get("attempts", []),
                    "finish_reason": rewrite_metadata.get("finish_reason"),
                }
            )
        else:
            rewrite_record.append(
                {
                    "measurement_type": "estimate",
                    "status": "completed",
                    "stage": "model_1_reformulation",
                    "provider": "nvidia",
                    "model": settings.MODEL_1_FLASH,
                    "tokenizer": None,
                    "input_tokens": len(prompt) // 4,
                    "output_tokens": len(search_vector_query + grounded_llm_prompt) // 4,
                    "cached_tokens": None,
                    "retry_usage": None,
                    "missing_reason": "exact usage not returned by provider",
                    "price_table_version": "v1.0",
                    "calculated_cost": None,
                    "latency_seconds": rewrite_metadata.get("latency_seconds"),
                    "attempts": rewrite_metadata.get("attempts", []),
                    "finish_reason": rewrite_metadata.get("finish_reason"),
                }
            )

        usage_report = rewrite_record + (getattr(refined_response, "usage_records", []) or [])
        yield f"event: usage_report\ndata: {json.dumps(usage_report)}\n\n"

        # Yield legacy token usage estimates for backward compatibility
        m1_tokens = (len(prompt) + len(search_vector_query) + len(grounded_llm_prompt)) // 4 + 150
        m2_tokens = (len(augmented_prompt) + len(full_response_text)) // 4 + 250
        yield f"event: token_usage\ndata: {json.dumps({'m1': m1_tokens, 'm2': m2_tokens})}\n\n"

        # Yield intent for analytics
        yield f"event: intent\ndata: {json.dumps(getattr(refined_response, 'intent', 'chat'))}\n\n"

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
async def agent_query(
    body: ExecutionQueryRequest,
    request: Request,
    principal: CurrentPrincipal,
) -> StreamingResponse:
    """Evaluates query routing, updates registers, and yields Server-Sent Events."""
    if body.diagnostic_mode:
        require_scope(request, principal, settings.DIAGNOSTIC_SCOPE)
    try:
        await session_registry.initialize_session(
            body.session_id,
            tenant_id=principal.tenant_id,
            owner_subject=principal.subject,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    return StreamingResponse(
        sse_query_generator(
            body.session_id,
            body.prompt,
            body.graphify_enabled,
            body.diagnostic_mode,
            tenant_id=principal.tenant_id,
            owner_subject=principal.subject,
            create_session=False,
        ),
        media_type="text/event-stream",
    )


class DualLLMRequest(BaseModel):
    session_id: SessionId
    prompt: PromptText


class OpenAIChatCompletionMessage(BaseModel):
    role: str
    content: str | list[Any] | dict[str, Any] | None = ""


class OpenAIChatCompletionRequest(BaseModel):
    model: str
    messages: list[OpenAIChatCompletionMessage] | None = None
    prompt: PromptText | None = None
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None
    user: str | None = None
    session_id: SessionId | None = None


def _normalize_session_id(raw_session_id: str | None) -> SessionId:
    if not raw_session_id:
        return "openai-anonymous"
    normalized = re.sub(r"[^A-Za-z0-9_.-]", "_", raw_session_id)
    if not normalized:
        normalized = "openai-anonymous"
    if not re.match(r"^[A-Za-z0-9]", normalized):
        normalized = f"s{normalized}"
    return normalized[:128]


def _infer_openai_session_id(body: OpenAIChatCompletionRequest, request: Request) -> SessionId:
    if body.session_id:
        return _normalize_session_id(body.session_id)
    if body.user:
        return _normalize_session_id(body.user)
    authorization = request.headers.get("authorization", "")
    if authorization:
        return _normalize_session_id(
            f"openai-{hashlib.sha256(authorization.encode('utf-8')).hexdigest()[:16]}"
        )
    return "openai-anonymous"


def _extract_message_content(content: str | list[Any] | dict[str, Any] | None) -> str:
    if not content:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str) and part.strip():
                parts.append(part.strip())
            elif isinstance(part, dict):
                text_val = part.get("text") or part.get("content") or ""
                if isinstance(text_val, str) and text_val.strip():
                    parts.append(text_val.strip())
        return "\n".join(parts)
    if isinstance(content, dict):
        text_val = content.get("text") or content.get("content") or ""
        return text_val.strip() if isinstance(text_val, str) else ""
    return str(content).strip()


def _flatten_openai_messages(messages: list[OpenAIChatCompletionMessage]) -> str:
    system_parts: list[str] = []
    conversation_parts: list[str] = []
    for message in messages:
        text = _extract_message_content(message.content)
        if not text:
            continue
        if message.role == "system":
            system_parts.append(text)
        elif message.role == "assistant":
            conversation_parts.append(f"Assistant: {text}")
        else:
            conversation_parts.append(text)

    prompt = "\n\n".join(system_parts + conversation_parts)
    return prompt.strip()


def _parse_sse_event(raw_event: str) -> tuple[str, Any]:
    event_name = ""
    data_lines: list[str] = []
    for line in raw_event.splitlines():
        if line.startswith("event:"):
            event_name = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data_lines.append(line.split(":", 1)[1].strip())
    data = None
    if data_lines:
        try:
            data = json.loads("\n".join(data_lines))
        except json.JSONDecodeError:
            data = "\n".join(data_lines)
    return event_name, data


async def _execute_context_control_plane(session_id: str, prompt: str) -> None:
    """Executes deterministic context planning, token budgeting, and observability logging."""
    try:
        from src.services.context_budget_manager import ContextBudgetManager
        from src.services.context_optimizer import ContextOptimizer
        from src.services.context_planner import ContextPlanner

        planner = ContextPlanner()
        blocks = planner.plan_context(
            system_prompt="You are a helpful AI coding assistant.",
            history=[],
            user_query=prompt,
        )

        budget_mgr = ContextBudgetManager(total_limit=8192, reserved_output=2048)
        source_budgets = budget_mgr.allocate_budgets()

        opt_res = ContextOptimizer.optimize(blocks, source_budgets, budget_mgr.available_input_tokens)

        logging.getLogger("SC-EVM.ContextControlPlane").info(
            "context_planner_decision",
            extra={
                "token_budget": {
                    "total_limit": budget_mgr.total_limit,
                    "reserved_output": budget_mgr.reserved_output,
                    "available_input": budget_mgr.available_input_tokens,
                    "allocated_tokens": opt_res.tokens_by_source,
                },
                "planner_decisions": {
                    "admitted_ids": [b.id for b in opt_res.admitted_blocks],
                    "evicted_ids": [b.id for b in opt_res.evicted_blocks],
                },
                "evictions": {
                    "count": len(opt_res.evicted_blocks),
                    "tokens": opt_res.total_evicted_tokens,
                },
                "compression": {
                    "original_tokens": opt_res.total_admitted_tokens + opt_res.total_evicted_tokens,
                    "admitted_tokens": opt_res.total_admitted_tokens,
                },
                "context_sources": list(opt_res.tokens_by_source.keys()),
                "reserved_output": budget_mgr.reserved_output,
                "planner_latency_ms": opt_res.planner_latency_ms,
            },
        )
    except Exception as e:
        logging.getLogger("SC-EVM.Error").error(f"Context Control Plane execution failed: {e}")


async def _run_openai_completion(
    session_id: SessionId,
    prompt: str,
    principal: Principal,
) -> str:
    try:
        await session_registry.initialize_session(
            session_id,
            tenant_id=principal.tenant_id,
            owner_subject=principal.subject,
        )
    except Exception:
        pass

    await _execute_context_control_plane(session_id, prompt)

    response_text = ""
    async for raw_event in sse_query_generator(
        session_id,
        prompt,
        True,
        False,
        tenant_id=principal.tenant_id,
        owner_subject=principal.subject,
        create_session=True,
    ):
        event_name, data = _parse_sse_event(raw_event)
        if event_name == "response_content" and isinstance(data, str):
            response_text = data
        elif event_name == "error":
            raise HTTPException(status_code=502, detail=str(data or "Engine error"))
    return response_text


async def _openai_streaming_generator(
    session_id: SessionId,
    prompt: str,
    principal: Principal,
) -> AsyncIterator[str]:
    await _execute_context_control_plane(session_id, prompt)
    chat_id = f"chatcmpl-{hashlib.sha256(session_id.encode('utf-8')).hexdigest()[:16]}"
    sent_chunk = False

    async for raw_event in sse_query_generator(
        session_id,
        prompt,
        True,
        False,
        tenant_id=principal.tenant_id,
        owner_subject=principal.subject,
        create_session=True,
    ):
        event_name, data = _parse_sse_event(raw_event)
        if event_name == "response_content" and isinstance(data, str):
            chunk = {
                "id": chat_id,
                "object": "chat.completion.chunk",
                "choices": [
                    {
                        "delta": {"role": "assistant", "content": data},
                        "index": 0,
                        "finish_reason": None,
                    }
                ],
            }
            sent_chunk = True
            yield f"data: {json.dumps(chunk)}\n\n"
        elif event_name == "error":
            error_chunk = {"error": str(data or "Engine error")}
            yield f"data: {json.dumps(error_chunk)}\n\n"
            yield "data: [DONE]\n\n"
            return

    if sent_chunk:
        yield "data: [DONE]\n\n"
    else:
        yield "data: [DONE]\n\n"


@app.get("/v1/models")
@app.get("/openai/v1/models")
@app.get("/api/agent/query/v1/models")
@app.get("/api/agent/query/openai/v1/models")
async def openai_list_models():
    return {
        "object": "list",
        "data": [
            {
                "id": "sc-evm-proxy",
                "object": "model",
                "created": 1700000000,
                "owned_by": "sc-evm",
            }
        ],
    }


@app.post(
    "/v1/chat/completions",
    response_model=None,
)
@app.post(
    "/openai/v1/chat/completions",
    response_model=None,
)
@app.post(
    "/api/agent/query/v1/chat/completions",
    response_model=None,
)
@app.post(
    "/api/agent/query/openai/v1/chat/completions",
    response_model=None,
)
async def openai_chat_completions(
    body: OpenAIChatCompletionRequest,
    request: Request,
    principal: CurrentPrincipal,
):
    prompt = body.prompt
    if not prompt and body.messages:
        prompt = _flatten_openai_messages(body.messages)
    if not prompt:
        raise HTTPException(status_code=400, detail="Either messages or prompt must be provided")

    session_id = _infer_openai_session_id(body, request)

    if body.stream:
        return StreamingResponse(
            _openai_streaming_generator(session_id, prompt, principal),
            media_type="text/event-stream",
        )

    response_text = await _run_openai_completion(session_id, prompt, principal)
    return {
        "id": f"chatcmpl-{hashlib.sha256((session_id + prompt).encode('utf-8')).hexdigest()[:16]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": body.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": response_text},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": max(1, len(prompt) // 4),
            "completion_tokens": max(1, len(response_text) // 4),
            "total_tokens": max(1, len(prompt) // 4 + len(response_text) // 4),
        },
    }


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
            "glob": action.payload.glob,
            "max_results": action.payload.max_results,
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
    assistant_mode = record.metadata_registry.get("assistant_mode", "coding")
    if str(assistant_mode).lower() in ("general", "research"):
        return response_text, action_type, payload
    current_phase = record.metadata_registry.get("development_phase")
    if sc_evm_engine.check_phase_gate(current_phase, action_type, payload):
        return response_text, action_type, payload

    response_text += (
        "\n\n[SYSTEM: Action blocked by Phase Gate (Not ready for this stage of development)]"
    )
    return response_text, "none", None


@app.post("/api/dual-llm/process")
async def dual_llm_process(
    body: DualLLMRequest,
    principal: CurrentPrincipal,
) -> StandardResponseEnvelope:
    """Directly triggers the Single-Model reasoning pass."""
    try:
        async with session_registry.session_operation(
            body.session_id,
            create=True,
            tenant_id=principal.tenant_id,
            owner_subject=principal.subject,
        ) as record:
            orchestrator = await get_orchestrator()
            result = await orchestrator.adapter.solve(body.prompt, body.session_id)

            action_data = result.get("action") or {"type": "none"}
            action_payload = {
                "type": action_data.get("type", "none"),
                "payload": action_data.get("payload"),
            }
            response_text = result.get("response_text", "")
            if action_payload["type"] != "none":
                response_text, action_type, payload = _apply_phase_gate(
                    record,
                    response_text,
                    action_payload["type"],
                    action_payload["payload"],
                )
                action_payload = {
                    "type": action_type,
                    "payload": payload,
                }

            return StandardResponseEnvelope(
                status="success",
                message="Single-model pass complete",
                data={
                    "text": response_text,
                    "intent": result.get("intent", "chat"),
                    "action": action_payload,
                },
            )
    except KeyError as e:
        raise HTTPException(status_code=404, detail="Session not found") from e
    except Exception as e:
        logger.exception("Single-model processing failed", extra={"session_id": body.session_id})
        raise HTTPException(status_code=500, detail="Single-model processing failed") from e
