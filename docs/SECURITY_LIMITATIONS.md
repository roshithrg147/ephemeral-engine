# Security Limitations & Notice

SC-EVM Developer Preview operates under a strict **Trusted-Environment Boundary**.

## Critical Security Caveats
- **Development Authentication Disabled:** Default development mode remains unauthenticated for localhost compatibility. Production mode requires OIDC bearer JWT validation and fails startup when identity configuration is unsafe or incomplete.
- **Single-Instance Ownership:** Authenticated sessions bind to one tenant and principal, but ownership remains process-local. Multi-replica production is unsupported until shared state is defined.
- **Logical Isolation Only:** Isolation between session spaces is managed logically via database collections, not via network sandbox layers.
- **Public Pilot Still Gated:** Authentication removes one blocker, but rate limiting, external threat review, operational readiness, and shared-state decisions remain required before public exposure.
- **Logical State Deletion:** The session burn endpoint (`/api/session/burn`) executes logical application-level deletion (purging Chroma database collections and registry records). It does not guarantee physical memory erasure.
