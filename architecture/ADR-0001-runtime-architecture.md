# ADR-0001: Runtime Architecture

- **Status:** Accepted
- **Date:** 2026-07-11
- **Decision Owners:** Architecture, Engineering
- **Related RFCs:** [RFC-0001](../rfcs/RFC-0001-product-boundary.md), [RFC-0002](../rfcs/RFC-0002-architecture-canonicalization.md)
- **Related Governance Documents:** [Manifesto](../MANIFESTO.md), [Product Boundary](../PRODUCT_BOUNDARY.md), [Architecture](../ARCHITECTURE.md)

## Context

The repository contains the SC-EVM context-control runtime plus multiple access surfaces, strategies, tools, and experiments. File layout alone does not communicate which paths are mandatory or allowed to fail independently.

## Decision

The canonical runtime uses nine layers: Integration/API; Session and Lifecycle; Context Intelligence; Reasoning Strategy; Provider Transport; Persistence and State; Optional Structural Context; Observability; and Reference Client. The mandatory path comprises the first six layers plus error handling. One reasoning strategy and the current transport are required by implementation. Graphify and external CLI comparison are experimental. User interfaces, IDE, clipboard, action, benchmark, telemetry, and container workflows are optional. Image generation and clipboard relay are stubbed; deleted legacy entry paths are deprecated.

Dependencies point inward from clients through the public integration boundary. Provider transport must not own session state. Experimental paths must degrade without becoming required by the MVP.

## Rationale

This model reflects actual ownership and failure boundaries while aligning every subsystem to Relevance, Isolation, Control, or Evidence. It avoids organizing the architecture around replaceable clients or one model strategy.

## Alternatives Considered

- Organize by repository directories: rejected because directories mix core, optional, and experimental behavior.
- Define the dual-model path as the product: rejected by the Product Boundary.
- Introduce new services for symmetry: rejected because current behavior does not require them.

## Consequences

Architecture reviews have one component model. Optional tools remain supported without gaining core status. Changes that cross layer ownership require explicit review.

## Security and Privacy Impact

The model makes external clients, providers, files, retrieved content, and actions explicit trust boundaries. It does not add controls.

## Operational Impact

Current single-process session ownership remains canonical. Public multi-replica deployment needs a future state decision.

## Validation Evidence

Source dependency inspection, endpoint tests, memory-isolation tests, lifecycle tests, and strategy adapters support the component map. See the inventory and invariants in `ARCHITECTURE.md`.

## Known Gaps

Authentication, shared-state deployment, quality scoring, provider-neutral errors, and production observability remain unresolved.

## Supersession Rules

A change to mandatory layers, state ownership, or experimental isolation requires an RFC and a superseding ADR.
