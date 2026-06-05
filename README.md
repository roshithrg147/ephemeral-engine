# Ephemeral Engine: State-Cached Ephemeral Vector Memory (SC-EVM)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Manager: uv](https://img.shields.io/badge/managed%20by-uv-purple.svg)](https://github.com/astral-sh/uv)
[![Backend: Vertex AI](https://img.shields.io/badge/Backend-Vertex%20AI-blue.svg)](https://cloud.google.com/vertex-ai)

Ephemeral Engine is an ultra-low latency, enterprise-grade AI middleware framework designed to break the **token accumulation death spiral** and eliminate **context blindness** in multi-turn LLM applications. 

By shifting from standard, linear append-only chat wrappers to a **State-Cached Ephemeral Vector Memory (SC-EVM)** architecture, the engine flattens input payload costs and keeps long-running agent conversations capped at a predictable, constant token footprint.

---

## 🏗️ Architecture Overview

The framework operates as an asynchronous pipeline that isolates session memories, reformulates ambiguous user intents, and dynamically pulls relevant context using advanced vector clustering statistics.

```
                  ┌──────────────────────────┐
                  │       User Prompt        │
                  └────────────┬─────────────┘
                               │
                               ▼
                  ┌──────────────────────────┐
                  │ Async Intent Realigner   │ ───► Dual-Purpose JSON payload output
                  └────────────┬─────────────┘      (Search query + Grounded Prompt)
                               │
                ┌──────────────┴──────────────┐
                ▼                             ▼
   ┌──────────────────────────┐  ┌──────────────────────────┐
   │    Transient ChromaDB    │  │ Grounded Stream Reasoner │
   │ (Dual-Anchor Protection) │  │  (Secure XML Enclosures) │
   └──────────────────────────┘  └──────────────────────────┘
```

### Key Engineering Features
* **Token Flattening Layer:** Pins long-turn conversation payloads to a predictable budget by avoiding forcing the primary model to re-read thousands of lines of redundant history.
* **Dual-Anchor Protection Gating Engine:** Prunes matching memories between `0.41` and `0.48` cosine distance against both the immediately accepted neighbor ($\Delta \le 0.12$) and the absolute closest top anchor match ($\Delta \le 0.18$). This completely neutralizes the threat vector where an irrelevant topic (like coffee) creeps into the session context by hitchhiking next to an adjacent cluster.
* **Dual-Purpose Intent Realignment:** The Async Query Reformulator outputs a structured JSON schema:
  1. `search_vector_query`: A dense, keyword-heavy search query optimized strictly for vector database similarity matches.
  2. `grounded_llm_prompt`: An expanded, fully explicit version of the prompt resolving all pronouns and fragmented context links. This ensures both vector search and primary reasoner are aligned.
* **Persistent Global Connection Singleton:** Lazy-initializes a thread-safe, module-level Google GenAI client (`_GENAI_CLIENT`), reusing it for query reformulations, embeddings, and token streaming to eliminate Google Auth credential validation handshake latencies.
* **XML-Tagged Enclosure Prompt Segregation:** Segregates retrieved contexts and pending memories inside explicit `<retrieved_memory>` XML tags. The system prompt instructs the reasoner to treat these contents strictly as untrusted data references, ensuring that instructions or overrides embedded in history cannot affect model behavior.
* **Volatile Memory Interceptor Proxy:** A thread-safe, locked buffer (`pending_commit_buffer`) that acts as a real-time cache. If an embedding worker thread is mid-flight over the network during high-speed typing, the downstream reasoner intercepts the raw string to guarantee complete contextual ingestion.
* **Hard Session Isolation:** Built for strict B2B compliance. Caches and memory frames exist strictly in serverless, transient in-memory spaces, completely wiped down to physical disk layers upon termination (`/burn` or `exit`).

---

## ⚡ Quick Start

### Prerequisites
* Python 3.11 or higher.
* Installed [`uv`](https://github.com/astral-sh/uv) package manager.
* A Google Cloud Project with the **Vertex AI API** enabled.
* User credentials or [Application Default Credentials (ADC)](https://cloud.google.com/docs/authentication/provide-credentials-adc) configured locally.

### Environment Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/roshithrg147/ephemeral-engine.git
   cd ephemeral-engine
   ```

2. Configure your environment variables:
   ```bash
   export GOOGLE_CLOUD_PROJECT="your-gcp-project-id"
   export VERTEX_GEMINI_LOCATION="us-central1"
   ```

3. Initialize dependencies and run the streaming interactive CLI using `uv`:
   ```bash
   uv run python src/sc_evm.py
   ```

### Running Automated Integration Tests
Verify the entire pipeline including connection diagnostics, dual-anchor gating boundaries, JSON query reformulation, and turn execution:
```bash
uv run python src/sc_evm.py --test
```

---

## 🛠️ Interactive Session Commands

Inside the execution loop, the interactive CLI exposes structural runtime actions:

* `/burn` : Forces an instantaneous clear of the volatile buffer queue, wipes out the active in-memory ChromaDB collection, and flushes dialogue histories.
* `exit` : Executes a safe, graceful termination sequence, triggers a full memory burn, and securely disconnects network socket channels.

---

## 🛡️ License

Distributed under the MIT License. See `LICENSE` for more information.
