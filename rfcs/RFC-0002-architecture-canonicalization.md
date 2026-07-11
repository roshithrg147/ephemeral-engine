# RFC-0002: Architecture Canonicalization

- **Status:** Accepted
- **Author:** Architecture Governance
- **Created:** 2026-07-11
- **Reviewers:** Founder, Product, Architecture, Engineering
- **Supersedes:** None
- **Superseded by:** None

## Summary

Accept [ARCHITECTURE.md](../ARCHITECTURE.md) and ADR-0001 through ADR-0005 as the canonical technical description of the current SC-EVM repository.

## Motivation

The repository contained accurate mechanisms alongside stale provider language, overstated security and streaming claims, ambiguous persistence language, and optional subsystems that could be mistaken for the core product. Engineers needed one source that explained complete runtime behavior without reading source code.

## Relationship to the Manifesto

- **Relevance:** Canonicalizes context realignment, admission, pending memory, and protected assembly.
- **Isolation:** Defines session ownership, locking, TTL, burn, persistence separation, and security gaps.
- **Control:** Makes component boundaries, provider responsibility, action policy, deployment limits, and change governance explicit.
- **Evidence:** Separates implemented mechanisms, experimental behavior, unsupported claims, and proposed work.

The decision preserves all six principles and four pillars in [MANIFESTO.md](../MANIFESTO.md).

## Relationship to the Product Boundary

The architecture implements, but does not alter, [PRODUCT_BOUNDARY.md](../PRODUCT_BOUNDARY.md). The context-control path remains the MVP. Dashboard, CLI, IDE, clipboard, generic actions, persistent facts, dual-model synthesis, and deployment assets remain optional or supporting. Graphify remains experimental and outside the MVP.

## Current State

The active runtime uses a network API, process-local isolated sessions, context intelligence, a reasoning strategy, and a provider connector backed by NVIDIA NIM. Local embeddings support semantic retrieval. Auxiliary files and generated artifacts mean the complete repository is not stateless. Authentication and authorization are incomplete.

## Proposed Decision

The accepted component model has nine layers: Integration/API; Session and Lifecycle; Context Intelligence; Reasoning Strategy; Provider Transport; Persistence and State; Optional Structural Context; Observability; and Reference Client.

The canonical provider boundary is `ModelConnector`. It is provider-adaptable but incomplete and supports one external transport. ADR-0003 remains Provisional; RFC-0004 is required for material abstraction work.

Core web session state is ephemeral. Auxiliary learned facts, logs, indexes, queues, configuration, previews, and generated artifacts have separate persistence and burn semantics. The repository is not universally stateless.

Graphify is optional, experimental, outside the MVP, failure-isolated from semantic retrieval, and not validated for downstream quality uplift.

Security language is bounded to logical isolation and application-level deletion. No claim of mathematical non-leakage, physical RAM destruction, enterprise authorization, provider-token API streaming, or production readiness is accepted.

Deployment modes are classified as development or evaluation paths. Container packaging exists; public multi-tenant production readiness does not.

The decision creates:

- [ADR-0001: Runtime Architecture](../architecture/ADR-0001-runtime-architecture.md)
- [ADR-0002: Context and Memory Lifecycle](../architecture/ADR-0002-context-and-memory-lifecycle.md)
- [ADR-0003: Provider Boundary](../architecture/ADR-0003-provider-boundary.md)
- [ADR-0004: Persistence Model](../architecture/ADR-0004-persistence-model.md)
- [ADR-0005: Security and Trust Boundaries](../architecture/ADR-0005-security-and-trust-boundaries.md)
- [Architecture Gap Register](../architecture/ARCHITECTURE_GAPS.md)

## Alternatives Considered

- Preserve multiple architecture narratives: rejected because conflicts would remain unresolved.
- Redesign runtime during documentation: rejected because Day 2 records behavior and decisions.
- Promote optional tooling into the core: rejected by RFC-0001.
- Claim full provider independence: rejected because only one transport is implemented.

## Security and Privacy Impact

No runtime control changes. The decision documents client, identity, tenant, retrieved-memory, provider, filesystem, action, Graphify, telemetry, and deletion boundaries and records missing controls as liabilities.

## Operational Impact

No deployment behavior changes. Operators now have explicit state, secrets, concurrency, persistence, and failure expectations for each mode.

## Compatibility and Migration

No API, state, configuration, or deployment migration is required. Future architecture documents and significant changes must conform or supersede this RFC.

## Validation Plan

Validate one status per subsystem, one persistence classification per state, provider limitations, Graphify fallback, SSE wording, ADR status vocabulary, internal links, generated artifact integrity, and a documentation-only scoped diff.

## Commercial-Claim Impact

The RFC prohibits unsupported claims about total token constancy, provider-native API streaming, Graphify/dual-model superiority, statelessness, physical erasure, zero leakage, authorization, and production readiness. It creates no new commercial claim.

## Risks

- Documentation can drift from source; future behavior changes must update the architecture and relevant ADR.
- The breadth of the inventory can obscure the MVP; mandatory and optional sections preserve the distinction.
- Accepted canonicalization may be mistaken for accepting unresolved gaps; the gap register and Provisional provider ADR prevent that inference.

## Rollback Plan

Documentation can be reverted without runtime migration. A replacement architecture decision must supersede this RFC rather than silently restoring conflicting narratives.

## Decision

Accepted. The repository has a coherent canonical architecture with no unresolved contradiction that prevents documenting current behavior. Implementation liabilities remain explicit and require later RFCs where marked.

## Evidence

- Canonical governance documents.
- Backend, client, tool, configuration, deployment, test, and benchmark source inventory.
- Existing Graphify and benchmark artifacts, preserved unchanged.
- Deterministic link, classification, status, and scoped-diff validation performed during Day 2.
