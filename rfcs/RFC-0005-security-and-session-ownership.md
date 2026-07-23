# RFC-0005: Security and Session Ownership

- **Status:** Draft
- **Author:** Architecture and Security
- **Created:** 2026-07-23
- **Reviewers:** Product, Architecture, Security, Operations
- **Supersedes:** None
- **Superseded by:** None

## Summary

Require authenticated principals, tenant-scoped session ownership, explicit authorization, and
fail-closed production configuration before SC-EVM accepts untrusted network traffic. Target first
release is a secured single-instance pilot. Multi-replica production remains blocked until a
separate persistence decision is accepted.

## Motivation

Current API trusts caller-supplied session IDs. Any caller can list sessions, read history, burn
another session, or enable diagnostic context disclosure. Localhost binding limits exposure but is
not an application security boundary. These gaps block public pilot and production use.

## Relationship to the Manifesto

- **Relevance:** Authentication must not alter retrieval or model-answer behavior.
- **Isolation:** Principal and tenant ownership become mandatory authorization boundaries.
- **Control:** Operators gain explicit authentication mode, role, origin, quota, and diagnostic
  policies.
- **Evidence:** Negative authorization, cross-tenant isolation, audit, and abuse-control tests make
  enforcement reproducible.

Proposal strengthens Isolation and Control. Added identity and audit metadata must remain bounded
so it does not weaken ephemeral-memory commitments.

## Relationship to the Product Boundary

This proposal changes production authentication from unsupported to planned. It does not promote
SC-EVM to enterprise-grade, multi-region, multi-replica, or compliance-certified status. Session
IDs remain identifiers, never credentials. Logical burn remains distinct from physical erasure.
Durable conversation storage remains outside this decision.

## Current State

- API endpoints have no authentication middleware.
- Client supplies session ID and query can create that session implicitly.
- Session listing and history retrieval have no principal filter.
- Any caller can request `diagnostic_mode=true` and receive retrieved context.
- Default CORS origins are local, but methods and headers are broad.
- Session registry and Chroma collections are process-local.
- Telemetry redacts configured content fields but lacks a complete identity-aware audit schema.

## Proposed Decision

### Release boundary

First production-oriented target is one SC-EVM API instance behind TLS ingress. Horizontal replicas
remain unsupported until shared-state and persistence RFCs define consistency and lifecycle rules.

### Authentication

- Production mode accepts OAuth 2.0/OIDC bearer JWTs validated in application middleware.
- Validator checks signature, issuer, audience, expiry, not-before time, and required claims.
- Required identity claims are immutable `sub` and `tenant_id` values from trusted issuer.
- Signing keys come from configured JWKS endpoint and use bounded caching with safe refresh.
- Missing, invalid, expired, or unverifiable credentials return `401` without session lookup.
- Development may explicitly set authentication mode to `disabled` only while bound to loopback.
- Production startup fails when authentication, issuer, audience, CORS, or secret settings are
  absent or unsafe.

### Session ownership

- Server associates each session with authenticated `tenant_id` and `sub` at creation.
- Client session ID selects only within caller ownership scope.
- Existing session with different owner returns `404` to avoid enumeration.
- Query-time implicit creation may remain, but ownership is assigned atomically before state use.
- Session list returns only sessions owned by caller unless caller has operator role.
- History, message, query, and burn operations require matching ownership.

### Authorization

- Normal user scope permits create, query, history, message, and burn for owned sessions.
- `diagnostic_mode` requires `scevm:diagnostic` scope and remains disabled by default.
- Cross-tenant access is denied regardless of operator role.
- Tenant-scoped operator role may list and burn sessions within its tenant for incident response.
- No provider credential, retrieved context, or internal exception text appears in authorization
  errors.

### Network and abuse controls

- Production CORS uses explicit HTTPS origins; wildcard origins are forbidden.
- Bearer-token deployment does not enable credentialed cookie CORS.
- Configurable request and token-rate limits apply per tenant and principal.
- Global concurrency and provider-budget caps protect upstream capacity.
- Health liveness remains public and contains no dependency details. Readiness may be restricted by
  deployment policy.

### Audit

- Authentication and authorization decisions emit structured records containing request ID,
  timestamp, hashed principal identifier, tenant identifier, action, resource hash, outcome, and
  reason code.
- Raw bearer tokens, prompts, responses, retrieved context, and provider secrets are prohibited in
  security audit records.
- Retention, access, deletion, and storage location require operator configuration and documentation.

## Alternatives Considered

- **Static shared API key:** simpler but cannot express session ownership or safe tenant isolation.
- **Authentication only at reverse proxy:** rejected as sole control because application still must
  enforce resource ownership.
- **Mutual TLS:** strong service identity but poor fit for end-user principal and tenant claims.
- **Keep localhost-only developer preview:** safe current option but does not meet production goal.
- **Build multi-replica persistence now:** rejected for first pilot due larger consistency, migration,
  backup, and burn-semantics scope.

## Security and Privacy Impact

Proposal adds identity data and authorization logs. This improves isolation but creates new retained
metadata requiring minimization and lifecycle controls. JWT validation must resist algorithm
confusion, forged issuers, stale keys, clock skew abuse, and claim substitution. Authorization must
occur before session existence, history, diagnostics, or model calls become observable.

## Operational Impact

Deployment needs OIDC issuer, audience, JWKS reachability, HTTPS ingress, explicit origins, rate
limits, audit destination, and clock synchronization. JWKS outage behavior must use last valid key
set only within bounded cache lifetime, then fail closed. On-call runbooks must cover identity
provider outage, key rotation, rate-limit saturation, and forced tenant session burn.

## Compatibility and Migration

Local development keeps explicit loopback-only disabled mode. Production clients must send
`Authorization: Bearer <token>`. Existing endpoint paths and SSE event shapes remain unchanged.
Existing anonymous in-memory sessions are not migrated; deployment drains or burns them before
enabling production mode. Future persistent ownership requires separate RFC and migration design.

## Validation Plan

- Unit tests for JWT signature, issuer, audience, time claims, malformed tokens, and key rotation.
- Route tests for missing credentials, insufficient scope, session ownership, and operator policy.
- Cross-principal and cross-tenant history, query, message, list, diagnostics, and burn tests.
- Verify denied requests perform no provider call and reveal no resource existence.
- Negative CORS tests for unknown and wildcard origins.
- Rate-limit and concurrency tests with deterministic retry metadata.
- Audit-schema tests proving token, prompt, response, retrieved-context, and secret exclusion.
- Production-startup tests proving unsafe configuration fails closed.
- External threat review before public pilot.

Acceptance requires all automated gates passing, zero critical/high findings in scoped security
review, documented residual risks, and reviewer sign-off.

## Commercial-Claim Impact

Implementation may support a bounded claim that authenticated session ownership is enforced in the
secured single-instance pilot. It does not support leakage-proof, enterprise-grade, compliance,
multi-replica, physical-erasure, or zero-trust claims.

## Risks

- Incorrect claim mapping could cross tenants; centralize principal parsing and ownership checks.
- Identity provider outage could block all traffic; bounded key cache and explicit readiness expose
  failure without failing open.
- Operator privilege could become broad; keep tenant scope and audit every privileged action.
- Identity metadata could outlive sessions; define minimum retention and deletion policy.
- Development bypass could reach production; enforce loopback binding and production startup checks.

## Rollback Plan

Public exposure must stop before authentication is disabled. Rollback returns deployment to
loopback-only developer-preview mode, drains active requests, burns pilot sessions, and preserves
security audit records under configured retention. Anonymous public operation is never a rollback
option.

## Decision

Undecided while Draft. Required review: Product, Architecture, Security, and Operations.

## Evidence

- [Architecture gap register](../architecture/ARCHITECTURE_GAPS.md)
- [Security limitations](../docs/SECURITY_LIMITATIONS.md)
- [Security and trust-boundary ADR](../architecture/ADR-0005-security-and-trust-boundaries.md)
- [Product Manifesto](../MANIFESTO.md)
- [Product Boundary](../PRODUCT_BOUNDARY.md)
- Current API, session registry, telemetry, and security evidence tests
