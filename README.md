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
   [User Prompt]
         │
         ▼
┌──────────────────────────┐
│   Async Query Rewriter   │ ───► Resolves context & pronouns via Gemini 2.5 Flash
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│  Transient Vector DB     │ ───► In-Memory ChromaDB (Ephemeral, isolated per session)
│ (Dynamic Top-K Gating)   │ ───► Prunes noise via Statistical Variance Delta Analysis
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐      ┌───────────────────────────────┐
│ Memory Queue Interceptor │ ◄─── │ Volatile Write Buffer Queue   │
└────────────┬─────────────┘      └───────────────────────────────┘
             │                     (Captures fast-typing threads before VDB commit)
             ▼
┌──────────────────────────┐
│ Grounded Stream Reasoner │ ───► Token Streaming via Gemini 2.5 Pro Async Client
└──────────────────────────┘
```

### Key Engineering Features
* **Token Flattening Layer:** Pins long-turn conversation payloads to a predictable budget by avoiding forcing the primary model to re-read thousands of lines of redundant history.
* **Dynamic Top-K Fallback Gating:** Replaces fragile static cosine thresholds with an aggressive distance variance calculator ($\Delta \le 0.15$). It automatically groups relevant topics together while mathematically excluding contextual drift (e.g., completely ignoring tangential queries).
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

---

## 🛠️ Interactive Session Commands

Inside the execution loop, the interactive CLI exposes structural runtime actions:

* `/burn` : Forces an instantaneous clear of the volatile buffer queue, wipes out the active in-memory ChromaDB collection, and flushes dialogue histories.
* `exit` : Executes a safe, graceful termination sequence, triggers a full memory burn, and securely disconnects network socket channels.

---

## 📦 SDK & Middleware Integration (Roadmap)

To easily drop the SC-EVM execution flow straight into any cloud-native pipeline or enterprise microservice framework (e.g., FastAPI), wrap the core pipeline as a modular client proxy class:

```python
import asyncio
from sc_evm import EphemeralMemoryProxy

async def main():
    # Instantiates transient collections, configures thread-safe locks, and binds Vertex AI channels
    proxy = EphemeralMemoryProxy()
    
    user_prompt = "Update our system architecture to utilize Kafka partitions."
    
    print("Assistant: ", end="")
    # Asynchronously reformulates intents, screens memories, and streams raw token chunks
    async for token in proxy.chat_stream(session_id="session_01j8", prompt=user_prompt):
        print(token, end="", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 🛡️ License

Distributed under the MIT License. See `LICENSE` for more information.
