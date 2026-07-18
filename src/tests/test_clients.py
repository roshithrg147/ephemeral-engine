import asyncio
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from src.clients import IncompleteModelResponseError, NVIDIA_NIM_Client
from src.config import settings


def test_qwen_payload_disables_reasoning_mode() -> None:
    payload = NVIDIA_NIM_Client()._prepare_payload(
        "qwen/qwen3.5-122b-a10b",
        0.6,
        0.95,
        "hello",
        None,
        False,
        128,
    )

    assert payload["chat_template_kwargs"] == {"enable_thinking": False}
    assert payload["temperature"] == 0.7
    assert payload["top_p"] == 0.8


def test_kimi_payload_disables_reasoning_mode() -> None:
    payload = NVIDIA_NIM_Client()._prepare_payload(
        "moonshotai/kimi-k2.6",
        1.0,
        1.0,
        "hello",
        None,
        False,
        128,
    )

    assert payload["thinking"] == {"type": "disabled"}


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ([{"type": "text", "text": "answer"}], "answer"),
        ({"text": "answer"}, "answer"),
        (["first", {"content": "second"}], "first\nsecond"),
    ],
)
def test_extract_response_text_supports_structured_content(content: Any, expected: str) -> None:
    result = {"choices": [{"message": {"role": "assistant", "content": content}}]}

    assert NVIDIA_NIM_Client._extract_response_text(result) == expected


def test_extract_response_text_rejects_reasoning_only_response() -> None:
    result = {
        "choices": [
            {
                "finish_reason": "length",
                "message": {
                    "role": "assistant",
                    "reasoning_content": "private chain of thought",
                },
            }
        ]
    }

    with pytest.raises(IncompleteModelResponseError) as error:
        NVIDIA_NIM_Client._extract_response_text(result)

    assert "private chain of thought" not in str(error.value)
    assert "reasoning_present=True" in str(error.value)


def test_incomplete_response_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    async def exercise() -> None:
        response = httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "length",
                        "message": {
                            "role": "assistant",
                            "reasoning_content": "private chain of thought",
                        },
                    }
                ]
            },
        )
        http_client = AsyncMock()
        http_client.post.return_value = response
        client = NVIDIA_NIM_Client()
        monkeypatch.setattr(client, "_get_async_client", AsyncMock(return_value=http_client))

        with pytest.raises(IncompleteModelResponseError):
            await client._call_with_retries(headers={}, payload={})

        http_client.post.assert_awaited_once()

    asyncio.run(exercise())


def test_read_timeout_uses_dedicated_retry_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    async def exercise() -> None:
        http_client = AsyncMock()
        http_client.post.side_effect = httpx.ReadTimeout("provider stalled")
        sleep = AsyncMock()
        client = NVIDIA_NIM_Client()
        monkeypatch.setattr(client, "_get_async_client", AsyncMock(return_value=http_client))
        monkeypatch.setattr("src.clients.asyncio.sleep", sleep)
        monkeypatch.setattr(settings, "NVIDIA_READ_TIMEOUT_RETRIES", 1)

        with pytest.raises(httpx.ReadTimeout):
            await client._call_with_retries(headers={}, payload={})

        assert http_client.post.await_count == 2
        sleep.assert_awaited_once_with(1.0)

    asyncio.run(exercise())
