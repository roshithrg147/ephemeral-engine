# Result and Provenance Schema

Canonical records are JSON-compatible and include `schema_name` plus semantic `schema_version`. Required fields are marked **R**; optional fields **O**. Unknown fields may be added only compatibly within a minor version; removed or redefined fields require a major version.

## Run manifest: `scevm.run-manifest/1.0.0`

| Field | Req | Type / meaning |
|---|:---:|---|
| `run_id`, `created_at`, `status` | R | Immutable ID, UTC timestamp, planned/running/completed/partial/invalid/failed |
| `hypotheses`, `claim_ids`, `acceptance_thresholds` | R | Preregistered questions and gates |
| `dataset` | R | Name, version, split, scenario IDs, checksum |
| `strategies` | R | Stable IDs, versions, baseline IDs, configuration checksums |
| `trials` | R | Categories, lengths, seeds, order, expected unit count |
| `models` | R | Provider, full identifiers, parameters, limits, pricing version |
| `prompts` | R | Role/name/version/checksum; protected text reference |
| `evaluators`, `analysis` | R | IDs, versions, prompt/rubric/checksums |
| `code` | R | Git commit, dirty flag, dependency-lock checksum |
| `environment` | R | Environment record ID |
| `timeouts`, `retry_policy`, `warmup` | R | Fixed execution policy |
| `exclusion_rules`, `stopping_rules` | R | Preregistered rules |
| `parent_run_id`, `rerun_reason` | O | Required for reruns |

## Strategy result: `scevm.strategy-result/1.0.0`

Required: `run_id`, `strategy_id`, `strategy_version`, `baseline_id`, `scenario_id`, `scenario_version`, `trial_id`, `seed`, `turn_length`, `started_at`, `finished_at`, `status`, ordered `turns`, cleanup/burn result, attempts, and raw-artifact references. Optional: strategy-native diagnostics.

## Turn result: `scevm.turn-result/1.0.0`

Required: `turn_id`, ordinal, input text/checksum, complete raw response reference/checksum, parsed response, status, attempt records, retrieval trace ID, token/cost record ID, latency record ID, action/intent where applicable, failure labels, evaluator IDs, and timestamps. Response excerpts alone are insufficient.

## Retrieval trace: `scevm.retrieval-trace/1.0.0`

Required: query text/checksum, retrieval sources, candidate IDs, source/session IDs, ranks, scores/distances, admission decision/reason, admitted text checksum/token count, pending-memory indicator, structural-context indicator, Graphify version/artifact checksum/status/latency, and errors. Sensitive raw text may be access-controlled but remains checksum-addressable.

## Token and cost record: `scevm.usage/1.0.0`

For every reformulation, summarization, reasoning, synthesis, embedding, graph, retry, and evaluator call record provider/model, input/output/cache tokens, measurement type (`provider_reported`, `tokenizer_calculated`, `estimated`), tokenizer, price-table version, currency, calculated cost, and missing reason. Aggregates must not mix estimates with billing-grade values without separate fields.

## Latency record: `scevm.latency/1.0.0`

Required monotonic durations: queue/start, reformulation, embedding, semantic retrieval, graph retrieval, context assembly, provider attempts, synthesis, first meaningful response, completion, indexing lag, and end-to-end. Unsupported phases are `null` with reason.

## Evaluator score: `scevm.evaluator-score/1.0.0`

Required: evaluator ID/type/version, blind strategy label, turn/scenario ID, rubric version, dimension scores, deterministic assertions, cited evidence, confidence, ambiguity flag, failure-label proposals, timestamp, and raw decision checksum. Human records include reviewer pseudonym; model judges include provider/model and judge-prompt checksum.

## Failures, exclusions, and reruns

- Failure record: primary code, secondary codes, scope, severity, observable evidence, attributed layer, adjudication status.
- Exclusion record: affected IDs, preregistered rule, requester, approver, reason, timestamp, and with/without analysis references.
- Rerun record: new/parent run IDs, reason, changed fields, original preservation confirmation.

## Environment and checksums

Environment record includes OS, architecture, runtime, hardware class, container digest, region, timezone, clock, non-secret config, secret variable names, dependency lock, and tool versions. `checksums.sha256` covers manifests, raw results, traces, evaluations, failures, exclusions, analysis, and environment records.

## Summary statistics

Summary records contain strata, sample/attempt/failure/missing counts, metric definition version, estimates, distribution fields, confidence intervals, effect sizes, corrected p-values where used, sensitivity results, and source-record checksums.

## Historical formats

Existing benchmark JSON remains unchanged. Migration is additive: an importer may create a new `scevm.legacy-import/1.x` wrapper referencing the original checksum, mapping available fields, and setting unavailable fields to `null` with `legacy_missing`. Never rewrite or backfill the original artifact.
