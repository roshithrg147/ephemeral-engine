# ADR-0002: Context and Memory Lifecycle

- **Status:** Accepted
- **Date:** 2026-07-11
- **Decision Owners:** Architecture, Engineering
- **Related RFCs:** [RFC-0001](../rfcs/RFC-0001-product-boundary.md), [RFC-0002](../rfcs/RFC-0002-architecture-canonicalization.md)
- **Related Governance Documents:** [Manifesto](../MANIFESTO.md), [Product Boundary](../PRODUCT_BOUNDARY.md), [Architecture](../ARCHITECTURE.md)

## Context

SC-EVM must preserve useful continuity without forwarding unbounded direct history or allowing asynchronous indexing and burn to produce inconsistent session behavior.

## Decision

Each web session owns an isolated ephemeral collection, bounded recent history, pending commit buffer, metadata, manifest, and lock. Intent realignment separates retrieval text from grounded reasoning text. Semantic candidates are session-scoped and confidence-gated. Pending memory is included until indexing completes. Retrieved material is enclosed as untrusted reference data. Completed turns are indexed in tracked background tasks. TTL and capacity eviction use the same burn path as explicit deletion. Burn removes the record before collection deletion; background indexing must stop on a missing collection and must not recreate the session.

Durable learned facts are a separate optional memory plane and are not deleted by web session burn.

## Rationale

Bounded history controls direct context growth, gating protects relevance, pending memory closes an asynchronous consistency gap, and shared burn semantics preserve isolation and lifecycle control.

## Alternatives Considered

- Append all history: rejected because it violates the product purpose.
- Block responses until indexing completes: rejected because pending memory already preserves immediate continuity.
- Merge durable facts into session state: rejected because lifetimes and deletion semantics differ.

## Consequences

Turns can be delivered even when indexing later fails. Later retrieval may miss such a turn. Burn is logical application-level deletion, not physical memory erasure.

## Security and Privacy Impact

Session filters and locks reduce cross-session access risk. Retrieved content remains untrusted. Durable auxiliary state requires separate retention controls.

## Operational Impact

Session state is process-local and disappears on restart. TTL and capacity settings bound in-process resources but do not coordinate replicas.

## Validation Evidence

`test_memory_isolation.py`, `test_secure_lifecycle.py`, `test_session_rehydration.py`, stress tests, and session-runtime source paths support the decision.

## Known Gaps

No authenticated tenant boundary, no multi-process session coordination, limited burn/index race testing, and no adversarial retrieved-context evaluation.

## Supersession Rules

Changing history bounds, admission policy, persistence lifetime, or burn semantics requires an RFC and a superseding ADR.
