# Metric Definitions

No unqualified “accuracy” metric is permitted. Unless stated otherwise, proportions aggregate first per scenario/trial, then as paired category/length distributions; report mean or median as appropriate with 95% confidence intervals. Claim-bearing primary metrics require at least 30 independent scenarios per reported category and length, every preregistered seed, and the statistical rules in [STATISTICAL_METHODS.md](STATISTICAL_METHODS.md). Larger samples may be required by power analysis. `TP`, `FP`, and `FN` use turn-specific ground-truth labels.

## Primary metrics

| Metric | Definition, unit, and calculation | Interpretation / better | Confounders | Claim eligible? |
|---|---|---|---|:---:|
| Context Recall | Required retrieval evidence recovered; proportion `TP/(TP+FN)` | Coverage of needed context; higher | Chunk granularity, duplicate sources, ground-truth completeness | Yes |
| Context Precision | Retrieved evidence labeled required or relevant; proportion `TP/(TP+FP)` | Selectivity; higher | Chunk size, K, unlabeled neutral context | Yes |
| Constraint Retention | Active required constraints satisfied; proportion satisfied/applicable | Long-horizon compliance; higher | Answer refusals, ambiguous constraints | Yes |
| Instruction Stability | Turns preserving the correct instruction hierarchy; proportion stable/applicable | Resistance to conflicting history; higher | Ground-truth priority ambiguity | Yes |
| Irrelevant Context Inclusion Rate | Irrelevant retrieved items / all retrieved items | Retrieval noise; lower | Retrieval trace completeness, chunking | Yes |
| Topic Recovery Accuracy | Topic-return turns restoring required earlier context and current constraints; proportion correct | Recovery after switches; higher | Return-turn definition, partial credit | Yes |
| Answer Correctness | Preregistered weighted 0–4 ground-truth rubric, normalized to `[0,1]` | Task outcome; higher | Reviewer subjectivity, style bias | Yes |
| Hallucination Rate | Unsupported factual propositions / all factual propositions, plus binary turn incidence | Unsupported output; lower | Proposition segmentation, incomplete sources | Yes |
| Stale Context Usage Rate | Turns using expired/superseded facts / applicable turns | Temporal discipline; lower | Ambiguous effective dates | Yes |
| Context Pollution Rate | Turns whose answer is materially changed by irrelevant/harmful context / evaluated turns | Downstream harm from context; lower | Causal attribution; requires paired evidence | Yes |
| Memory Coverage | Unique required memory source groups retrieved at least once / required source groups | Scenario-level memory coverage; higher | Duplicate grouping, unqueried requirements | Yes |
| Cross-Session Leakage Rate | Turns containing another session's canary or protected fact / attack turns | Isolation outcome; lower; zero desired | Accidental shared public facts, canary collision | Security approval required |
| Burn Correctness | Burn trials with inaccessible pre-burn ephemeral facts, absent session record/collection, and unaffected control session / burn trials | Logical deletion behavior; higher | Provider prior knowledge, auxiliary durable state | Security approval required |
| Direct Input Token Growth | Regression slope and per-turn series of tokens sent to final reasoner versus turn index | Direct growth; slope closer to zero | Tokenizer, retrieved-context variability | Yes, direct-input wording only |
| Cumulative Input Tokens | Sum of provider-reported input tokens across reformulation, summary, reasoning, synthesis, and evaluators per scenario | Total input usage; lower at equal quality | Missing usage, retries, provider tokenizers | Yes only with exact usage |
| Output Tokens | Sum of provider-reported output tokens per scenario | Output volume/cost; contextual, not inherently better | Verbosity and tokenizer | Supporting claim only |
| End-to-End Latency | Monotonic time from submitted turn to completion event, seconds | User-visible completion time; lower | Network/provider load, staged chunking | Yes with controlled environment |
| Time to First Meaningful Response | Monotonic time to first non-whitespace answer content that survives parsing, seconds | Perceived responsiveness; lower | Simulated chunks, buffering; current API cannot claim provider TTFT | Pending runner support |
| Failure Rate | Failed or invalid strategy turns/trials / attempted turns/trials, excluding separately reported dataset defects | Reliability; lower | Failure taxonomy and invalid-run policy | Yes |
| Cost Per Completed Scenario | Total measured provider/tool/evaluator cost divided by valid completed scenarios; currency/scenario | Economic trade-off; lower at comparable quality | Pricing date, missing usage, free tiers | Yes with billing evidence |

## Supporting metrics

| Metric | Calculation and unit | Aggregation / better | Minimum sample and confounders | Claim use |
|---|---|---|---|---|
| p50 latency | 50th percentile turn latency, seconds | Per strategy/category/length; lower | At least 30 turns; network/provider load | Supporting |
| p95 latency | 95th percentile, nearest-rank or declared quantile, seconds | Same strata; lower | At least 100 turns preferred | Supporting |
| p99 latency | 99th percentile, seconds | Same strata; lower | At least 500 turns preferred | Supporting |
| Retry count | Total and per-turn provider retries | Distribution; lower | Adapter retry ownership | Diagnostic |
| Timeout rate | Timed-out attempts / attempts | Proportion; lower | Timeout configuration | Reliability claim |
| Retrieval count | Number of returned chunks/items | Distribution; neutral | K and empty results | Diagnostic |
| Retrieved-context token count | Exact tokenizer count of admitted retrieved context | Per turn/scenario; lower only at equal quality | Tokenizer and enclosures | Supporting |
| Context-budget utilization | Direct context tokens / declared direct budget | Proportion; context-dependent | Budget definition | Diagnostic |
| Indexing lag | Time from response completion to successful searchable commit, milliseconds | Distribution; lower | Clock/process instrumentation | Reliability |
| Evaluator disagreement rate | Nonmatching categorical labels or rubric difference beyond tolerance / double-reviewed items | Per evaluator/version; lower | Rubric ambiguity | Evidence-quality control |
| Invalid-output rate | Outputs failing declared schema/parser / attempted outputs | Proportion; lower | Parser strictness | Reliability |

## Measurement hierarchy

Provider-reported usage is preferred and must include provider/model/tokenizer provenance. Exact local tokenization is second choice and labeled calculated. Character-based estimates are diagnostic only, never billing-grade and never sufficient for cost or cumulative-token claims. Latency uses monotonic clocks. Costs use a versioned price table and include retries; missing exact usage makes cost `null`, not zero.
