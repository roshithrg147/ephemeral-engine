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

## Canonical Capability Mapping Matrix

Every claimed capability maps to **one canonical backend module**, **one canonical test suite**, and **one canonical dashboard surface**:

| Capability | Canonical Backend Module | Canonical Test Suite | Canonical Dashboard Surface |
| :--- | :--- | :--- | :--- |
| **1. Session Lifecycle & Burn Isolation** | [`src/memory.py`](../src/memory.py) & [`src/services/session_lifecycle.py`](../src/services/session_lifecycle.py) | [`src/tests/test_secure_lifecycle.py`](../src/tests/test_secure_lifecycle.py) | **Session Rail** (`SessionRail.tsx`) & Header Status |
| **2. Adaptive Outlier Thresholding & Calibration** | [`src/thresholds.py`](../src/thresholds.py) (`AdaptiveThresholdEngine`) | [`src/tests/test_thresholds_engine.py`](../src/tests/test_thresholds_engine.py) | **Inspector Context Panel** (`Inspector.tsx`) |
| **3. Hybrid Retrieval Fusion (Vector + Graphify AST)** | [`src/sc_evm.py`](../src/sc_evm.py) & [`src/services/fusion_engine.py`](../src/services/fusion_engine.py) | [`src/tests/test_hybrid_fusion.py`](../src/tests/test_hybrid_fusion.py) | **Inspector Event Log & Context Viewer** |
| **4. Query Reformulation & Context Control Plane** | [`src/services/prompt_manager.py`](../src/services/prompt_manager.py) & [`src/services/intent_router.py`](../src/services/intent_router.py) | [`src/tests/test_context_control_plane.py`](../src/tests/test_context_control_plane.py) | **Conversation Canvas** (`ConversationCanvas.tsx`) & Intent Badges |
| **5. Assistant Mode Switching (Coding vs Research)** | [`src/services/prompt_manager.py`](../src/services/prompt_manager.py) & [`src/main.py`](../src/main.py) | [`src/tests/test_assistant_mode.py`](../src/tests/test_assistant_mode.py) | **Session Rail Mode Switcher Pill** (`SessionRail.tsx`) |
| **6. Production Security & OIDC Auth** | [`src/security.py`](../src/security.py) (`SecurityManager`) | [`src/tests/test_security_auth.py`](../src/tests/test_security_auth.py) | **Login & Auth View** (`Login.tsx`) |

## Lifecycle Guide

For a plain-language walkthrough of session isolation, bounded history, context retrieval, turn
commit, background indexing, and burn across a representative workload, see
[20-Turn, 20-Session Lifecycle](20-TURN-20-SESSION-LIFECYCLE.md).
