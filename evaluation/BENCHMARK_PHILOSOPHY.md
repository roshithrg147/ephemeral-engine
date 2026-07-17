# Benchmark Philosophy

SC-EVM benchmarks exist to determine whether controlled context improves sustained task performance, not to produce attractive charts. “Better context management” means retaining active constraints and relevant facts, excluding irrelevant, stale, harmful, or cross-session material, recovering after topic changes, and doing so with understood quality, latency, token, cost, and failure trade-offs.

Token reduction alone is insufficient. A strategy that sends less context but forgets a legal condition, procedure step, or software dependency has failed. Conversely, correctness without context discipline may be too expensive or unreliable at long horizons. Answer quality and context quality must therefore be measured together.

Mechanisms do not justify commercial claims. Bounded history proves a bound on direct replay, not lower cumulative usage. Structural context proves an available input, not better answers. Isolation mechanisms prove design intent, not zero leakage. Every external claim must map to controlled outcomes and appropriate uncertainty.

Unfavorable, null, partial, and failed results are evidence and must be preserved. Benchmark design, metrics, exclusions, and acceptance thresholds are fixed before tuning. Reruns do not replace original runs.

Development prompts and the final evaluation corpus remain separate. Threshold, prompt, model, and baseline tuning may use Development; selection decisions may use Validation; Final Evaluation is opened only for preregistered runs and is never used for tuning.

The framework is implementation-neutral: all strategies receive equivalent scenarios, model access where technically possible, output limits, retry policy, and evaluation. Differences required by a strategy are disclosed rather than hidden.
