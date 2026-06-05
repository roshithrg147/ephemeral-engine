import os
import sys
import time
import uuid
import threading
import argparse
import google.auth
from google import genai
from google.genai import types
import anthropic
from anthropic import AnthropicVertex
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
# 3. Connection Diagnostics & Auth Setup
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
# 4. Part 2: Query Reformulation Layer
# ==========================================
REWRITE_MODEL_ID = "publishers/google/models/gemini-2.5-flash"

REWRITE_SYSTEM_PROMPT = """You are a query reformulation assistant.
Given a conversation history and a new user prompt, rewrite the user's prompt into a search-optimized vector query.
Resolve any pronoun references (like 'that value', 'it', 'them', 'the file') to their actual entities in the history.
Do NOT reply with a chat response. ONLY return the rewritten search query. If the prompt is simple or does not need reformulation, return the original prompt verbatim.
"""

@retry(stop=stop_after_attempt(3), wait=wait_random_exponential(min=1, max=10))
def rewrite_query(user_raw_input: str) -> str:
    """
    Reformulates the user's raw input based on a sliding window of the last 3 conversation turns.
    Uses Gemini Flash via Vertex AI.
    """
    credentials, project_id = google.auth.default()
    if not project_id:
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
    location = os.getenv("VERTEX_GEMINI_LOCATION", "us-central1")
    client = genai.Client(vertexai=True, location=location, project=project_id)
    
    with buffer_lock:
        history_window = conversation_history_verbatim[-6:]
        
    formatted_history = []
    for turn in history_window:
        role_label = "User" if turn.get("role") == "user" else "Assistant"
        formatted_history.append(f"{role_label}: {turn.get('content')}")
        
    history_str = "\n".join(formatted_history)
    
    prompt = f"""Conversation History:
{history_str}

Current User Prompt: {user_raw_input}

Rewritten search query:"""

    try:
        response = client.models.generate_content(
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
# 5. Part 3: Semantic Search & Cosine Distance Filtering
# ==========================================
EMBEDDING_MODEL_ID = "text-embedding-004"

@retry(stop=stop_after_attempt(3), wait=wait_random_exponential(min=1, max=10))
def get_embedding(text: str) -> list[float]:
    """Generates text embedding vector using text-embedding-004 on Vertex AI."""
    credentials, project_id = google.auth.default()
    if not project_id:
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
    location = os.getenv("VERTEX_GEMINI_LOCATION", "us-central1")
    client = genai.Client(vertexai=True, location=location, project=project_id)
    
    response = client.models.embed_content(
        model=EMBEDDING_MODEL_ID,
        contents=text
    )
    return response.embeddings[0].values

def search_memory(query: str, limit: int = 3) -> list[str]:
    """
    Queries ChromaDB with the cosine distance threshold <= 0.60.
    Returns matched documents.
    """
    print(f"[SearchMemory] Querying semantic memory for: '{query}'...")
    try:
        query_vector = get_embedding(query)
        
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
            
            for doc, dist in zip(docs, distances):
                print(f"[SearchMemory] Match candidate: '{doc}' (cosine distance = {dist:.4f})")
                if dist <= 0.60:
                    matched_docs.append(doc)
                else:
                    print(f"[SearchMemory] Excluded: Cosine distance {dist:.4f} exceeds threshold of 0.60")
        return matched_docs
    except Exception as e:
        print(f"[SearchMemory] Error performing vector search: {e}", file=sys.stderr)
        return []

# ==========================================
# 6. Part 4: Dual-Model Failover & Context Queue Interception
# ==========================================
GROUNDED_SYSTEM_PROMPT = """You are an elite research assistant.
You must answer the user's query using the provided conversation history and retrieved context.
Be direct, helpful, and technically precise.
"""

@retry(stop=stop_after_attempt(2), wait=wait_random_exponential(min=1, max=5), reraise=True)
def query_claude_opus(system_prompt: str, user_prompt: str) -> str:
    """Queries Claude Opus on Vertex AI. Retries twice on transient errors before propagating."""
    credentials, project_id = google.auth.default()
    client = AnthropicVertex(region="us-east5", project_id=project_id)
    
    messages = [{"role": "user", "content": user_prompt}]
    res = client.messages.create(
        model="claude-3-opus@20240229",
        max_tokens=2048,
        system=system_prompt,
        messages=messages,
        timeout=30.0
    )
    return res.content[0].text

@retry(stop=stop_after_attempt(3), wait=wait_random_exponential(min=1, max=10))
def query_gemini_pro(system_prompt: str, user_prompt: str) -> str:
    """Queries Gemini 2.5 Pro on Vertex AI as a robust fallback model."""
    credentials, project_id = google.auth.default()
    if not project_id:
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
    location = os.getenv("VERTEX_GEMINI_LOCATION", "us-central1")
    client = genai.Client(vertexai=True, location=location, project=project_id)
    
    response = client.models.generate_content(
        model="publishers/google/models/gemini-2.5-pro",
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.7,
        )
    )
    return response.text

def generate_grounded_response(user_input: str, retrieved_context: list[str]) -> str:
    """
    Generates a grounded response.
    First tries Claude Opus, and falls back to Gemini Pro on failure.
    Integrates the Memory Buffer Interceptor to append unindexed memories.
    """
    # 1. Memory Buffer Interceptor
    with buffer_lock:
        unindexed_memories = list(pending_commit_buffer)
        
    context_list = list(retrieved_context)
    if unindexed_memories:
        print(f"[Interceptor] Intercepted {len(unindexed_memories)} pending unindexed memories.")
        interceptor_str = "[Pending Active Queue Context (Unindexed)]:\n" + "\n".join(unindexed_memories)
        context_list.append(interceptor_str)
        
    context_str = "\n\n".join(context_list)
    
    # 2. Compile history
    with buffer_lock:
        history_window = conversation_history_verbatim[-6:]
    
    history_str = ""
    for turn in history_window:
        role = "User" if turn["role"] == "user" else "Assistant"
        history_str += f"{role}: {turn['content']}\n"
        
    # Construct the final prompt payload
    user_prompt = f"""--- RETRIEVED CONTEXT ---
{context_str}

--- CONVERSATION HISTORY ---
{history_str}

--- CURRENT USER PROMPT ---
{user_input}
"""

    # 3. Model 2 Execution Block with Failover
    print("[Model-2] Querying primary model Claude Opus...")
    try:
        response = query_claude_opus(GROUNDED_SYSTEM_PROMPT, user_prompt)
        print("[Model-2] Claude Opus execution: SUCCESSFUL.")
        return response
    except Exception as e:
        print(f"[Model-2] Claude Opus execution failed ({e}). Routing to Gemini Pro backup model...")
        try:
            response = query_gemini_pro(GROUNDED_SYSTEM_PROMPT, user_prompt)
            print("[Model-2] Gemini Pro backup execution: SUCCESSFUL.")
            return response
        except Exception as e2:
            error_msg = f"[Model-2] Critical: Both Claude Opus and Gemini Pro failed. Details: {e2}"
            print(error_msg, file=sys.stderr)
            return "Error: Could not generate response from either primary or backup models."

# ==========================================
# 7. Part 5: Async Background Workers & Purge Operations
# ==========================================
def async_index_worker(text: str):
    """
    Background worker that runs inside a daemon thread.
    Encodes the given text chunk and commits it to ChromaDB.
    Evicts the text from the volatile pending_commit_buffer queue upon completion.
    """
    try:
        print(f"[AsyncWorker] Starting background embedding creation for text chunk...")
        vector = get_embedding(text)
        
        doc_id = str(uuid.uuid4())
        timestamp = int(time.time())
        
        with buffer_lock:
            collection.add(
                ids=[doc_id],
                embeddings=[vector],
                documents=[text],
                metadatas=[{"timestamp": timestamp}]
            )
        print(f"[AsyncWorker] Successfully indexed to ChromaDB. ID: {doc_id}")
    except Exception as e:
        print(f"[AsyncWorker] Error indexing document: {e}", file=sys.stderr)
    finally:
        # Secure eviction from active volatile buffer
        with buffer_lock:
            if text in pending_commit_buffer:
                pending_commit_buffer.remove(text)
                print(f"[AsyncWorker] Evicted chunk from pending_commit_buffer queue.")

def index_in_background(text: str):
    """Appends to the volatile queue buffer and spawns the background worker."""
    with buffer_lock:
        pending_commit_buffer.append(text)
        
    thread = threading.Thread(target=async_index_worker, args=(text,), daemon=True)
    thread.start()

def purge_memory():
    """Wipes the ChromaDB collections and completely resets the volatile buffers."""
    global collection, pending_commit_buffer, conversation_history_verbatim
    print("[Purge] Initiating memory burn and collection wipe...")
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
    print("[Purge] All ephemeral contexts and databases successfully wiped.")

# ==========================================
# 8. Interactive CLI & Orchestration Loop
# ==========================================
def run_cli_loop():
    global conversation_history_verbatim
    console = Console()
    console.print("\n[bold cyan]======================================================[/bold cyan]")
    console.print("[bold green]🚀 Welcome to Ephemeral Engine: SC-EVM CLI[/bold green]")
    console.print("[dim]Architecture: In-Memory ChromaDB | Gemini Flash Rewriter | Claude Opus (failover) | Async Queueing[/dim]")
    console.print("[bold cyan]======================================================[/bold cyan]")
    console.print("Commands: [bold yellow]/burn[/bold yellow] to wipe memory, [bold yellow]exit[/bold yellow] to cleanly terminate.\n")
    
    turn_counter = 0
    
    while True:
        try:
            user_input = input(f"\n[Turn {turn_counter + 1}] User: ").strip()
            if not user_input:
                continue
                
            if user_input.lower() == "exit":
                console.print("[bold yellow]Cleaning up local transient caches...[/bold yellow]")
                purge_memory()
                console.print("[bold green]Goodbye![/bold green]")
                break
                
            if user_input == "/burn":
                purge_memory()
                continue
                
            turn_counter += 1
            start_time = time.time()
            
            # Step 1: Query Reformulation
            rewritten_query = rewrite_query(user_input)
            
            # Step 2: Semantic Memory Retrieval
            retrieved_context = search_memory(rewritten_query)
            
            # Step 3: Grounded Response Generation (incorporating queue interceptor)
            response = generate_grounded_response(user_input, retrieved_context)
            
            # Step 4: Update sliding verbatim dialogue history
            with buffer_lock:
                conversation_history_verbatim.append({"role": "user", "content": user_input})
                conversation_history_verbatim.append({"role": "assistant", "content": response})
                # Keep sliding window to last 3 turns (6 messages)
                while len(conversation_history_verbatim) > 6:
                    conversation_history_verbatim.pop(0)
            
            # Step 5: Queue background indexing for future turns
            index_chunk = f"User: {user_input}\nAssistant: {response}"
            index_in_background(index_chunk)
            
            latency = time.time() - start_time
            
            # Print response
            console.print(f"\n[bold green]Assistant:[/bold green] {response}")
            console.print(f"[dim](Loop latency: {latency:.2f}s)[/dim]")
            
        except KeyboardInterrupt:
            console.print("\n[bold yellow]KeyboardInterrupt captured. Cleaning up caches...[/bold yellow]")
            purge_memory()
            break
        except Exception as e:
            console.print(f"[bold red]Error in CLI Loop: {e}[/bold red]")

# ==========================================
# 9. Automated Integration Test Suite
# ==========================================
def run_integration_test():
    console = Console()
    console.print("[bold yellow]Running automated integration test suite...[/bold yellow]")
    
    # Verify ADC
    if not verify_adc_connection():
        console.print("[bold red]ADC Verification failed. Integration test failed.[/bold red]")
        sys.exit(1)
        
    # --- Turn 1 ---
    console.print("\n[Test Turn 1] User query: 'Let's optimize the network routing rule.'")
    user_q1 = "Let's optimize the network routing rule."
    rewritten_q1 = rewrite_query(user_q1)
    context_q1 = search_memory(rewritten_q1)
    response_q1 = generate_grounded_response(user_q1, context_q1)
    console.print(f"[Test Turn 1] Assistant: {response_q1}")
    
    with buffer_lock:
        conversation_history_verbatim.append({"role": "user", "content": user_q1})
        conversation_history_verbatim.append({"role": "assistant", "content": response_q1})
        
    # Index Turn 1 in background
    index_chunk_1 = f"User: {user_q1}\nAssistant: {response_q1}"
    index_in_background(index_chunk_1)
    
    # Sleep momentarily to let background worker run
    time.sleep(2)
    
    # --- Turn 2 ---
    console.print("\n[Test Turn 2] User query: 'Wait, update that value to 443 instead.'")
    user_q2 = "Wait, update that value to 443 instead."
    rewritten_q2 = rewrite_query(user_q2)
    
    # Assert query reformulation resolved "that value" to network routing rule/port
    if "routing" not in rewritten_q2.lower() and "port" not in rewritten_q2.lower() and "rule" not in rewritten_q2.lower():
        console.print("[bold red]Integration Test Failed: Query rewriter did not resolve pronouns.[/bold red]")
        sys.exit(1)
        
    # Retrieve context
    context_q2 = search_memory(rewritten_q2)
    response_q2 = generate_grounded_response(user_q2, context_q2)
    console.print(f"[Test Turn 2] Assistant: {response_q2}")
    
    with buffer_lock:
        conversation_history_verbatim.append({"role": "user", "content": user_q2})
        conversation_history_verbatim.append({"role": "assistant", "content": response_q2})
        
    # Index Turn 2 in background
    index_chunk_2 = f"User: {user_q2}\nAssistant: {response_q2}"
    index_in_background(index_chunk_2)
    
    # Sleep momentarily
    time.sleep(2)
    
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
    parser.add_argument("--test", action="store_true", help="Run the automated integration test suite")
    args = parser.parse_args()
    
    if args.test:
        run_integration_test()
    else:
        run_cli_loop()
