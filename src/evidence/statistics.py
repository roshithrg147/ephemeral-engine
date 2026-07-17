from __future__ import annotations

import json
import math
import random
import statistics
from pathlib import Path
from typing import Any


def percentile(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(probability * len(ordered)) - 1))
    return ordered[index]


def bootstrap_ci(
    values: list[float], *, seed: int = 11, samples: int = 10_000
) -> list[float] | None:
    if not values:
        return None
    rng = random.Random(seed)
    means = []
    for _ in range(samples):
        means.append(statistics.fmean(rng.choice(values) for _ in values))
    means.sort()
    return [means[int(samples * 0.025)], means[min(samples - 1, int(samples * 0.975))]]


def paired_effect(left: list[float], right: list[float]) -> dict[str, Any]:
    if len(left) != len(right) or not left:
        return {
            "count": 0,
            "mean_difference": None,
            "standardized_mean_difference": None,
            "ci95": None,
        }
    differences = [a - b for a, b in zip(left, right, strict=True)]
    deviation = statistics.stdev(differences) if len(differences) > 1 else 0.0
    mean_difference = statistics.fmean(differences)
    return {
        "count": len(differences),
        "mean_difference": mean_difference,
        "median_difference": statistics.median(differences),
        "standardized_mean_difference": mean_difference / deviation if deviation else 0.0,
        "ci95": bootstrap_ci(differences),
    }


def analyze_run(run_dir: Path) -> dict[str, Any]:
    records: dict[str, list[dict[str, Any]]] = {}
    for path in sorted((run_dir / "raw").glob("*.json")):
        strategy = path.stem.rsplit("-", 1)[-1]
        # Strategy IDs contain underscores but no hyphens; recover from each record.
        turns = json.loads(path.read_text(encoding="utf-8"))
        if turns:
            strategy = turns[0]["strategy_id"]
        records.setdefault(strategy, []).extend(turns)

    strategies = {}
    for strategy, turns in records.items():
        latencies = [
            float(item["latency"]["end_to_end_seconds"])
            for item in turns
            if item["latency"].get("end_to_end_seconds") is not None
        ]
        correctness = [
            1.0
            if next(
                (
                    result
                    for result in item["evaluator_outputs"]
                    if result["type"] == "deterministic"
                ),
                {"passed": False},
            )["passed"]
            else 0.0
            for item in turns
        ]
        failed = sum(item["status"] != "completed" for item in turns)
        missing_latency = len(turns) - len(latencies)
        latency_units = _cluster_means(
            turns,
            lambda item: item["latency"].get("end_to_end_seconds"),
        )
        correctness_units = _cluster_means(turns, _deterministic_score)
        strategies[strategy] = {
            "turns": len(turns),
            "failed_turns": failed,
            "missing_latency": missing_latency,
            "correctness": _distribution(correctness, inference_units=correctness_units),
            "latency": _distribution(latencies, inference_units=latency_units),
        }

    comparisons = {}
    reference = records.get("sc_evm_without_graphify", [])
    reference_by_turn = {
        (item["scenario_id"], item["turn_id"], item["seed"]): item for item in reference
    }
    for strategy, turns in records.items():
        if strategy == "sc_evm_without_graphify":
            continue
        paired = [
            (item, reference_by_turn[(item["scenario_id"], item["turn_id"], item["seed"])])
            for item in turns
            if (item["scenario_id"], item["turn_id"], item["seed"]) in reference_by_turn
        ]
        latency_differences = _paired_cluster_means(
            paired,
            lambda item: item["latency"].get("end_to_end_seconds"),
        )
        correctness_differences = _paired_cluster_means(paired, _deterministic_score)
        comparisons[f"{strategy}_vs_sc_evm_without_graphify"] = {
            "latency": paired_effect(latency_differences, [0.0] * len(latency_differences)),
            "correctness": paired_effect(
                correctness_differences,
                [0.0] * len(correctness_differences),
            ),
        }
    return {
        "schema_name": "scevm.statistical-analysis",
        "schema_version": "1.0.0",
        "strategies": strategies,
        "paired_comparisons": comparisons,
        "bootstrap_samples": 10_000,
        "failed_run_accounting": True,
        "missing_data_accounting": True,
        "inference_unit": "scenario_seed",
    }


def _deterministic_score(item: dict[str, Any]) -> float:
    result = next(
        (value for value in item["evaluator_outputs"] if value["type"] == "deterministic"), None
    )
    return 1.0 if result and result["passed"] else 0.0


def _cluster_means(turns: list[dict[str, Any]], value_fn) -> list[float]:
    clusters: dict[tuple[str, int], list[float]] = {}
    for item in turns:
        value = value_fn(item)
        if value is None:
            continue
        key = (item["scenario_id"], int(item["seed"]))
        clusters.setdefault(key, []).append(float(value))
    return [statistics.fmean(values) for _, values in sorted(clusters.items())]


def _paired_cluster_means(
    pairs: list[tuple[dict[str, Any], dict[str, Any]]], value_fn
) -> list[float]:
    clusters: dict[tuple[str, int], list[float]] = {}
    for left, right in pairs:
        left_value = value_fn(left)
        right_value = value_fn(right)
        if left_value is None or right_value is None:
            continue
        key = (left["scenario_id"], int(left["seed"]))
        clusters.setdefault(key, []).append(float(left_value) - float(right_value))
    return [statistics.fmean(values) for _, values in sorted(clusters.items())]


def _distribution(
    values: list[float],
    *,
    inference_units: list[float] | None = None,
) -> dict[str, Any]:
    units = values if inference_units is None else inference_units
    return {
        "count": len(values),
        "mean": statistics.fmean(values) if values else None,
        "median": statistics.median(values) if values else None,
        "variance": statistics.variance(values) if len(values) > 1 else 0.0 if values else None,
        "p50": percentile(values, 0.50),
        "p95": percentile(values, 0.95),
        "p99": percentile(values, 0.99),
        "ci95": bootstrap_ci(units),
        "inference_unit_count": len(units),
        "distribution": values,
    }
