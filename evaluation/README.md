# SC-EVM Evidence and Evaluation

This directory defines how SC-EVM claims are tested, reproduced, challenged, and approved. It contains methodology only; it does not assert favorable results.

- [Evaluation Handbook](EVALUATION_HANDBOOK.md) — canonical operating manual and approval workflow.
- [Benchmark Philosophy](BENCHMARK_PHILOSOPHY.md) — principles governing fair and useful evidence.
- [Benchmark Specification](BENCHMARK_SPECIFICATION.md) — run, trial, scenario, artifact, and failure protocol.
- [Baselines](BASELINES.md) — six mandatory comparison strategies and fairness controls.
- [Dataset Design Guide](DATASET_DESIGN_GUIDE.md) — scenario construction, splits, review, versioning, and retirement.
- [Ground Truth Specification](GROUND_TRUTH_SPECIFICATION.md) — required facts, constraints, labels, rubrics, and adjudication.
- [Metrics](METRICS.md) — primary and supporting metric definitions.
- [Failure Taxonomy](FAILURE_TAXONOMY.md) — hierarchical multi-label failure codes.
- [Statistical Methods](STATISTICAL_METHODS.md) — paired trials, intervals, effect sizes, and missing-data rules.
- [Reproducibility Charter](REPRODUCIBILITY_CHARTER.md) — required provenance and anti-cherry-picking rules.
- [Graphify Ablation](GRAPHIFY_ABLATION.md) — controlled structural-context on/off study.
- [Commercial Claim Matrix](COMMERCIAL_CLAIM_MATRIX.md) — evidence gates and permitted external wording.
- [Result Schema](RESULT_SCHEMA.md) — versioned JSON-compatible run and evaluation records.
- [Evaluator Guide](EVALUATOR_GUIDE.md) — deterministic, human, and model-assisted evaluation controls.
- [Benchmark Runner Gaps](BENCHMARK_RUNNER_GAPS.md) — differences between current code and this methodology.
- [Evidence Runner](EVIDENCE_RUNNER.md) — developer setup, execution, artifact, and offline-smoke instructions.
- [Runner Gap Resolution](RUNNER_GAP_RESOLUTION.md) — Day 5 implementation status for every recorded runner gap.
- [Validation Report](VALIDATION_REPORT.md) — deterministic platform verification.
- [Smoke Benchmark Report](SMOKE_BENCHMARK_REPORT.md) — non-publishable Development smoke outcome.
- [Execution Certification](EXECUTION_CERTIFICATION.md) — Day 5 campaign-readiness decision.
- [Gap Closure Report](GAP_CLOSURE_REPORT.md) — resolved, partial, and missing engineering blockers.
- [Live Smoke Campaign Report](LIVE_SMOKE_CAMPAIGN_REPORT.md) — preserved live-provider prerequisite failure.

Governance: [Manifesto](../MANIFESTO.md), [Product Boundary](../PRODUCT_BOUNDARY.md), [Architecture](../ARCHITECTURE.md), and [RFC-0003](../rfcs/RFC-0003-benchmark-methodology.md).

## Quick execution

```bash
uv run python -m src.evidence.cli \
  --dataset evaluation/datasets/development/smoke-software-engineering-v1.json \
  --output-root evaluation-results \
  --turn-length 20 --seed 11 --tuning --smoke
```

This command validates the platform with a deterministic offline provider. It does not generate publishable comparative evidence.
