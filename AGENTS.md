# Repository Guidelines

## Project Structure & Module Organization
`src/` contains the Python backend, session state, model connectors, and CLI entry points. `src/services/` holds the prompt and model abstraction layer. `src/tests/` contains the unittest-style harnesses, stress checks, and integration scripts. `engine-dashboard/` is the React control plane. `docs/` holds agent/domain notes and operational references.

## Build, Test, and Development Commands
Use the project virtualenv or `uv`-managed environment.

- `uv run python src/sc_evm.py` runs the main interactive engine flow.
- `uv run python src/tests/run_all_tests.py` discovers and runs `src/tests/test_*.py`.
- `uv run python src/tests/test_harness.py` runs the live SSE verification harness and writes `sc_evm_validation_report.json`.
- `uv run python -m uvicorn src.main:app --host 127.0.0.1 --port 8000` starts the FastAPI backend.
- `cd engine-dashboard && npm start` launches the dashboard.

## Coding Style & Naming Conventions
Use Python 3.11+, 4-space indentation, ASCII text, and type hints on public interfaces. Prefer small service methods over route logic in `src/main.py`. Keep names explicit and descriptive: `session_registry`, `MemorySnapshot`, `PromptManager`, `run_query_reformulation_async`. Avoid silent failures; log exceptions with structured context and telemetry.

## Testing Guidelines
Tests are mostly `unittest`-based, with a few async integration harnesses that hit `localhost`. Name new tests `test_*.py` and keep them in `src/tests/`. When adding session or SSE behavior, verify both isolation and burn/reset behavior. For live tests, capture latency and token metrics in the same report format used by `test_harness.py`.

## Commit & Pull Request Guidelines
Git history uses short, prefixed summaries such as `fix:` and `refactor:`. Keep commits focused and readable. PRs should describe the behavior change, list commands run, and include screenshots or logs when changing `engine-dashboard/` or streamed API behavior.

## Security & Configuration Notes
Do not commit `.env` values, local audit logs, or generated validation reports. The backend expects NVIDIA API keys and local filesystem access for memory and telemetry files; verify those paths before running live tests.
