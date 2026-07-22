# MATH500-Style Smoke Benchmark Run Notes

Run date: 2026-07-20  
Session: `math500_evaluation_session_01`

## Outcome

The two benchmark cases were transported successfully through the SC-EVM HTTP/SSE
pipeline, but neither run produced an evaluable mathematical answer. Accuracy is
therefore **not available**; the result must not be reported as 0%.

Expected reference answers:

- Number Theory: `1007`
- Probability: `9/64`

## Attempt 1: Project-configured model

The project resolved both model roles to `qwen/qwen3.5-122b-a10b`. NVIDIA returned
HTTP 410 for every provider call because that model reached end-of-life at
`2026-07-20T00:00:00Z`.

- Number Theory latency: 0.412 seconds; status: `PROVIDER_FAILED`
- Probability latency: 0.194 seconds; status: `PROVIDER_FAILED`
- Burn verification: passed

## Attempt 2: Temporary active-model override

The gateway was restarted without changing repository configuration, temporarily
setting both physical model routes to NVIDIA's documented active
`qwen/qwen3.5-397b-a17b` endpoint.

- Number Theory latency: 363.835 seconds; status: `PROVIDER_FAILED`
- Probability latency: 363.844 seconds; status: `PROVIDER_FAILED`
- Failure mode: provider read timeouts and exhausted retries
- Burn verification: passed

The machine-readable JSON and response transcript correspond to this second,
latest attempt.

## Harness corrections

The supplied sample required the following corrections before execution:

- awaited the asynchronous `httpx` request;
- initialized the session explicitly;
- removed unsupported `phase_id`;
- parsed the `text/event-stream` response instead of calling `response.json()`;
- captured `response_content`, `usage_report`, `token_usage`, intent, and all
  diagnostic events;
- separated transport completion from evaluable completion;
- treated provider failure placeholders as non-evaluable;
- extracted nested LaTeX `\boxed{\frac{...}{...}}` answers safely;
- checkpointed JSON and text artifacts;
- burned the session in `finally` and verified HTTP 404 plus list absence.

## Validation

- Python compilation: passed
- Ruff lint: passed
- Ruff formatting: passed
- Pytest: 5 passed
- Mypy: not installed in the project virtual environment
