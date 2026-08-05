# Security Audit Fixes Log & Root Cause Analysis

## Root Cause Analysis
During the investigation of the cross-account data leakage ("a completely different account immediately sees another account's previous conversations"), we traced the execution through `AuthContext.tsx`, `RuntimeContext.tsx`, `main.py`, `memory.py`, and `security.py`.

**The Root Cause**: 
The issue stems from the development authentication mechanism in `src/security.py`. When developers log in, `issue_dev_tokens` and `get_current_principal` assigned `tenant_id="development"` and `OPERATOR_SCOPE` to EVERY developer user (e.g. `dev-alice` and `dev-bob` both shared `tenant_id="development"` and `OPERATOR_SCOPE`).

Because both users had `OPERATOR_SCOPE`, the API endpoint `/api/session/list` called `session_registry.list_session_ids(include_tenant=True)`. This completely bypassed the `owner_subject` filter, returning ALL sessions in the `development` tenant to any authenticated dev user. The frontend `RuntimeContext` then naively added these sessions to the UI. If Alice clicked Bob's session, the backend would actually throw a 404 because `get_session` still checks `owner_subject`, resulting in Alice seeing an empty chat. However, if the session was evicted and Alice sent a message, Alice would end up claiming Bob's orphaned Chroma collection (`session_<id>`), thereby giving Alice access to Bob's indexed memory!

## Implemented Fixes

1. **Development Authentication Scoping (`src/security.py`)**:
   - Modified `get_current_principal` to ensure that development tokens are assigned unique tenant IDs (`tenant_id=f"dev-{meta.get('email')}"`) instead of a shared `"development"` tenant.
   - Stripped the `OPERATOR_SCOPE` from standard dev users so they can no longer list all sessions in their tenant.

2. **Global Singletons and Local Persistence (`src/memory.py`)**:
   - Modified `MemoryManager` to use a tenant-isolated local path (`~/.ephemeral-engine/memory/<tenant_id>/<owner_subject>/memory.json`) rather than the global `~/.assistant_memory.json`.

3. **ChromaDB Collection Isolation (`src/memory.py`)**:
   - Updated `SessionRecord` to prefix Chroma collection names with `tenant_id`: `self.collection_name = f"t_{safe_tenant}_s_{safe_session}"`. This ensures that even if session IDs collide or are reused across accounts, their underlying Chroma collections will remain cryptographically separate.

4. **Telemetry Enrichment (`src/telemetry_sink.py`)**:
   - Updated `log_interaction` to accept and persist `tenant_id` and `owner_subject` to the immutable JSON-lines audit trail (`sc-evm-telemetry.log`).

5. **ContextVars Propagation (`src/main.py`)**:
   - Implemented and mounted `RequestContextMiddleware` in `src/main.py` which manages context-local variables (`tenant_context`, `user_context`) through the entire async request lifecycle, establishing a foundation for deep downstream identity propagation.
