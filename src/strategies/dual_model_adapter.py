from __future__ import annotations

import json
import time
from typing import Any

import httpx

from src.config import settings
from src.strategies.base import StrategyAdapter


class DualModelAdapter(StrategyAdapter):
    """
    Strategy adapter for the current dual-model SC-EVM behavior.

    In live mode, this proxies the existing FastAPI backend so the harness can
    benchmark the same behavior without coupling to route internals.
    """

    def __init__(self, base_url: str = settings.SC_EVM_BASE_URL, timeout: float = 400.0):
        super().__init__(name="dual_model")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=3.0, read=45.0, write=45.0, pool=5.0)
        )

    def _count_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)

    async def _consume_sse(
        self, client: httpx.AsyncClient, session_id: str, prompt: str
    ) -> dict[str, Any]:
        payload = {"session_id": session_id, "prompt": prompt}
        full_text = []
        current_event: str | None = None
        action_payload: dict[str, Any] | None = None
        token_usage: dict[str, Any] = {}
        intent: str | None = None
        start = time.perf_counter()

        async with client.stream(
            "POST",
            f"{self.base_url}/api/agent/query",
            json=payload,
            timeout=self.timeout,
        ) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                line = line.strip()
                if not line:
                    continue
                if line.startswith("event: "):
                    current_event = line[7:].strip()
                    continue
                if not line.startswith("data: "):
                    continue

                data_str = line[6:].strip()
                if current_event == "response_content":
                    try:
                        token = json.loads(data_str)
                        if isinstance(token, str):
                            full_text.append(token)
                    except json.JSONDecodeError:
                        full_text.append(data_str)
                elif current_event == "action":
                    try:
                        action_payload = json.loads(data_str)
                    except json.JSONDecodeError:
                        action_payload = {"type": "none"}
                elif current_event == "token_usage":
                    try:
                        token_usage = json.loads(data_str)
                    except json.JSONDecodeError:
                        token_usage = {}
                elif current_event == "intent":
                    try:
                        intent = json.loads(data_str)
                    except json.JSONDecodeError:
                        intent = data_str

        elapsed = time.perf_counter() - start
        response_text = "".join(full_text)
        tokens_in = int(token_usage.get("m1", self._count_tokens(prompt)))
        tokens_out = int(token_usage.get("m2", self._count_tokens(response_text)))
        success = bool(response_text.strip())

        return {
            "strategy": self.name,
            "session_id": session_id,
            "prompt": prompt,
            "response_text": response_text,
            "intent": intent,
            "action": action_payload,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "total_latency": elapsed,
            "success": success,
        }

    async def solve(self, prompt: str, session_id: str) -> dict[str, Any]:
        return await self._consume_sse(self._client, session_id, prompt)

    async def aclose(self) -> None:
        if not self._client.is_closed:
            await self._client.aclose()
