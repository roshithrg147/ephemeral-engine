# Repository Classification

This document classifies every top-level file and directory in the repository to clarify ownership and publication decisions.

## 1. Classification Definitions

- **Core Runtime:** Code executed as part of the primary context-control middleware runtime or REST API.
- **Core Evaluation:** Evaluation scripts, loader logic, metrics, and statistical analyzers.
- **Public Documentation:** Manifestos, ADRs, RFCs, READMEs, and onboarding guides.
- **Reference Client:** Demonstration code, desktop applets, CLI interfaces, and visual dashboards.
- **Optional Integration:** Deployment tooling (Docker, Compose configs).
- **Development Tool:** Helper scripts, data generators, and local troubleshooting scripts.
- **Test Fixture:** Verification test files (Pytest suites).
- **Generated Artifact:** Ephemeral output results, telemetry metrics, and validation logs.
- **Historical Evidence:** Archive of previous campaign runs or audit logs.
- **Experimental:** Prototypes or feature stubs (e.g. Graphify).
- **Deprecated:** Outdated code slated for archival/moving.
- **Dead:** Unreferenced and non-functional code slated for immediate deletion.
- **Sensitive / Must Not Publish:** Private keys, real credentials, raw client data.

---

## 2. Directory and File Classification Matrix

| Path | Classification | Public Release Decision | Notes / Purpose |
| :--- | :--- | :--- | :--- |
| `src/agent.py` | Core Runtime | Keep (Public) | Primary context assembly and agent routing logic. |
| `src/apply_diff_engine.py` | Core Runtime | Keep (Public) | Volatile update and memory merge engine. |
| `src/clients.py` | Core Runtime | Keep (Public) | HTTP clients (including NVIDIA NIM connection wrapper). |
| `src/config.py` | Core Runtime | Keep (Public) | Server and client environment variable parsing. |
| `src/main.py` | Core Runtime | Keep (Public) | FastAPI REST API endpoints and SSE stream generator. |
| `src/memory.py` | Core Runtime | Keep (Public) | In-memory session registry and Chroma DB vector storage. |
| `src/sc_evm.py` | Core Runtime | Keep (Public) | Core context retrieval, summary compaction, and distance gating logic. |
| `src/secure_lifecycle_manager.py` | Core Runtime | Keep (Public) | Volatile directory registration, flushing, and state-deletion logic. |
| `src/session_rehydration_hook.py` | Core Runtime | Keep (Public) | Hooks for persistence and recovery across session rehydration. |
| `src/telemetry_sink.py` | Core Runtime | Keep (Public) | Immutable logging for performance and correct admissions. |
| `src/vscode_context_provider.py` | Core Runtime | Keep (Public) | Local context collector for active development workspaces. |
| `src/services/` | Core Runtime | Keep (Public) | Supporting runtime modules (prompts, errors, model connectors). |
| `src/strategies/` | Core Runtime | Keep (Public) | Gating and LLM adapter strategies. |
| `src/graphify_bridge.py` | Experimental | Keep (Public) | Bridge logic for inserting Graphify structure. |
| `src/cli.py` | Reference Client | Keep (Public) | User-facing `assistant` command-line utility. |
| `src/clipboard_service.py` | Reference Client | Keep (Public) | Daemon for synchronization via clipboard buffers. |
| `src/clipboard_gui.py` | Reference Client | Keep (Public) | GUI indicator applet for system tray controls. |
| `src/daemon.py` | Reference Client | Keep (Public) | Process management interface for local background daemons. |
| `src/sync.py` | Reference Client | Keep (Public) | Synchronizer for syncing file paths with session state. |
| `src/tests/` | Test Fixture | Keep (Public) | Local Pytest suites and test configurations. |
| `src/evidence/` | Core Evaluation | Keep (Public) | Implementation of runner, baselines, statistics, and certification. |
| `evaluation/` | Core Evaluation | Keep (Public) | Benchmarking datasets, stats reports, matrices. |
| `evaluation-results/` | Generated / Historical | Exclude (Gitignored) | Intermediate campaign runs and checksum signatures. |
| `docs/` | Public Documentation | Keep (Public) | System documentation, limitations, and user guides. |
| `architecture/` | Public Documentation | Keep (Public) | Accepted ADRs and designs. |
| `rfcs/` | Public Documentation | Keep (Public) | Accepted RFC specifications. |
| `MANIFESTO.md` | Public Documentation | Keep (Public) | Repository integrity values and governing manifesto. |
| `PRODUCT_BOUNDARY.md` | Public Documentation | Keep (Public) | Core definition of MVP constraints. |
| `ARCHITECTURE.md` | Public Documentation | Keep (Public) | Core architectural definition. |
| `README.md` | Public Documentation | Keep (Public) | Primary onboarding user guide. |
| `pyproject.toml` | Core Runtime | Keep (Public) | Build requirements and entrypoint definitions. |
| `uv.lock` | Core Runtime | Keep (Public) | Strict dependencies lockfile. |
| `Dockerfile.backend` | Optional Integration | Keep (Public) | Backend docker build instructions. |
| `Dockerfile.frontend` | Optional Integration | Keep (Public) | Frontend docker build instructions. |
| `docker-compose.yml` | Optional Integration | Keep (Public) | Local multi-container compose configuration. |
| `engine-dashboard/` | Reference Client | Keep (Public) | Node-based visual admin panel. |
| `scratch/` | Development Tool | Exclude (Gitignored) | Local scratch scripts and experimentation logs. |
| `scripts/` | Development Tool | Keep (Public) | Data generators, link checkers, validation utilities. |
| `src/benchmarks/` | Deprecated | Keep (Public) | Old benchmark scripts replaced by `src/evidence`. |
