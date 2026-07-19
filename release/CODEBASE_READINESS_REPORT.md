# SC-EVM Codebase Readiness Report

**Reviewed:** 2026-07-19
**Source baseline:** `8efc3f978d61`
**Verdict:** Ready for trusted local developer-preview use. Not ready for a
public pilot, production deployment, or claim-bearing efficiency/quality
publication.

## Architecture-gap reconciliation

GitHub issue
[#6](https://github.com/roshithrg147/ephemeral-engine/issues/6) re-audited all
registered gaps against current source, tests, and evidence. The canonical
result is [ARCHITECTURE_GAPS.md](../architecture/ARCHITECTURE_GAPS.md).

- 1 resolved entry: AG-016.
- 8 partially resolved entries with explicit remaining work: AG-004, AG-005,
  AG-006, AG-008, AG-010, AG-013, AG-014, and AG-017.
- 9 open entries, including new AG-018 for the exposed but unenforced
  2,500-token budget.
- 5 public-pilot blockers: AG-001, AG-007, AG-009, AG-014, and AG-015.
- 7 production blockers: all public-pilot blockers plus AG-003 and AG-008.

No risk was removed merely because a class, endpoint, evaluator, or report
exists. Execution-dependent and policy-dependent work remains open or partial.

## Verified current controls

- Direct session history is bounded across generated and manually ingested
  messages.
- Same-session operations are serialized; burn waits for in-flight generation
  and background indexing cannot resurrect a burned session.
- Local JSON fact persistence uses file locking and atomic replacement.
- Executor sizes, IPC payloads, workspace files, session capacity, and provider
  retries/timeouts have configured bounds.
- API origins, NVIDIA inference endpoint, logical model roles and aliases,
  physical model IDs, generation ceilings, pricing, and retrieval distance
  policy are centralized in `src/config.py`.
- Runtime and live evidence inference use the unified `NVIDIA_NIM_Client`;
  direct Vertex AI and Google AI code and dependencies are absent.
- FastAPI lifespan explicitly cancels the TTL collector, awaits tracked
  background tasks, and closes the shared provider client.
- Dashboard session count, latency, intent distribution, memory anchors, and
  token estimates are populated from API/SSE state instead of static chart
  fixtures.
- Telemetry content redaction, restrictive file permissions, and size-bounded
  rotation are implemented.
- The evidence platform has deterministic/rule evaluators, paired statistics,
  failure and missing-data accounting, immutable artifacts, checksums, and
  certification gates.

## Verification performed for this reconciliation

- Python default suite: **53 passed, 10 live/network tests deselected**.
- Frontend: **2 test suites and 5 tests passed**.
- Frontend production build: **compiled successfully**.
- Documentation references and whitespace are checked as part of the issue #6
  change validation.

Live/network tests, container builds, provider campaigns, and deployment-scale
stress are not silently inferred from these local gates. Earlier reports remain
historical evidence and are not rewritten as current execution.

## Release boundaries

- The HTTP service has no application authentication or authorization and
  implicitly creates a valid unknown session on query. Bind it to a trusted
  localhost boundary.
- Any caller can request diagnostic context. Do not expose diagnostic mode
  across an untrusted boundary.
- Active sessions are process-local. Restart, reschedule, or multiple replicas
  lose or diverge session state.
- CORS defaults are appropriate for the local dashboard, not a public
  authenticated deployment.
- Audit content is redacted by default and rotated, but retention duration,
  access policy, deletion, error-field redaction, and relationship to burn are
  undefined.
- The dashboard's token-efficiency presentation uses heuristic
  `tokensSaved`/legacy token estimates. It is not billing-grade or
  claim-bearing telemetry.
- `token_budget=2500` is a compatibility/scaffolding field. No tokenizer-backed
  admission or per-turn budget enforcement consumes it.
- Evaluation scoring and statistics exist, but Development smoke artifacts do
  not establish live Validation/Final Evaluation quality, cost, latency,
  Graphify uplift, or dual-model benefit.
- Provider-live transport success is not equivalent to a governed,
  claim-bearing campaign.
- Current third-party deprecation warnings originate in the ChromaDB/Uvicorn
  dependency stack.

## Next gates

### Developer preview

1. Add deterministic CI gates for the verified Python, frontend, documentation,
   and build checks.
2. Keep architecture, readiness, and claim language synchronized with the gap
   register.

### Public pilot

1. Accept and implement authenticated principal/session ownership.
2. Restrict diagnostic context to an authorized operator boundary.
3. Define public CORS policy and negative tests.
4. Define sticky or deployable active-session state.
5. Accept and implement audit retention, access, redaction, and deletion policy.
6. Complete an external-boundary security review.

### Claim-bearing evaluation

1. Define and enforce tokenizer-backed per-call and per-turn budgets.
2. Complete exact/estimated usage records on every provider path.
3. Freeze governed Validation/Final Evaluation datasets.
4. Execute live paired campaigns under accepted RFC-0003.
5. Publish only claims that pass claim-specific certification.
