# Isolated Ollama Performance Benchmark

This standalone project talks only to the local Ollama API. It does not import,
start, or write to the parent SC-EVM application.

Selected model: `gemma4:latest` (8B, Q4_K_M, 131K maximum context). The runner
uses a 32K context allocation to balance multi-turn capacity and local memory
usage.

## Run

```bash
cd standalone/ollama_performance_benchmark
uv sync

# One-turn smoke run
uv run python run_performance_benchmark.py --turns 1 --fresh

# Full run
uv run python run_performance_benchmark.py --turns 50 --fresh
```

Results are checkpointed after every turn under
`outputs/benchmark_results.json`. Resume an interrupted run with:

```bash
uv run python run_performance_benchmark.py --turns 50 --resume
```

## Validate without calling Ollama

```bash
uv run pytest -q
uv run ruff check .
uv run mypy run_performance_benchmark.py tests/test_runner.py
```
