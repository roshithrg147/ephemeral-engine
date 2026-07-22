#!/usr/bin/env node

import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const reportDir = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(reportDir, "../..");

const sources = {
  scevm: {
    path: "sc_evm_50_turn_analysis.json",
    label: "SC-EVM stress harness",
    model: "SC-EVM dual-model gateway",
    configuredTurns: 50,
    status: "COMPLETE",
    workload: "Multi-phase adversarial SC-EVM validation sequence",
  },
  gemini: {
    path: "standalone/gemini_performance_benchmark/outputs/benchmark_results.json",
    label: "Gemini 3.5 Flash",
    model: "gemini-3.5-flash",
    configuredTurns: 50,
    status: "PARTIAL",
    workload: "Repeated architectural status-update prompt",
  },
  ollama: {
    path: "standalone/ollama_performance_benchmark/outputs/benchmark_results.json",
    label: "Local Gemma 4",
    model: "gemma4:latest",
    configuredTurns: 50,
    status: "COMPLETE",
    workload: "Repeated architectural status-update prompt",
  },
};

function readJson(relativePath) {
  const raw = readFileSync(resolve(repoRoot, relativePath));
  return {
    raw,
    value: JSON.parse(raw.toString("utf8")),
    sha256: createHash("sha256").update(raw).digest("hex"),
  };
}

function quantile(values, fraction) {
  const ordered = [...values].sort((a, b) => a - b);
  const index = Math.max(0, Math.ceil(ordered.length * fraction) - 1);
  return ordered[index];
}

function median(values) {
  const ordered = [...values].sort((a, b) => a - b);
  const middle = Math.floor(ordered.length / 2);
  return ordered.length % 2
    ? ordered[middle]
    : (ordered[middle - 1] + ordered[middle]) / 2;
}

function mean(values) {
  return values.reduce((total, value) => total + value, 0) / values.length;
}

function populationStdDev(values) {
  const average = mean(values);
  return Math.sqrt(mean(values.map((value) => (value - average) ** 2)));
}

function round(value, digits = 3) {
  if (value === null || value === undefined) return null;
  const scale = 10 ** digits;
  return Math.round(value * scale) / scale;
}

function extractResults(document) {
  if (Array.isArray(document)) return document;
  if (Array.isArray(document.turns)) return document.turns;
  return document.results;
}

function latencyFor(row) {
  return Number(
    row.total_turn_latency_seconds ?? row.latency_seconds ?? row.latency,
  );
}

function normalizeRun(key, source, document) {
  const isLegacyArray = Array.isArray(document);
  const isScEvmAnalysis = Array.isArray(document.turns);
  const results = extractResults(document);
  const latencies = results.map(latencyFor);
  const responseLengths = results.map((row) => String(row.response ?? "").length);
  const capCount = isLegacyArray || isScEvmAnalysis
    ? null
    : results.filter((row) =>
        ["MAX_TOKENS", "length"].includes(
          row.usage?.finish_reason ?? row.usage?.done_reason,
        ),
      ).length;
  const usageEntries = isScEvmAnalysis
    ? results.flatMap((row) => row.token_usage?.usage_report ?? [])
    : [];
  const promptTokens = isLegacyArray
    ? null
    : isScEvmAnalysis
      ? results.reduce(
          (total, row) =>
            total + Number(row.token_usage?.usage_report_input_total ?? 0),
          0,
        )
    : results.reduce((total, row) => total + Number(row.usage?.prompt_tokens ?? 0), 0);
  const outputTokens = isLegacyArray
    ? null
    : isScEvmAnalysis
      ? results.reduce(
          (total, row) =>
            total + Number(row.token_usage?.usage_report_output_total ?? 0),
          0,
        )
    : results.reduce((total, row) => total + Number(row.usage?.output_tokens ?? 0), 0);
  const reportedTotalTokens =
    promptTokens === null || outputTokens === null
      ? null
      : isScEvmAnalysis
        ? promptTokens + outputTokens
        : results.reduce(
            (total, row) =>
              total +
              Number(
                row.usage?.total_tokens ??
                  ((row.usage?.prompt_tokens ?? 0) +
                    (row.usage?.output_tokens ?? 0)),
              ),
            0,
          );
  const exactTokens = isScEvmAnalysis
    ? usageEntries
        .filter((entry) => entry.measurement_type === "exact")
        .reduce(
          (total, entry) =>
            total +
            Number(entry.input_tokens ?? 0) +
            Number(entry.output_tokens ?? 0),
          0,
        )
    : null;
  const estimatedTokens = isScEvmAnalysis
    ? usageEntries
        .filter((entry) => entry.measurement_type === "estimate")
        .reduce(
          (total, entry) =>
            total +
            Number(entry.input_tokens ?? 0) +
            Number(entry.output_tokens ?? 0),
          0,
        )
    : null;
  const firstWindow = latencies.slice(0, Math.min(10, latencies.length));
  const lastWindow = latencies.slice(-Math.min(10, latencies.length));
  const firstMean = mean(firstWindow);
  const lastMean = mean(lastWindow);

  return {
    key,
    run: source.label,
    backend_model: source.model,
    source_path: source.path,
    workload: source.workload,
    status: source.status,
    configured_turns: source.configuredTurns,
    completed_turns: results.length,
    completion_rate_pct: round((results.length / source.configuredTurns) * 100, 1),
    min_latency_seconds: round(Math.min(...latencies)),
    mean_latency_seconds: round(mean(latencies)),
    median_latency_seconds: round(median(latencies)),
    p95_latency_seconds: round(quantile(latencies, 0.95)),
    source_reported_p95_seconds: isScEvmAnalysis
      ? round(document.summary?.latency_seconds?.p95)
      : null,
    max_latency_seconds: round(Math.max(...latencies)),
    latency_stddev_seconds: round(populationStdDev(latencies)),
    total_measured_latency_seconds: round(
      latencies.reduce((total, value) => total + value, 0),
    ),
    first_10_mean_latency_seconds: round(firstMean),
    last_10_mean_latency_seconds: round(lastMean),
    last_vs_first_latency_pct: round(((lastMean / firstMean) - 1) * 100, 1),
    nonempty_responses: results.filter((row) => String(row.response ?? "").trim()).length,
    mean_response_characters: round(mean(responseLengths), 1),
    median_response_characters: round(median(responseLengths), 1),
    max_response_characters: Math.max(...responseLengths),
    cap_count: capCount,
    cap_rate_pct: capCount === null ? null : round((capCount / results.length) * 100, 1),
    prompt_tokens: promptTokens,
    output_tokens: outputTokens,
    prompt_plus_output_tokens:
      promptTokens === null ? null : promptTokens + outputTokens,
    reported_total_tokens: reportedTotalTokens,
    reported_tokens_per_completed_turn:
      reportedTotalTokens === null
        ? null
        : round(reportedTotalTokens / results.length, 1),
    other_provider_tokens:
      reportedTotalTokens === null
        ? null
        : reportedTotalTokens - promptTokens - outputTokens,
    exact_tokens: exactTokens,
    estimated_tokens: estimatedTokens,
    legacy_sse_estimated_tokens: isScEvmAnalysis
      ? results.reduce(
          (total, row) => total + Number(row.token_usage?.legacy_total ?? 0),
          0,
        )
      : null,
    usage_record_count: isScEvmAnalysis ? usageEntries.length : results.length,
    usage_records_per_completed_turn: round(
      (isScEvmAnalysis ? usageEntries.length : results.length) / results.length,
      2,
    ),
    estimated_usage_record_count: isScEvmAnalysis
      ? usageEntries.filter((entry) => entry.measurement_type === "estimate").length
      : 0,
    calculated_cost_usd: isScEvmAnalysis
      ? round(
          usageEntries.reduce(
            (total, entry) => total + Number(entry.calculated_cost ?? 0),
            0,
          ),
          6,
        )
      : null,
    token_accounting: isScEvmAnalysis
      ? "Multi-call usage report: exact counts plus fallback estimates"
      : key === "gemini"
        ? "Provider prompt/output counters plus provider total tokens"
        : "Local prompt-evaluation and output counters",
    final_prompt_tokens: isLegacyArray || isScEvmAnalysis
      ? null
      : Number(results.at(-1)?.usage?.prompt_tokens ?? 0),
    configured_token_budget: isScEvmAnalysis
      ? Number(document.initial_token_budget ?? 0)
      : null,
    evidence_grade:
      isScEvmAnalysis
        ? "Complete; token accounting differs"
        : source.status === "COMPLETE"
        ? capCount === null
          ? "Complete; token ceiling unknown"
          : capCount > 0
            ? "Complete; output-capped"
            : "Complete"
        : "Partial; quota-stopped",
  };
}

const raw = Object.fromEntries(
  Object.entries(sources).map(([key, source]) => [key, readJson(source.path)]),
);
const matrix = Object.entries(sources).map(([key, source]) =>
  normalizeRun(key, source, raw[key].value),
);

const latencyByTurn = Object.entries(sources).flatMap(([key, source]) => {
  const document = raw[key].value;
  const results = extractResults(document);
  return results.map((row) => ({
    run: source.label,
    run_key: key,
    status: source.status,
    workload: source.workload,
    turn: Number(row.turn),
    latency_seconds: round(latencyFor(row)),
    response_characters: String(row.response ?? "").length,
  }));
});

const qualityMarkers = [
  {
    run: sources.scevm.label,
    marker: "Completed adversarial validation turn",
    count: raw.scevm.value.turns.filter((row) => row.status === "completed").length,
    denominator: raw.scevm.value.requested_turns,
    interpretation:
      "All requested stress-harness turns completed; the workload is not prompt-equivalent to the standalone runs.",
  },
  {
    run: sources.gemini.label,
    marker: "Introduces fabricated named project `Project Horizon`",
    count: raw.gemini.value.results.filter((row) =>
      row.response.includes("Project Horizon"),
    ).length,
    denominator: raw.gemini.value.results.length,
    interpretation:
      "The direct model invented project context that was absent from the prompt.",
  },
  {
    run: sources.ollama.label,
    marker: "Explicitly acknowledges missing context",
    count: raw.ollama.value.results.filter((row) =>
      row.response.toLowerCase().includes("without context"),
    ).length,
    denominator: raw.ollama.value.results.length,
    interpretation:
      "The local model generally avoids pretending it received project facts, but often returns templates.",
  },
];

const sourceInventory = Object.entries(sources).map(([key, source]) => ({
  run_key: key,
  run: source.label,
  source_path: source.path,
  sha256: raw[key].sha256,
  bytes: raw[key].raw.length,
}));

const output = {
  generated_at: new Date().toISOString(),
  comparison_basis:
    "Descriptive performance comparison only. SC-EVM uses a multi-phase adversarial validation workload, while Gemini and Local Gemma use the repeated architectural status-update prompt. Completion and latency are reported, but model-quality and per-turn latency differences are not controlled head-to-head estimates.",
  matrix,
  latency_by_turn: latencyByTurn,
  quality_markers: qualityMarkers,
  source_inventory: sourceInventory,
};

writeFileSync(
  resolve(reportDir, "derived_metrics.json"),
  `${JSON.stringify(output, null, 2)}\n`,
);
