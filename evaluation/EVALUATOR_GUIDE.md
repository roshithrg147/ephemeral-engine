# Evaluator Guide

## Evaluator types

- **Deterministic:** exact canary absence/presence, schema validity, session existence, burn outcome, token/latency arithmetic, source IDs. Preferred whenever observable behavior has an exact rule.
- **Rule-based:** normalized facts, constraints, regex/structured assertions, temporal and source checks. Rules are versioned and tested against calibration cases.
- **Human:** required for nuanced correctness, legal/procedural interpretation, ambiguity, material pollution, and high-stakes/security adjudication.
- **LLM-as-judge:** permitted for scalable preliminary rubric scoring and error discovery after calibration; never the sole evaluator for high-stakes correctness, security, leakage, deletion, or commercial approval.

## Independence and blinding

Evaluators see anonymous strategy labels and randomized output order where technically possible. Judge models must not be the exact candidate instance/configuration under evaluation when an alternative is available. Dataset authors cannot be sole adjudicators. Evaluators never receive the commercial hypothesis wording when it could bias scoring.

## Versioning and calibration

Every evaluator has ID, version, rubric/rule or prompt checksum, model/provider where relevant, and calibration-set results. Calibration sets contain clear passes, clear failures, boundary cases, and adversarial examples and remain separate from Final Evaluation. Changes create a new version and require rescoring impact analysis.

## Agreement and adjudication

Double-score at least 20% of ordinary qualitative items and 100% of high-value, ambiguous, legal, security, or claim-critical items. Report Cohen's kappa for categorical labels and weighted kappa or intraclass correlation for ordinal scores, plus raw disagreement. Low agreement blocks claim approval until rubric or ground truth is repaired.

Reviewers may appeal with cited scenario evidence. An independent adjudicator records original decisions, final decision, rationale, and whether the issue was evaluator ambiguity or dataset defect. Strategy identity remains blind through adjudication where possible.

## Bias controls and limitations

Control verbosity, order, style, provider familiarity, self-preference, and position bias through blinded labels, randomized order, length-aware rubrics, multiple evaluators, and deterministic anchors. Model judges can reproduce common biases and cannot validate provider independence or security guarantees. Human reviewers can drift and require training, calibration, and fatigue controls.
