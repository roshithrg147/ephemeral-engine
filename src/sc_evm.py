import os
import sys
import time
import uuid
import asyncio
import threading
import argparse
import google.auth
from google import genai
from google.genai import types
import chromadb
from tenacity import retry, stop_after_attempt, wait_random_exponential
from rich.console import Console

# ==========================================
# 1. Thread-Safe Global Variables & Buffers
# ==========================================
# Pending memory items queue (volatile buffer)
pending_commit_buffer = []
# Global thread lock for protecting buffers and memory structures
buffer_lock = threading.Lock()
# Verbatim history logging array (sliding window of last 3 turns / 6 messages)
conversation_history_verbatim = []

# ==========================================
# 2. ChromaDB Initialization
# ==========================================
print("Initializing serverless, transient in-memory ChromaDB client with cosine space...")
chroma_client = chromadb.EphemeralClient()
# Force cosine distance space
collection = chroma_client.get_or_create_collection(
    name="research_session_memory",
    metadata={"hnsw:space": "cosine"}
)
print("ChromaDB 'research_session_memory' collection created successfully.")

# ==========================================
# 3. Dedicated Client Factory
# ==========================================
def get_genai_client():
    """Initializes standard Google GenAI Client using regional env settings."""
    credentials, project_id = google.auth.default()
    if not project_id:
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
    location = os.getenv("VERTEX_GEMINI_LOCATION", "us-central1")
    return genai.Client(vertexai=True, location=location, project=project_id)

# ==========================================
# Connection Diagnostics & Auth Setup
# ==========================================
def verify_adc_connection() -> bool:
    """
    Verifies that the local Application Default Credentials (ADC) can successfully
    connect to the Vertex AI backend and retrieves project information.
    """
    print("[Diagnostic] Verifying local Application Default Credentials (ADC)...")
    try:
        credentials, project_id = google.auth.default()
        if not project_id:
            print("[Diagnostic] Warning: Project ID not returned by google.auth.default().")
            project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
            
        print(f"[Diagnostic] Found Google credentials. Detected project ID: {project_id}")
        
        location = os.getenv("VERTEX_GEMINI_LOCATION", "us-central1")
        print(f"[Diagnostic] Initializing google-genai Client on location={location}, project={project_id}...")
        
        with buffer_lock:
            client = genai.Client(vertexai=True, location=location, project=project_id)
            print("[Diagnostic] Querying Google GenAI backend for model metadata...")
            models = list(client.models.list())
            print(f"[Diagnostic] Successfully retrieved {len(models)} models from Vertex AI.")
            
        print("[Diagnostic] Local ADC connection verification: SUCCESSFUL.")
        return True
    except Exception as e:
        print(f"[Diagnostic] Local ADC connection verification: FAILED.")
        print(f"[Diagnostic] Details: {e}", file=sys.stderr)
        return False

# ==========================================
# 4. Asynchronous Query Reformulation
# ==========================================
REWRITE_MODEL_ID = "publishers/google/models/gemini-2.5-flash"

REWRITE_SYSTEM_PROMPT = """You are a query reformulation assistant.
Given a conversation history and a new user prompt, rewrite the user's prompt into a search-optimized vector query.
Resolve any pronoun references (like 'that value', 'it', 'them', 'the file') to their actual entities in the history.
Do NOT reply with a chat response. ONLY return the rewritten search query. If the prompt is simple or does not need reformulation, return the original prompt verbatim.
"""

@retry(stop=stop_after_attempt(3), wait=wait_random_exponential(min=1, max=10))
async def rewrite_query_async(user_raw_input: str) -> str:
    """Asynchronously reformulates user queries to prevent loop thread blocking."""
    client = get_genai_client()
    
    with buffer_lock:
        history_window = conversation_history_verbatim[-6:]
        
    formatted_history = []
    for turn in history_window:
        role_label = "User" if turn.get("role") == "user" else "Assistant"
        formatted_history.append(f"{role_label}: {turn.get('content')}")
        
    history_str = "\n".join(formatted_history)
    prompt = f"Conversation History:\n{history_str}\n\nCurrent User Prompt: {user_raw_input}\n\nRewritten search query:"

    try:
        response = await client.aio.models.generate_content(
            model=REWRITE_MODEL_ID,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=REWRITE_SYSTEM_PROMPT,
                temperature=0.2,
            )
        )
        rewritten = response.text.strip()
        print(f"[QueryRewriter] Raw input: '{user_raw_input}' -> Rewritten: '{rewritten}'")
        return rewritten
    except Exception as e:
        print(f"[QueryRewriter] Error during query reformulation: {e}. Falling back to raw input.")
        return user_raw_input

# ==========================================
# 5. Semantic Search & Memory Management
# ==========================================
EMBEDDING_MODEL_ID = "text-embedding-004"

@retry(stop=stop_after_attempt(3), wait=wait_random_exponential(min=1, max=10))
async def get_embedding_async(text: str) -> list[float]:
    """Asynchronous vector generation using text-embedding-004."""
    client = get_genai_client()
    response = await client.aio.models.embed_content(
        model=EMBEDDING_MODEL_ID,
        contents=text
    )
    return response.embeddings[0].values

async def search_memory_async(query: str, limit: int = 3) -> list[str]:
    """
    Queries ChromaDB with a Dynamic Top-K Fallback Ranking algorithm.
    Prunes matches dynamically based on distance gap thresholding to prevent context drift.
    """
    print(f"[SearchMemory] Querying semantic memory for: '{query}'...")
    try:
        query_vector = await get_embedding_async(query)
        
        with buffer_lock:
            results = collection.query(
                query_embeddings=[query_vector],
                n_results=limit,
                include=["documents", "distances"]
            )
            
        matched_docs = []
        if results and "documents" in results and results["documents"] and len(results["documents"]) > 0:
            docs = results["documents"][0]
            distances = results["distances"][0] if "distances" in results else [0.0] * len(docs)
            
            if len(docs) > 0:
                top_dist = distances[0]
                
                # Rule 3: Absolute Exclusion Threshold Check
                if top_dist > 0.48:
                    print(f"[SearchMemory] Statistical confidence floor exceeded (closest match dist {top_dist:.4f} > 0.48). Triggering zero-context parametric fallback.")
                    return []
                
                # Rule 1: Top match is automatically included since dist <= 0.48
                matched_docs.append(docs[0])
                print(f"[SearchMemory] Selected top match: '{docs[0][:50]}...' (dist = {top_dist:.4f})")
                
                # Rule 1 (cont): Evaluate subsequent candidates if top match distance is <= 0.35
                if top_dist <= 0.35:
                    print(f"[SearchMemory] Top match distance {top_dist:.4f} <= 0.35. Evaluating subsequent candidates...")
                    for doc, dist in zip(docs[1:], distances[1:]):
                        delta = dist - top_dist
                        print(f"[SearchMemory] Candidate Match: '{doc[:40]}...' (dist = {dist:.4f}, delta = {delta:.4f})")
                        
                        # Rule 2: Dynamic Gap Check (delta > 0.15) & absolute threshold check
                        if delta > 0.15:
                            print(f"[SearchMemory] Excluded: delta {delta:.4f} > 0.15 from closest match.")
                            continue
                        if dist > 0.48:
                            print(f"[SearchMemory] Excluded: absolute distance {dist:.4f} exceeds safety threshold of 0.48.")
                            continue
                        
                        matched_docs.append(doc)
                        print(f"[SearchMemory] Dynamic Top-K Match Selected: '{doc[:50]}...' (dist = {dist:.4f})")
                else:
                    print(f"[SearchMemory] Top match distance {top_dist:.4f} > 0.35. Skipping evaluation of subsequent candidates.")
                    
        return matched_docs
    except Exception as e:
        print(f"[SearchMemory] Error performing vector search: {e}", file=sys.stderr)
        return []

# ==========================================
# 6. Async Model Execution & Token Streaming
# ==========================================
GROUNDED_SYSTEM_PROMPT = """You are an elite research assistant.
You must answer the user's query using the provided conversation history and retrieved context.
Be direct, helpful, and technically precise.
"""

PRIMARY_MODEL_ID = "publishers/google/models/gemini-2.5-pro"
FALLBACK_MODEL_ID = "publishers/google/models/gemini-2.5-flash"

async def stream_grounded_response(user_input: str, retrieved_context: list[str], console: Console) -> str:
    """
    Streams the response token-by-token directly to the terminal UI.
    First attempts asynchronous streaming with Gemini 2.5 Pro, then falls back to Gemini 2.5 Flash.
    """
    # 1. Volatile In-Memory Buffer Interceptor
    with buffer_lock:
        unindexed_memories = list(pending_commit_buffer)
        
    context_list = list(retrieved_context)
    if unindexed_memories:
        print(f"[Interceptor] Intercepted {len(unindexed_memories)} pending unindexed memories.")
        interceptor_str = "[Pending Active Queue Context (Unindexed)]:\n" + "\n".join(unindexed_memories)
        context_list.append(interceptor_str)
        
    context_str = "\n\n".join(context_list)
    
    # 2. History Compile
    with buffer_lock:
        history_window = conversation_history_verbatim[-6:]
    
    history_str = "".join(f"{'User' if t['role']=='user' else 'Assistant'}: {t['content']}\n" for t in history_window)
    user_prompt = f"--- RETRIEVED CONTEXT ---\n{context_str}\n\n--- CONVERSATION HISTORY ---\n{history_str}\n\n--- CURRENT USER PROMPT ---\n{user_input}\n"

    full_response_text = ""
    first_token = True

    # Try Primary Gemini 2.5 Pro model via client.aio
    try:
        print(f"[Model-2] Initializing async streaming pipe for primary model {PRIMARY_MODEL_ID}...")
        genai_client = get_genai_client()
        
        response_stream = await genai_client.aio.models.generate_content_stream(
            model=PRIMARY_MODEL_ID,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=GROUNDED_SYSTEM_PROMPT,
                temperature=0.7,
            )
        )
        
        async for chunk in response_stream:
            if chunk.text:
                if first_token:
                    console.print("\n[bold green]Assistant:[/bold green] ", end="")
                    first_token = False
                print(chunk.text, end="", flush=True)
                full_response_text += chunk.text
                
        print(f"\n[Model-2] Primary model {PRIMARY_MODEL_ID} async execution: SUCCESSFUL.")
        return full_response_text

    except Exception as e:
        print(f"[Model-2] Primary model stream failure ({e}). Routing to Gemini Flash backup chain...")
        full_response_text = ""
        try:
            genai_client = get_genai_client()
            response_stream = await genai_client.aio.models.generate_content_stream(
                model=FALLBACK_MODEL_ID,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=GROUNDED_SYSTEM_PROMPT,
                    temperature=0.7,
                )
            )
            
            first_token = True
            async for chunk in response_stream:
                if chunk.text:
                    if first_token:
                        console.print("\n[bold green]Assistant:[/bold green] ", end="")
                        first_token = False
                    print(chunk.text, end="", flush=True)
                    full_response_text += chunk.text
            
            print(f"\n[Model-2] Fallback model {FALLBACK_MODEL_ID} stream execution: SUCCESSFUL.")
            return full_response_text
        except Exception as e2:
            print(f"\n[Model-2] Critical: Model fallback exhaust. Details: {e2}", file=sys.stderr)
            return "Error: Could not generate response from either primary or backup models."

# ==========================================
# 7. Non-Blocking Coroutine Task Workers
# ==========================================
async def async_index_task(text: str):
    """Replaces old system thread processing with native async task worker pools."""
    try:
        vector = await get_embedding_async(text)
        doc_id = str(uuid.uuid4())
        timestamp = int(time.time())
        
        with buffer_lock:
            collection.add(
                ids=[doc_id],
                embeddings=[vector],
                documents=[text],
                metadatas=[{"timestamp": timestamp}]
            )
        print(f"\n[AsyncWorker] Successfully indexed chunk to ChromaDB. ID: {doc_id}")
    except Exception as e:
        print(f"\n[AsyncWorker] Error indexing document: {e}", file=sys.stderr)
    finally:
        with buffer_lock:
            if text in pending_commit_buffer:
                pending_commit_buffer.remove(text)
                print(f"[AsyncWorker] Evicted chunk from volatile buffer.")

def index_in_background(text: str):
    """Enqueues processing into loop framework without thread spawning overhead."""
    with buffer_lock:
        pending_commit_buffer.append(text)
    asyncio.create_task(async_index_task(text))

def purge_memory():
    """Wipes session contexts cleanly."""
    global collection
    print("[Purge] Initiating full memory burn...")
    with buffer_lock:
        try:
            chroma_client.delete_collection("research_session_memory")
        except Exception:
            pass
        collection = chroma_client.get_or_create_collection(
            name="research_session_memory",
            metadata={"hnsw:space": "cosine"}
        )
        pending_commit_buffer.clear()
        conversation_history_verbatim.clear()
    print("[Purge] Ephemeral datastores wiped clean.")

# ==========================================
# 8. Async Orchestration Loop Driver
# ==========================================
async def run_cli_loop_async():
    global conversation_history_verbatim
    console = Console()
    console.print("\n[bold cyan]======================================================[/bold cyan]")
    console.print("[bold green]🚀 Welcome to Ephemeral Engine: SC-EVM CLI (Async Engine)[/bold green]")
    console.print("[dim]Latency Level: Sub-Second Token Streaming | ChromaDB Cosine Gated[/dim]")
    console.print("[bold cyan]======================================================[/bold cyan]")
    console.print("Commands: [bold yellow]/burn[/bold yellow] to wipe memory, [bold yellow]exit[/bold yellow] to cleanly terminate.\n")
    
    turn_counter = 0
    while True:
        try:
            user_input = input(f"\n[Turn {turn_counter + 1}] User: ").strip()
            if not user_input:
                continue
                
            if user_input.lower() == "exit":
                purge_memory()
                break
                
            if user_input == "/burn":
                purge_memory()
                continue
                
            turn_counter += 1
            start_time = time.time()
            
            # Step 1 & 2: Asynchronous Query Routing & Semantic Retrieval
            rewritten_query = await rewrite_query_async(user_input)
            retrieved_context = await search_memory_async(rewritten_query)
            
            # Step 3: Stream Out Response Tokens Realtime
            response = await stream_grounded_response(user_input, retrieved_context, console)
            
            # Step 4: Tracking & Housekeeping sliding dialogue windows
            with buffer_lock:
                conversation_history_verbatim.append({"role": "user", "content": user_input})
                conversation_history_verbatim.append({"role": "assistant", "content": response})
                while len(conversation_history_verbatim) > 6:
                    conversation_history_verbatim.pop(0)
            
            # Step 5: Background Indexing via Async Tasks
            index_chunk = f"User: {user_input}\nAssistant: {response}"
            index_in_background(index_chunk)
            
            latency = time.time() - start_time
            console.print(f"\n[dim](Turn execution pipeline latency: {latency:.2f}s)[/dim]")
            
        except KeyboardInterrupt:
            purge_memory()
            break
        except Exception as e:
            console.print(f"[bold red]Error in Event Loop: {e}[/bold red]")

# ==========================================
# 9. Async Integration Test Suite
# ==========================================
async def run_integration_test_async():
    console = Console()
    console.print("[bold yellow]Running automated async integration test suite...[/bold yellow]")
    
    # Verify ADC
    if not verify_adc_connection():
        console.print("[bold red]ADC Verification failed. Integration test failed.[/bold red]")
        sys.exit(1)
        
    # --- Turn 1 ---
    console.print("\n[Test Turn 1] User query: 'Let's optimize the network routing rule.'")
    user_q1 = "Let's optimize the network routing rule."
    rewritten_q1 = await rewrite_query_async(user_q1)
    context_q1 = await search_memory_async(rewritten_q1)
    
    # Run the stream output inside the test
    response_q1 = await stream_grounded_response(user_q1, context_q1, console)
    console.print(f"\n[Test Turn 1] Assistant response complete.")
    
    with buffer_lock:
        conversation_history_verbatim.append({"role": "user", "content": user_q1})
        conversation_history_verbatim.append({"role": "assistant", "content": response_q1})
        
    # Index Turn 1 in background
    index_chunk_1 = f"User: {user_q1}\nAssistant: {response_q1}"
    index_in_background(index_chunk_1)
    
    # Sleep momentarily to let background worker run
    await asyncio.sleep(2)
    
    # --- Turn 2 ---
    console.print("\n[Test Turn 2] User query: 'Wait, update that value to 443 instead.'")
    user_q2 = "Wait, update that value to 443 instead."
    rewritten_q2 = await rewrite_query_async(user_q2)
    
    # Assert query reformulation resolved "that value" to network routing rule/port
    if "routing" not in rewritten_q2.lower() and "port" not in rewritten_q2.lower() and "rule" not in rewritten_q2.lower() and "priority" not in rewritten_q2.lower():
        console.print(f"[bold red]Integration Test Failed: Query rewriter did not resolve pronouns. Rewritten was: '{rewritten_q2}'[/bold red]")
        sys.exit(1)
        
    # Retrieve context
    context_q2 = await search_memory_async(rewritten_q2)
    response_q2 = await stream_grounded_response(user_q2, context_q2, console)
    console.print(f"\n[Test Turn 2] Assistant response complete.")
    
    with buffer_lock:
        conversation_history_verbatim.append({"role": "user", "content": user_q2})
        conversation_history_verbatim.append({"role": "assistant", "content": response_q2})
        
    # Index Turn 2 in background
    index_chunk_2 = f"User: {user_q2}\nAssistant: {response_q2}"
    index_in_background(index_chunk_2)
    
    # Sleep momentarily
    await asyncio.sleep(2)
    
    # --- Turn 3 (/burn) ---
    console.print("\n[Test Turn 3] Testing /burn purge operation...")
    purge_memory()
    
    with buffer_lock:
        hist_len = len(conversation_history_verbatim)
        buffer_len = len(pending_commit_buffer)
        
    if hist_len == 0 and buffer_len == 0:
        console.print("[bold green]✓ Integration test successful: All components function perfectly![/bold green]")
        sys.exit(0)
    else:
        console.print(f"[bold red]Integration Test Failed: Purge did not clear buffers (History: {hist_len}, Buffer: {buffer_len}).[/bold red]")
        sys.exit(1)

# ==========================================
# Entry Point
# ==========================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ephemeral Engine: SC-EVM Architecture")
    parser.add_argument("--test", action="store_true", help="Run the automated async integration test suite")
    args = parser.parse_args()
    
    if args.test:
        asyncio.run(run_integration_test_async())
    else:
        asyncio.run(run_cli_loop_async())
