import asyncio
import json
from pathlib import Path

import httpx
import pytest

from run_performance_benchmark import (
    BenchmarkConfig,
    GeminiBackend,
    _parse_gemini_response,
)


def make_config(tmp_path: Path) -> BenchmarkConfig:
    return BenchmarkConfig(
        api_key="test-key",
        model="gemini-3.5-flash",
        turns=1,
        timeout_seconds=10.0,
        max_output_tokens=128,
        temperature=0.0,
        output_path=tmp_path / "result.json",
        api_base_url="https://test.invalid",
        max_retries=0,
        request_interval_seconds=0.0,
    )


def test_backend_uses_gemini_contract_without_exposing_key(tmp_path: Path) -> None:
    async def exercise() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/v1beta/models/gemini-3.5-flash:generateContent"
            assert request.headers["x-goog-api-key"] == "test-key"
            payload = json.loads(request.content)
            assert payload["contents"] == [
                {"role": "user", "parts": [{"text": "hello"}]}
            ]
            return httpx.Response(
                200,
                json={
                    "candidates": [
                        {
                            "content": {"parts": [{"text": "hello back"}]},
                            "finishReason": "STOP",
                        }
                    ],
                    "usageMetadata": {
                        "promptTokenCount": 2,
                        "candidatesTokenCount": 3,
                        "totalTokenCount": 5,
                    },
                },
            )

        config = make_config(tmp_path)
        async with GeminiBackend(
            config,
            transport=httpx.MockTransport(handler),
        ) as backend:
            result = await backend.generate(
                [{"role": "user", "parts": [{"text": "hello"}]}]
            )

        assert result.text == "hello back"
        assert result.total_tokens == 5

    asyncio.run(exercise())


def test_backend_surfaces_provider_error(tmp_path: Path) -> None:
    async def exercise() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                400,
                json={"error": {"message": "API key not valid"}},
            )

        config = make_config(tmp_path)
        async with GeminiBackend(
            config,
            transport=httpx.MockTransport(handler),
        ) as backend:
            with pytest.raises(RuntimeError, match="API key not valid"):
                await backend.generate(
                    [{"role": "user", "parts": [{"text": "hello"}]}]
                )

    asyncio.run(exercise())


def test_parser_rejects_blocked_or_empty_response() -> None:
    with pytest.raises(RuntimeError, match="SAFETY"):
        _parse_gemini_response(
            {"promptFeedback": {"blockReason": "SAFETY"}, "candidates": []}
        )
