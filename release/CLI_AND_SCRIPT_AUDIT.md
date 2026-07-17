# CLI and Script Audit

This audit evaluates all CLI utilities, entrypoints, and standalone scripts in the repository, making keep/delete decisions.

## 1. CLI & Entrypoint Classification Matrix

| Path | Classification | Keep / Delete Decision | Justification |
| :--- | :--- | :--- | :--- |
| `src/cli.py` | Required Public Interface | **Keep** | Implements the main `assistant` CLI for developer interaction, onboarding, and workspace diagnostics. |
| `src/clipboard_service.py` | Reference Interface | **Keep** | Runs the background daemon that syncs files and context via the clipboard. |
| `src/clipboard_gui.py` | Reference Interface | **Keep** | Provides the system tray GUI for easy start/stop control of the background daemon. |
| `src/daemon.py` | Reference Interface | **Keep** | Manages start, stop, status, and logging of local background daemon processes. |
| `src/sync.py` | Reference Interface | **Keep** | Synchronizes path directories and content registers into the active session memory. |
| `scripts/run_campaign.py` | Evaluation Tool | **Keep** | Primary entrypoint for running campaigns and generating evidence artifacts. |
| `scripts/run_validation_campaign.py` | Evaluation Tool | **Keep** | Executes the Day 8 Validation Campaign matrix. |
| `scripts/generate_validation_data.py` | Internal Development Tool | **Keep** | Programmatically creates schema-compliant validation scenarios. |
| `scripts/validate_datasets.py` | Evaluation Tool | **Keep** | Verifies schemas, checks split leakage, and generates cryptographic checksums. |
| `src/benchmarks/runner.py` | Superseded | **Archive/Keep** | Legacy benchmark execution logic. Retained in codebase for reference comparison but not called in active campaign pipelines. |
| `src/tests/run_stress_benchmark.py` | Evaluation Tool | **Keep** | Runs local concurrency stress benchmarks for memory boundary checks. |
| `src/tests/run_all_tests.py` | Evaluation Tool | **Keep** | Test runner for executing all local unit and integration tests. |

## 2. Deleted / Superseded CLI Decisions

- **`src/vscode_bridge.py`:** Classification: **Dead**. Removed during Day 6. VSCode context retrieval is handled natively by `src/vscode_context_provider.py`.
- **`test_main_endpoints.py`, `test_memory_isolation.py`, `test_sc_evm.py`:** Classification: **Dead**. Replaced by pytest suites inside `src/tests/` and removed to prevent root namespace pollution.
