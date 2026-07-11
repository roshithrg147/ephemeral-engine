# ADR-0004: Persistence Model

- **Status:** Accepted
- **Date:** 2026-07-11
- **Decision Owners:** Architecture, Engineering
- **Related RFCs:** [RFC-0001](../rfcs/RFC-0001-product-boundary.md), [RFC-0002](../rfcs/RFC-0002-architecture-canonicalization.md)
- **Related Governance Documents:** [Manifesto](../MANIFESTO.md), [Product Boundary](../PRODUCT_BOUNDARY.md), [Architecture](../ARCHITECTURE.md)

## Context

The core web session uses ephemeral process-local state, while auxiliary tools write learned facts, audit logs, indexes, queues, configuration, previews, and generated artifacts locally. Describing the whole repository as stateless is incorrect.

## Decision

Core web session context is ephemeral and session-scoped. Persistent learned facts, telemetry, IDE indexes, rehydration queues, preview files, and local tool configuration are separate optional or auxiliary durable state. Graphify and benchmark outputs are generated artifacts. Secrets and deployment configuration are external state. Session burn affects only session-owned ephemeral state unless a separate lifecycle tool explicitly removes registered previews.

The complete repository is not universally stateless. Public deployment must declare which local state is disposable, mounted, externalized, or unsupported.

## Rationale

The decision documents actual storage and deletion behavior without redesigning it or weakening the ephemeral product boundary.

## Alternatives Considered

- Call the service stateless: rejected because process and local files own state.
- Treat all local files as core memory: rejected because their lifetimes and product classifications differ.
- Migrate storage during canonicalization: rejected because it requires a separate persistence RFC.

## Consequences

Operators must govern auxiliary state separately. Replicas cannot share active sessions. Restart loses core session context but may retain mounted auxiliary files.

## Security and Privacy Impact

Audit, fact, index, queue, clipboard, and preview state may contain sensitive data outside burn semantics. No unified encryption or retention policy exists.

## Operational Impact

Container deployments need explicit volume decisions. Backup is operator-managed; no repository-wide backup mechanism exists.

## Validation Evidence

The canonical persistence matrix traces each state category to its owner and medium.

## Known Gaps

No unified retention policy, shared session store, coordinated backup, or authenticated multi-tenant persistence boundary.

## Supersession Rules

Any persistence-model or burn-scope change requires an RFC and a superseding ADR.
