# Statistical Methods

## Design

Strategies run paired on identical scenario, version, turn length, seed, model configuration, and environment block. Strategy order is seeded and randomized. Report results by category and turn length before any overall aggregation.

## Trials, seeds, and nondeterminism

- Default claim-bearing design: at least **30 independent scenarios per category and reported length**, each run with **5 fixed seeds** (`11, 29, 47, 71, 97`) unless preregistered power analysis requires more.
- Deterministic mechanisms use every applicable scenario once plus boundary repetitions.
- Model temperature is fixed across strategies; use `0` where supported for deterministic checks and one preregistered realistic temperature for quality comparisons.
- If providers ignore seeds or remain nondeterministic, record that fact; seeds still control strategy order and local randomness, and repeated trials estimate model variance.
- No optional stopping. Sample size and stopping rules are frozen before Final Evaluation.

## Estimation

Report distributions, counts, failures, median, mean where meaningful, and 95% confidence intervals. Use stratified paired bootstrap with at least 10,000 resamples over scenario units, preserving seed observations within scenario. Proportions also report Wilson intervals. Tail latencies report empirical quantiles and bootstrap intervals when sample size permits.

## Comparisons and effect sizes

Primary comparisons are paired strategy differences. Report absolute difference and relative change, plus:

- paired standardized mean difference for approximately continuous scores;
- Cliff's delta for ordinal/skewed outcomes;
- paired risk difference and odds ratio for binary failures;
- median paired difference for latency/token/cost distributions.

Two-sided `alpha=0.05` may accompany intervals but never replaces effect size or practical threshold. Holm correction applies within each preregistered claim family. Exploratory tests are labeled and do not support claims.

## Outliers, missing data, and failures

Outliers are never removed solely for magnitude. Report robust and untrimmed analyses; exclusion requires a preregistered infrastructure rule and preserved record. Failed turns remain in denominators and receive worst-case task scores where the task was attempted. Missing usage or cost remains `null`; it is not zero and excludes that unit only from that metric, with missingness reported. Dataset defects are reported separately and analyzed with and without affected cases.

## Sensitivity and replication

Mandatory sensitivity analyses cover retrieval thresholds, K/window/budget, scoring weights, evaluator choice, failed-run treatment, and exclusion decisions. Graphify uses its exact paired ablation. Claim-bearing quality results require replication on at least two model families when technically available; if only one is available, status remains Pending Evaluation or Partially Supported. Replication uses the same frozen protocol and reports heterogeneity rather than pooling incompatible families.

## Practical acceptance

Every claim preregisters a minimum practical effect, non-inferiority guardrails for correctness/security, and maximum acceptable latency/cost regression. Statistical significance without practical effect does not approve a claim. A quality gain that violates an isolation guardrail fails acceptance.
