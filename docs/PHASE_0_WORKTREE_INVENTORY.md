# Phase 0 Worktree Inventory

**Recorded:** 2026-07-23  
**Branch:** `agent/github-project-workflow`  
**Baseline:** `f2b5eb2`

This inventory separates current local work into reviewable deliverables. It does
not approve every file for commit.

## Deliverable A: Model routing and runtime accounting

Tracked changes:

- `.env.example`
- `src/config.py`
- `src/clients.py`
- `src/agent.py`
- `src/main.py` usage-accounting lines
- `src/strategies/single_model_adapter.py`
- `src/tests/test_clients.py`
- `docs/SYSTEM_ARCHITECTURE_AND_WORKFLOW_SPECIFICATION.md`

Status: offline tests pass. Live Model 2 is blocked because NVIDIA returns a 404
for the configured Kimi route. Running backend must be restarted after configuration
changes. Silent Model 1 fallback and incomplete `finish_reason` handling remain open.

## Deliverable B: Anti-Gravity SC-EVM wrapper

Source candidates:

- `agy-scevm`
- `src/agy_scevm.py`
- `src/tests/test_agy_scevm.py`
- `pyproject.toml` console entry point

Compatibility probe candidates:

- `src/tests/run_antigravity_front_test.py`
- `src/tests/test_antigravity_front_test.py`

Status: unit tests pass. Strict-core live operation cannot pass until Model 2 succeeds
and emits exact usage evidence.

## Deliverable C: Hardened sandbox filesystem

Source candidates:

- `src/tools/__init__.py`
- `src/tools/sandbox_fs.py`
- `tests/test_sandbox_fs.py`
- `.gitignore` sandbox exclusion
- `src/config.py` sandbox setting
- `src/main.py` POST burn route

Status: focused tests pass. Filesystem burn and existing memory/Chroma burn remain
separate lifecycle operations and require consolidation before adding persistent DB
state.

## Deliverable D: Benchmark tooling

Source candidates:

- `codex_50_turn_driver.py`
- `sc_evm_50_turn_driver.py`
- `math500_benchmark_driver.py`
- `src/tests/test_math500_benchmark_driver.py`
- `tests/run_manual_test.py`
- `tests/test_run_manual_test.py`
- `analysis/benchmark_comparison/analyze_results.mjs`
- `analysis/benchmark_comparison/build_artifact.mjs`

Review candidates:

- `sc_evm_vs_codex_50_turn_comparison.md`
- `math500_benchmark_run_notes.md`

Generated outputs are ignored at repository root or under the analysis directory.
Existing files remain on disk.

Status: tooling tests pass. Existing MATH500 output has no evaluable turns because
provider calls failed. Existing comparison is development evidence, not claim-bearing
certification.

## Deliverable E: Standalone benchmark projects

- `standalone/gemini_performance_benchmark/`
- `standalone/ollama_performance_benchmark/`

Each project owns its source, lock file, tests, and local ignore rules. Nested virtual
environments, caches, and outputs are ignored. These projects should be reviewed and
committed independently from SC-EVM runtime changes.

## Generated or local-only state

Ignored without deletion:

- provider/manual-test logs
- benchmark result JSON and response text
- Codex event JSONL
- generated comparison HTML and derived JSON
- nested virtual environments and caches
- session sandboxes

## Required commit order

1. Worktree/test-discovery hygiene.
2. Model routing and explicit failure semantics.
3. Anti-Gravity wrapper.
4. Sandbox filesystem and unified lifecycle behavior.
5. Benchmark tooling.
6. Standalone benchmark projects, if retained.

No frontend or `engine-dashboard/` change belongs in these commits.

## Phase 0 validation

- Main repository suite: 79 passed, 10 deselected.
- Gemini standalone suite: 3 passed.
- Ollama standalone suite: 3 passed.
- Ruff: passed for main source, tests, evaluation, and benchmark drivers.
- `compileall`: passed for main source, tests, and benchmark drivers.
- Whitespace validation: passed.
- Current checkout gateway: started successfully on temporary port 8001; OpenAPI
  exposed both DELETE memory burn and POST filesystem burn routes.

## External blockers

- Existing port 8000 gateway is stale and runs outside the visible process namespace.
  Its owner must restart it from this checkout.
- GitHub CLI authentication is invalid for both configured accounts. Pull request,
  issue, and Project state cannot be refreshed until an operator runs `gh auth login`.
