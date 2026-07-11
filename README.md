# Ephemeral Engine: State-Cached Ephemeral Vector Memory (SC-EVM)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Manager: uv](https://img.shields.io/badge/managed%20by-uv-purple.svg)](https://github.com/astral-sh/uv)
[![Backend: NVIDIA NIM](https://img.shields.io/badge/Backend-NVIDIA%20NIM-76B900.svg)](https://build.nvidia.com/)

Ephemeral Engine is AI context-control middleware designed to reduce unbounded conversation-history growth and context blindness in multi-turn applications.

By shifting from linear append-only chat history to a **State-Cached Ephemeral Vector Memory (SC-EVM)** architecture, the engine bounds the direct active-history window and retrieves selected prior context. Total token use remains variable because retrieved context, reformulation, reasoning, and output also contribute to usage.

## Governance and Source of Truth

- [Product Manifesto](MANIFESTO.md) — the highest-level philosophy, principles, pillars, and long-term ambition.
- [Product Boundary](PRODUCT_BOUNDARY.md) — the authoritative product definition, MVP, scope, classification, and non-goals.
- [Architecture](ARCHITECTURE.md) — the authoritative description of implemented technical behavior, experiments, limitations, and proposed work.
- [RFC process](rfcs/README.md) — the controlled process for significant product and architecture decisions.

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
* **Bounded Active History:** Caps the direct conversation-history window while selected retrieved context remains variable.
* **Dual-Anchor Protection Gating Engine:** Prunes matching memories using absolute and relative confidence rules to reduce irrelevant context creep; retrieval-quality improvement requires controlled validation.
* **Dual-Purpose Intent Realignment:** The Async Query Reformulator outputs a structured JSON schema:
  1. `search_vector_query`: A dense, keyword-heavy search query optimized strictly for vector database similarity matches.
  2. `grounded_llm_prompt`: An expanded, fully explicit version of the prompt resolving all pronouns and fragmented context links. This ensures both vector search and primary reasoner are aligned.
* **Pooled Model Connections:** Reuses configured HTTP clients for model calls and applies timeouts and retries.
* **XML-Tagged Enclosure Prompt Segregation:** Segregates retrieved contexts and pending memories inside explicit `<retrieved_memory>` XML tags. The system prompt instructs the reasoner to treat these contents strictly as untrusted data references, ensuring that instructions or overrides embedded in history cannot affect model behavior.
* **Volatile Memory Interceptor Proxy:** A thread-safe, locked buffer (`pending_commit_buffer`) that acts as a real-time cache. If an embedding worker thread is mid-flight over the network during high-speed typing, the downstream reasoner intercepts the raw string to guarantee complete contextual ingestion.
* **Session Isolation and Burn:** Maintains separate in-process session state and provides explicit burn behavior that deletes the session record and its ephemeral collection. This does not claim physical RAM destruction or erase separate durable audit and learned-fact files.

---

## ⚡ Quick Start

### Prerequisites
* Python 3.11 or higher.
* Installed [`uv`](https://github.com/astral-sh/uv) package manager.
* An NVIDIA API key with access to the configured models.

### Environment Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/roshithrg147/ephemeral-engine.git
   cd ephemeral-engine
   ```

2. Configure your environment variables:
   ```bash
   export NVIDIA_API_KEY="your-api-key"
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
