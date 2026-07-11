# RFC-0001: Product Boundary

- **Status:** Accepted
- **Author:** Founder, Product, Architecture
- **Created:** 2026-07-11
- **Reviewers:** Founder, Product, Architecture
- **Supersedes:** None
- **Superseded by:** None
- **Canonical source:** [PRODUCT_BOUNDARY.md](../PRODUCT_BOUNDARY.md)

## Alignment

This RFC enforces all manifesto principles, especially Relevance Over Accumulation, Boundaries Create Trust, and Simplicity at the Boundary. It adopts the complete classifications in the Product Boundary as the controlling definition of Core Product, Core Architecture, Supporting Infrastructure, Experimental, and Deprecated subsystems.

## Summary

Accept the Day 1 Product Boundary as SC-EVM's authoritative scope and classification record without reproducing it inside this RFC.

## Context

SC-EVM contains a focused context-control product surrounded by reasoning strategies, user interfaces, developer tools, operational services, experiments, and deployment assets. Without a binding product boundary, the repository's breadth can cause implementation visibility to be mistaken for commercial importance and can allow peripheral capabilities to redefine the company.

## Decision

The canonical product definition is:

> SC-EVM is a session-isolated context-control layer that keeps multi-turn AI applications grounded in relevant memory while bounding the conversation history sent to their reasoning models.

The [Product Manifesto](../MANIFESTO.md) is the highest-level source of truth. The [Product Boundary](../PRODUCT_BOUNDARY.md) is the authoritative classification of the existing product. Every material proposal must identify how it strengthens Relevance, Isolation, Control, or Evidence and must cite the affected boundary classification.

SC-EVM is context-control middleware rather than a complete agent, user-interface product, model provider, automation suite, or general-purpose vector database.

The approved MVP is limited to the service contract, isolated ephemeral session memory, bounded active history, intent realignment, confidence-gated retrieval, pending-memory continuity, protected context enclosure, session lifecycle controls, one supported reasoning strategy, configuration, and structured error boundaries. The canonical Product Boundary remains authoritative if this summary and the detailed matrix ever diverge.

Graphify is recorded as **a strategically differentiating structural-context capability whose downstream quality uplift remains unvalidated**. It is experimental, outside the MVP, preserved in the repository, and ineligible for measured-quality claims without controlled evidence.

Dual-model synthesis is an optional experimental strategy rather than the product identity or an MVP requirement. Its presence does not justify a superiority claim.

Commercially meaningful claims—including relevance, retention, hallucination resistance, token behavior, isolation, deletion, and comparative strategy quality—require controlled evidence designed for the claim.

No subsystem becomes Core Product because it is prominent, technically novel, or already implemented. A change to the canonical definition, official product boundary, MVP, or controlled architectural classification requires a superseding RFC and formal product and architecture approval.

## Alternatives considered

- **Allow the implementation to define the product implicitly.** Rejected because repository structure reflects engineering history, not purchasing intent.
- **Maintain separate product narratives for different audiences.** Rejected because divergent definitions create conflicting engineering and commercial decisions.
- **Treat the boundary as advisory.** Rejected because advisory boundaries cannot constrain roadmap expansion.

## Consequences and trade-offs

- Product, engineering, and commercial documents share one definition.
- Peripheral capabilities may continue to exist without receiving product status.
- Some technically attractive work will be deferred or declined when it does not strengthen the product pillars.
- Changing the boundary becomes deliberate and slower, which is accepted in exchange for coherence.

## Security, privacy, operations, and evidence

Isolation and deletion claims remain product commitments and require corresponding verification. Commercial language must distinguish mechanisms from measured outcomes. Operational surfaces must not weaken the lifecycle or state boundaries defined by the core product.

## Adoption and rollback

This RFC is effective immediately. Existing and future documents must use the canonical definition verbatim. Rollback requires a superseding accepted RFC; deletion or silent reinterpretation is not permitted.

Future scope changes must identify the exact classification being superseded, provide supporting evidence, and be accepted through a later RFC that explicitly supersedes this record where applicable.

## Unresolved questions

None. Specific boundary changes belong in future RFCs.
