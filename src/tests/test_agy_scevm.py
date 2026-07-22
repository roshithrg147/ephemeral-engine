import asyncio

import httpx
import pytest

from src.agy_scevm import (
    QueryResult,
    SCEVMGatewayClient,
    completion_script,
    decode_sse_data,
    execute_prompt,
)
from src.config import settings


def test_decode_sse_data_supports_json_and_plain_text() -> None:
    assert decode_sse_data('"answer"') == "answer"
    assert decode_sse_data("plain") == "plain"
    assert decode_sse_data("[DONE]") == "[DONE]"


def test_core_model_requires_exact_physical_model_usage() -> None:
    result = QueryResult(
        usage_report=[
            {
                "measurement_type": "exact",
                "status": "completed",
                "stage": "model_2_synthesis",
                "model": settings.MODEL_2_CORE,
            }
        ]
    )
    assert result.core_model_used is True


def test_completion_scripts_cover_supported_shells() -> None:
    assert "agy-scevm" in completion_script("bash")
    assert "agy-scevm" in completion_script("zsh")
    assert "agy-scevm" in completion_script("fish")


def test_gateway_query_parses_response_and_usage() -> None:
    body = "\n".join(
        [
            "event: response_content",
            'data: "hello"',
            "",
            "event: degradation",
            'data: {"degraded":true,"reasons":["model_2_candidate_failed"]}',
            "",
            "event: usage_report",
            (
                "data: "
                f'[{{"measurement_type":"exact","status":"completed",'
                f'"stage":"model_2_synthesis","model":"{settings.MODEL_2_CORE}"}}]'
            ),
            "",
            "event: done",
            "data: [DONE]",
            "",
        ]
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/agent/query"
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    async def scenario() -> QueryResult:
        async with httpx.AsyncClient(
            base_url="http://test", transport=httpx.MockTransport(handler)
        ) as client:
            return await SCEVMGatewayClient(client).query("session", "prompt")

    result = asyncio.run(scenario())
    assert result.response_text == "hello"
    assert result.degradation_reasons == ["model_2_candidate_failed"]
    assert result.core_model_used is False


def test_execute_prompt_burns_session_when_strict_core_fails() -> None:
    calls: list[str] = []

    class FakeGateway:
        async def initialize(self, session_id: str) -> None:
            calls.append(f"initialize:{session_id}")

        async def query(self, session_id: str, prompt: str) -> QueryResult:
            calls.append(f"query:{session_id}:{prompt}")
            return QueryResult(response_text="fallback")

        async def burn(self, session_id: str) -> None:
            calls.append(f"burn:{session_id}")

    with pytest.raises(RuntimeError, match="did not return exact usage"):
        asyncio.run(
            execute_prompt(
                FakeGateway(),
                session_id="test-session",
                prompt="hello",
                strict_core=True,
                keep_session=False,
            )
        )

    assert calls == [
        "initialize:test-session",
        "query:test-session:hello",
        "burn:test-session",
    ]
