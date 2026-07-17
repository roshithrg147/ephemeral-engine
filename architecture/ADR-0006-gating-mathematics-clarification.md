# ADR-0006: Gating Mathematics Clarification

- **Status:** Accepted
- **Date:** 2026-07-13
- **Decision Owners:** Architecture, Engineering, Benchmark Integrity
- **Related ADRs:** [ADR-0002](ADR-0002-context-and-memory-lifecycle.md)
- **Related Governance Documents:** [Manifesto](../MANIFESTO.md), [Product Boundary](../PRODUCT_BOUNDARY.md), [ARCHITECTURE.md](../ARCHITECTURE.md)

## Context

An independent repository audit identified mathematical inconsistency and contradictions in the SC-EVM retrieval and gating pipeline. Specifically, the codebase mixed:
1. Cosine similarity checks in the dual-anchor gating math (`max_similarity >= base_threshold`);
2. Calibrated threshold values derived as cosine distances in `_calibrate_threshold()`;
3. Chroma DB query distances that default to L2 distance space rather than cosine distance space.

These contradictions compromised the integrity of the gating pipeline and violated the requirement for rigorous mathematical consistency.

## Decision

We designate **cosine distance** as the single canonical metric for all calibration, retrieval, admission, logging, traces, documentation, and tests in SC-EVM.

To enforce this, we:
1. Configure all Chroma collections to explicitly use the `cosine` distance space (which returns cosine distance `1 - cosine_similarity`).
2. Calibrate the threshold and absolute limits as explicit `cosine_distance` metrics.
3. Rename all retrieval, admission, and gating parameters to avoid ambiguous terms like `score` or `threshold`. Specifically:
   - `maximum_admitted_distance` is the calibrated dynamic/fallback boundary.
   - `absolute_floor` is the maximum distance for unconditional admission (default `0.38`).
   - `absolute_ceiling` is the maximum allowed distance for any candidate (default `0.48`).
   - `neighboring_delta_limit` (default `0.12`) and `top_anchor_delta_limit` (default `0.18`) remain distance deltas.
4. Rewrite the dual-anchor gating math to use `cosine_distance` directly, checking if the minimum distance to either anchor is below the maximum allowed threshold: `min(dist_a, dist_b) <= maximum_admitted_anchor_distance`.

## Rationale

Using a single canonical metric (cosine distance) across all stages of the pipeline ensures mathematical correctness, alignment with Chroma DB's cosine space, and clear, inspection-friendly semantics.

## Alternatives Considered

- **Cosine Similarity:** Rejected because Chroma DB's native `cosine` space returns cosine distance, which would require multiple `1 - similarity` conversions. Using cosine distance directly is cleaner and less error-prone.
- **L2 Distance:** Rejected because cosine distance is scale-invariant and more appropriate for text embedding semantics.

## Consequences

- The admission pipeline is mathematically consistent and matches Chroma DB retrieval semantics.
- Threshold values like 0.38 and 0.48 represent cosine distances (where 0.0 is identical and 1.0 is orthogonal).
- All traces and reports will consistently log cosine distances.

## Security and Privacy Impact

None.

## Operational Impact

None.

## Validation Evidence

Validated via `test_sc_evm.py` and consolidated deterministic unit tests.
