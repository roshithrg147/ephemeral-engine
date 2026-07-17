# Evidence Runner

## Architecture

`src/evidence` is the methodology-compliant execution path:

- `models.py`: versioned scenario, ground-truth, failure, and turn records.
- `loaders.py`: split-aware scenario and ground-truth loading.
- `baselines.py`: six frozen context policies and provider-neutral reasoner contract.
- `evaluators.py`: blinded deterministic/rule evaluation, human placeholder, optional LLM-judge adapter, and agreement records.
- `artifacts.py`: exclusive-create immutable run directories and SHA-256 manifests.
- `runner.py`: paired seeded scheduling, evidence capture, failure preservation, cleanup, manifests, and summaries.
- `live.py`: live provider and real SC-EVM adapters.
- `statistics.py`: paired effects, bootstrap intervals, distributions, tails, and missing-data accounting.
- `certification.py`: executable publication gates.
- `security.py`: live security scenario executor.
- `cli.py`: governed command-line entrypoint.

The legacy `src/benchmarks` runner remains available for historical compatibility but is not the claim-bearing engine.

## Developer setup

Use the repository environment and lockfile. No additional dependency is required. Datasets must conform to `RESULT_SCHEMA.md` and name one of the three governed splits. Final Evaluation is rejected when `--tuning` is present.

## Smoke execution

```bash
uv run python -m src.evidence.cli \
  --dataset evaluation/datasets/development/smoke-software-engineering-v1.json \
  --output-root evaluation-results \
  --turn-length 20 \
  --seed 11 \
  --tuning \
  --smoke
```

Smoke mode uses `OfflineSmokeReasoner`. Its output and estimated tokens validate data flow only and are marked `publishable: false`. It must never support a product or commercial claim.

## Live execution

Start the real SC-EVM service, then run:

```bash
uv run python -m src.evidence.cli \
  --dataset evaluation/datasets/development/smoke-software-engineering-v1.json \
  --output-root evaluation-results \
  --turn-length 20 \
  --seed 11 \
  --tuning \
  --live \
  --base-url http://127.0.0.1:8000
```

Live mode uses the configured provider for the four direct baselines and the actual service lifecycle for SC-EVM with Graphify OFF and ON. Run a single provider prerequisite request before a campaign; preserve the failure and stop if it cannot complete.

## Artifacts

Each invocation creates a unique `evaluation-results/<run_id>/` directory using exclusive creation. It contains planned/final manifests, environment, configuration, dataset/model/prompt versions, complete raw trial results, evaluator records, retrieval/Graphify traces, failures, statistics, certification, summary, and checksums. A rerun always creates a new ID; no file is overwritten.

## Current execution status

The governed live adapters and separated usage/cost records are implemented. The 2026-07-11 prerequisite request timed out, so the live six-strategy campaign was not started and the repository remains uncertified for publication. See `LIVE_SMOKE_CAMPAIGN_REPORT.md` and `EXECUTION_CERTIFICATION.md`.
