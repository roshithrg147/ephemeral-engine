# Security Limitations & Notice

SC-EVM Developer Preview operates under a strict **Trusted-Environment Boundary**.

## Critical Security Caveats
- **No Authentication Middleware:** All API endpoints are unauthenticated. Unauthenticated requests to `/api/session/history` will succeed.
- **Logical Isolation Only:** Isolation between session spaces is managed logically via database collections, not via network sandbox layers.
- **Localhost Default:** For security, the server must only be bound to localhost (`127.0.0.1`). Public internet-facing deployments are prohibited.
- **Logical State Deletion:** The session burn endpoint (`/api/session/burn`) executes logical application-level deletion (purging Chroma database collections and registry records). It does not guarantee physical memory erasure.
