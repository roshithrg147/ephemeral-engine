# Architecture Overview

SC-EVM is a session-isolated context-control middleware.

## Core Pillars
1. **Relevance:** Dense retrieval via local embeddings and outlier gating to filter context.
2. **Isolation:** Strict separation of session spaces in volatile RAM and vector storage.
3. **Control:** Ephemeral memory constraints and deletion hooks.
4. **Evidence:** Immutable execution telemetry and statistical verification.

SC-EVM uses a local vector collection (ChromaDB) to manage context indexes per session. It employs a dual-model synthesis strategy for processing queries.
