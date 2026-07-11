# SC-EVM Architecture Decisions

This directory records accepted and provisional technical decisions subordinate to the [Product Manifesto](../MANIFESTO.md), [Product Boundary](../PRODUCT_BOUNDARY.md), canonical [Architecture](../ARCHITECTURE.md), and [RFC process](../rfcs/README.md).

ADRs describe how an accepted product boundary is implemented. Significant product or architecture changes still require an RFC. Accepted ADRs may be clarified but are superseded, not silently rewritten, when their decision changes.

| ADR | Status | Scope |
|---|---|---|
| [ADR-0001](ADR-0001-runtime-architecture.md) | Accepted | Canonical active, optional, experimental, and deprecated runtime |
| [ADR-0002](ADR-0002-context-and-memory-lifecycle.md) | Accepted | Context, memory, indexing, TTL, and burn lifecycle |
| [ADR-0003](ADR-0003-provider-boundary.md) | Provisional | Provider-adaptable boundary and current transport limitations |
| [ADR-0004](ADR-0004-persistence-model.md) | Accepted | Ephemeral core state and auxiliary durable state |
| [ADR-0005](ADR-0005-security-and-trust-boundaries.md) | Accepted | Current logical controls and bounded security claims |

Allowed statuses are **Accepted**, **Provisional**, **Deprecated**, and **Superseded**.
