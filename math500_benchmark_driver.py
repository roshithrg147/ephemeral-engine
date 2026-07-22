"""Run a small MATH500-style benchmark against the live SC-EVM SSE gateway."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx

BASE_URL = "http://127.0.0.1:8000"
SESSION_ID = "math500_evaluation_session_01"
RESULTS_PATH = Path("math500_benchmark_results.json")
RESPONSES_PATH = Path("math500_benchmark_responses.txt")


@dataclass(frozen=True)
class MathSample:
    """One benchmark problem and its expected boxed answer."""

    domain: str
    prompt: str
    expected_answer: str


@dataclass
class TurnResult:
    """Captured response, telemetry, and exact-answer score for one turn."""

    turn: int
    domain: str
    prompt: str
    expected_answer: str
    extracted_answer: str | None
    exact_match: bool
    status: str
    http_status: int | None
    latency_seconds: float
    response: str
    events: dict[str, Any]
    error: str | None = None


MATH500_SAMPLES = [
    MathSample(
        domain="Number Theory",
        prompt=(
            "Find the number of ordered pairs of positive integers (x, y) such "
            "that x^2 - y^2 = 2^2016."
        ),
        expected_answer="1007",
    ),
    MathSample(
        domain="Probability",
        prompt=(
            "A fair coin is flipped 10 times. What is the probability that no "
            "two consecutive flips land on heads? Express your answer as a "
            "common fraction."
        ),
        expected_answer="9/64",
    ),
]


def parse_sse_data(raw_text: str) -> dict[str, Any]:
    """Parse the SC-EVM event stream into a dictionary keyed by event name."""

    events: dict[str, Any] = {}
    current_event: str | None = None
    for line in raw_text.splitlines():
        if line.startswith("event:"):
            current_event = line.removeprefix("event:").strip()
            continue
        if not line.startswith("data:") or current_event is None:
            continue

        payload = line.removeprefix("data:").strip()
        if payload == "[DONE]":
            events[current_event] = payload
            continue
        try:
            decoded: Any = json.loads(payload)
        except json.JSONDecodeError:
            decoded = payload

        previous = events.get(current_event)
        if previous is None:
            events[current_event] = decoded
        elif isinstance(previous, list):
            previous.append(decoded)
        else:
            events[current_event] = [previous, decoded]
    return events


def extract_boxed_answer(response: str) -> str | None:
    """Extract and normalize the final LaTeX boxed value."""

    matches: list[str] = []
    for match in re.finditer(r"\\boxed\s*\{", response):
        start = match.end()
        depth = 1
        for index in range(start, len(response)):
            character = response[index]
            if character == "{":
                depth += 1
            elif character == "}":
                depth -= 1
                if depth == 0:
                    matches.append(response[start:index])
                    break
    if not matches:
        return None
    answer = matches[-1]
    answer = answer.replace(r"\dfrac", r"\frac").replace(r"\tfrac", r"\frac")
    fraction = re.fullmatch(r"\\frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}", answer)
    if fraction:
        return f"{fraction.group(1).strip()}/{fraction.group(2).strip()}"
    return answer.replace(" ", "").replace(",", "")


def build_prompt(sample: MathSample) -> str:
    """Build the user prompt sent to the reasoning engine."""

    return (
        f"Domain: {sample.domain}. Problem: {sample.prompt} "
        "Provide the solution step-by-step and place your final numerical result "
        r"inside a standard LaTeX \boxed{} wrapper."
    )


async def initialize_session(client: httpx.AsyncClient) -> None:
    """Initialize the benchmark session."""

    response = await client.post(
        f"{BASE_URL}/api/session/initialize",
        json={"session_id": SESSION_ID},
    )
    response.raise_for_status()


async def run_turn(client: httpx.AsyncClient, turn: int, sample: MathSample) -> TurnResult:
    """Execute one problem and capture the entire SSE response."""

    payload = {
        "session_id": SESSION_ID,
        "prompt": build_prompt(sample),
        "graphify_enabled": False,
        "diagnostic_mode": True,
    }
    started = time.perf_counter()
    try:
        async with client.stream("POST", f"{BASE_URL}/api/agent/query", json=payload) as response:
            response.raise_for_status()
            chunks = [chunk async for chunk in response.aiter_text()]
            raw_stream = "".join(chunks)
        latency = time.perf_counter() - started
        events = parse_sse_data(raw_stream)
        response_text = events.get("response_content")
        if not isinstance(response_text, str):
            error_event = events.get("error")
            return TurnResult(
                turn=turn,
                domain=sample.domain,
                prompt=sample.prompt,
                expected_answer=sample.expected_answer,
                extracted_answer=None,
                exact_match=False,
                status="FAILED",
                http_status=response.status_code,
                latency_seconds=latency,
                response="",
                events=events,
                error=f"No response_content event; error={error_event!r}",
            )

        if events.get("degradation") or response_text.startswith("[DEGRADED:"):
            return TurnResult(
                turn=turn,
                domain=sample.domain,
                prompt=sample.prompt,
                expected_answer=sample.expected_answer,
                extracted_answer=None,
                exact_match=False,
                status="PROVIDER_FAILED",
                http_status=response.status_code,
                latency_seconds=latency,
                response=response_text,
                events=events,
                error="Upstream model failure returned inside response_content",
            )

        extracted_answer = extract_boxed_answer(response_text)
        return TurnResult(
            turn=turn,
            domain=sample.domain,
            prompt=sample.prompt,
            expected_answer=sample.expected_answer,
            extracted_answer=extracted_answer,
            exact_match=extracted_answer == sample.expected_answer,
            status="COMPLETED",
            http_status=response.status_code,
            latency_seconds=latency,
            response=response_text,
            events=events,
        )
    except (httpx.HTTPError, TimeoutError) as exc:
        return TurnResult(
            turn=turn,
            domain=sample.domain,
            prompt=sample.prompt,
            expected_answer=sample.expected_answer,
            extracted_answer=None,
            exact_match=False,
            status="FAILED",
            http_status=getattr(getattr(exc, "response", None), "status_code", None),
            latency_seconds=time.perf_counter() - started,
            response="",
            events={},
            error=f"{type(exc).__name__}: {exc}",
        )


def write_artifacts(
    turns: list[TurnResult],
    started_at_epoch: float,
    burn_verification: dict[str, Any] | None,
) -> None:
    """Checkpoint machine-readable results and a readable response transcript."""

    transport_completed = sum(turn.http_status == 200 for turn in turns)
    evaluable = sum(turn.status == "COMPLETED" for turn in turns)
    exact_matches = sum(turn.exact_match for turn in turns)
    artifact = {
        "benchmark": "MATH500-style two-sample smoke evaluation",
        "session_id": SESSION_ID,
        "started_at_epoch": started_at_epoch,
        "transport_completed_turns": transport_completed,
        "evaluable_turns": evaluable,
        "total_turns": len(MATH500_SAMPLES),
        "exact_matches": exact_matches,
        "accuracy": exact_matches / evaluable if evaluable else None,
        "burn_verification": burn_verification,
        "turns": [asdict(turn) for turn in turns],
    }
    RESULTS_PATH.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")

    sections = []
    for turn in turns:
        sections.append(
            "\n".join(
                [
                    f"TURN {turn.turn}: {turn.domain}",
                    f"STATUS: {turn.status}",
                    f"LATENCY_SECONDS: {turn.latency_seconds:.3f}",
                    f"EXPECTED: {turn.expected_answer}",
                    f"EXTRACTED: {turn.extracted_answer}",
                    f"EXACT_MATCH: {turn.exact_match}",
                    f"ERROR: {turn.error or ''}",
                    "",
                    turn.response,
                ]
            )
        )
    RESPONSES_PATH.write_text(
        "\n\n" + ("\n\n" + "=" * 80 + "\n\n").join(sections) + "\n",
        encoding="utf-8",
    )


async def burn_and_verify(client: httpx.AsyncClient) -> dict[str, Any]:
    """Burn the benchmark session and verify it is no longer addressable."""

    burn = await client.delete(f"{BASE_URL}/api/session/burn/{SESSION_ID}")
    history = await client.get(f"{BASE_URL}/api/session/history/{SESSION_ID}")
    sessions = await client.get(f"{BASE_URL}/api/session/list")
    session_ids = sessions.json().get("data", []) if sessions.is_success else []
    return {
        "burn_http_status": burn.status_code,
        "history_http_status": history.status_code,
        "absent_from_session_list": SESSION_ID not in session_ids,
        "verified": (
            burn.status_code == 200 and history.status_code == 404 and SESSION_ID not in session_ids
        ),
    }


async def evaluate_engine_math() -> int:
    """Run the two benchmark turns, checkpoint evidence, and burn the session."""

    turns: list[TurnResult] = []
    burn_verification: dict[str, Any] | None = None
    started_at_epoch = time.time()
    timeout = httpx.Timeout(300.0, connect=10.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            print(f"Initializing SC-EVM math session: {SESSION_ID}")
            await initialize_session(client)
            for turn, sample in enumerate(MATH500_SAMPLES, start=1):
                print(f"[Turn {turn}] {sample.domain}")
                result = await run_turn(client, turn, sample)
                turns.append(result)
                write_artifacts(turns, started_at_epoch, burn_verification)
                print(
                    f"  {result.status} | {result.latency_seconds:.2f}s | "
                    f"boxed={result.extracted_answer!r} | exact={result.exact_match}"
                )
        finally:
            try:
                burn_verification = await burn_and_verify(client)
                print(f"Burn verified: {burn_verification['verified']}")
            except httpx.HTTPError as exc:
                burn_verification = {
                    "verified": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            write_artifacts(turns, started_at_epoch, burn_verification)

    return (
        0
        if len(turns) == len(MATH500_SAMPLES) and all(turn.status == "COMPLETED" for turn in turns)
        else 1
    )


def main() -> int:
    """CLI entry point."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    return asyncio.run(evaluate_engine_math())


if __name__ == "__main__":
    raise SystemExit(main())
