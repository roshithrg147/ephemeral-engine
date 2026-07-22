#!/usr/bin/env python3
"""Run an isolated multi-turn performance benchmark against the Gemini API."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

DEFAULT_MODEL = "gemini-3.5-flash"
DEFAULT_TURNS = 50
DEFAULT_API_BASE_URL = "https://generativelanguage.googleapis.com"
PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_PATH = PROJECT_DIR / "outputs" / "benchmark_results.json"
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
MODEL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
RETRY_DELAY_PATTERN = re.compile(r"retry in ([0-9.]+)s", re.IGNORECASE)

JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True)
class BenchmarkConfig:
    """Runtime configuration for one isolated Gemini benchmark."""

    api_key: str
    model: str
    turns: int
    timeout_seconds: float
    max_output_tokens: int
    temperature: float
    output_path: Path
    api_base_url: str = DEFAULT_API_BASE_URL
    max_retries: int = 3
    request_interval_seconds: float = 25.0

    def __post_init__(self) -> None:
        """Validate configuration before any network request is made."""
        if not self.api_key.strip():
            raise ValueError("GEMINI_API_KEY is required")
        if not MODEL_NAME_PATTERN.fullmatch(self.model):
            raise ValueError(f"Invalid Gemini model name: {self.model!r}")
        if self.turns < 1:
            raise ValueError("turns must be at least 1")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_output_tokens < 1:
            raise ValueError("max_output_tokens must be at least 1")
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError("temperature must be between 0.0 and 2.0")
        if self.request_interval_seconds < 0:
            raise ValueError("request_interval_seconds cannot be negative")
        if self.max_retries < 0:
            raise ValueError("max_retries cannot be negative")


@dataclass(frozen=True, slots=True)
class GeminiResult:
    """Normalized result from one Gemini generateContent call."""

    text: str
    prompt_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    finish_reason: str | None


class GeminiBackend:
    """Minimal async Gemini Developer API transport."""

    def __init__(
        self,
        config: BenchmarkConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        """Create a backend with an optionally injected test transport."""
        self._config = config
        self._client = httpx.AsyncClient(
            base_url=config.api_base_url.rstrip("/"),
            timeout=httpx.Timeout(config.timeout_seconds, connect=10.0),
            transport=transport,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": config.api_key,
            },
        )

    async def __aenter__(self) -> GeminiBackend:
        """Enter the backend context."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def generate(self, contents: list[JsonObject]) -> GeminiResult:
        """Generate one response, retrying transient provider failures."""
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": self._config.temperature,
                "maxOutputTokens": self._config.max_output_tokens,
            },
        }
        endpoint = f"/v1beta/models/{self._config.model}:generateContent"

        for attempt in range(self._config.max_retries + 1):
            try:
                response = await self._client.post(endpoint, json=payload)
            except (httpx.TimeoutException, httpx.TransportError):
                if attempt == self._config.max_retries:
                    raise
                await asyncio.sleep(2**attempt)
                continue

            if response.status_code in RETRYABLE_STATUS_CODES and attempt < self._config.max_retries:
                await asyncio.sleep(_retry_delay(response, attempt))
                continue
            if response.status_code != 200:
                raise RuntimeError(
                    f"Gemini request failed with HTTP {response.status_code}: "
                    f"{_response_error(response)}"
                )

            return _parse_gemini_response(response.json())

        raise RuntimeError("Gemini retry loop ended unexpectedly")


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    """Return a bounded provider-directed or exponential retry delay."""
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return min(max(float(retry_after), 0.0), 60.0)
        except ValueError:
            pass
    match = RETRY_DELAY_PATTERN.search(response.text)
    if match:
        return min(max(float(match.group(1)) + 1.0, 1.0), 60.0)
    return float(2**attempt)


def _response_error(response: httpx.Response) -> str:
    """Extract a useful provider error without exposing request headers."""
    try:
        payload = response.json()
    except json.JSONDecodeError:
        return response.text[:1_000]
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str):
                return message[:1_000]
    return json.dumps(payload)[:1_000]


def _parse_gemini_response(payload: JsonObject) -> GeminiResult:
    """Normalize Gemini text, usage, and completion metadata."""
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        block_reason = None
        prompt_feedback = payload.get("promptFeedback")
        if isinstance(prompt_feedback, dict):
            block_reason = prompt_feedback.get("blockReason")
        raise RuntimeError(f"Gemini returned no candidates; block_reason={block_reason!r}")

    candidate = candidates[0]
    if not isinstance(candidate, dict):
        raise RuntimeError("Gemini returned a malformed candidate")
    content = candidate.get("content")
    parts = content.get("parts") if isinstance(content, dict) else None
    text_parts = [
        part["text"]
        for part in parts or []
        if isinstance(part, dict) and isinstance(part.get("text"), str)
    ]
    text = "".join(text_parts).strip()
    if not text:
        raise RuntimeError(
            f"Gemini returned no text; finish_reason={candidate.get('finishReason')!r}"
        )

    usage = payload.get("usageMetadata")
    usage = usage if isinstance(usage, dict) else {}
    return GeminiResult(
        text=text,
        prompt_tokens=_optional_int(usage.get("promptTokenCount")),
        output_tokens=_optional_int(usage.get("candidatesTokenCount")),
        total_tokens=_optional_int(usage.get("totalTokenCount")),
        finish_reason=(
            str(candidate["finishReason"]) if candidate.get("finishReason") is not None else None
        ),
    )


def _optional_int(value: object) -> int | None:
    """Convert an integer-like JSON value while preserving missing values."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise RuntimeError(f"Gemini returned an invalid token count: {value!r}")
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"Gemini returned an invalid token count: {value!r}") from exc


def build_prompts(turns: int) -> list[str]:
    """Build the same deterministic prompt sequence used by the original test."""
    return [f"Turn {turn}: Provide architectural status update." for turn in range(1, turns + 1)]


def _write_checkpoint(
    config: BenchmarkConfig,
    started_at: str,
    results: list[JsonObject],
) -> None:
    """Atomically write the benchmark checkpoint inside the standalone directory."""
    config.output_path.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "schema_version": "gemini-performance-benchmark-v1",
        "started_at": started_at,
        "updated_at": datetime.now(UTC).isoformat(),
        "backend": "gemini-developer-api",
        "model": config.model,
        "configured_turns": config.turns,
        "completed_turns": len(results),
        "results": results,
    }
    temporary_path = config.output_path.with_suffix(config.output_path.suffix + ".tmp")
    temporary_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    temporary_path.replace(config.output_path)


def _load_checkpoint(config: BenchmarkConfig) -> tuple[str, list[JsonObject]]:
    """Load and validate a checkpoint before resuming a partially completed run."""
    try:
        document = json.loads(config.output_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot read checkpoint: {config.output_path}") from exc
    if not isinstance(document, dict):
        raise RuntimeError("Checkpoint root must be a JSON object")
    if document.get("model") != config.model:
        raise RuntimeError(
            f"Checkpoint model {document.get('model')!r} does not match {config.model!r}"
        )
    if document.get("configured_turns") != config.turns:
        raise RuntimeError(
            "Checkpoint configured_turns does not match the requested turn count"
        )
    started_at = document.get("started_at")
    results = document.get("results")
    if not isinstance(started_at, str) or not isinstance(results, list):
        raise RuntimeError("Checkpoint is missing started_at or results")
    if len(results) > config.turns or any(not isinstance(item, dict) for item in results):
        raise RuntimeError("Checkpoint results are malformed")
    return started_at, results


def _history_from_results(results: list[JsonObject]) -> list[JsonObject]:
    """Reconstruct Gemini chat history from completed checkpoint turns."""
    history: list[JsonObject] = []
    for expected_turn, result in enumerate(results, start=1):
        if result.get("turn") != expected_turn:
            raise RuntimeError("Checkpoint turns are not contiguous")
        prompt = result.get("prompt")
        response = result.get("response")
        if not isinstance(prompt, str) or not isinstance(response, str) or not response:
            raise RuntimeError(f"Checkpoint turn {expected_turn} has invalid content")
        history.extend(
            [
                {"role": "user", "parts": [{"text": prompt}]},
                {"role": "model", "parts": [{"text": response}]},
            ]
        )
    return history


async def run_benchmark(
    config: BenchmarkConfig,
    *,
    resume: bool = False,
) -> list[JsonObject]:
    """Run all turns sequentially while maintaining local Gemini chat history."""
    if resume:
        started_at, results = _load_checkpoint(config)
        history = _history_from_results(results)
    else:
        history = []
        results = []
        started_at = datetime.now(UTC).isoformat()

    async with GeminiBackend(config) as backend:
        prompts = build_prompts(config.turns)
        for turn in range(len(results) + 1, config.turns + 1):
            if results and config.request_interval_seconds:
                await asyncio.sleep(config.request_interval_seconds)
            prompt = prompts[turn - 1]
            request_contents = [*history, {"role": "user", "parts": [{"text": prompt}]}]
            started = time.perf_counter()
            result = await backend.generate(request_contents)
            latency = time.perf_counter() - started

            history.extend(
                [
                    {"role": "user", "parts": [{"text": prompt}]},
                    {"role": "model", "parts": [{"text": result.text}]},
                ]
            )
            results.append(
                {
                    "turn": turn,
                    "prompt": prompt,
                    "latency_seconds": latency,
                    "response": result.text,
                    "usage": asdict(result),
                }
            )
            _write_checkpoint(config, started_at, results)
            print(f"Turn {turn}/{config.turns} complete ({latency:.2f}s)")

    return results


def parse_args() -> argparse.Namespace:
    """Parse the standalone runner command line."""
    parser = argparse.ArgumentParser(
        description="Run an isolated multi-turn benchmark against the Gemini Developer API."
    )
    parser.add_argument("--turns", type=int, default=DEFAULT_TURNS)
    parser.add_argument(
        "--model",
        default=os.environ.get("GEMINI_MODEL", DEFAULT_MODEL),
    )
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--max-output-tokens", type=int, default=1_024)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument(
        "--request-interval-seconds",
        type=float,
        default=25.0,
        help="Minimum delay between calls; defaults to 25 seconds for free-tier pacing.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--fresh",
        action="store_true",
        help="Allow an existing output checkpoint to be replaced.",
    )
    mode.add_argument(
        "--resume",
        action="store_true",
        help="Resume from a compatible existing checkpoint.",
    )
    return parser.parse_args()


def main() -> None:
    """Validate configuration and execute the benchmark."""
    args = parse_args()
    output_path = args.output.expanduser().resolve()
    if args.resume and not output_path.exists():
        raise SystemExit(f"Cannot resume; checkpoint does not exist: {output_path}")
    if output_path.exists() and not args.fresh and not args.resume:
        raise SystemExit(
            f"Output already exists: {output_path}. Pass --resume or --fresh."
        )

    try:
        config = BenchmarkConfig(
            api_key=os.environ.get("GEMINI_API_KEY", ""),
            model=args.model,
            turns=args.turns,
            timeout_seconds=args.timeout_seconds,
            max_output_tokens=args.max_output_tokens,
            temperature=args.temperature,
            output_path=output_path,
            request_interval_seconds=args.request_interval_seconds,
            max_retries=args.max_retries,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    asyncio.run(run_benchmark(config, resume=args.resume))
    print(f"Results saved to {config.output_path}")


if __name__ == "__main__":
    main()
