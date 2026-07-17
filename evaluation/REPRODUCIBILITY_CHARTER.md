# Reproducibility Charter

**A benchmark result that cannot be reproduced or audited is not valid evidence for a commercial claim.**

Every formal run must preserve:

- fixed dataset version, split, scenario IDs, and scenario checksums;
- fixed seeds and randomized execution order;
- provider and complete model identifiers;
- temperature, sampling controls, output limits, timeouts, and retry policy;
- complete system, rewrite, summary, synthesis, and judge prompt versions/checksums;
- strategy and baseline configuration;
- source git commit and dirty-worktree state;
- dependency lockfile name and checksum;
- OS, architecture, runtime, container image/digest, hardware class, region, timezone, and clock source;
- non-secret configuration and names of required secret variables;
- immutable run ID and schema versions;
- raw prompts, outputs, retrieval traces, usage, timing, failures, evaluator records, and analysis inputs;
- SHA-256 checksums for every generated artifact;
- analysis code/version and exact invocation.

## Anti-cherry-picking rules

All preregistered strategies, categories, lengths, seeds, scenarios, and failures are reported. Best-seed, best-category, or successful-only selection is prohibited. Negative and null results remain preserved. Development, Validation, and Final Evaluation data are stored and permissioned separately; Final Evaluation is never used for tuning.

Reruns create new immutable IDs and link to every prior attempt. Reports disclose reason, changed variables, and whether the original conclusion changed. Manual exclusions record reviewer, timestamp, reason code, affected records, and with/without analysis. Silent overwrite or deletion invalidates claim eligibility.

## Independent reproduction

A second engineer must be able to verify checksums, reconstruct the environment from recorded artifacts, execute analysis from raw records, and obtain equivalent statistics within declared numerical tolerance. Claims require at least one independent analysis reproduction; high-impact claims require an independent execution reproduction or a disclosed limitation.
