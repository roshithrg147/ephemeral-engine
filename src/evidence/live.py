from __future__ import annotations

import json
import os
import time
from typing import Any

import httpx

from src.config import settings

from .baselines import (
    Baseline,
    ContextResult,
    FullReplay,
    RollingSummary,
    SlidingWindow,
    StrategyState,
    TopKRetrieval,
)
from .models import Turn


class NvidiaReasoner:
    # ponytail: current ceiling is the implemented NVIDIA transport; add providers only after RFC-0004.
    provider = "nvidia-nim"
    version = "1.0.0"

    def __init__(self, *, model: str | None = None, timeout: float = 45.0, max_retries: int = 3):
        self.model = model or settings.MODEL_1_FLASH
        self.timeout = timeout
        self.max_retries = max_retries
        self.last_metadata: dict[str, Any] = {}
        self._client = httpx.Client(timeout=timeout)

    def complete(self, *, prompt: str, context: str, seed: int) -> str:
        self.last_metadata = {}
        api_key = settings.NVIDIA_API_KEY_QWEN or settings.NVIDIA_API_KEY
        if not api_key:
            raise RuntimeError("NVIDIA API key is not configured")
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": f"Context:\n{context}\n\nPrompt:\n{prompt}"}],
            "temperature": 0.0,
            "top_p": 1.0,
            "max_tokens": 512,
            "stream": False,
            "seed": seed,
        }
        started = time.perf_counter()
        attempts = []
        response = None
        for attempt in range(self.max_retries + 1):
            attempt_start = time.perf_counter()
            try:
                response = self._client.post(
                    "https://integrate.api.nvidia.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                attempts.append(
                    {
                        "attempt": attempt + 1,
                        "status": response.status_code,
                        "seconds": time.perf_counter() - attempt_start,
                    }
                )
                if response.status_code == 200:
                    break
                if (
                    response.status_code not in {429, 500, 502, 503, 504}
                    or attempt == self.max_retries
                ):
                    response.raise_for_status()
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                attempts.append(
                    {
                        "attempt": attempt + 1,
                        "error": type(exc).__name__,
                        "seconds": time.perf_counter() - attempt_start,
                    }
                )
                if attempt == self.max_retries:
                    self.last_metadata = {
                        "attempts": attempts,
                        "latency_seconds": time.perf_counter() - started,
                    }
                    if isinstance(exc, httpx.TimeoutException):
                        raise TimeoutError(str(exc)) from exc
                    raise
            time.sleep(2**attempt)
        if response is None:
            raise RuntimeError("provider produced no response")
        body = response.json()
        text = body["choices"][0]["message"].get("content") or body["choices"][0]["message"].get(
            "reasoning_content"
        )
        if not text:
            raise RuntimeError("provider response contained no completion text")
        usage = body.get("usage")
        self.last_metadata = {
            "attempts": attempts,
            "latency_seconds": time.perf_counter() - started,
            "usage": _usage_record(usage, prompt + context, str(text)),
            "provider_request_id": response.headers.get("x-request-id"),
        }
        return str(text)

    def close(self) -> None:
        self._client.close()


def _usage_record(provider_usage: dict | None, input_text: str, output_text: str) -> dict[str, Any]:
    calculated = {
        "input_tokens": max(1, len(input_text) // 4),
        "output_tokens": max(1, len(output_text) // 4),
        "method": "character_estimate",
    }
    input_rate = os.getenv("EVIDENCE_INPUT_USD_PER_M")
    output_rate = os.getenv("EVIDENCE_OUTPUT_USD_PER_M")
    reported = None
    cost = None
    if provider_usage:
        reported = {
            "input_tokens": provider_usage.get("prompt_tokens"),
            "output_tokens": provider_usage.get("completion_tokens"),
            "total_tokens": provider_usage.get("total_tokens"),
        }
        if (
            input_rate
            and output_rate
            and reported["input_tokens"] is not None
            and reported["output_tokens"] is not None
        ):
            cost = {
                "currency": "USD",
                "pricing_version": os.getenv("EVIDENCE_PRICING_VERSION", "operator-supplied"),
                "input": reported["input_tokens"] * float(input_rate) / 1_000_000,
                "output": reported["output_tokens"] * float(output_rate) / 1_000_000,
            }
            cost["total"] = cost["input"] + cost["output"]
    return {
        "provider_reported": reported,
        "calculated": calculated,
        "estimated": None,
        "cost": cost,
        "cost_missing_reason": None if cost else "pricing or provider usage unavailable",
    }


class LiveSCEVMBaseline(Baseline):
    def __init__(self, reasoner: NvidiaReasoner, *, base_url: str, graphify_enabled: bool):
        super().__init__(reasoner)
        self.base_url = base_url.rstrip("/")
        self.graphify_enabled = graphify_enabled
        self.strategy_id = "sc_evm_with_graphify" if graphify_enabled else "sc_evm_without_graphify"
        self._client = httpx.Client(timeout=httpx.Timeout(400.0, connect=5.0))
        self._initialized: set[str] = set()

    def build_context(self, turn: Turn, state: StrategyState) -> ContextResult:
        raise NotImplementedError("live SC-EVM context is built by the backend")

    def answer(self, turn: Turn, state: StrategyState, seed: int) -> tuple[str, ContextResult]:
        del seed
        if state.session_id not in self._initialized:
            response = self._client.post(
                f"{self.base_url}/api/session/initialize", json={"session_id": state.session_id}
            )
            response.raise_for_status()
            self._initialized.add(state.session_id)
        started = time.perf_counter()
        event = None
        completion = []
        events: dict[str, Any] = {}
        first_content = None
        with self._client.stream(
            "POST",
            f"{self.base_url}/api/agent/query",
            json={
                "session_id": state.session_id,
                "prompt": turn.prompt,
                "graphify_enabled": self.graphify_enabled,
            },
        ) as response:
            response.raise_for_status()
            for raw_line in response.iter_lines():
                line = raw_line.strip()
                if line.startswith("event: "):
                    event = line[7:]
                elif line.startswith("data: ") and event:
                    value = line[6:]
                    try:
                        parsed = json.loads(value)
                    except json.JSONDecodeError:
                        parsed = value
                    if event == "response_content" and isinstance(parsed, str):
                        if first_content is None:
                            first_content = time.perf_counter()
                        completion.append(parsed)
                    elif event == "error":
                        raise RuntimeError(f"SC-EVM error event: {parsed}")
                    else:
                        events[event] = parsed
        text = "".join(completion)
        retrieved = events.get("retrieved_context") or []
        context_text = retrieved[0] if isinstance(retrieved, list) and retrieved else ""
        graph_status = (
            "available"
            if "<graphify_context>" in context_text
            else ("empty" if self.graphify_enabled else "disabled")
        )
        token_usage = events.get("token_usage") or {}
        self.last_call_metadata = {
            "latency_seconds": time.perf_counter() - started,
            "time_to_first_meaningful_response_seconds": (first_content - started)
            if first_content
            else None,
            "attempts": [{"attempt": 1, "status": 200}],
            "usage": {
                "provider_reported": None,
                "calculated": None,
                "estimated": {
                    "input_tokens": token_usage.get("m1"),
                    "output_tokens": token_usage.get("m2"),
                },
                "cost": None,
                "cost_missing_reason": "SC-EVM SSE exposes estimates, not provider billing usage",
            },
            "indexing": {"status": "scheduled", "lag_seconds": None},
        }
        state.history.append((turn.prompt, text))
        context = ContextResult(
            context_text,
            {
                "mode": "live_sc_evm",
                "query_reformulation": events.get("query_reformulation"),
                "retrieved_context": retrieved,
            },
            {"enabled": self.graphify_enabled, "status": graph_status},
            [{"source_id": "live-admitted-context", "admitted": bool(context_text)}],
        )
        return text, context

    def cleanup(self, state: StrategyState) -> dict:
        try:
            response = self._client.delete(f"{self.base_url}/api/session/burn/{state.session_id}")
            status = "completed" if response.status_code == 200 else "failed"
            detail = response.text
        except Exception as exc:
            status = "failed"
            detail = repr(exc)
        self._initialized.discard(state.session_id)
        state.history.clear()
        return {"attempted": True, "status": status, "detail": detail}

    def close(self) -> None:
        self._client.close()


def local_onnx_vectorizer():
    from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

    embed = ONNXMiniLM_L6_V2()
    return lambda text: list(embed([text])[0])


def required_live_baselines(reasoner: NvidiaReasoner, *, base_url: str) -> list[Baseline]:
    vectorizer = local_onnx_vectorizer()
    return [
        FullReplay(reasoner),
        SlidingWindow(reasoner),
        RollingSummary(reasoner),
        TopKRetrieval(reasoner, vectorizer=vectorizer),
        LiveSCEVMBaseline(reasoner, base_url=base_url, graphify_enabled=False),
        LiveSCEVMBaseline(reasoner, base_url=base_url, graphify_enabled=True),
    ]
