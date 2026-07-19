# Existing Evaluation Inventory and Benchmark Runner Gaps

## Existing evaluation inventory

| Component | Path | Inputs / outputs / metrics | Evidence type | Limitations | Reuse status | Required change |
|---|---|---|---|---|---|---|
| BenchmarkRunner | `src/benchmarks/runner.py` | Prompt list + adapters → JSON turns; success, estimated tokens, latency | Reliability/cost proxy | No scenarios, ground truth, seeds, manifest, raw response, traces, environment, checksums | Reusable With Changes | Implement versioned protocol after methodology approval |
| Token estimator | `src/benchmarks/token_utils.py` | Text → `len/4` estimate | Cost proxy | Not provider/billing-grade | Insufficient | Retain only as labeled estimate fallback |
| Strategy contract | `src/strategies/base.py` | Prompt/session → result dict | Mechanism | No version/capability/schema contract | Reusable With Changes | Add stable identity/version and schema validation |
| Dual-model adapter | `src/strategies/dual_model_adapter.py` | API SSE → response/action/estimated usage/latency | Reliability | Simulated chunks; no retrieval/raw event preservation | Reusable With Changes | Preserve all events and exact failure/usage provenance |
| Single-model adapter | `src/strategies/single_model_adapter.py` | Prompt + local state → structured result | Comparative mechanism | Not one of six complete baselines; different context path | Reusable With Changes | Define as strategy/config, not proof baseline |
| AntiGravity adapter | `src/strategies/antigravity_cli_adapter.py` | External command → normalized result | Reliability | Environment-dependent; historical run failed | Reusable With Changes | Capture executable/version/environment and failure records |
| Entrypoints | `src/tests/run_benchmark_suite*.py` | CLI args → runner artifacts | Mechanism | Fixed 50-prompt assumptions; naming inconsistency | Reusable With Changes | Accept manifest/dataset/run ID after runner work |
| Prompt dataset | `src/tests/benchmark_suite.json`, `test_stress_50.py` | Prompt strings | Mechanism/load | No scenario structure, split, version, or ground truth | Insufficient | Replace for claim runs with governed datasets; preserve fixture use |
| Live SSE harness | `src/tests/test_harness.py` | Two-session live flow → JSON report | Isolation/reliability | Model-dependent assertions; overstates zero leakage/physical wipe; post-burn query path mismatch risk | Reusable With Changes | Bound claims and emit schema/failure provenance |
| Unit/integration tests | `src/tests/test_*.py` | Fixtures/runtime → assertions | Functional/security mechanism | Uneven coverage; some require live services | Reusable | Map tests to invariants and separate live evidence |
| Stress harnesses | `test_concurrency_stress.py`, `test_stress_50.py` | concurrent/prompts → results | Reliability | Load-oriented checks without quality ground truth | Reusable With Changes | Integrate governed scenario and evidence records before claim use |
| Historical dual report | `benchmarks/dual_model/*.json` | 50 turns; success/latency/estimated usage | Historical reliability | Success is not correctness; no provenance schema | Historical Only | Preserve unchanged; optionally wrap by checksum |
| Historical “single” report | `benchmarks/single_model/*.json` | AntiGravity failure run | Historical failure | Directory/name mismatch; 0/50 success | Historical Only | Preserve unfavorable result and label accurately |
| Legacy test reports | `src/tests/results/`, validation JSON | Earlier harness outputs | Historical mechanism/reliability | Stale providers/code, inconsistent schemas/claims | Historical Only | Preserve; exclude from current claims |
| Graphify artifacts | `graphify-out/` | Generated graph/report/cache | Mechanism | No downstream on/off evidence | Reusable With Changes | Pin checksum/version for ablation; never rewrite |

## Gaps against accepted methodology

| ID | Required behavior | Current behavior / evidence | Severity | Affected metric | Required implementation | Blocks methodology validation? | Blocks execution? | Blocks claims? | RFC? |
|---|---|---|---|---|---|:---:|:---:|:---:|:---:|
| BRG-001 | Versioned run manifest and immutable run ID | Timestamp payload only | High | All | Manifest loader/validator and immutable artifact directory | No | Yes | Yes | No |
| BRG-002 | Stable scenario identity/version/split/ground truth | Flat prompt strings | Critical | Quality/retrieval | Governed dataset schema and loader | No | Yes | Yes | No |
| BRG-003 | Six required baselines | Three adapters; none implements full baseline set | Critical | Comparative claims | Implement baseline adapters after review | No | Yes | Yes | No |
| BRG-004 | Raw complete turn preservation | Excerpt persisted; adapter raw discarded by report | High | Correctness/failures | Store full raw result by checksum | No | Yes | Yes | No |
| BRG-005 | Retrieval trace | Not captured | Critical | Recall/precision/pollution | Instrument strategy/API trace contract | No | Yes | Yes | Yes |
| BRG-006 | Ground-truth evaluator records | None | Critical | All quality/security | Deterministic/human/judge pipeline | No | Yes | Yes | No |
| BRG-007 | Provider-exact usage and cost | Character estimates and API estimates | High | Tokens/cost | Normalized usage provenance and price table | No | No | Yes | Yes |
| BRG-008 | Phase and TTFR latency | End-to-end only; response chunks simulated | Medium | Latency | Monotonic phase instrumentation | No | No | Yes | Yes |
| BRG-009 | Fixed seeds and paired randomized order | Strategies run sequentially; no seed | High | Statistical validity | Paired scheduler and seed capture | No | Yes | Yes | No |
| BRG-010 | Failure taxonomy and invalid/partial states | Boolean success and exception string | High | Failure rate | Typed status/failure records | No | Yes | Yes | No |
| BRG-011 | Environment/config/prompt provenance | Base URL and timestamps only | High | Reproducibility | Environment and checksum manifest | No | Yes | Yes | No |
| BRG-012 | Checksums, reruns, exclusions, immutability | Files can overwrite `analysis_report.json` | High | Evidence integrity | Artifact store, SHA-256, parent run/exclusion records | No | Yes | Yes | No |
| BRG-013 | 20/50/100/250/500 lengths | Default capped at 50 | High | Horizon effects | Manifest-driven lengths; preserve infeasible failures | No | Yes | Yes | No |
| BRG-014 | Category/length stratified statistics and intervals | Average/min/max/p95 only | High | All claims | Reproducible paired analysis implementation | No | No | Yes | No |
| BRG-015 | Controlled Graphify on/off condition | No toggle or paired trace | Critical | Graphify claims | Explicit condition and artifact pinning | No | Yes | Yes | Yes |
| BRG-016 | Burn/isolation attack units | Separate tests, not integrated protocol | High | Leakage/burn | Security scenario executor and deterministic canaries | No | No | Yes | Yes |

## Day 3 implementation decision

No runner source is changed. The gaps are coupled: adding a few manifest fields without governed datasets, baselines, traces, and evaluators would create false confidence while remaining non-executable under the accepted specification. Implementation belongs in a scoped follow-up before Day 4 execution, with RFC review where the API/provider/trace boundaries change.

## Day 5 closure status

Day 5 implementation status is maintained in [RUNNER_GAP_RESOLUTION.md](RUNNER_GAP_RESOLUTION.md). This original gap statement remains as the audit baseline; closure claims must be read from the resolution matrix and execution certification, not inferred from source presence.
