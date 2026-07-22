# Isolated Gemini Performance Benchmark

This directory is a standalone project. It does not import, start, or write to
the parent SC-EVM application.

The runner calls the Gemini Developer API directly, keeps conversation history
in memory, and checkpoints every completed turn under `outputs/`.

## Setup

```bash
cd standalone/gemini_performance_benchmark
uv sync
export GEMINI_API_KEY="your-key-from-Google-AI-Studio"
```

Do not put the real key in `.env.example` or commit it.

## Run

Run one inexpensive smoke turn first:

```bash
uv run python run_performance_benchmark.py --turns 1
```

Then run all 50 turns:

```bash
uv run python run_performance_benchmark.py
```

The default model is `gemini-3.5-flash`. Override it with either
`GEMINI_MODEL` or `--model`:

```bash
uv run python run_performance_benchmark.py --model gemini-3.5-flash --turns 50
```

Use `--fresh` to overwrite an existing checkpoint. Without it, the runner
refuses to overwrite prior evidence. If a rate limit or network interruption
stops a run, continue from its next unfinished turn with:

```bash
uv run python run_performance_benchmark.py --resume
```

The runner waits 25 seconds between calls by default to accommodate the
observed free-tier request limit.

## Validate without calling Gemini

```bash
uv run pytest -q
uv run ruff check .
uv run mypy run_performance_benchmark.py
```
