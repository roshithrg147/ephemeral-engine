"""Run a bounded three-turn manual SSE test through the SC-EVM gateway."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

BASE_URL = "http://127.0.0.1:8000"
SESSION_ID = "antigravity_test_session_01"
EXECUTION_TIMEOUT_SECONDS = 45.0
LOG_PATH = Path("sc_evm_manual_test_log.json")

PROMPTS = [
    (
        "We are building an order-processing microservice for an e-commerce "
        "platform handling 30,000 active users. System Constraint: Enforce a "
        "Postgres-only database schema with explicit two-column balance check "
        "exclusions. Message broker backpressure must use a 4-partition Kafka pool."
    ),
    (
        "I was also looking at a recipe for making sourdough bread from scratch "
        "with a 75% hydration dough, and an error log from an unrelated local "
        "Docker container showing code 0x04F."
    ),
    (
        "Generate the initial PostgreSQL DDL migration script for that service's "
        "primary ledger table, including the database constraints we established "
        "earlier."
    ),
]


def utc_now() -> str:
    """Return a stable UTC timestamp for the evidence artifact."""

    return datetime.now(UTC).isoformat()


def decode_sse_data(raw_data: str) -> Any:
    """Decode one SSE data value without discarding its raw representation."""

    if raw_data == "[DONE]":
        return raw_data
    try:
        return json.loads(raw_data)
    except json.JSONDecodeError:
        return raw_data


def is_provider_failure(value: Any) -> bool:
    """Identify provider failure placeholders returned as normal response content."""

    if not isinstance(value, str):
        return False
    return value.startswith("[DEGRADED:") or (value.startswith("[Model ") and " failed:" in value)


async def verify_gateway(client: httpx.AsyncClient) -> dict[str, Any]:
    """Verify the gateway using its available health surface."""

    checks: list[dict[str, Any]] = []
    for path in ("/health", "/"):
        response = await client.get(f"{BASE_URL}{path}")
        checks.append(
            {
                "path": path,
                "status_code": response.status_code,
                "body": response.text,
            }
        )
        if response.status_code == 200:
            return {"available": True, "selected_path": path, "checks": checks}
    raise RuntimeError(f"SC-EVM gateway health checks failed: {checks}")


async def initialize_session(client: httpx.AsyncClient) -> dict[str, Any]:
    """Initialize the exact manual-test session before sending turns."""

    response = await client.post(
        f"{BASE_URL}/api/session/initialize",
        json={"session_id": SESSION_ID},
        headers={"Content-Type": "application/json"},
    )
    response.raise_for_status()
    return {"status_code": response.status_code, "body": response.json()}


async def run_turn(
    client: httpx.AsyncClient,
    turn_number: int,
    prompt: str,
    turn_log: dict[str, Any],
) -> None:
    """Stream one turn and append every SSE event and data payload to its log."""

    payload = {"session_id": SESSION_ID, "prompt": prompt}
    turn_started = time.perf_counter()
    current_event = "message"
    first_content_at: float | None = None
    response_content: list[Any] = []

    try:
        async with client.stream(
            "POST",
            f"{BASE_URL}/api/agent/query",
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
        ) as response:
            turn_log["http_status"] = response.status_code
            turn_log["response_content_type"] = response.headers.get("content-type")
            response.raise_for_status()

            async for line in response.aiter_lines():
                elapsed = time.perf_counter() - turn_started
                turn_log["raw_sse_lines"].append(line)

                if line.startswith("event:"):
                    current_event = line.removeprefix("event:").strip()
                    continue
                if not line.startswith("data: "):
                    continue

                raw_data = line.removeprefix("data: ")
                decoded = decode_sse_data(raw_data)
                event_record = {
                    "event": current_event,
                    "elapsed_seconds": elapsed,
                    "raw_data": raw_data,
                    "data": decoded,
                }
                turn_log["events"].append(event_record)
                print(
                    f"[Turn {turn_number}] event={current_event} "
                    f"elapsed={elapsed:.3f}s data={raw_data[:240]}"
                )

                if current_event in {"token", "response_content"}:
                    if first_content_at is None:
                        first_content_at = elapsed
                    response_content.append(decoded)
                if current_event == "error":
                    turn_log["status"] = "SSE_ERROR"

        turn_log["status"] = (
            "PROVIDER_FAILED"
            if any(is_provider_failure(value) for value in response_content)
            else turn_log.get("status", "COMPLETED")
        )
    except asyncio.CancelledError:
        turn_log["status"] = "TIMEOUT"
        raise
    except httpx.HTTPError as exc:
        turn_log["status"] = "HTTP_ERROR"
        turn_log["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        turn_log["ttft_seconds"] = first_content_at
        turn_log["total_duration_seconds"] = time.perf_counter() - turn_started


async def burn_and_verify() -> dict[str, Any]:
    """Burn the session and verify HTTP confirmation plus post-burn absence."""

    timeout = httpx.Timeout(90.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        burn = await client.delete(f"{BASE_URL}/api/session/burn/{SESSION_ID}")
        history = await client.get(f"{BASE_URL}/api/session/history/{SESSION_ID}")
        sessions = await client.get(f"{BASE_URL}/api/session/list")
        session_ids = sessions.json().get("data", []) if sessions.is_success else []
        return {
            "status_code": burn.status_code,
            "body": burn.json() if burn.content else None,
            "history_status_code": history.status_code,
            "absent_from_session_list": SESSION_ID not in session_ids,
            "verified": (
                burn.status_code == 200
                and history.status_code == 404
                and SESSION_ID not in session_ids
            ),
        }


async def execute() -> int:
    """Run the globally bounded test and always attempt verified session burn."""

    log: dict[str, Any] = {
        "session_id": SESSION_ID,
        "base_url": BASE_URL,
        "started_at": utc_now(),
        "execution_timeout_seconds": EXECUTION_TIMEOUT_SECONDS,
        "gateway": None,
        "initialization": None,
        "timed_out": False,
        "error": None,
        "turns": [],
        "burn": None,
    }
    execution_started = time.perf_counter()

    try:
        client_timeout = httpx.Timeout(None, connect=5.0)
        async with httpx.AsyncClient(timeout=client_timeout) as client:
            async with asyncio.timeout(EXECUTION_TIMEOUT_SECONDS):
                log["gateway"] = await verify_gateway(client)
                log["initialization"] = await initialize_session(client)

                for turn_number, prompt in enumerate(PROMPTS, start=1):
                    turn_log: dict[str, Any] = {
                        "turn": turn_number,
                        "prompt": prompt,
                        "status": "RUNNING",
                        "http_status": None,
                        "response_content_type": None,
                        "ttft_seconds": None,
                        "total_duration_seconds": None,
                        "events": [],
                        "raw_sse_lines": [],
                        "error": None,
                    }
                    log["turns"].append(turn_log)
                    await run_turn(client, turn_number, prompt, turn_log)
    except TimeoutError:
        log["timed_out"] = True
        log["error"] = "Global 45-second execution timeout expired"
    except (httpx.HTTPError, RuntimeError) as exc:
        log["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        log["execution_duration_seconds"] = time.perf_counter() - execution_started
        try:
            log["burn"] = await burn_and_verify()
        except httpx.HTTPError as exc:
            log["burn"] = {
                "verified": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
        log["finished_at"] = utc_now()
        LOG_PATH.write_text(json.dumps(log, indent=2) + "\n", encoding="utf-8")

    burn_verified = bool(log["burn"] and log["burn"].get("verified"))
    all_turns_completed = len(log["turns"]) == len(PROMPTS) and all(
        turn["status"] == "COMPLETED" for turn in log["turns"]
    )
    print(f"Log written: {LOG_PATH.resolve()}")
    print(f"Burn verified: {burn_verified}")
    return 0 if all_turns_completed and burn_verified else 1


def main() -> int:
    """Run the async manual test from a synchronous CLI entry point."""

    return asyncio.run(execute())


if __name__ == "__main__":
    raise SystemExit(main())
