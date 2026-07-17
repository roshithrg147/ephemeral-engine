# Required Baselines

All six baselines use identical scenario turns, reasoning model where technically possible, model parameters, output limits, retry policy, timeouts, and evaluators. No strategy receives hidden ground truth, future turns, extra tools, or favorable model access. Token budgets and any unavoidable differences are declared before execution.

| Baseline | Context construction | History / summary / retrieval / graph | Failure behavior | Required parameters | Prohibited optimization |
|---|---|---|---|---|---|
| **1. Full Conversation Replay** | Sends all prior scenario turns plus current turn in order | Retains full history; no summary, retrieval, or graph | Context overflow is a recorded failure; no silent truncation | Provider limit, output reserve, overflow policy=`fail` | Selective deletion, hidden summary, retrieval |
| **2. Sliding Window** | Sends the most recent turns fitting a fixed direct-input budget | Drops oldest complete turns; no summary, retrieval, or graph | Missing required older context remains a quality failure | Window turns and token budget fixed globally | Query-aware selection or adaptive expansion |
| **3. Rolling Summarization** | Sends a cumulative summary plus fixed recent window | Summary updates at declared intervals using one fixed summarizer/config; no retrieval or graph | Summary failure and lost facts are recorded; prior summary retained only if preregistered | Summary prompt/version, update cadence, summary budget, recent window | Access to raw omitted history during answering |
| **4. Standard Top-K Vector Retrieval** | Sends current turn, fixed recent window, and top-K semantically retrieved chunks | Same chunking/index timing for all trials; no SC-EVM gating, intent realignment, pending interceptor, or graph | Empty retrieval is valid; indexing failure recorded | K, chunking, distance metric, embedding model, budget | Hand filtering, dual-anchor admission, Graphify |
| **5. SC-EVM Without Graphify** | Current SC-EVM context path with structural lookup disabled | Bounded history, intent realignment, semantic retrieval, gating, pending memory; no graph | Existing fallbacks apply and are recorded | SC-EVM settings, prompts, thresholds, provider roles | Any Graphify artifact or output |
| **6. SC-EVM With Graphify** | Same as baseline 5 plus separately enclosed structural output | Every variable identical to baseline 5 except Graphify enabled | Missing/error/timeout structural context recorded; semantic path continues | Identical settings plus Graphify version/artifact checksum | Threshold, prompt, model, K, or budget changes between on/off |

## Fairness and budgets

Two views are mandatory: **native-policy**, where each declared strategy uses its intended context rule, and **matched-direct-budget**, where direct input budgets are equal. The same output reserve applies. Full replay may exceed the matched budget only in the native-policy view; overflow is reported. Summarization and reformulation costs count toward cumulative tokens and cost. Embedding, indexing, graph query, and evaluator costs are reported separately and in total.

Baseline definitions are versioned. A changed K, window, prompt, summarizer, threshold, or graph artifact constitutes a new configuration, not an in-place correction.
