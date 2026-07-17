# Commercial Claim Matrix

Statuses: **Supported**, **Partially Supported**, **Unsupported**, **Prohibited**, and **Pending Evaluation**. No current benchmark artifact satisfies this methodology; therefore no comparative quality/cost claim is marked Supported.

| Claim | Required metrics and baselines | Minimum evidence | Review | Status | Permitted wording | Prohibited wording |
|---|---|---|---|---|---|---|
| Reduces direct prompt growth | Direct Input Token Growth; all six baselines | 30 scenarios/category/length, 5 seeds, 95% CI, 2 model families preferred, all categories | Evidence + Product | Partially Supported | “Bounds direct active-history replay by design”; measured reduction only with results | “Constant total tokens” |
| Reduces cumulative input tokens | Cumulative Input Tokens; all baselines | Exact provider usage, all lengths/categories, 2 families | Evidence + Finance/Product | Pending Evaluation | “Under evaluation” | “Always lowers token cost” |
| Preserves long-horizon constraints | Constraint Retention, Correctness; replay/window/summary/vector baselines | 100–500 turns, 30 scenarios/category, 5 seeds, 2 families | Evidence + domain reviewers | Pending Evaluation | “Designed to preserve” | “Never forgets” |
| Improves retrieval relevance | Recall, Precision, Inclusion; vector and SC-EVM baselines | Retrieval-labeled scenarios, paired CI, 2 families | Evidence | Pending Evaluation | “Uses explicit admission policy” | “Proven more relevant” |
| Reduces irrelevant context | Inclusion and Pollution rates; vector/replay/window | All categories/lengths, paired CI | Evidence | Pending Evaluation | “Designed to reject irrelevant context” | “Eliminates context pollution” |
| Improves answer correctness | Correctness; all baselines | All categories, 30 scenarios/length, 5 seeds, 2 families | Evidence + domain | Pending Evaluation | “Under evaluation” | “More accurate” |
| Reduces hallucinations | Hallucination Rate; all baselines | Source-grounded cases, two human reviewers, 2 families | Evidence + domain/security | Pending Evaluation | “Measures unsupported claims” | “Hallucination-proof” |
| Improves topic recovery | Topic Recovery; replay/window/summary/vector | Topic switch/return cases at all lengths | Evidence | Pending Evaluation | “Supports topic-return evaluation” | “Always recovers context” |
| Prevents cross-session leakage | Leakage Rate; adversarial isolated/control runs | Security-specific tests, large attack set, independent security review | Security + Architecture | Prohibited | “Uses session-scoped logical isolation” | “Prevents” or “zero leakage” |
| Deletes session state | Burn Correctness and artifact inspection | Concurrency/race tests and security review | Security + Architecture | Partially Supported | “Burn removes application access to session-owned ephemeral state” | “Physically erases RAM/all data” |
| Improves latency | E2E, TTFR, p50/p95/p99; all baselines | Controlled environment, all lengths, paired CI | Evidence + Operations | Pending Evaluation | “Latency measured as a trade-off” | “Ultra-low latency” |
| Reduces cost | Exact tokens and Cost/Completed Scenario | Billing-grade usage/prices, quality guardrail, 2 families | Evidence + Finance/Product | Pending Evaluation | “Cost under evaluation” | “Cheaper” from estimates |
| Graphify improves structural context | Graph ablation metrics | Exact ablation, structural strata, 2 snapshots/repos, 2 families for broad claim | Evidence + Architecture | Pending Evaluation | “Experimental structural-context capability” | “Graphify improves accuracy” |
| Dual-model synthesis improves quality | Correctness/hallucination/cost/latency; matched single-model | Paired all-category trials, 2 families/configs | Evidence + Product | Pending Evaluation | “Optional strategy” | “Two models are better” |
| Provider-independent | Adapter conformance and replicated outcomes | At least two supported transports with common contract | Architecture + Product | Unsupported | “Provider-adaptable boundary” | “Provider-independent” |
| Production-ready | Reliability, security, scale, operations evidence | Production acceptance program and gap closure | Security + Operations + Executive | Prohibited | “Container-capable for controlled evaluation” | “Production-ready” |
| Enterprise-grade | Defined enterprise requirements and independent evidence | Auth, audit, retention, support, security, scale validation | Executive + Security + Product | Prohibited | No permitted enterprise-grade wording | “Enterprise-grade” |

Claim approval records must state categories, model families, scenario count, confidence, practical threshold, reviewers, artifact links, expiration/revalidation trigger, and exact wording.
