# Phase 1 Model Reliability

**Recorded:** 2026-07-23  
**Model 2:** `openai/gpt-oss-120b`  
**Transport:** NVIDIA NIM chat completions

## Reproduction

A fresh gateway loaded the current checkout and updated `.env`. Three strict-core
probes were run:

1. Model-specific NVIDIA key with the prior Kimi payload.
2. General NVIDIA key with the prior Kimi payload.
3. Model-specific NVIDIA key after removing the non-reference `thinking` field.

Every probe produced the same provider result for both the Model 2 candidate and
Model 2 synthesis stages:

```text
HTTP 404: configured provider function was not available to the account
```

Model 1 reformulation and candidate calls returned HTTP 200 in the same requests.
This isolates the remaining live blocker to NVIDIA's Kimi function/account routing,
not SC-EVM session transport, API-key selection order, or the removed payload field.

## Implemented reliability controls

- Reject visible provider content when `finish_reason="length"`.
- Preserve provider `finish_reason` in response metadata.
- Replace raw provider-error placeholders with non-sensitive unavailable markers.
- Mark candidate and synthesis failures with stable degradation reason codes.
- Prefix fallback text with a visible degraded-state notice.
- Emit a typed `degradation` SSE event.
- Emit stage-labeled `exact`, `estimate`, or `unavailable` usage records.
- Require exact, completed `model_2_synthesis` usage for `agy-scevm --strict-core`.
- Use `openai/gpt-oss-120b`, which completed both candidate and synthesis stages with exact usage in the live SC-EVM probe.

## Resolution

Kimi K2.6 remains unavailable to the configured NVIDIA account. Model 2 was therefore
changed to `openai/gpt-oss-120b`. A direct strict-JSON probe and a full SC-EVM turn both
returned HTTP 200; the full turn completed Model 2 candidate and synthesis stages with
exact usage records, emitted no degradation event, and burned the test session
successfully. The reliability controls remain active for future provider failures.
