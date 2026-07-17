# Campaign Manifest: Day 7 Controlled Scientific Validation

- **Campaign ID:** `scevm-eval-20260713T143422Z-development-smoke-1-0-0-2558c093-db9c5534`
- **Date:** 2026-07-13
- **Classification:** Controlled Scientific Validation (Smoke/Development Scope)
- **Custodian:** Chief Scientific Validation Officer & Independent Evidence Custodian

## 1. Dataset Provenance & Integrity

| Asset | Location | Cryptographic Hash (SHA-256) | Split / Version |
| :--- | :--- | :--- | :---: |
| Evaluation Dataset | [smoke-software-engineering-v1.json](datasets/development/smoke-software-engineering-v1.json) | `703e45bd2948f1926ed86af5583c65b8abbed4909bd25b9156e8ff384027f794` | Development / 1.0.0 |

## 2. Frozen Environment Metadata

- **Git Commit Hash:** `2558c09392035f146aa879b5f895b0c336790c2f`
- **Working Directory Status:** `Dirty` (Tracked edits only; untracked logs and results present)
- **Dependency Lockfile:** `uv.lock` (SHA-256: `2f41856e99116d8ca020acca0ad8f7857efd6ce3eb660ad527cd5c078103d173`)
- **Python Execution Version:** `3.14.4`
- **Execution Platform:** `Linux-7.0.0-27-generic-x86_64-with-glibc2.43`
- **Host Timezone:** `IST` (Indian Standard Time)

## 3. Configuration & Stopping Rules

- **Total Turns Per Strategy:** 20
- **Seeds Executed:** `(11, 42, 101)`
- **Strategies Enforced:** All 6 required baselines:
  1. `full_replay`
  2. `sliding_window`
  3. `rolling_summary`
  4. `top_k_retrieval` (using local `ONNXMiniLM_L6_V2` vectorizer and cosine distance)
  5. `sc_evm_without_graphify` (using cosine distance gating)
  6. `sc_evm_with_graphify` (using cosine distance gating + Graphify)
- **Tuning Mode:** Active (`tuning_mode=True`)
- **Execution Mode:** Offline Smoke Reasoner (`fact-extractor / 1.0.0`)
- **Exclusion/Stopping Rules:** 3 seeds * 6 strategies * 20 turns = 360 total turns planned and executed. No turns or trials were skipped or excluded.
