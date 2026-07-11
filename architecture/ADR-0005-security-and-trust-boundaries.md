# ADR-0005: Security and Trust Boundaries

- **Status:** Accepted
- **Date:** 2026-07-11
- **Decision Owners:** Architecture, Security, Engineering
- **Related RFCs:** [RFC-0001](../rfcs/RFC-0001-product-boundary.md), [RFC-0002](../rfcs/RFC-0002-architecture-canonicalization.md)
- **Related Governance Documents:** [Manifesto](../MANIFESTO.md), [Product Boundary](../PRODUCT_BOUNDARY.md), [Architecture](../ARCHITECTURE.md)

## Context

The implementation has useful logical isolation and context controls but lacks application-user authentication and authorization. Earlier language risked overstating deletion and leakage assurance.

## Decision

The canonical trust boundaries are external client, authentication, session identity, tenant isolation, retrieved memory, provider, local filesystem, action execution, Graphify artifacts, telemetry, and deletion. Client input, retrieved context, provider responses, workspace/history files, proposed actions, and inferred graph relationships are untrusted. Controls are described as logical mechanisms, not mathematical or physical guarantees.

Session IDs scope state but do not authorize access. Retrieved content is confidence-gated and separately enclosed. Burn removes application access to session-owned ephemeral state but does not guarantee physical RAM destruction or erase auxiliary durable state. Provider requests cross an external data boundary. Action execution remains optional, human-mediated in the CLI, and outside the core product.

## Rationale

Bounded claims preserve trust and make missing controls visible without discarding existing isolation, validation, and lifecycle mechanisms.

## Alternatives Considered

- Describe session IDs as tenant authentication: rejected because possession is sufficient.
- Claim zero leakage or physical erasure: rejected because tests and runtime cannot establish those guarantees.
- Add authentication during documentation work: rejected because it requires product and security design.

## Consequences

The current service is suitable for trusted development/evaluation environments, not unauthenticated public multi-tenant production. Public pilot requirements are tracked as gaps.

## Security and Privacy Impact

This decision narrows claims and identifies exposure points; it does not add a security control. Audit logs and diagnostic SSE events may expose sensitive context.

## Operational Impact

Operators must restrict network access, protect credentials/files, configure CORS, and govern retained artifacts.

## Validation Evidence

Endpoint contracts, session-isolation tests, lifecycle tests, prompt enclosures, provider transport, and filesystem tools provide mechanism evidence.

## Known Gaps

Authentication/authorization, redaction, retention policy, public network hardening, action sandboxing, and independent security validation.

## Supersession Rules

Security-boundary changes require an RFC, threat review, evidence, and a superseding ADR.
