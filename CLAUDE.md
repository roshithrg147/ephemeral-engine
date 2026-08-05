# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Development Commands

### Running the Application
- Start the REST API backend: `uv run uvicorn src.main:app --host 127.0.0.1 --port 8000`
- Run the interactive CLI assistant: `uv run assistant`
- Run the VS Code terminal bridge: Start gateway then `uv run scevm-vscode`
- Test with bounded smoke test: `uv run scevm-vscode --prompt "Explain transaction atomicity in two sentences." --timeout 120`

### Development Workflow
- Run tests: `uv run pytest`
- Copy environment template: `cp .env.example .env` and fill in `NVIDIA_API_KEY`
- Build VS Code extension: 
  ```bash
  cd vscode-extension
  npm ci
  npm run package
  code --install-extension scevm-chat-0.3.0.vsix --force
  ```

## High-Level Architecture

SC-EVM (State-Cached Ephemeral Vector Memory) is a session-isolated context-control middleware for multi-turn AI applications that optimizes context retention and provides logical session boundaries.

### Core Layers
1. **Integration/API Layer** (`src/main.py`) - Validates requests, coordinates turns, emits events
2. **Session and Lifecycle Layer** (`src/memory.py`, `src/services/session_lifecycle.py`) - Manages session identity, locks, TTL, burn operations
3. **Context Intelligence Layer** (`src/sc_evm.py`, `src/services/fusion_engine.py`) - Realigns intent, retrieves/admits context, fuses vector + Graphify retrieval
4. **Reasoning Strategy Layer** (`src/agent.py`, `src/strategies/`) - Generates candidate responses, synthesizes results
5. **Provider Transport Layer** (`src/clients.py`, `src/services/model_connector.py`) - Normalizes external reasoning calls (currently NVIDIA NIM)

### Key Features
- **Session Burn**: `/burn` command or API endpoint purges volatile memory and session-scoped vector collections
- **Adaptive Outlier Gating**: Dynamically admits/rejects memories based on cosine distance thresholds
- **Async Query Reformulation**: Translates conversational prompts into search queries
- **Logical State Deletion**: Provides explicit session lifecycle controls
- **Bounded History**: Maintains 6-message direct history window per session

### Important Files
- `src/main.py` - API entry point
- `src/memory.py` - Session registry and vector memory management
- `src/sc_evm.py` - Core context intelligence engine
- `src/agent.py` - Reasoning orchestrator
- `src/clients.py` - NVIDIA NIM transport
- `src/services/prompt_manager.py` - Prompt construction and response cleanup
- `src/thresholds.py` - Adaptive threshold engine

### Configuration
- Environment variables via `.env` file (see `.env.example`)
- Key settings: `NVIDIA_API_KEY`, `MODEL_1_FLASH`, `MODEL_2_CORE`, `DEPLOYMENT_MODE`, `AUTH_MODE`

## Testing
- Full test suite: `uv run pytest`
- Specific test files in `src/tests/` directory
- Benchmark runners in `src/benchmarks/` and `src/evidence/`

This architecture provides session isolation, context control, and explicit lifecycle management for multi-turn AI applications while preventing context window saturation and reducing unbounded token growth.