# Benchmark Specification

## Core units

- **Scenario:** versioned multi-turn case with category, ground truth, distractors, and expected evidence.
- **Turn:** one scenario input and its observable strategy output, retrieval trace, timing, token/cost record, and evaluation.
- **Trial:** one strategy executing one scenario at one required length under one seed and model configuration.
- **Benchmark unit:** paired set of trials for every required strategy on the same scenario, length, seed, and model configuration.
- **Benchmark run:** immutable collection of preregistered units sharing dataset, evaluator, code, environment, and analysis versions.
- **Strategy:** declared context-construction and reasoning procedure.
- **Baseline:** required reference strategy defined in [BASELINES.md](BASELINES.md).

## Required turn lengths and categories

Every formal comparison includes **20, 50, 100, 250, and 500 turns**. An infeasible length is retained as an explicit failed, invalid, or incomplete trial with reason; it is never silently omitted.

Categories are:

1. **Software Engineering:** dependencies, corrected requirements, source provenance, structural relationships, and instruction injection.
2. **Legal and Contract Analysis:** active/superseded clauses, temporal ordering, conflicts, citations, and forbidden conclusions.
3. **Enterprise SOP and Operational Procedure:** step ordering, exceptions, roles, escalation, safety constraints, and topic returns.
4. **Knowledge and Research Assistant:** source attribution, delayed references, ambiguity, corrections, noise, and uncertainty.

## Fixed configuration

The manifest records strategy version, baseline, full provider/model identifier, model parameters, output limit, system/control prompt checksums, dataset version, scenario IDs, evaluator version, git commit, dependency-lock checksum, environment, and seed. Strategies use the same target reasoning model, temperature, output limit, timeout, retries, and scenario content where technically possible. Deviations are preregistered and analyzed separately.

## Execution protocol

1. Validate manifest and artifact paths before any trial.
2. Run one unscored warm-up request per model/provider/configuration; warm-up content is not a benchmark scenario.
3. Randomize strategy order within each paired unit using the recorded seed.
4. Start every trial from declared empty state; use unique session IDs.
5. Apply a fixed per-turn timeout and a fixed trial deadline from the manifest.
6. Retry only provider/network failures eligible under the common retry policy. Preserve every attempt and backoff.
7. Record raw inputs, outputs, traces, timings, tokens, failures, and evaluator inputs before aggregation.
8. Burn/clear strategy state after the trial and record cleanup outcome.

## Failure, invalidity, and reruns

- A model refusal, invalid output, timeout, provider error, leakage, or burn error is a result, not an exclusion.
- A run is **invalid** only for preregistered infrastructure defects that prevent fair comparison, dataset corruption, manifest mismatch, or artifact-write failure. Invalid evidence remains stored.
- A partial run reports all completed and missing units; it cannot support an aggregate commercial claim requiring the missing units.
- Reruns receive a new run ID, point to the prior run, state reason and changed conditions, and never overwrite it.
- Manual exclusion requires reviewer, reason code, timestamp, affected units, and analysis with and without exclusion.

## Artifact rules

Run ID format: `scevm-eval-YYYYMMDDThhmmssZ-<dataset>-<commit8>-<nonce>`. Artifacts live under `evaluation-results/<run_id>/` when implemented: `manifest.json`, `raw/`, `evaluations/`, `failures.jsonl`, `summary.json`, `checksums.sha256`, and analysis outputs. Historical files retain their existing names and schema.

Schema version is mandatory and defined in [RESULT_SCHEMA.md](RESULT_SCHEMA.md). A completed run is immutable; corrections create a derived analysis artifact with provenance.
