# Graphify Ablation Methodology

## Hypothesis

Graphify may improve structural-context retrieval and answers on tasks whose ground truth depends on explicit relationships. It remains a differentiating hypothesis until controlled evidence demonstrates uplift.

## Paired conditions

- **SC-EVM Without Graphify:** required baseline 5.
- **SC-EVM With Graphify:** required baseline 6.

Every other variable is identical: scenario/order, seed, code commit, model/provider, parameters, prompts, semantic index, embeddings, K, gating, history, pending-memory behavior, context budget, output limit, retries, timeout, environment, and evaluator. The on/off flag, Graphify invocation, and resulting structural block are the only intended differences. Artifact version and checksum are fixed.

## Scenario strata

Primary structural strata are software dependency/caller relationships, multi-file impact, ownership/hierarchy, procedural dependencies, source provenance, and long-horizon dependency recall. Legal, SOP, and research scenarios may qualify only where an explicit governed relationship graph exists. Nonstructural scenarios form a negative-control stratum.

## Required measures

Report retrieval precision, retrieval recall, structural dependency recall, answer correctness, irrelevant-context inclusion, context pollution, hallucination rate, direct/retrieved prompt tokens, end-to-end latency, Graphify query latency, timeout/error rate, and overall failure rate. Record whether the structural context was empty, stale, inferred, or contradicted ground truth.

## Analysis and acceptance

Use paired scenario/seed comparisons and category/stratum-level intervals. Do not average structural and unrelated categories without showing each. Uplift requires a preregistered practical improvement in structural recall or answer correctness, no material degradation in correctness/security negative controls, and disclosed token/latency/failure trade-offs. Replicate across two graph snapshots or repositories and, for a broad claim, two model families.

A no-benefit, negative, or mixed outcome is acceptable evidence and remains published. It may support narrowing or rejecting the hypothesis. Until acceptance criteria are met, claims that Graphify improves precision, relevance, correctness, hallucination resistance, or efficiency are prohibited.
