# Phase 1 Model Reliability

**Recorded:** 2026-07-23  
**Model 2:** `openai/gpt-oss-120b`  
**Transport:** NVIDIA NIM chat completions

## Current model boundary

- Model 1: `nvidia/nemotron-3-nano-30b-a3b`
- Model 2: `openai/gpt-oss-120b`
- Credential: `NVIDIA_API_KEY`

No alternate model aliases or model-specific credential fallbacks are supported.

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

## Validation

A strict-JSON probe and a full SC-EVM turn returned HTTP 200. The full turn completed
Model 2 candidate and synthesis stages with exact usage records, emitted no degradation
event, and burned the test session successfully. Reliability controls remain active for
future provider failures.
