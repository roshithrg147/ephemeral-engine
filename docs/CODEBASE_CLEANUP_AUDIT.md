# SC-EVM Codebase Cleanup Audit

**Reviewed:** 2026-07-23  
**Scope:** Python runtime, evaluation tooling, benchmark adapters, tests, frontend test baseline,
tracked repository files, and current untracked deliverables.  
**Intent:** Remove proven dead code first, then reduce architectural duplication without changing
runtime behavior.

## Current verdict

The repository is healthy enough for phased refactoring: Python lint passes, 83 Python tests pass,
and all 5 frontend tests pass. No critical security defect was introduced by the cleanup. The main
maintenance risks are oversized orchestration modules, duplicated SSE consumers, split burn
semantics, and model routing that requires editing connector logic for every provider/model change.

The worktree already contained multiple in-progress deliverables. Those files were preserved and
were not classified as dead merely because they are untracked.

## Phase 0 cleanup executed

The following removals were proven safe by repository-wide symbol/reference searches and the full
test baseline:

| Removed or consolidated item | Reason |
|---|---|
| `package-lock.json` | Empty npm lock with no root `package.json`; the dashboard owns its real lock. |
| `src/package-lock.json` | Empty npm lock inside the Python package. |
| `hashed_vector_diagnostic()` | Unreferenced implementation superseded by the ONNX vectorizer. |
| `cosine()` in `src/evidence/baselines.py` | Unreferenced helper; active ranking performs its calculation locally. |
| `Judge` and `LLMJudge` | Neither was instantiated, imported, registered, or tested. |
| `sha256_bytes()` | Unreferenced helper. |
| Duplicate `sha256_file()` | Dataset validation now uses `src.evidence.artifacts.sha256_file`. |
| Duplicate fenced-JSON cleanup | `SingleModelAdapter` now uses `strip_code_fences()`. |

Ruff reports no remaining unused imports or local variables in the scanned Python source.

## Dead-code and orphan assessment

### Confirmed and removed

- Two accidental empty npm lockfiles.
- Four unreferenced functions/classes plus the now-unused `Judge` protocol.
- Two redundant implementations replaced by existing shared helpers.

### Not dead; retain

- `src/strategies/dual_model_adapter.py` appears unreferenced statically, but
  `src.benchmarks.runner.discover_strategy_instances()` imports strategy modules dynamically and
  discovers it at runtime.
- `src/benchmarks/` is deprecated for claim-bearing evaluation, but its runner is still executable,
  documented, and used by the `run_benchmark_suite*` compatibility commands.
- Clipboard, daemon, VS Code context, diff application, and rehydration modules are optional
  reference interfaces with explicit CLI/test consumers.
- Current untracked benchmark drivers, wrapper code, sandbox code, standalone projects, reports,
  and analysis files are active Phase 0 deliverables. They require commit-by-commit review, not
  deletion.

### Generated/local-only files

`benchmarks/`, `graphify-out/`, `evaluation-results/`, `scratch/`, generated reports, response logs,
and session sandboxes are ignored local artifacts. They should remain outside publication commits;
deleting them is an operator choice because they may contain useful local evidence.

## Duplication findings

### Major: SSE parsing is implemented repeatedly

At least six production/tool consumers independently parse `event:` and `data:` lines:

- `src/agy_scevm.py`
- `src/cli.py`
- `src/strategies/dual_model_adapter.py`
- `src/evidence/live.py`
- `src/evidence/security.py`
- `sc_evm_50_turn_driver.py`

Manual harnesses add further copies. Event handling already differs between consumers: some know
about `usage_report` and `degradation`, while others consume only legacy `token_usage`. This is a
contract-drift risk.

### Major: usage accounting has competing representations

`src/main.py` emits exact/estimated stage records in `usage_report`, then separately computes legacy
`token_usage` estimates. The latter can report Model 2 tokens even when Model 2 failed. Token
estimation (`len(text) // 4`) is repeated across the API, agent, evidence engine, and strategy
adapters.

### Moderate: benchmark analysis utilities are duplicated

`utc_now`, `percentile`, and `linear_slope` have exact or near-exact copies in the Codex and SC-EVM
50-turn drivers. These should move into a benchmark utility module only after the driver deliverable
is committed and its output schema is frozen.

### Resolved in this cleanup

- Dataset SHA-256 calculation now has one implementation.
- Model JSON fence removal now has one implementation.

## SOLID assessment

### SRP: `src/main.py` owns too much application logic

`_sse_query_generator_locked()` performs metadata collection, reformulation, embedding, retrieval,
prompt assembly, orchestration, action gating, usage calculation, SSE serialization, history
mutation, and indexing. Route code should translate HTTP/SSE contracts; a turn service should own
the workflow.

### SRP/DIP: `AgentOrchestrator` mixes unrelated responsibilities

The orchestrator authenticates configuration, schedules model calls, synthesizes answers, builds
usage records, writes to clipboard IPC, and retains an image-generation stub. Model execution,
usage accounting, and optional response sinks should be injected services.

### OCP: model routing is hardcoded

`NVIDIA_NIM_Client._map_model()` uses a two-branch conditional tied to settings fields. Every new M2
requires modifying connector code and aliases. A route registry lets configuration add or replace
models without changing transport logic.

### ISP/LSP: strategy lifecycle is outside the interface

`StrategyAdapter` specifies only `solve()`, while the runner probes optional `use_remote_session`,
`clear_session()`, and `aclose()` members with `getattr`. Concrete strategies cannot be treated
uniformly through the declared abstraction.

### Lifecycle cohesion: burn is split across two operations

`DELETE /api/session/burn/{session_id}` clears RAM/Chroma, while `POST` on the same path clears the
filesystem sandbox. Callers can successfully execute one purge and leave the other state behind.
One lifecycle service and one canonical endpoint should coordinate both operations and report
partial failures explicitly.

### Large state modules

`src/memory.py` combines persistent JSON profile memory, manifested conversation history, Chroma
runtime setup, threshold calibration, locking, TTL collection, capacity eviction, and session
lifecycle. These responsibilities should be separated after the API pipeline is stable; doing so
first would create unnecessary regression risk.

## Prioritized refactoring plan

### Phase 1 — correctness contracts

1. Make `usage_report` the canonical usage contract.
2. Deprecate `token_usage`, or derive it only from completed usage records and label it estimated.
3. Add a shared SSE decoder and contract tests for every supported event.
4. Introduce one lifecycle coordinator for memory, Chroma, pending tasks, and sandbox burn.
5. Add direct unit tests for all three strategy adapters before changing their interfaces.

### Phase 2 — orchestration extraction

1. Extract a `TurnPipeline` from `_sse_query_generator_locked()`.
2. Extract a typed `UsageRecorder` from `main.py` and `agent.py`.
3. Move clipboard handoff behind an optional `ResponseSink` protocol.
4. Replace model-routing conditionals with a validated route registry.

### Phase 3 — memory boundaries

1. Split Chroma creation/embedding into `VectorStoreFactory`.
2. Split threshold calibration into a pure, cached calibration service.
3. Keep `MultiTenantSessionRegistry` responsible only for session ownership, locking, TTL, and
   capacity.
4. Decide whether JSON profile memory remains supported before introducing another persistent store.

### Phase 4 — compatibility retirement

1. Freeze and migrate the legacy benchmark output schema.
2. Consolidate 50-turn driver statistics helpers.
3. Mark compatibility scripts with owners and removal dates.
4. Remove legacy routes/events only after all consumers use the shared contracts.

## Proposed modular code

### 1. Shared SSE decoder

```python
from dataclasses import dataclass
import json
from typing import Any, AsyncIterator


@dataclass(frozen=True)
class SSEEvent:
    name: str
    data: Any


async def iter_sse(lines: AsyncIterator[str]) -> AsyncIterator[SSEEvent]:
    """Decode the SC-EVM SSE wire format in one place for every client."""
    current_event: str | None = None
    async for raw_line in lines:
        line = raw_line.strip()
        if line.startswith("event: "):
            current_event = line.removeprefix("event: ").strip()
        elif current_event and line.startswith("data: "):
            payload = line.removeprefix("data: ").strip()
            if payload == "[DONE]":
                yield SSEEvent(current_event, payload)
            else:
                yield SSEEvent(current_event, json.loads(payload))
```

### 2. Typed usage records

```python
from typing import Literal
from pydantic import BaseModel


class UsageRecord(BaseModel):
    """One provider stage outcome; failed calls never receive invented token counts."""
    stage: str
    model: str
    status: Literal["completed", "failed"]
    measurement_type: Literal["exact", "estimate", "unavailable"]
    input_tokens: int | None = None
    output_tokens: int | None = None
    missing_reason: str | None = None


def completed_usage(records: list[UsageRecord]) -> list[UsageRecord]:
    return [record for record in records if record.status == "completed"]
```

Legacy totals can then be derived only from `completed_usage(records)`; a failed M2 stage contributes
no fabricated usage.

### 3. Configurable model registry

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelRoute:
    physical_id: str
    temperature: float
    top_p: float
    api_key: str


class ModelRegistry:
    def __init__(self, routes: dict[str, ModelRoute], aliases: dict[str, str]):
        self._routes = routes
        self._aliases = aliases

    def resolve(self, requested: str) -> ModelRoute:
        """Resolve aliases without embedding model-specific branches in HTTP transport."""
        canonical = self._aliases.get(requested.lower(), requested.lower())
        try:
            return self._routes[canonical]
        except KeyError as exc:
            raise ValueError(f"Unknown model route: {requested}") from exc
```

### 4. Complete strategy contract

```python
class StrategyAdapter(ABC):
    use_remote_session = True

    @abstractmethod
    async def solve(self, prompt: str, session_id: str) -> dict[str, Any]: ...

    async def clear_session(self, session_id: str) -> None:
        """Default no-op for strategies without local session state."""

    async def aclose(self) -> None:
        """Default no-op for strategies without owned async resources."""
```

The runner can call lifecycle methods directly instead of relying on reflective `getattr()` checks.

### 5. Unified burn coordinator

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class BurnResult:
    memory_removed: bool
    sandbox_removed: bool


class SessionLifecycleService:
    def __init__(self, registry, sandbox):
        self._registry = registry
        self._sandbox = sandbox

    async def burn(self, session_id: str) -> BurnResult:
        """Purge every session-owned state surface through one operation."""
        memory_removed = await self._registry.flush_session(session_id)
        sandbox_removed = self._sandbox.burn_session(session_id)
        return BurnResult(memory_removed, sandbox_removed)
```

The API should retain one canonical `DELETE` route and return both outcomes.

### 6. Turn workflow service

```python
class TurnPipeline:
    def __init__(self, reformulator, retriever, orchestrator, usage_recorder, indexer):
        self._reformulator = reformulator
        self._retriever = retriever
        self._orchestrator = orchestrator
        self._usage = usage_recorder
        self._indexer = indexer

    async def execute(self, session, prompt: str, options) -> "TurnResult":
        """Execute one turn without knowing FastAPI or SSE serialization details."""
        reformulated = await self._reformulator.rewrite(prompt, session.history)
        context = await self._retriever.retrieve(session, reformulated.search_query, options)
        response = await self._orchestrator.respond(session.snapshot(), reformulated, context)
        usage = self._usage.collect(reformulated, response)
        await self._indexer.schedule(session, prompt, response.text)
        return TurnResult(reformulated, context, response, usage)
```

`src/main.py` then becomes an HTTP adapter that converts `TurnResult` into ordered SSE events.

## Validation after Phase 0 cleanup

- Ruff, including gitignored tracked benchmark source: passed.
- Python suite: 83 passed, 10 live/network tests deselected.
- Frontend: 2 suites, 5 tests passed.
- Python compilation: passed.
- Whitespace validation: passed.

## Ship decision

The executed cleanup is behavior-preserving and test-safe. Ship it separately from the existing
model-routing, wrapper, sandbox, benchmark, and standalone-project changes. Start Phase 1 with usage
contract correction and shared SSE parsing; they have the highest correctness payoff and smallest
architectural blast radius.
