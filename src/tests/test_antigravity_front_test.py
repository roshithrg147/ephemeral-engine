import asyncio
from typing import Any

import pytest

from src.tests import run_antigravity_front_test as bridge


class FakeEngine:
    async def run_query_reformulation_async(
        self, prompt: str, history: list[dict[str, str]]
    ) -> tuple[str, str, dict[str, int]]:
        assert prompt == "original"
        assert history == []
        return "search terms", "grounded request", {"total_tokens": 12}


class FakeAdapter:
    last_prompt: str = ""

    def __init__(self, **kwargs: Any) -> None:
        assert kwargs["command"] == "agy --sandbox"
        assert kwargs["prompt_arg"] == "-p"

    async def solve(self, prompt: str, session_id: str) -> dict[str, Any]:
        self.last_prompt = prompt
        assert session_id == bridge.SESSION_ID
        return {
            "success": True,
            "response_text": "downstream answer",
            "tokens_in": 10,
            "tokens_out": 4,
            "total_tokens": 14,
            "total_latency": 0.25,
            "exit_code": 0,
            "stderr": "",
        }


def test_run_probe_routes_grounded_prompt_to_antigravity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bridge, "SCEVMEngine", FakeEngine)
    monkeypatch.setattr(bridge, "AntiGravityCLIAdapter", FakeAdapter)

    result = asyncio.run(bridge.run_probe("original"))

    assert result["success"] is True
    assert result["grounded_llm_prompt"] == "grounded request"
    assert result["antigravity_response"] == "downstream answer"
    assert result["antigravity_estimated_usage"]["total_tokens"] == 14


def test_run_probe_stops_when_model_1_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    class FailedEngine:
        async def run_query_reformulation_async(
            self, prompt: str, history: list[dict[str, str]]
        ) -> tuple[str, str, None]:
            return prompt, prompt, None

    monkeypatch.setattr(bridge, "SCEVMEngine", FailedEngine)

    with pytest.raises(RuntimeError, match="Model 1 reformulation failed"):
        asyncio.run(bridge.run_probe("original"))
