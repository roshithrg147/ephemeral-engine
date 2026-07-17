# RFC-0003: Benchmark Methodology

- **Status:** Accepted
- **Author:** Evaluation Governance
- **Created:** 2026-07-11
- **Reviewers:** Product, Architecture, Evaluation, Security
- **Supersedes:** None
- **Superseded by:** None

## Summary

Accept the [SC-EVM Evidence and Evaluation framework](../evaluation/README.md) as the mandatory methodology for claim-bearing benchmarks. This RFC defines how evidence is produced; it does not assert favorable outcomes.

## Motivation

Existing artifacts measure execution success, latency, and estimated tokens but do not establish context quality, answer correctness, isolation assurance, cost, Graphify uplift, or commercial claims. A preregistered and reproducible framework is required to prevent mechanism evidence and favorable subsets from being presented as outcomes.

## Relationship to the Manifesto

- **Relevance:** measures recall, precision, constraints, topic recovery, stale context, pollution, and correctness.
- **Isolation:** requires adversarial cross-session, burn, injection, and lifecycle evidence.
- **Control:** freezes baselines, datasets, configurations, exclusions, reruns, and claim approvals before execution.
- **Evidence:** preserves raw results, failures, provenance, uncertainty, unfavorable outcomes, and independent review.

## Relationship to the Product Boundary

The methodology tests the existing product hypothesis without promoting optional capabilities. Graphify remains experimental and outside the MVP. Dual-model synthesis remains optional. Provider independence, production readiness, enterprise-grade operation, zero leakage, physical erasure, and total-token constancy remain unsupported or prohibited absent their specific evidence gates.

## Current State

The repository has a reusable runner, strategy adapters, unit/integration/security mechanism tests, historical reports, and Graphify artifacts. It lacks governed scenarios and ground truth, six required baselines, quality evaluators, retrieval traces, exact usage/cost, paired seeded trials, versioned manifests, checksums, and reproducible claim analysis.

## Proposed Decision

Formal evidence uses:

- six required baselines: Full Conversation Replay, Sliding Window, Rolling Summarization, Standard Top-K Vector Retrieval, SC-EVM Without Graphify, and SC-EVM With Graphify;
- four categories: Software Engineering, Legal and Contract Analysis, Enterprise SOP and Operational Procedure, and Knowledge and Research Assistant;
- 20, 50, 100, 250, and 500-turn conditions, preserving infeasibility as evidence;
- Development, Validation, and sealed Final Evaluation splits;
- structured ground truth, metric definitions, failure taxonomy, paired seeded trials, confidence intervals, effect sizes, sensitivity analysis, and model-family replication;
- immutable raw results, complete failures, environment/configuration provenance, checksums, rerun/exclusion disclosure, and no cherry-picking;
- an exact Graphify on/off ablation with all other variables controlled;
- claim-specific approval gates in the commercial claim matrix.

## Alternatives Considered

- Continue latency/success runs: rejected because transport success is not correctness.
- Add only a manifest to the current runner: rejected because it would not supply scenarios, quality, baselines, traces, or fair comparisons.
- Tune before freezing methodology: rejected because it contaminates evaluation design.
- Use one composite score: rejected because it hides safety and quality trade-offs.

## Security and Privacy Impact

Customer data is prohibited without explicit governance. Isolation and deletion claims require dedicated security evidence. Raw prompts, retrieved context, and outputs require access and retention controls. Model judges cannot solely approve security claims.

## Operational Impact

Claim-bearing runs will be slower and more expensive due to repeated paired trials, long horizons, human review, and artifact preservation. Infeasible conditions are reported rather than silently dropped.

## Compatibility and Migration

Historical artifacts remain unchanged and may be referenced through checksum-addressed legacy wrappers. Current entrypoints remain available but are not compliant claim runners until the documented gaps are implemented.

## Validation Plan

Validate document presence, required baselines/categories/lengths/scenarios/metrics/failures, split restrictions, statistical and reproducibility rules, Graphify controls, claim statuses, schema fields, links, and artifact/source impact.

## Commercial-Claim Impact

No claim becomes supported by accepting this RFC. Claims become eligible only after compliant execution meets preregistered thresholds and reviewer approval. Failed, negative, null, rerun, and excluded evidence remains disclosed.

## Risks

- High evaluation cost may reduce cadence; use Development subsets without weakening Final Evaluation.
- Human and model evaluators can disagree; preserve agreement and adjudication.
- Runner implementation may lag methodology; execution readiness remains explicitly partial.

## Rollback Plan

Reverting documents does not change runtime. Any replacement methodology must supersede this RFC, preserve existing artifacts, and explain effects on prior claims.

## Decision

Accepted as the canonical methodology. Benchmark execution under this methodology remains blocked by gaps recorded in [BENCHMARK_RUNNER_GAPS.md](../evaluation/BENCHMARK_RUNNER_GAPS.md). No Day 4 execution is authorized by this decision.

## Evidence

- [Evaluation Handbook](../evaluation/EVALUATION_HANDBOOK.md)
- [Benchmark Specification](../evaluation/BENCHMARK_SPECIFICATION.md)
- [Metrics](../evaluation/METRICS.md)
- [Statistical Methods](../evaluation/STATISTICAL_METHODS.md)
- [Reproducibility Charter](../evaluation/REPRODUCIBILITY_CHARTER.md)
- [Commercial Claim Matrix](../evaluation/COMMERCIAL_CLAIM_MATRIX.md)
- Existing runner, adapters, tests, and historical artifacts inventoried without modification
