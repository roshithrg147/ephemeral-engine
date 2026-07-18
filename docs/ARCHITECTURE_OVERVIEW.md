# Architecture Overview

SC-EVM is a session-isolated context-control middleware.

For the granular code-derived runtime, API, state, deployment, integration, and
clean-room replication specification, see
[System Architecture and Workflow Specification](SYSTEM_ARCHITECTURE_AND_WORKFLOW_SPECIFICATION.md).

## Core Pillars
1. **Relevance:** Dense retrieval via local embeddings and outlier gating to filter context.
2. **Isolation:** Strict separation of session spaces in volatile RAM and vector storage.
3. **Control:** Ephemeral memory constraints and deletion hooks.
4. **Evidence:** Immutable execution telemetry and statistical verification.

SC-EVM uses a local vector collection (ChromaDB) to manage context indexes per session. It employs a dual-model synthesis strategy for processing queries.

## Lifecycle Guide

For a plain-language walkthrough of session isolation, bounded history, context retrieval, turn
commit, background indexing, and burn across a representative workload, see
[20-Turn, 20-Session Lifecycle](20-TURN-20-SESSION-LIFECYCLE.md).
