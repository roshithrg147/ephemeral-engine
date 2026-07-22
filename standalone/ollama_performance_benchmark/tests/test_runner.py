import asyncio
import json
from pathlib import Path

import httpx
import pytest

from run_performance_benchmark import (
    BenchmarkConfig,
    OllamaBackend,
    _parse_ollama_response,
)


def make_config(tmp_path: Path) -> BenchmarkConfig:
    return BenchmarkConfig(
        model="gemma4:latest",
        turns=1,
        timeout_seconds=10.0,
        max_output_tokens=128,
        context_length=32_768,
        temperature=0.0,
        output_path=tmp_path / "result.json",
        base_url="http://test",
    )


def test_backend_uses_ollama_chat_contract(tmp_path: Path) -> None:
    async def exercise() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/api/tags":
                return httpx.Response(200, json={"models": [{"name": "gemma4:latest"}]})
            payload = json.loads(request.content)
            assert request.url.path == "/api/chat"
            assert payload["model"] == "gemma4:latest"
            assert payload["messages"] == [{"role": "user", "content": "hello"}]
            assert payload["stream"] is False
            assert payload["think"] is False
            assert payload["options"]["num_ctx"] == 32_768
            return httpx.Response(
                200,
                json={
                    "message": {"role": "assistant", "content": "hello back"},
                    "done_reason": "stop",
                    "prompt_eval_count": 2,
                    "eval_count": 3,
                    "total_duration": 10,
                },
            )

        config = make_config(tmp_path)
        async with OllamaBackend(
            config,
            transport=httpx.MockTransport(handler),
        ) as backend:
            await backend.verify_model()
            result = await backend.generate([{"role": "user", "content": "hello"}])

        assert result.text == "hello back"
        assert result.output_tokens == 3

    asyncio.run(exercise())


def test_backend_rejects_missing_model(tmp_path: Path) -> None:
    async def exercise() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"models": [{"name": "other:latest"}]})

        config = make_config(tmp_path)
        async with OllamaBackend(
            config,
            transport=httpx.MockTransport(handler),
        ) as backend:
            with pytest.raises(RuntimeError, match="not installed"):
                await backend.verify_model()

    asyncio.run(exercise())


def test_parser_rejects_empty_response() -> None:
    with pytest.raises(RuntimeError, match="no response text"):
        _parse_ollama_response({"message": {"content": ""}})
