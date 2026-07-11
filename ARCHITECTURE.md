# Architecture and State Report

> **Governance:** This document describes the implemented technical architecture. Changes require architecture review, and this record must distinguish implemented behavior, experimental behavior, limitations, and proposed work. It conforms to the [Product Manifesto](MANIFESTO.md), [Product Boundary](PRODUCT_BOUNDARY.md), and [RFC process](rfcs/README.md).

This document records the current implemented state of the `ephemeral-engine` codebase. It is descriptive rather than aspirational.

## 1. System Overview & Tech Stack
**Primary Purpose:**
The application serves as a terminal-based and web-interfaced personal assistant, functioning fundamentally as a State-Cached Ephemeral Vector Memory (SC-EVM) Microservice. It features a Dual-LLM architecture (leveraging Qwen and Kimi via NVIDIA NIM APIs) to provide highly synthesized, context-aware responses with separate short-term (ephemeral) and long-term (persistent) memory planes.

**Tech Stack:**
*   **Runtime/Language:** Python >= 3.11
*   **Backend Framework:** FastAPI with Uvicorn (ASGI server)
*   **Vector Database:** ChromaDB (Ephemeral Client, ONNXMiniLM_L6_V2)
*   **LLM Interface:** NVIDIA NIM APIs (via standard `httpx` async/sync clients)
*   **Frontend Dashboard:** React 19, React Router DOM 7, TailwindCSS 3 (PostCSS/Autoprefixer), Recharts
*   **Other Critical Dependencies:** Pydantic (data validation), asyncio (concurrency).

## 2. Architectural Map

**Component Breakdown:**
*   **Frontend (`engine-dashboard/`)**: A Create React App structured with TailwindCSS for styling. Acts as the control plane to visualize engine stats, session data, and interact via chat.
*   **Backend Application Entry (`src/main.py`)**: Defines FastAPI routes, an SSE endpoint (`/api/agent/query`), and lifespan events. Orchestrates requests into the SC-EVM engine and the MultiTenantSessionRegistry.
*   **Agent Orchestrator (`src/agent.py`)**: Houses the Dual-LLM logic. Prompts two models simultaneously (Claude/Kimi and Gemini/Qwen equivalents) in separate threads, then uses a synthesis prompt to refine their outputs into a final `RefinedResponse`. Connects to a local UNIX socket to push responses to a clipboard daemon.
*   **Memory Manager (`src/memory.py`)**:
    *   **Long-Term Memory:** Managed via a persistent JSON file (`~/.assistant_memory.json`).
    *   **Short-Term Memory:** Managed via a `MultiTenantSessionRegistry` which dynamically provisions isolated ChromaDB volatile collections per session and runs a background TTL garbage collector for stale sessions.
*   **SC-EVM Engine (`src/sc_evm.py`)**: Handles complex vector math, reformulates queries, and implements a Dual-Anchor Confidence Gating mechanism to filter retrieved context blocks aggressively, preventing context bloat.
*   **Clients (`src/clients.py`)**: Normalizes LLM API communication, handling exponential backoffs, streaming iterations, and local environment parsing.

**Module Interaction:**
1.  Frontend sends an SSE request to `/api/agent/query`.
2.  `main.py` yields events, querying `sc_evm.py` to reformulate the query and retrieve vector/graphify context.
3.  The augmented prompt is passed to `agent.py`, which fetches long-term context from `memory.py`.
4.  `agent.py` concurrently queries NVIDIA NIM endpoints via `clients.py` and synthesizes the response. The API then emits the completed response as simulated word chunks over SSE; this is not provider-token streaming.
5.  Post-generation, an async background task in `main.py` indexes the interaction back into the ChromaDB session collection.

## 3. Current Execution State

### Implemented behavior

* FastAPI session, memory, burn, dual-model, and SSE query routes.
* Per-session ephemeral collections, bounded history, per-session locking, state manifests, TTL/capacity eviction, and background interaction indexing.
* Query reformulation, confidence-gated context retrieval, protected context assembly, and phase-gated structured actions.
* Configured NVIDIA NIM transport with pooled clients, retries, timeouts, and configurable model identifiers.
* React and terminal reference clients, local lifecycle tooling, VS Code context ingestion, telemetry, and strategy benchmark infrastructure.

### Experimental or incomplete behavior

* **Graphify:** An optional structural-context bridge is implemented and graph artifacts are preserved. It is a strategically differentiating capability outside the MVP; downstream quality uplift remains unvalidated.
* **Dual-model synthesis:** Implemented as an optional reasoning strategy, not the product identity; superiority over a single-model strategy is unvalidated.
* **Image generation:** The action is a stub and is not a product capability.
* **Clipboard synchronization:** Key derivation and integration seams exist, but no relay is implemented; cross-device synchronization is not complete.
* **Dashboard analytics:** Some visualized metrics are placeholders rather than live operational data.

## 4. Known Limitations

* Response text is generated completely before being emitted as word chunks; the current SSE path is not true provider-token streaming.
* Total token use is variable. Only the direct active-history window is bounded; reformulation, retrieved context, synthesis, and output still contribute variable usage.
* The service has no production-grade authentication or authorization boundary for multi-tenant public deployment.
* Session state is local to a process, while learned facts and audit data can use local files; the complete system is not fully stateless.
* Graphify, dual-model quality, long-horizon retention, and hallucination resistance lack controlled outcome evidence.

## 5. Proposed Work

Proposed architectural changes are not canonical merely because they appear in planning documents. Significant changes must begin through the [RFC process](rfcs/README.md), align with the Product Manifesto, and preserve the Product Boundary. RFC-0002 through RFC-0004 are reserved topics only; Day 2 work has not begun.
