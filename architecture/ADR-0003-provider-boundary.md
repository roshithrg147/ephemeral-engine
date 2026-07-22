# ADR-0003: Provider Boundary

- **Status:** Provisional
- **Date:** 2026-07-11
- **Decision Owners:** Architecture, Engineering
- **Related RFCs:** [RFC-0002](../rfcs/RFC-0002-architecture-canonicalization.md); RFC-0004 is reserved for a complete provider-abstraction proposal
- **Related Governance Documents:** [Manifesto](../MANIFESTO.md), [Product Boundary](../PRODUCT_BOUNDARY.md), [Architecture](../ARCHITECTURE.md)

## Context

The Product Manifesto requires choice beneath SC-EVM, while the current repository implements one external transport and embeds logical model roles in strategies.

## Decision

`ModelConnector` is the canonical provider boundary. Context and strategy callers supply a logical model key, messages or text, system control, token limit, and synchronous or asynchronous intent. Transport adapters own credentials, endpoints, payload mapping, retry, timeout, and response extraction. They must never own session, retention, or burn state.

The current implementation supports NVIDIA NIM only. Physical model identifiers are configurable, but their logical roles in reformulation, candidate reasoning, and synthesis are code-defined. Local ONNX MiniLM supplies embeddings. Vertex AI, Anthropic, and other direct adapters are unsupported.

## Rationale

This is the smallest boundary already present in code. Claiming a universal provider layer would exceed evidence; bypassing the connector would increase coupling.

## Alternatives Considered

- Direct transport calls from strategies: rejected because provider concerns would leak inward.
- A universal capability framework now: rejected as unrequested and unimplemented.
- Claim current provider independence: rejected because only one transport exists.

## Consequences

SC-EVM is provider-adaptable but not currently provider-independent. A future adapter contract must normalize errors, usage, capabilities, and streaming behavior.

## Security and Privacy Impact

Prompts and retrieved context cross the external provider boundary. Credentials remain environment-owned and must not enter logs or artifacts.

## Operational Impact

Retryable network/status failures use bounded exponential backoff. Provider-native streaming support exists in transport but is not connected to the API response path.

## Validation Evidence

`src/services/model_connector.py`, `src/clients.py`, `src/agent.py`, `src/sc_evm.py`, and strategy adapters establish current behavior.

## Known Gaps

No second provider adapter, no normalized error/usage contract, hardwired logical roles, and stale provider wording in project metadata.

## Supersession Rules

RFC-0004 must resolve the open contract before this ADR can become Accepted. New adapters must not bypass `ModelConnector`.
