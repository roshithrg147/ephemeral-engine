# Evaluation Handbook

## 1. Purpose and scope

This is the canonical manual for creating, executing, reviewing, and publishing SC-EVM evidence. It governs context quality, correctness, reliability, isolation, token, latency, cost, Graphify, and commercial claims. It does not tune the product or declare outcomes.

## 2. Evaluation philosophy and evidence hierarchy

Evaluation follows [BENCHMARK_PHILOSOPHY.md](BENCHMARK_PHILOSOPHY.md). Evidence strength, from narrowest to strongest, is:

1. **Mechanism evidence:** code path, contract, or artifact exists.
2. **Functional correctness:** deterministic test proves specified behavior under controlled cases.
3. **Comparative quality:** paired strategy trials on governed scenarios and ground truth.
4. **Operational reliability:** repeated failure, latency, concurrency, and lifecycle evidence.
5. **Security/isolation evidence:** adversarial, cross-session, burn, and trust-boundary testing.
6. **Commercial-claim evidence:** replicated results meeting the claim matrix and review gate.

Higher levels require, and cannot be inferred from, lower levels.

## 3. Claim approval model

Every proposed claim receives an ID, exact wording, owner, relevant Product Boundary row, required metrics/baselines/categories, preregistered thresholds, evidence links, statistical review, security review where applicable, and approval status. Product and Evidence owners approve ordinary claims; Architecture joins boundary claims; Security joins isolation/deletion claims; executive review is required for changes to canonical positioning. See [COMMERCIAL_CLAIM_MATRIX.md](COMMERCIAL_CLAIM_MATRIX.md).

## 4. Benchmark categories and baselines

Formal runs cover Software Engineering, Legal and Contract Analysis, Enterprise SOP and Operational Procedure, and Knowledge and Research Assistant at 20, 50, 100, 250, and 500 turns. The six required strategies are defined in [BASELINES.md](BASELINES.md); no substitution is allowed in a claim-bearing run.

## 5. Dataset and ground-truth governance

[DATASET_DESIGN_GUIDE.md](DATASET_DESIGN_GUIDE.md) controls scenario construction, versions, splits, provenance, sensitive data, and retirement. [GROUND_TRUTH_SPECIFICATION.md](GROUND_TRUTH_SPECIFICATION.md) defines fact/constraint labels, acceptable variation, retrieval relevance, rubrics, ambiguity, and two-reviewer requirements. Final Evaluation remains sealed from tuning.

## 6. Metric and statistical governance

Every reported measure uses [METRICS.md](METRICS.md); undefined “accuracy” is prohibited. Paired trials, seeds, intervals, effect sizes, failures, missing data, stratification, and sensitivity follow [STATISTICAL_METHODS.md](STATISTICAL_METHODS.md). Aggregates never replace category, length, seed, and failure distributions.

## 7. Failure taxonomy

Every failed turn may have multiple labels from [FAILURE_TAXONOMY.md](FAILURE_TAXONOMY.md), with one primary label when evidence permits. Provider failures, evaluator ambiguity, and dataset defects remain distinct from strategy-quality failures.

## 8. Graphify ablation

Graphify claims require the paired on/off design in [GRAPHIFY_ABLATION.md](GRAPHIFY_ABLATION.md). All non-Graphify variables remain identical. Structural categories are reported separately, and a null or negative result is valid evidence.

## 9. Reproducibility and provenance

Every run follows [REPRODUCIBILITY_CHARTER.md](REPRODUCIBILITY_CHARTER.md) and [RESULT_SCHEMA.md](RESULT_SCHEMA.md): immutable run ID, versions, seeds, model/provider parameters, prompt checksums, commit, dependency lock, environment, raw artifacts, checksums, failures, reruns, and exclusions. Historical artifacts are preserved without migration-in-place.

## 10. Benchmark execution lifecycle

1. Author and independently review dataset and ground truth.
2. Freeze dataset, evaluator, prompt, strategy, and analysis versions.
3. Preregister hypotheses, thresholds, comparisons, exclusions, and stopping rules.
4. Validate manifest and perform unscored warm-up.
5. Execute paired, seeded units using [BENCHMARK_SPECIFICATION.md](BENCHMARK_SPECIFICATION.md).
6. Persist raw records before evaluation.
7. Run deterministic evaluators, then blinded human or permitted model-assisted review.
8. Adjudicate disagreements without seeing strategy identity where possible.
9. Produce stratified statistics, sensitivity analyses, and failure report.
10. Verify checksums and independent reproducibility.
11. Review claim eligibility; publish complete limitations and failed units.

## 11. Evaluator and review process

[EVALUATOR_GUIDE.md](EVALUATOR_GUIDE.md) governs evaluator choice. Dataset reviewers cannot be the sole final adjudicators of their own scenarios. Analysis changes are code-reviewed. Claim-bearing evidence requires an independent evidence reviewer and, for ambiguous/high-value cases, two human reviewers plus adjudication.

## 12. Result publication rules

Publish the manifest, dataset/evaluator versions, all included and failed units, distributions and intervals, effect sizes, exclusions, reruns, costs, limitations, and artifact checksums. Do not publish a best seed, best category, or favorable rerun as the overall result. Internal negative results remain retained and discoverable.

## 13. Known limitations

The current runner cannot implement this complete protocol. It lacks scenario/ground-truth identity, raw full results, retrieval traces, exact usage/cost, evaluator records, manifests, checksums, seeds, environment capture, and required baselines. These are recorded in [BENCHMARK_RUNNER_GAPS.md](BENCHMARK_RUNNER_GAPS.md); Day 3 does not force broad runner changes.

## 14. Supporting governance

[RFC-0003](../rfcs/RFC-0003-benchmark-methodology.md) accepts this methodology. The [Manifesto](../MANIFESTO.md), [Product Boundary](../PRODUCT_BOUNDARY.md), [Architecture](../ARCHITECTURE.md), and accepted ADRs remain superior authorities.
