# SC-EVM P0 SECURITY AUDIT REPORT

## Executive Summary
**Date:** 2026-08-05  
**Verdict:** **NOT PRODUCTION-READY**  
An exhaustive, zero-trust security audit was performed on the SC-EVM codebase, focusing on identity isolation, authorization boundaries, memory confinement, and data leakage. Several critical P0 vulnerabilities were discovered that compromise tenant isolation, session isolation, and cross-tenant data boundaries. 

The system cannot safely host multi-tenant workloads in its current state.

---

## 1. Tenant Isolation & Global State Audit (P0 - CRITICAL)

### 1.1 MemoryManager Global Singleton Leakage
**Code Path:** `src/memory.py` -> `MemoryManager`
**Description:** The `MemoryManager` orchestrates long-term persistence and is initialized with a hardcoded, shared global file path: `DEFAULT_MEMORY_PATH = os.path.expanduser("~/.assistant_memory.json")`. The resulting `long_term_data` dictionary (which stores `user_profile`, `learned_facts`, and `interaction_stats`) is shared globally across the entire microservice. 
**Impact:** Tenant A's learned facts, user profiles, and interaction stats are written into the exact same JSON file and memory object as Tenant B. Any user can theoretically recall or pollute long-term memories belonging to another tenant.
**Required Fix:** `MemoryManager` must partition its persistent JSON file (or database equivalent) using `tenant_id` and `owner_subject`.

### 1.2 Vector Collection Hijacking on Eviction 
**Code Path:** `src/memory.py` -> `_evict_capacity_pressure` and `SessionRecord.__init__`
**Description:** Chroma collections are named using an unguarded scalar: `f"session_{session_id}"`. When the system experiences memory pressure, it invokes `_evict_capacity_pressure()`, which pops the session from `MultiTenantSessionRegistry._sessions` but **does not** explicitly delete the Chroma collection from the ephemeral client. 
**Impact:** If Tenant A's session (`session_123`) is evicted, and Tenant B later initiates a session with `session_id="123"`, the `MultiTenantSessionRegistry` will instantiate a new `SessionRecord` under Tenant B's ownership but bind it to the preexisting `session_123` Chroma collection. Tenant B can now retrieve and read all embeddings/documents previously stored by Tenant A.
**Required Fix:** 
1. Bind collections using cryptographic compounds: `f"tenant_{tenant_id}_session_{session_id}"`.
2. Ensure `_evict_capacity_pressure` physically tears down the vector storage space, or maintain tombstone records to block reallocation.

---

## 2. Telemetry and Audit Logs (P1 - HIGH RISK)

### 2.1 Missing Tenant Identifiers in Telemetry Sink
**Code Path:** `src/telemetry_sink.py` -> `log_interaction`
**Description:** The telemetry system writes immutable audit logs to a local disk. The entry payload includes `timestamp`, `session_id`, `role`, and `content`. It explicitly omits `tenant_id`, `owner_subject`, and any unique `request_id`.
**Impact:** It is impossible to attribute an audit log back to its originating tenant in a multi-tenant environment. This violates the audit requirement that every storage key must include `tenant_id`. Furthermore, without `tenant_id`, log scraping systems cannot reliably enforce tenant-based log isolation boundaries.
**Required Fix:** Append `tenant_id` and `owner_subject` to all payloads written by `_append_audit_entry`.

---

## 3. Retrieval Pipeline Audit (P1 - HIGH RISK)

### 3.1 Unbound BM25 Lexical and AST Structural Indexing
**Code Path:** `src/sc_evm.py` -> `do_lexical_search` & `do_structural_search`
**Description:** While BM25 indexing is correctly instantiated locally per request, the AST Indexer (`ASTIndexer`) is invoked on global workspace files without explicit `tenant_id` or repository bounds checks. 
**Impact:** In a true multi-tenant deployment, if the backend shares a local disk for AST processing, an attacker could craft natural language structural queries to leak the abstract syntax trees, function signatures, or proprietary code structure of another tenant's repository.
**Required Fix:** The AST Indexer and BM25 indexer must enforce workspace boundaries mapped securely to the authenticated `tenant_id`.

---

## 4. Authentication & Authorization (P2 - MEDIUM RISK)

### 4.1 Missing Immutable RequestContext
**Code Path:** FastAPI Routes (`src/main.py`)
**Description:** Authentication correctly verifies the OIDC JWT via `security.py` and extracts `CurrentPrincipal`. However, this principal is only passed downward as dependency-injected arguments. There is no globally propagated, immutable `RequestContext` (or ContextVar) enforced at the middleware layer.
**Impact:** Deep backend services (like background GC, asynchronous retrievals, or nested memory logic) rely on parameters being manually plumbed through function signatures. This introduces a high risk of developer error where a downstream function defaults to global scope or assumes ownership.
**Required Fix:** Implement a strict `contextvars`-based `RequestContext` middleware that permanently binds `tenant_id`, `session_id`, and `trace_id` to the running asyncio task.

---

## 5. Streaming & SSE Isolation (PASS)

### 5.1 Event Emitter Isolation
**Code Path:** `src/main.py` -> `sse_query_generator`
**Verdict:** Safe.
**Description:** The Server-Sent Events (SSE) generator is instantiated securely inside the `agent_query` endpoint. Because the generator is inherently bound to the HTTP request context of the authenticated user, and memory yields are tightly coupled to the scoped `SessionRecord`, cross-session broadcast leakage is not possible at the transport layer.

---

## REQUIRED REMEDIATION ACTIONS

1. **Delete Global Singletons:** Remove `MemoryManager`'s reliance on `~/.assistant_memory.json`. Pivot to a tenant-indexed datastore.
2. **Namespace Storage Backends:** Rename all Chroma collections to `tenant_{tenant_id}_session_{session_id}`.
3. **Hard-Delete Evicted Vectors:** Ensure Chroma collections are dropped aggressively when `_evict_capacity_pressure` triggers, avoiding dangling data reuse.
4. **Enrich Telemetry Logs:** Pipe `tenant_id` into all calls originating in `telemetry_sink.py`.
5. **Implement RequestContext Middleware:** Enforce an immutable ContextVar object at the FastAPI entrypoint containing the caller's identity, preventing ID spoofing deep in the call stack.

*End of Audit Report.*
