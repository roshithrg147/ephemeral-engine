# Execution Certification

**Certification status: PARTIAL**

| Gate | Status | Evidence |
|---|---|---|
| Runner Ready | PASS | Immutable runner, paired scheduler, typed failures, schema tests |
| Dataset Ready | PARTIAL | Split enforcement works; only synthetic Development smoke dataset exists |
| Baseline Ready | PASS | Six offline baselines execute using the local ONNX MiniLM embedding function and cosine distance ranking |
| Statistics Ready | PASS | Executable paired effects, bootstrap intervals, distributions, tails, failure/missing accounting |
| Security Ready | PASS | Cosine distance gating unified, telemetry rotation and redaction active, session burn registry checks verified |
| Graphify Ready | PARTIAL | Single API switch and live ON/OFF adapters verified; ablated run completed in smoke campaign |
| Evidence Ready | PASS | Raw/traces/evaluators/failures/manifests/checksums are immutable |
| Reproducibility Ready | PASS | Seeds, versions, commit, lock hash, configuration, environment captured |
| Provider Ready | PASS | Model connectivity, entitlement, and timeouts verified successfully via `scripts/check_provider.py` |
| Claim Ready | PARTIAL | Live Development certification campaign executed successfully; publication requires Final Evaluation split |

Publication certification rejects runs missing sample size, provenance, schemas, artifacts, confidence intervals, effects, evaluator output, failure accounting, or valid checksums. The repository is certified for development and internal testing campaigns, but not for claim-bearing public publication.
