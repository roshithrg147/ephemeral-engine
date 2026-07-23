"""Run 20 independent SC-EVM questions and persist full performance evidence."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import time
import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

QUESTIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "q01",
        "category": "arithmetic",
        "prompt": "What is 17 multiplied by 23? Answer concisely.",
        "expected_any": ["391"],
    },
    {
        "id": "q02",
        "category": "geography",
        "prompt": "What is the capital city of Japan? Answer concisely.",
        "expected_any": ["tokyo"],
    },
    {
        "id": "q03",
        "category": "science",
        "prompt": "What is the chemical formula for water? Answer concisely.",
        "expected_any": ["h2o", "h₂o"],
    },
    {
        "id": "q04",
        "category": "astronomy",
        "prompt": "What is the largest planet in our solar system? Answer concisely.",
        "expected_any": ["jupiter"],
    },
    {
        "id": "q05",
        "category": "computing",
        "prompt": "Write decimal 42 in binary. Answer with the binary digits.",
        "expected_any": ["101010"],
    },
    {
        "id": "q06",
        "category": "python",
        "prompt": "Which built-in Python sequence type is immutable: list or tuple?",
        "expected_any": ["tuple"],
    },
    {
        "id": "q07",
        "category": "http",
        "prompt": "Which HTTP status code means Not Found? Answer with the code.",
        "expected_any": ["404"],
    },
    {
        "id": "q08",
        "category": "sql",
        "prompt": "Which SQL aggregate expression counts every row? Answer concisely.",
        "expected_any": ["count(*)", "count (*)"],
    },
    {
        "id": "q09",
        "category": "mathematics",
        "prompt": "What is the first prime number greater than 29?",
        "expected_any": ["31"],
    },
    {
        "id": "q10",
        "category": "arithmetic",
        "prompt": "What is 15 percent of 240? Answer concisely.",
        "expected_any": ["36"],
    },
    {
        "id": "q11",
        "category": "literature",
        "prompt": "Who wrote the novel 1984?",
        "expected_any": ["george orwell", "orwell"],
    },
    {
        "id": "q12",
        "category": "science",
        "prompt": "At standard sea-level pressure, at what Celsius temperature does water boil?",
        "expected_any": ["100"],
    },
    {
        "id": "q13",
        "category": "computing",
        "prompt": "What does CPU stand for?",
        "expected_any": ["central processing unit"],
    },
    {
        "id": "q14",
        "category": "algorithms",
        "prompt": "What is the standard worst-case time complexity of merge sort?",
        "expected_any": ["o(n log n)", "o(nlogn)", "n log n"],
    },
    {
        "id": "q15",
        "category": "mathematics",
        "prompt": "What is the principal square root of 144?",
        "expected_any": ["12"],
    },
    {
        "id": "q16",
        "category": "geography",
        "prompt": "On which continent is Egypt located?",
        "expected_any": ["africa"],
    },
    {
        "id": "q17",
        "category": "git",
        "prompt": "Give a Git command that creates and switches to a new branch named feature-x.",
        "expected_any": ["git switch -c feature-x", "git checkout -b feature-x"],
    },
    {
        "id": "q18",
        "category": "json",
        "prompt": "How is the Boolean true value written in valid JSON?",
        "expected_any": ["true"],
    },
    {
        "id": "q19",
        "category": "networking",
        "prompt": "What is the default TCP port for HTTPS?",
        "expected_any": ["443"],
    },
    {
        "id": "q20",
        "category": "calendar",
        "prompt": "How many days are in a leap year?",
        "expected_any": ["366"],
    },
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def metric_summary(values: list[float]) -> dict[str, float | int | None]:
    return {
        "count": len(values),
        "min": min(values) if values else None,
        "mean": sum(values) / len(values) if values else None,
        "p50": percentile(values, 0.50),
        "p95": percentile(values, 0.95),
        "max": max(values) if values else None,
    }


def decode_data(value: str) -> Any:
    if value == "[DONE]":
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def evaluate_accuracy(response: str, expected_any: list[str]) -> tuple[bool, str | None]:
    normalized = " ".join(response.lower().split())
    for expected in expected_any:
        if " ".join(expected.lower().split()) in normalized:
            return True, expected
    return False, None


def aggregate_usage(turns: list[dict[str, Any]]) -> dict[str, Any]:
    by_stage: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    all_records: list[dict[str, Any]] = []
    for turn in turns:
        for record in turn.get("usage_report", []):
            if not isinstance(record, dict):
                continue
            all_records.append(record)
            by_stage[str(record.get("stage"))].append(record)
            by_model[str(record.get("model"))].append(record)

    def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
        latencies = [
            float(item["latency_seconds"])
            for item in records
            if isinstance(item.get("latency_seconds"), (int, float))
        ]
        input_tokens = [
            int(item["input_tokens"])
            for item in records
            if isinstance(item.get("input_tokens"), int)
        ]
        output_tokens = [
            int(item["output_tokens"])
            for item in records
            if isinstance(item.get("output_tokens"), int)
        ]
        costs = [
            float(item["calculated_cost"])
            for item in records
            if isinstance(item.get("calculated_cost"), (int, float))
        ]
        return {
            "calls": len(records),
            "completed": sum(item.get("status") == "completed" for item in records),
            "failed": sum(item.get("status") == "failed" for item in records),
            "measurement_types": dict(
                Counter(str(item.get("measurement_type")) for item in records)
            ),
            "latency_seconds": metric_summary(latencies),
            "input_tokens_total": sum(input_tokens),
            "output_tokens_total": sum(output_tokens),
            "total_tokens": sum(input_tokens) + sum(output_tokens),
            "calculated_cost_total": sum(costs) if costs else None,
        }

    return {
        "all_stages": summarize(all_records),
        "by_stage": {name: summarize(records) for name, records in sorted(by_stage.items())},
        "by_model": {name: summarize(records) for name, records in sorted(by_model.items())},
    }


def build_summary(turns: list[dict[str, Any]], run_seconds: float) -> dict[str, Any]:
    completed = [turn for turn in turns if turn.get("status") == "completed"]
    accurate = [turn for turn in completed if turn.get("accuracy", {}).get("passed")]
    burns_succeeded = [
        turn
        for turn in turns
        if isinstance(turn.get("burn", {}).get("http_status"), int)
        and 200 <= turn["burn"]["http_status"] < 300
    ]
    durations = [float(turn["timing"]["total_seconds"]) for turn in completed]
    ttfts = [
        float(turn["timing"]["time_to_first_response_seconds"])
        for turn in completed
        if isinstance(turn.get("timing", {}).get("time_to_first_response_seconds"), (int, float))
    ]
    return {
        "questions_planned": len(QUESTIONS),
        "questions_completed": len(completed),
        "questions_failed": len(turns) - len(completed),
        "session_burns_succeeded": len(burns_succeeded),
        "session_burns_failed": len(turns) - len(burns_succeeded),
        "accuracy_passed": len(accurate),
        "accuracy_rate": len(accurate) / len(completed) if completed else 0.0,
        "degraded_turns": sum(bool(turn.get("degradation")) for turn in turns),
        "run_seconds": run_seconds,
        "turn_latency_seconds": metric_summary(durations),
        "time_to_first_response_seconds": metric_summary(ttfts),
        "usage": aggregate_usage(turns),
        "accuracy_method": "case-insensitive expected-substring match; inspect responses for qualitative scoring",
    }


async def consume_question(
    client: httpx.AsyncClient,
    base_url: str,
    run_id: str,
    ordinal: int,
    question: dict[str, Any],
) -> dict[str, Any]:
    session_id = f"scevm-20q-{run_id[-8:]}-{ordinal:02d}"
    started_wall = utc_now()
    started = time.perf_counter()
    first_sse: float | None = None
    first_response: float | None = None
    current_event: str | None = None
    event_log: list[dict[str, Any]] = []
    captured: dict[str, Any] = {}
    response_parts: list[str] = []
    http_status: int | None = None
    error: str | None = None

    try:
        async with client.stream(
            "POST",
            f"{base_url}/api/agent/query",
            json={
                "session_id": session_id,
                "prompt": question["prompt"],
                "graphify_enabled": False,
                "diagnostic_mode": True,
            },
        ) as response:
            http_status = response.status_code
            response.raise_for_status()
            async for raw_line in response.aiter_lines():
                line = raw_line.strip()
                if not line:
                    continue
                elapsed = time.perf_counter() - started
                if line.startswith("event:"):
                    current_event = line.partition(":")[2].strip()
                    first_sse = elapsed if first_sse is None else first_sse
                    continue
                if not line.startswith("data:") or current_event is None:
                    continue
                value = decode_data(line.partition(":")[2].strip())
                event_log.append(
                    {"event": current_event, "elapsed_seconds": elapsed, "data": value}
                )
                if current_event == "response_content" and isinstance(value, str):
                    first_response = elapsed if first_response is None else first_response
                    response_parts.append(value)
                elif current_event not in {"done"}:
                    captured[current_event] = value
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"

    finished = time.perf_counter()
    response_text = "".join(response_parts)
    passed, matched = evaluate_accuracy(response_text, question["expected_any"])
    status = "completed" if response_text and error is None else "failed"
    burn: dict[str, Any]
    try:
        burn_response = await client.delete(f"{base_url}/api/session/burn/{session_id}")
        burn = {"http_status": burn_response.status_code, "body": burn_response.json()}
    except Exception as exc:
        burn = {"http_status": None, "error": f"{type(exc).__name__}: {exc}"}

    return {
        "turn": ordinal,
        "question_id": question["id"],
        "category": question["category"],
        "session_id": session_id,
        "prompt": question["prompt"],
        "expected_any": question["expected_any"],
        "response": response_text,
        "status": status,
        "http_status": http_status,
        "error": error,
        "accuracy": {"passed": passed, "matched": matched},
        "timing": {
            "started_at": started_wall,
            "total_seconds": finished - started,
            "time_to_first_sse_seconds": first_sse,
            "time_to_first_response_seconds": first_response,
        },
        "models": {
            "model_1_records": [
                item
                for item in captured.get("usage_report", [])
                if isinstance(item, dict) and str(item.get("stage", "")).startswith("model_1_")
            ],
            "model_2_records": [
                item
                for item in captured.get("usage_report", [])
                if isinstance(item, dict) and str(item.get("stage", "")).startswith("model_2_")
            ],
        },
        "usage_report": captured.get("usage_report", []),
        "legacy_token_usage": captured.get("token_usage"),
        "query_reformulation": captured.get("query_reformulation"),
        "retrieved_context": captured.get("retrieved_context"),
        "intent": captured.get("intent"),
        "action": captured.get("action"),
        "degradation": captured.get("degradation"),
        "metadata": captured.get("metadata"),
        "event_counts": dict(Counter(item["event"] for item in event_log)),
        "analytics_log": event_log,
        "burn": burn,
    }


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


async def run(args: argparse.Namespace) -> Path:
    base_url = args.base_url.rstrip("/")
    run_id = f"scevm-20q-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    output = args.output or Path("benchmarks/20_turn") / f"{run_id}.json"
    started = time.perf_counter()
    report: dict[str, Any] = {
        "schema_name": "scevm.independent-20-question-benchmark",
        "schema_version": "1.0.0",
        "run_id": run_id,
        "status": "running",
        "started_at": utc_now(),
        "finished_at": None,
        "base_url": base_url,
        "execution": "sequential; one isolated session per question; every session burned",
        "questions": list(QUESTIONS),
        "turns": [],
        "summary": None,
    }

    timeout = httpx.Timeout(connect=10.0, read=args.timeout, write=45.0, pool=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        health = await client.get(f"{base_url}/")
        health.raise_for_status()
        report["gateway_health"] = health.json()
        write_report(output, report)

        for ordinal, question in enumerate(QUESTIONS, start=1):
            print(f"[{ordinal:02d}/20] {question['id']} {question['category']}", flush=True)
            result = await consume_question(client, base_url, run_id, ordinal, question)
            report["turns"].append(result)
            report["summary"] = build_summary(report["turns"], time.perf_counter() - started)
            write_report(output, report)
            print(
                f"         status={result['status']} accuracy={result['accuracy']['passed']} "
                f"seconds={result['timing']['total_seconds']:.2f}",
                flush=True,
            )

    all_turns_completed = all(turn["status"] == "completed" for turn in report["turns"])
    all_sessions_burned = all(
        isinstance(turn.get("burn", {}).get("http_status"), int)
        and 200 <= turn["burn"]["http_status"] < 300
        for turn in report["turns"]
    )
    report["status"] = "completed" if all_turns_completed and all_sessions_burned else "partial"
    report["finished_at"] = utc_now()
    report["summary"] = build_summary(report["turns"], time.perf_counter() - started)
    write_report(output, report)
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=float, default=400.0)
    parser.add_argument("--output", type=Path)
    return parser


def main() -> None:
    output = asyncio.run(run(build_parser().parse_args()))
    print(f"Benchmark report: {output}")


if __name__ == "__main__":
    main()
