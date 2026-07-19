# SC-EVM Architecture Gap and Liability Register

This register records verified architecture liabilities. It does not authorize
implementation. Significant remedies begin through the
[RFC process](../rfcs/README.md).

**Last reconciled:** 2026-07-19
**Source baseline:** `8efc3f978d61`
**Reconciliation scope:** GitHub issue
[#6](https://github.com/roshithrg147/ephemeral-engine/issues/6)

## Status definitions

- **Open:** the described liability remains materially unchanged.
- **Partial:** verified implementation reduced the liability, but stated
  remaining work or evidence is still required.
- **Resolved:** source and test evidence close the registered liability.
  Resolved rows remain in the register for audit history.

## Reconciled register

| ID | Status | Current evidence | Remaining liability | Severity | Pillar | RFC? | Blocks benchmark claim? | Blocks public pilot? | Blocks production? |
|---|---|---|---|---|---|:---:|:---:|:---:|:---:|
| AG-001 | Open | `src/main.py` accepts client-supplied session IDs, implicitly creates a session on query, and exposes session listing without an authenticated principal. | Define authentication, authorization, session ownership, and enumeration policy before untrusted network exposure. | Critical | Isolation, Control | Yes | No | Yes | Yes |
| AG-002 | Open | `src/services/model_connector.py` delegates directly to the NVIDIA transport. `src/clients.py` owns NVIDIA-specific payloads, model resolution, errors, and usage handling. | RFC-0004 must define the minimum provider capability, error, usage, and tokenizer contract. Current single-provider operation remains supported. | Medium | Control | Yes | No | No | No |
| AG-003 | Open | `MemoryManager` uses a file lock and atomic replacement; `test_memory_manager_persists_relative_path_atomically` verifies the local write path. | One local JSON document has no distributed-writer semantics, recovery log, or transactional history. Keep it local-only until a persistence RFC is accepted. | Medium | Isolation | Yes | No | No | Yes |
| AG-004 | Partial | `src/main.py` emits one complete `response_content` event after synthesis. `test_query_pipeline_emits_response_and_commits_state` verifies staged SSE completion. Provider-native stream parsing exists only below the API path. | Time to first answer content remains approximately full-turn latency. Do not describe the API as provider-token streaming until the strategy and synthesis contract is redesigned and tested. | Medium | Evidence | Yes | No | No | No |
| AG-005 | Partial | RFC-0003, paired Graphify ON/OFF runner paths, executable statistics, and a Development smoke ablation now exist. The smoke result was a null quality effect and is not publishable live evidence. | A governed live Validation/Final Evaluation ablation with relevant structural scenarios is still required for any Graphify quality or efficiency claim. | Medium | Relevance, Evidence | Yes | Yes | No | No |
| AG-006 | Partial | `src/config.py` now owns logical Model 1/Model 2 keys, exact aliases, physical NVIDIA model IDs, generation parameters, and token ceilings. `src/sc_evm.py` uses Model 1 for reformulation; `src/agent.py` uses both roles for candidates and Model 2 for synthesis. Compatibility aliases such as `claude` and `opus` resolve only to the configured NVIDIA Model 2 route. | RFC-0004 must still define capability discovery, adaptive role selection, escalation, and provider-neutral routing. Configurable aliases are deterministic routing, not task-aware orchestration. | Medium | Control | Yes | No | No | No |
| AG-007 | Open | `src/config.py` defaults CORS to the two local dashboard origins while `src/main.py` enables credentials and broad methods/headers. | Public deployment needs an authenticated origin policy, deployment-specific allowlist, and negative CORS tests. Localhost defaults alone are not a public boundary. | High | Control, Isolation | Yes | No | Yes | Yes |
| AG-008 | Partial | Bounded thread pools, per-session operation locks, tracked background tasks, and explicit daemon shutdown are implemented; concurrency and burn-race tests cover one process. | The registry and collections remain process-local. Replicas do not share sessions, and sustained provider/capacity behavior lacks deployment-scale evidence. | High | Isolation, Evidence | Yes | No | No | Yes |
| AG-009 | Open | Active records and Chroma collections are owned by the API process. Docker deployment provides no shared active-session state. | Restart/reschedule interrupts conversations and multiple replicas diverge. Public evaluation must use an explicit sticky single-instance boundary until a deployment-state RFC is accepted. | High | Isolation | Yes | No | Yes | Yes |
| AG-010 | Partial | `src/evidence/evaluators.py` supplies deterministic and rule evaluators; `src/evidence/statistics.py` supplies paired effects, intervals, distributions, and missing/failure accounting. `evaluation/test_evidence_platform.py` verifies the executable pipeline. | The available corpus is Development smoke data, human review is a placeholder, and claim-bearing live Validation/Final Evaluation execution is incomplete. Commercial quality claims remain blocked. | High | Evidence | Yes | Yes | No | No |
| AG-011 | Open | `AgentOrchestrator.generate_image` returns a path without generating an image while the action remains in the response schema. | Keep the action explicitly stubbed and outside supported product capability, or propose removal/addition through product-boundary governance. | Low | Control | Yes | No | No | No |
| AG-012 | Open | `src/sync.py` derives local cryptographic state but has no external relay and reports BYOB synchronization as unavailable. | Keep cross-device synchronization classified as stubbed and do not advertise it. | Low | Control | No | No | No | No |
| AG-013 | Partial | The dashboard now derives active sessions, end-to-end request latency, intent counts, token estimates, and memory anchors from API/SSE state; frontend tests verify runtime loading and SSE parsing. | “Context efficiency” and “tokens removed” still use heuristic `tokensSaved` and legacy character-based usage estimates. Relabel them as estimates or connect them to validated token accounting before operator or product claims. | Low | Evidence | No | No | No | No |
| AG-014 | Partial | `src/telemetry_sink.py` implements content redaction, size-bounded rotation, `0700` directories, and `0600` files. Redaction and limits are configurable in `src/config.py`. | Error strings are not field-redacted, and access, retention duration, deletion, audit schema, and relationship to session burn remain undefined. | High | Isolation, Control | Yes | No | Yes | Yes |
| AG-015 | Open | Any caller can set `diagnostic_mode=true`; `src/main.py` then emits complete retrieved context. No application authentication or authorization guards the switch. | Authenticate first, then define a privileged diagnostic policy and negative disclosure tests before untrusted network exposure. | High | Isolation | Yes | No | Yes | Yes |
| AG-016 | Resolved | FastAPI lifespan calls `stop_daemons`, awaits tracked background tasks, and closes the shared provider client. `test_registry_stops_gc_task` verifies cancellation and cleanup of the TTL task. | No remaining liability under this entry. Provider readiness and health semantics remain separate concerns. | None | Control | No | No | No | No |
| AG-017 | Partial | Manifested history refreshes checksums on mutation. A detected mismatch is logged, refreshed, and fails the current request closed. | No focused corruption/retry test or documented operator repair/burn procedure exists. Recovery is implicit on a later request rather than an explicit contract. | Low | Isolation | No | No | No | No |
| AG-018 | Open | `SessionRecord.metadata_registry` exposes `token_budget=2500`, but no prompt builder or model boundary reads it to admit, truncate, or reject context. The live path can perform reformulation, two candidate calls, and synthesis for one turn. | Define enforceable per-call and per-turn budgets, tokenizer provenance, context allocation, fallback behavior, and complete usage capture before claiming cumulative token or cost efficiency. | High | Relevance, Control, Evidence | Yes | Yes | No | No |

## Recalculated release interpretation

- **Resolved:** AG-016.
- **Partial with explicit remaining work:** AG-004, AG-005, AG-006, AG-008,
  AG-010, AG-013, AG-014, and AG-017.
- **Public-pilot blockers:** AG-001, AG-007, AG-009, AG-014, and AG-015.
- **Production blockers:** all public-pilot blockers plus AG-003 and AG-008.
- **Claim-bearing benchmark blockers:**
  - AG-005 blocks Graphify quality and efficiency claims.
  - AG-010 blocks answer-quality and comparative-quality claims.
  - AG-018 blocks cumulative-token, cost-efficiency, and fixed-budget claims.
  - AG-004 blocks provider-token-streaming and time-to-first-token claims, but
    not unrelated benchmark execution.

AG-013 is no longer a release blocker because static placeholder charts were
replaced with runtime-derived state. Its remaining heuristic labeling risk is
retained rather than removed.

## Evidence rules applied

- Source presence narrowed a gap only when observable behavior or a focused
  test supported the change.
- Offline Development smoke artifacts validate runner plumbing and may record
  null results; they do not close live or public claim gates.
- A resolved implementation gap does not close a different operational,
  security, or certification gap.
- Generated local stress reports remain operator evidence and are not committed
  as canonical repository artifacts.
