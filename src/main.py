import os
import json
import asyncio
from typing import Dict, List, Any, Optional, AsyncIterator
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel, Field

from src.memory import session_registry
from src.sc_evm import SCEVMEngine
from src.clients import NVIDIA_NIM_Client

# Instantiate a global instance of SCEVMEngine containing the NVIDIA client
sc_evm_engine = SCEVMEngine()

class SessionMemoryAdapter:
    """Adapts a session record to the MemoryManager interface required by AgentOrchestrator."""
    def __init__(self, record):
        self.record = record
        
    def get_short_term_history(self) -> List[Dict[str, str]]:
        return self.record.chat_history
        
    def add_interaction(self, user_message: str, assistant_response: str) -> None:
        # Avoid duplicate history appending since sse_query_generator handles it
        pass
        
    def add_fact(self, fact: str) -> bool:
        facts = self.record.metadata_registry.setdefault("learned_facts", [])
        if any(f.lower() == fact.lower() for f in facts):
            return False
        facts.append(fact)
        return True
        
    def get_long_term_context(self) -> str:
        facts = self.record.metadata_registry.get("learned_facts", [])
        parts = []
        if facts:
            parts.append("Learned Facts about User:")
            for f in facts:
                parts.append(f"- {f}")
        return "\n".join(parts) + "\n"

_ORCHESTRATOR: Optional[Any] = None
_ORCHESTRATOR_LOCK: asyncio.Lock = asyncio.Lock()

async def get_orchestrator(memory_manager) -> Any:
    global _ORCHESTRATOR
    if _ORCHESTRATOR is None:
        async with _ORCHESTRATOR_LOCK:
            if _ORCHESTRATOR is None:
                from src.agent import AgentOrchestrator
                _ORCHESTRATOR = AgentOrchestrator(memory_manager)
            else:
                _ORCHESTRATOR.memory = memory_manager
    else:
        _ORCHESTRATOR.memory = memory_manager
    return _ORCHESTRATOR

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event manager to verify connection on startup."""
    print("[Diagnostic] Verifying local NVIDIA API key configuration...")
    key = os.getenv("NVIDIA_API_KEY")
    if key:
        print("[Diagnostic] Local NVIDIA connection verification: SUCCESSFUL.")
    else:
        print("[Diagnostic] Local NVIDIA connection verification: FAILED (API Key missing).")
    yield

app = FastAPI(
    title="State-Cached Ephemeral Vector Memory (SC-EVM) Microservice",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
async def get_ui():
    """Serves the premium single-file HTML/CSS/JS Chat interface."""
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    if not os.path.exists(html_path):
        html_path = "index.html"
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content=content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"UI file not found: {str(e)}")

# --- Ingestion Contracts / Schemas ---

class SessionInitRequest(BaseModel):
    session_id: str

class ChatMessageInput(BaseModel):
    session_id: str
    role: str
    content: str

class ExecutionQueryRequest(BaseModel):
    session_id: str
    prompt: str

class StandardResponseEnvelope(BaseModel):
    status: str
    message: str
    data: Optional[Any] = None

# --- Network Interface Controllers ---

@app.post("/api/session/initialize", response_model=StandardResponseEnvelope)
async def initialize_session(body: SessionInitRequest) -> StandardResponseEnvelope:
    """Invokes the session_registry.initialize_session lifecycle logic."""
    try:
        await session_registry.initialize_session(body.session_id)
        return StandardResponseEnvelope(
            status="success",
            message=f"Session {body.session_id} initialized successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize session: {str(e)}")

@app.post("/api/session/message", response_model=StandardResponseEnvelope)
async def append_message(body: ChatMessageInput) -> StandardResponseEnvelope:
    """Manually synchronizes conversational entries under session-specific sub-locks."""
    try:
        await session_registry.append_message(body.session_id, body.role, body.content)
        return StandardResponseEnvelope(
            status="success",
            message="Message successfully appended to session history"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to append message: {str(e)}")

@app.delete("/api/session/burn/{session_id}", response_model=StandardResponseEnvelope)
async def burn_session(session_id: str) -> StandardResponseEnvelope:
    """Completely purges the volatile RAM footprint and ChromaDB collection for a session."""
    try:
        await session_registry.flush_session(session_id)
        return StandardResponseEnvelope(
            status="success",
            message=f"Session {session_id} successfully flushed from memory"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to flush session: {str(e)}")

@app.get("/api/session/history/{session_id}", response_model=StandardResponseEnvelope)
async def get_session_history(session_id: str) -> StandardResponseEnvelope:
    """Retrieves conversation history for a specific session ID."""
    try:
        record = await session_registry.get_session(session_id)
        if not record:
            return StandardResponseEnvelope(status="success", message="Session not found", data=[])
        return StandardResponseEnvelope(
            status="success",
            message="History retrieved successfully",
            data=record.chat_history
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve history: {str(e)}")

@app.get("/api/session/memory/{session_id}", response_model=StandardResponseEnvelope)
async def get_session_memory(session_id: str) -> StandardResponseEnvelope:
    """Retrieves index contents and metadata registry for a session."""
    try:
        record = await session_registry.get_session(session_id)
        if not record:
            return StandardResponseEnvelope(status="success", message="Session not found", data={})
        
        # Get documents from ChromaDB collection
        docs = []
        try:
            res = record.collection.get()
            if res and "documents" in res:
                docs = res["documents"]
        except Exception:
            pass
            
        return StandardResponseEnvelope(
            status="success",
            message="Memory data retrieved successfully",
            data={
                "pending_commit_buffer": record.metadata_registry.get("pending_commit_buffer", []),
                "base_threshold": record.metadata_registry.get("base_threshold", 0.52),
                "token_budget": record.metadata_registry.get("token_budget", 2500),
                "indexed_documents": docs
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve memory: {str(e)}")





async def sse_query_generator(session_id: str, prompt: str) -> AsyncIterator[str]:
    """Generates server-sent events for query reformulation, context retrieval, and response token streams."""
    # 1. Initialize/Retrieve session registration record
    record = await session_registry.initialize_session(session_id)
    session_lock = await session_registry.get_session_lock(session_id)
    async with session_lock:
        history = list(record.chat_history)

        # 2. Query Reformulation using NVIDIA NIM Qwen model
        try:
            search_vector_query, grounded_llm_prompt = await sc_evm_engine.run_query_reformulation_async(prompt, history)
        except Exception:
            search_vector_query = prompt
            grounded_llm_prompt = prompt

        yield f"event: query_reformulation\ndata: {json.dumps({'search_vector_query': search_vector_query, 'grounded_llm_prompt': grounded_llm_prompt})}\n\n"

        # 3. Retrieve Context & Apply Cosine Similarity Gating
        retrieved_context: List[str] = []
        try:
            # Generate query vector locally using the session's ONNX embedding function
            query_vector = record.embedding_fn([search_vector_query])[0]

            # Perform query in the session's in-memory ChromaDB collection
            collection = record.collection
            results = collection.query(
                query_embeddings=[query_vector],
                n_results=3,
                include=["documents", "distances", "embeddings"]
            )

            if results and "documents" in results and results["documents"]:
                docs = results["documents"][0]
                distances = results["distances"][0] if "distances" in results else [0.0] * len(docs)
                embeddings = results["embeddings"][0] if "embeddings" in results else [[]] * len(docs)

                # Fetch baseline threshold dynamically from metadata_registry
                base_threshold = record.metadata_registry.get("base_threshold", 0.52)

                retrieved_context = SCEVMEngine.filter_documents_via_gating(
                    query_vector=query_vector,
                    documents=docs,
                    distances=distances,
                    embeddings=embeddings,
                    base_threshold=base_threshold
                )
        except Exception:
            pass

        yield f"event: retrieved_context\ndata: {json.dumps(retrieved_context)}\n\n"

        # 4. Synthesize context blocks and execute primary reasoning stream
        context_list = [f"<retrieved_memory>\n{doc}\n</retrieved_memory>" for doc in retrieved_context]
        
        # Merge volatile in-memory buffer interceptors (mapped to metadata_registry keys)
        pending_mems = record.metadata_registry.get("pending_commit_buffer", [])
        for pending in pending_mems:
            context_list.append(f"<retrieved_memory>\n[Pending Active Queue Context (Unindexed)]:\n{pending}\n</retrieved_memory>")
            
        context_str = "\n\n".join(context_list)
        
        # 4. Invoke Dual-LLM Agent Orchestrator to generate response and actions
        adapter = SessionMemoryAdapter(record)
        orchestrator = await get_orchestrator(adapter)
        
        # Build augmented prompt for the orchestrator, passing SC-EVM context
        augmented_prompt = f"--- RETRIEVED MEMORY CONTEXT ---\n{context_str}\n\n--- CURRENT USER PROMPT ---\n{grounded_llm_prompt}"
        
        full_response_text = ""
        action_payload = {"type": "none"}
        
        try:
            loop = asyncio.get_running_loop()
            # Run AgentOrchestrator's synchronous parallel queries inside a thread pool
            refined_response = await loop.run_in_executor(
                None, orchestrator.generate_response, augmented_prompt
            )
            
            full_response_text = refined_response.text
            
            # Format action payload
            if refined_response.action:
                action_payload = {
                    "type": refined_response.action.type,
                    "payload": {
                        "command": refined_response.action.payload.command if refined_response.action.payload else None,
                        "prompt": refined_response.action.payload.prompt if refined_response.action.payload else None,
                        "file_path": refined_response.action.payload.file_path if refined_response.action.payload else None,
                        "file_content": refined_response.action.payload.file_content if refined_response.action.payload else None,
                    }
                }
            
            # Simulate real-time word-by-word streaming for TUI/Web SSE rendering
            words = full_response_text.split(" ")
            for i, word in enumerate(words):
                spaced_word = word + (" " if i < len(words) - 1 else "")
                yield f"event: token\ndata: {json.dumps(spaced_word)}\n\n"
                await asyncio.sleep(0.015)
                
            # Yield action payload over SSE
            yield f"event: action\ndata: {json.dumps(action_payload)}\n\n"
            
        except Exception as e:
            yield f"event: error\ndata: {json.dumps(str(e))}\n\n"

        yield "event: done\ndata: [DONE]\n\n"

        # 5. Synchronize memory dialogue state
        record.chat_history.append({"role": "user", "content": prompt})
        record.chat_history.append({"role": "assistant", "content": full_response_text})
        # Slide dialogue window to prevent context death spiral (cap at last 6 messages / 3 turns)
        while len(record.chat_history) > 6:
            record.chat_history.pop(0)

        # 6. Non-blocking asynchronous vector database ingestion task allocation
        index_chunk = f"User: {prompt}\nAssistant: {full_response_text}"
        async def background_indexing():
            try:
                vector = record.embedding_fn([index_chunk])[0]
                import uuid
                import time
                doc_id = str(uuid.uuid4())
                record.collection.add(
                    ids=[doc_id],
                    embeddings=[vector],
                    documents=[index_chunk],
                    metadatas=[{"timestamp": int(time.time())}]
                )
            except Exception:
                pass

        asyncio.create_task(background_indexing())


@app.post("/api/agent/query")
async def agent_query(body: ExecutionQueryRequest) -> StreamingResponse:
    """Evaluates query routing, updates registers, and yields Server-Sent Events."""
    return StreamingResponse(
        sse_query_generator(body.session_id, body.prompt),
        media_type="text/event-stream"
    )

class DualLLMRequest(BaseModel):
    session_id: str
    prompt: str

@app.post("/api/dual-llm/process")
async def dual_llm_process(body: DualLLMRequest) -> StandardResponseEnvelope:
    """Directly triggers the Dual-LLM Orchestrator reasoning pass."""
    try:
        # Re-initialize/Retrieve session
        record = await session_registry.initialize_session(body.session_id)
        from src.agent import SessionMemoryAdapter
        adapter = SessionMemoryAdapter(record)
        orchestrator = await get_orchestrator(adapter)
        
        # Execute orchestrator pass
        result = orchestrator.generate_response(body.prompt)
        
        return StandardResponseEnvelope(
            status="success",
            message="Dual-LLM pass complete",
            data={
                "text": result.text,
                "intent": result.intent,
                "action": result.action.dict() if result.action else None
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dual-LLM processing failed: {str(e)}")
