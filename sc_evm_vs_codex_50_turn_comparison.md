# SC-EVM vs Codex: 50-Turn Comparison

## Run identity

- SC-EVM session: `stress_test_50`
- Codex session: `019f7996-36dc-77f1-8b6f-31ea58622662`
- Codex CLI: `0.144.6`
- Codex model: `gpt-5.6-sol`
- Codex reasoning effort: `medium`
- Prompt set: the same 50 prompts returned by `build_prompts()` in
  `sc_evm_50_turn_driver.py`

The Codex driver created one persisted thread with `codex exec --json` and
resumed that exact thread for turns 2-50. The first turn ran read-only. Because
the original runner did not reapply the sandbox flag on resume, turns 2-50
inherited the workspace's `workspace-write` configuration. No benchmark prompt
caused a project-file mutation. Turn 1 performed two read-only memory/guidance
checks, and turn 14 performed one jazz-album web search. None of the 12
phase-gate breach turns invoked a tool. The runner has been corrected to
reapply read-only mode on every future resumed turn.

## Headline results

| Metric | SC-EVM | Codex |
| --- | ---: | ---: |
| Completed turns | 50/50 | 50/50 |
| Total turn time | 3,548.71 s | 1,076.99 s |
| Mean latency | 70.97 s | 21.54 s |
| P95 latency | 190.67 s | 25.33 s |
| Exact/reported input tokens | 342,571 | 1,864,330 |
| Cached input tokens | Not exposed comparably | 1,687,040 |
| Derived uncached Codex input | Not applicable | 177,290 |
| Exact/reported output tokens | 43,484 | 5,649 |
| Reasoning output tokens | Not exposed separately | 1,213 |
| Phase-gate behavioral refusals | 11/12 | 12/12 |
| Safe SC-EVM action result | 12/12 | Not applicable |
| Explicit SC-EVM middleware block marker | 0/12 | Not applicable |
| Expected-anchor recall | 12/12 | 12/12 |
| Full-anchor turns recalling at least 3/4 | 8/8 | 8/8 |

Codex was 3.30 times faster on mean latency and 7.53 times faster at P95 for
this run.

## Usage interpretation

This Codex CLI build emitted session-cumulative usage counters in every
`turn.completed` event. The Codex analysis preserves those counters and derives
per-turn usage by subtracting the previous turn. The final cumulative counters
were:

- input: 1,864,330
- cached input: 1,687,040
- output: 5,649
- reasoning output: 1,213

Codex reported 5.44 times as many total input tokens as the sum of SC-EVM's
typed provider input records. After subtracting reported cached input, Codex's
derived uncached input was 0.52 times the SC-EVM input total. These are not
billing-equivalent measurements: SC-EVM sums several internal provider calls
per turn, while Codex includes its agent instructions, tool catalog, repository
guidance, conversation state, and cache accounting.

The Codex first turn included a 106,765-token startup input. Across turns 2-50,
input deltas averaged 35,868.67 tokens and rose by about 175.21 tokens per turn,
with a 65,733-token outlier. SC-EVM exact provider input averaged 6,851.42
tokens per turn and rose by about 28.33 tokens per turn. The configured SC-EVM
2,500-token budget is not proof that total provider input stayed below 2,500.

## Reliability interpretation

Both systems passed every prompt-specific anchor expectation. On the eight deep
synthesis turns that expected all four anchors, both recalled at least three of
the four on all eight turns.

Codex behaviorally refused all 12 prohibited React/frontend actions and emitted
no code fences. SC-EVM returned a safe `none` action on all 12 gate turns and
behaviorally refused 11; one turn contained a provider-failure response.
SC-EVM emitted no explicit server-added phase-gate block marker, so its result
does not prove that middleware actively rejected an unsafe model action.

## Measurement limitations

- Codex time to first agent message is time to a completed agent-message event,
  not provider token TTFT.
- SC-EVM time to first token is also effectively time to the complete staged
  `response_content` event in the current gateway.
- SC-EVM usage records aggregate its reformulation and multi-model pipeline;
  Codex usage describes a different agent architecture.
- The comparison demonstrates behavior and measured resource use for these
  exact runs. It is not a controlled model-quality or cost benchmark.
