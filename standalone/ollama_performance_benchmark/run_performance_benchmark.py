#!/usr/bin/env python3
"""Run an isolated multi-turn performance benchmark against local Ollama."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

DEFAULT_MODEL = "gemma4:latest"
DEFAULT_TURNS = 50
DEFAULT_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_CONTEXT_LENGTH = 32_768
PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_PATH = PROJECT_DIR / "outputs" / "benchmark_results.json"
MODEL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]*$")

JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True)
class BenchmarkConfig:
    """Runtime configuration for one isolated Ollama benchmark."""

    model: str
    turns: int
    timeout_seconds: float
    max_output_tokens: int
    context_length: int
    temperature: float
    output_path: Path
    base_url: str = DEFAULT_BASE_URL

    def __post_init__(self) -> None:
        """Validate configuration before contacting Ollama."""
        if not MODEL_NAME_PATTERN.fullmatch(self.model):
            raise ValueError(f"Invalid Ollama model name: {self.model!r}")
        if self.turns < 1:
            raise ValueError("turns must be at least 1")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_output_tokens < 1:
            raise ValueError("max_output_tokens must be at least 1")
        if self.context_length < 1:
            raise ValueError("context_length must be at least 1")
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError("temperature must be between 0.0 and 2.0")


@dataclass(frozen=True, slots=True)
class OllamaResult:
    """Normalized result from one Ollama chat call."""

    text: str
    prompt_tokens: int | None
    output_tokens: int | None
    total_duration_ns: int | None
    load_duration_ns: int | None
    prompt_eval_duration_ns: int | None
    eval_duration_ns: int | None
    done_reason: str | None


class OllamaBackend:
    """Minimal async transport for the local Ollama API."""

    def __init__(
        self,
        config: BenchmarkConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        """Create a backend with an optionally injected test transport."""
        self._config = config
        self._client = httpx.AsyncClient(
            base_url=config.base_url.rstrip("/"),
            timeout=httpx.Timeout(config.timeout_seconds, connect=5.0),
            transport=transport,
        )

    async def __aenter__(self) -> OllamaBackend:
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

    async def verify_model(self) -> None:
        """Fail early unless the selected model is installed locally."""
        response = await self._client.get("/api/tags")
        if response.status_code != 200:
            raise RuntimeError(
                f"Ollama model listing failed with HTTP {response.status_code}: "
                f"{_response_error(response)}"
            )
        payload = response.json()
        models = payload.get("models") if isinstance(payload, dict) else None
        installed: set[str] = set()
        for item in models or []:
            if isinstance(item, dict):
                name = item.get("name")
                if isinstance(name, str):
                    installed.add(name)
        if self._config.model not in installed:
            raise RuntimeError(
                f"Ollama model {self._config.model!r} is not installed; "
                f"available={sorted(installed)}"
            )

    async def generate(self, messages: list[JsonObject]) -> OllamaResult:
        """Generate one non-streaming Ollama chat response."""
        response = await self._client.post(
            "/api/chat",
            json={
                "model": self._config.model,
                "messages": messages,
                "stream": False,
                "think": False,
                "keep_alive": "30m",
                "options": {
                    "temperature": self._config.temperature,
                    "num_predict": self._config.max_output_tokens,
                    "num_ctx": self._config.context_length,
                },
            },
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"Ollama request failed with HTTP {response.status_code}: "
                f"{_response_error(response)}"
            )
        return _parse_ollama_response(response.json())


def _response_error(response: httpx.Response) -> str:
    """Extract a bounded Ollama error message."""
    try:
        payload = response.json()
    except json.JSONDecodeError:
        return response.text[:1_000]
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, str):
            return error[:1_000]
    return json.dumps(payload)[:1_000]


def _parse_ollama_response(payload: JsonObject) -> OllamaResult:
    """Normalize Ollama text, usage, and timing metadata."""
    message = payload.get("message")
    text = message.get("content") if isinstance(message, dict) else None
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError(f"Ollama returned no response text: {payload!r}")
    return OllamaResult(
        text=text.strip(),
        prompt_tokens=_optional_int(payload.get("prompt_eval_count")),
        output_tokens=_optional_int(payload.get("eval_count")),
        total_duration_ns=_optional_int(payload.get("total_duration")),
        load_duration_ns=_optional_int(payload.get("load_duration")),
        prompt_eval_duration_ns=_optional_int(payload.get("prompt_eval_duration")),
        eval_duration_ns=_optional_int(payload.get("eval_duration")),
        done_reason=(
            str(payload["done_reason"]) if payload.get("done_reason") is not None else None
        ),
    )


def _optional_int(value: object) -> int | None:
    """Convert an integer-like JSON value while preserving missing values."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise RuntimeError(f"Ollama returned an invalid integer: {value!r}")
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"Ollama returned an invalid integer: {value!r}") from exc


def build_prompts(turns: int) -> list[str]:
    """Build the deterministic prompt sequence used by the original test."""
    return [f"Turn {turn}: Provide architectural status update." for turn in range(1, turns + 1)]


def _write_checkpoint(
    config: BenchmarkConfig,
    started_at: str,
    results: list[JsonObject],
) -> None:
    """Atomically checkpoint completed turns inside the standalone directory."""
    config.output_path.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "schema_version": "ollama-performance-benchmark-v1",
        "started_at": started_at,
        "updated_at": datetime.now(UTC).isoformat(),
        "backend": "ollama",
        "model": config.model,
        "context_length": config.context_length,
        "configured_turns": config.turns,
        "completed_turns": len(results),
        "results": results,
    }
    temporary_path = config.output_path.with_suffix(config.output_path.suffix + ".tmp")
    temporary_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    temporary_path.replace(config.output_path)


def _load_checkpoint(config: BenchmarkConfig) -> tuple[str, list[JsonObject]]:
    """Load and validate a compatible partial benchmark checkpoint."""
    try:
        document = json.loads(config.output_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot read checkpoint: {config.output_path}") from exc
    if not isinstance(document, dict):
        raise RuntimeError("Checkpoint root must be a JSON object")
    expected = {
        "model": config.model,
        "context_length": config.context_length,
        "configured_turns": config.turns,
    }
    for field, value in expected.items():
        if document.get(field) != value:
            raise RuntimeError(
                f"Checkpoint {field}={document.get(field)!r} does not match {value!r}"
            )
    started_at = document.get("started_at")
    results = document.get("results")
    if not isinstance(started_at, str) or not isinstance(results, list):
        raise RuntimeError("Checkpoint is missing started_at or results")
    if len(results) > config.turns or any(not isinstance(item, dict) for item in results):
        raise RuntimeError("Checkpoint results are malformed")
    return started_at, results


def _history_from_results(results: list[JsonObject]) -> list[JsonObject]:
    """Reconstruct Ollama chat history from completed checkpoint turns."""
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
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": response},
            ]
        )
    return history


async def run_benchmark(
    config: BenchmarkConfig,
    *,
    resume: bool = False,
) -> list[JsonObject]:
    """Run all turns sequentially while maintaining local chat history."""
    if resume:
        started_at, results = _load_checkpoint(config)
        history = _history_from_results(results)
    else:
        history = []
        results = []
        started_at = datetime.now(UTC).isoformat()

    async with OllamaBackend(config) as backend:
        await backend.verify_model()
        prompts = build_prompts(config.turns)
        for turn in range(len(results) + 1, config.turns + 1):
            prompt = prompts[turn - 1]
            request_messages = [*history, {"role": "user", "content": prompt}]
            started = time.perf_counter()
            result = await backend.generate(request_messages)
            latency = time.perf_counter() - started

            history.extend(
                [
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": result.text},
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
            print(f"Turn {turn}/{config.turns} complete ({latency:.2f}s)", flush=True)

    return results


def parse_args() -> argparse.Namespace:
    """Parse the standalone runner command line."""
    parser = argparse.ArgumentParser(
        description="Run an isolated multi-turn benchmark against local Ollama."
    )
    parser.add_argument("--turns", type=int, default=DEFAULT_TURNS)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--timeout-seconds", type=float, default=600.0)
    parser.add_argument("--max-output-tokens", type=int, default=512)
    parser.add_argument("--context-length", type=int, default=DEFAULT_CONTEXT_LENGTH)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--fresh", action="store_true")
    mode.add_argument("--resume", action="store_true")
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
            model=args.model,
            turns=args.turns,
            timeout_seconds=args.timeout_seconds,
            max_output_tokens=args.max_output_tokens,
            context_length=args.context_length,
            temperature=args.temperature,
            output_path=output_path,
            base_url=args.base_url,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    asyncio.run(run_benchmark(config, resume=args.resume))
    print(f"Results saved to {config.output_path}")


if __name__ == "__main__":
    main()
