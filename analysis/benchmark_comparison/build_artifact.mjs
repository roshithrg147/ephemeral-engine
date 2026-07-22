import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const directory = path.dirname(fileURLToPath(import.meta.url));
const derived = JSON.parse(
  fs.readFileSync(path.join(directory, "derived_metrics.json"), "utf8"),
);

const byKey = Object.fromEntries(derived.matrix.map((row) => [row.key, row]));
const speedup = (slower, faster) =>
  (byKey[slower].mean_latency_seconds / byKey[faster].mean_latency_seconds).toFixed(2);
const p95Speedup = (slower, faster) =>
  (byKey[slower].p95_latency_seconds / byKey[faster].p95_latency_seconds).toFixed(2);

const title = "SC-EVM, Gemini, and Local Gemma Benchmark Comparison";

const manifest = {
  version: 1,
  surface: "report",
  title,
  description:
    "A technical comparison of completion, latency, output ceilings, and qualitative grounding signals across three 50-turn benchmark attempts.",
  generatedAt: derived.generated_at,
  sources: [
    {
      id: "benchmark-analysis",
      label: "Reproducible benchmark result transformation",
      path: "analysis/benchmark_comparison/analyze_results.mjs",
      query: {
        description:
          "Loads the three benchmark JSON artifacts, validates result shape, computes latency distributions and completion rates, and counts explicitly defined qualitative text markers.",
        engine: "node",
        language: "javascript",
        tables_used: [
          "sc_evm_50_turn_analysis.json",
          "standalone/gemini_performance_benchmark/outputs/benchmark_results.json",
          "standalone/ollama_performance_benchmark/outputs/benchmark_results.json",
        ],
        filters: [
          "Only non-empty response rows are counted as completed turns.",
          "The Gemini run is retained as partial evidence after quota stopped it at turn 22.",
          "SC-EVM is sourced from the named root-level 50-turn analysis artifact.",
          "Latency is compared descriptively because the SC-EVM and standalone prompt workloads differ.",
        ],
        metric_definitions: [
          "Mean latency is arithmetic mean of per-turn wall-clock latency in seconds.",
          "P95 latency uses the nearest-rank position over sorted per-turn latencies.",
          "Cap rate is the share of completed rows whose recorded completion reason indicates a configured output ceiling.",
          "Reported total tokens preserves each backend's own accounting; SC-EVM combines exact and fallback-estimated multi-call usage, Gemini includes provider total tokens, and Ollama sums prompt and output counters.",
          "Qualitative markers are transparent string-pattern counts, not correctness or human-preference scores.",
        ],
      },
    },
  ],
  blocks: [
    {
      id: "report-title",
      type: "markdown",
      body: `# ${title}`,
    },
    {
      id: "technical-summary",
      type: "markdown",
      body:
        "## Technical Summary\n\nLocal Gemma 4 is the strongest completed throughput baseline: it finished all 50 turns with 9.969 s mean latency, **" +
        `${speedup("scevm", "ollama")}x faster than the SC-EVM stress harness** on that descriptive measure. Gemini 3.5 Flash was fastest over the 22 observed turns (5.371 s mean), but quota exhaustion left the run only 44% complete. SC-EVM completed its full multi-phase adversarial workload and recorded 70.974 s mean latency. Because its prompts differ from the standalone runs, these ratios measure observed workload throughput rather than controlled model speed.`,
    },
    {
      id: "key-findings",
      type: "markdown",
      body:
        `## Key Findings\n\n- **Best complete direct-model throughput baseline:** Local Gemma 4, with no remote-token spend and 498.462 s of measured turn latency across 50 repeated status-update prompts.\n- **Fastest observed, incomplete:** Gemini averaged 5.371 s, 1.86x faster than Local Gemma, but stopped at 22/50 turns.\n- **SC-EVM validation completed:** The named root artifact completed 50/50 adversarial turns, with 70.974 s mean and ${byKey.scevm.p95_latency_seconds.toFixed(3)} s common-method p95 latency.\n- **Reliability caveat:** Gemini hit its output ceiling in 20/22 responses and Local Gemma in 44/50. SC-EVM reports a configured 2,500-token budget and legacy token estimates, not directly comparable provider usage fields.`,
    },
    {
      id: "latency-chart-block",
      type: "chart",
      chartId: "latency-by-turn",
    },
    {
      id: "matrix-section",
      type: "markdown",
      body:
        "## Comparison Matrix\n\nThe table separates complete-run evidence from partial evidence and exposes output-cap differences. Sorting by mean latency puts the partial Gemini run first; status and completion rate must be considered before selecting a winner.",
    },
    {
      id: "matrix-table-block",
      type: "table",
      tableId: "comparison-matrix",
    },
    {
      id: "token-usage-section",
      type: "markdown",
      body:
        "## Token Usage Requires Accounting Context\n\nSC-EVM reports 386,055 input-plus-output tokens across 161 model-call records: 358,025 tokens are marked exact and 28,030 are fallback estimates. Local Gemma reports 187,000 tokens across 50 turns. Gemini reports 86,348 provider-total tokens across its partial 22-turn run; 69,639 are explicit prompt plus output tokens and 16,709 are additional provider-counted tokens. These totals are auditable but not a fair efficiency ranking because workloads, completed turns, output ceilings, and calls per turn differ.",
    },
    {
      id: "token-usage-table-block",
      type: "table",
      tableId: "token-usage",
    },
    {
      id: "quality-section",
      type: "markdown",
      body:
        "## Qualitative Response Signals\n\nThe SC-EVM marker now records stress-harness completion rather than content quality because its prompts differ from the standalone workload. Within the shared standalone prompt sequence, Gemini frequently supplied an unsupported project identity, while Local Gemma usually disclosed that project context was missing. These transparent counts are behavioral diagnostics, not rubric-scored factual accuracy.",
    },
    {
      id: "quality-table-block",
      type: "table",
      tableId: "quality-markers",
    },
    {
      id: "scope-definitions",
      type: "markdown",
      body:
        "## Scope and Definitions\n\nThis report compares the named root-level `sc_evm_50_turn_analysis.json` artifact with the Gemini and Ollama-hosted Gemma 4 standalone artifacts. A completed turn requires a completed row with a non-empty response. Latency is recorded wall-clock time per completed turn. SC-EVM uses a multi-phase adversarial validation sequence; the standalone runs repeat an architectural status-update prompt.",
    },
    {
      id: "methodology",
      type: "markdown",
      body:
        `## Methodology\n\n\`analyze_results.mjs\` reads each source artifact, computes completion and latency statistics with one common method, preserves token and completion-reason fields where available, and records source SHA-256 hashes. P95 uses nearest rank; this yields ${byKey.scevm.p95_latency_seconds.toFixed(3)} s for SC-EVM, while its source artifact reports ${byKey.scevm.source_reported_p95_seconds.toFixed(3)} s using its own percentile convention. First-versus-last-ten latency change is included as a coarse drift indicator. Text markers are counted with explicit case-insensitive patterns documented in the analysis script.`,
    },
    {
      id: "limitations",
      type: "markdown",
      body:
        "## Limitations and Robustness\n\nThis is not a controlled head-to-head quality benchmark. The SC-EVM artifact embeds a substantially different, multi-phase adversarial prompt sequence and includes orchestration work that the direct-model runs do not. Gemini stopped after 22 turns because of quota. Gemini and Local Gemma used 128-token-style output ceilings, while SC-EVM used a configured 2,500-token budget with different token accounting. Consequently, latency ratios are descriptive workload observations; response length and qualitative markers must not be ranked across all three as equivalent quality measures.",
    },
    {
      id: "next-steps",
      type: "markdown",
      body:
        "## Recommended Next Steps\n\nUse Local Gemma 4 as the completed direct-model throughput baseline, and treat the SC-EVM result as validation of the full agent workflow rather than a controlled inference-speed competitor. Do not promote Gemini from this partial run alone. For a decisive head-to-head rerun, feed the exact SC-EVM prompt sequence to every backend under the same output ceiling, temperature, timeout, and context; record standardized prompt/output tokens and completion reasons; then apply a blinded factuality rubric.",
    },
    {
      id: "further-questions",
      type: "markdown",
      body:
        "## Further Questions\n\n- How much of SC-EVM’s latency comes from orchestration versus underlying model inference?\n- Can Gemma 4 and Gemini complete the same adversarial sequence without losing constraint adherence?\n- Does Local Gemma remain stable when the output ceiling is raised above 128 tokens?\n- Can Gemini finish 50 turns under a quota tier suitable for repeatable benchmarking?",
    },
  ],
  charts: [
    {
      id: "latency-by-turn",
      title: "Per-turn latency across benchmark runs",
      subtitle:
        `Workloads differ; Gemini stops after turn 22 and SC-EVM p95 is ${p95Speedup("scevm", "ollama")}x Local Gemma's observed p95.`,
      type: "line",
      intent: "trend",
      question: "How does recorded wall-clock latency vary by turn and backend?",
      rationale:
        "A line chart exposes the magnitude gap and within-run drift while making the partial Gemini series visible.",
      dataset: "latency_by_turn",
      source: {
        id: "latency-series",
        label: "Per-turn latency analysis dataset",
        path: "analysis/benchmark_comparison/derived_metrics.json",
        query: {
          description:
            "Selects the reviewed per-turn latency series produced by the reproducible benchmark transformation.",
          engine: "artifact-snapshot",
          language: "sql",
          sql: "SELECT turn, latency_seconds, run, run_key FROM latency_by_turn ORDER BY turn ASC, run ASC;",
          tables_used: ["latency_by_turn"],
          metric_definitions: [
            "latency_seconds is recorded per-turn wall-clock latency.",
          ],
        },
      },
      encodings: {
        x: { field: "turn", type: "quantitative", title: "Turn" },
        y: {
          field: "latency_seconds",
          type: "quantitative",
          title: "Latency (seconds)",
        },
        color: { field: "run", type: "nominal", title: "Run" },
      },
      legend: { position: "bottom", title: "Run" },
      palette: { kind: "categorical" },
    },
  ],
  tables: [
    {
      id: "comparison-matrix",
      title: "Benchmark comparison matrix",
      subtitle:
        "SC-EVM uses adversarial prompts; Gemini is partial and output ceilings differ.",
      dataset: "comparison_matrix",
      source: {
        id: "comparison-matrix-query",
        label: "Benchmark comparison matrix dataset",
        path: "analysis/benchmark_comparison/derived_metrics.json",
        query: {
          description:
            "Selects the reviewed run-level comparison metrics produced by the reproducible benchmark transformation.",
          engine: "artifact-snapshot",
          language: "sql",
          sql: "SELECT * FROM comparison_matrix ORDER BY mean_latency_seconds ASC;",
          tables_used: ["comparison_matrix"],
          metric_definitions: [
            "completion_rate_pct is completed non-empty turns divided by configured turns.",
            "mean_latency_seconds is the arithmetic mean of recorded per-turn latency.",
            "p95_latency_seconds uses nearest rank over sorted per-turn latency.",
          ],
        },
      },
      columns: [
        { field: "run", label: "Run", type: "text" },
        { field: "backend_model", label: "Backend / model", type: "text" },
        { field: "source_path", label: "Source artifact", type: "text" },
        { field: "workload", label: "Prompt workload", type: "text" },
        { field: "status", label: "Status", type: "text" },
        { field: "completed_turns", label: "Turns", type: "number" },
        {
          field: "completion_rate_pct",
          label: "Completion %",
          type: "number",
          format: ".1f",
        },
        {
          field: "mean_latency_seconds",
          label: "Mean latency (s)",
          type: "number",
          format: ".3f",
        },
        {
          field: "median_latency_seconds",
          label: "Median (s)",
          type: "number",
          format: ".3f",
        },
        {
          field: "p95_latency_seconds",
          label: "P95 (s)",
          type: "number",
          format: ".3f",
        },
        {
          field: "source_reported_p95_seconds",
          label: "Source P95 (s)",
          type: "number",
          format: ".3f",
        },
        {
          field: "last_vs_first_latency_pct",
          label: "Last vs first 10",
          type: "number",
          format: ".1f",
        },
        {
          field: "cap_rate_pct",
          label: "Output-cap %",
          type: "number",
          format: ".1f",
        },
        {
          field: "mean_response_characters",
          label: "Mean chars",
          type: "number",
          format: ".1f",
        },
        { field: "evidence_grade", label: "Evidence", type: "text" },
      ],
      defaultSort: { field: "mean_latency_seconds", direction: "asc" },
    },
    {
      id: "quality-markers",
      title: "Transparent qualitative marker counts",
      subtitle:
        "Pattern counts characterize behavior; they do not independently score correctness.",
      dataset: "quality_markers",
      source: {
        id: "quality-marker-query",
        label: "Qualitative response marker dataset",
        path: "analysis/benchmark_comparison/derived_metrics.json",
        query: {
          description:
            "Selects transparent string-pattern counts calculated over non-empty benchmark responses.",
          engine: "artifact-snapshot",
          language: "sql",
          sql: "SELECT run, marker, count, denominator, interpretation FROM quality_markers ORDER BY count DESC;",
          tables_used: ["quality_markers"],
          metric_definitions: [
            "count is the number of responses matching the documented case-insensitive text pattern.",
          ],
        },
      },
      columns: [
        { field: "run", label: "Run", type: "text" },
        { field: "marker", label: "Marker", type: "text" },
        { field: "count", label: "Count", type: "number" },
        { field: "denominator", label: "Responses", type: "number" },
        { field: "interpretation", label: "Interpretation", type: "text" },
      ],
      defaultSort: { field: "count", direction: "desc" },
    },
    {
      id: "token-usage",
      title: "Reported token usage by benchmark run",
      subtitle:
        "Backend-native accounting; SC-EVM includes multiple model calls and 24 estimated usage records.",
      dataset: "comparison_matrix",
      source: {
        id: "token-usage-query",
        label: "Benchmark token accounting dataset",
        path: "analysis/benchmark_comparison/derived_metrics.json",
        query: {
          description:
            "Selects the reviewed token counters and accounting classifications produced from each raw benchmark artifact.",
          engine: "artifact-snapshot",
          language: "sql",
          sql: "SELECT run, completed_turns, prompt_tokens, output_tokens, prompt_plus_output_tokens, reported_total_tokens, other_provider_tokens, reported_tokens_per_completed_turn, usage_record_count, usage_records_per_completed_turn, exact_tokens, estimated_tokens, legacy_sse_estimated_tokens, calculated_cost_usd, token_accounting FROM comparison_matrix ORDER BY reported_total_tokens DESC;",
          tables_used: ["comparison_matrix"],
          metric_definitions: [
            "prompt_plus_output_tokens is the sum of explicit prompt/input and output token counters.",
            "reported_total_tokens preserves the backend-native total; Gemini may include provider-counted tokens beyond explicit prompt plus output.",
            "SC-EVM exact_tokens and estimated_tokens classify its nested per-call usage records.",
            "calculated_cost_usd is available only from SC-EVM's recorded price table and must not be interpreted as a cross-backend cost comparison.",
          ],
        },
      },
      columns: [
        { field: "run", label: "Run", type: "text" },
        { field: "completed_turns", label: "Turns", type: "number" },
        { field: "prompt_tokens", label: "Input / prompt", type: "number" },
        { field: "output_tokens", label: "Output", type: "number" },
        {
          field: "reported_total_tokens",
          label: "Reported total",
          type: "number",
        },
        {
          field: "other_provider_tokens",
          label: "Other provider tokens",
          type: "number",
        },
        {
          field: "reported_tokens_per_completed_turn",
          label: "Tokens / turn",
          type: "number",
          format: ".1f",
        },
        {
          field: "usage_record_count",
          label: "Usage records",
          type: "number",
        },
        {
          field: "usage_records_per_completed_turn",
          label: "Records / turn",
          type: "number",
          format: ".2f",
        },
        { field: "exact_tokens", label: "SC-EVM exact", type: "number" },
        {
          field: "estimated_tokens",
          label: "SC-EVM estimated",
          type: "number",
        },
        {
          field: "calculated_cost_usd",
          label: "Recorded cost (USD)",
          type: "number",
          format: ".6f",
        },
        { field: "token_accounting", label: "Accounting basis", type: "text" },
      ],
      defaultSort: { field: "reported_total_tokens", direction: "desc" },
    },
  ],
};

const snapshot = {
  version: 1,
  status: "ready",
  generatedAt: derived.generated_at,
  datasets: {
    comparison_matrix: derived.matrix,
    latency_by_turn: derived.latency_by_turn,
    quality_markers: derived.quality_markers,
    source_inventory: derived.source_inventory,
  },
};

fs.writeFileSync(
  path.join(directory, "artifact.json"),
  `${JSON.stringify({ surface: "report", manifest, snapshot }, null, 2)}\n`,
);
