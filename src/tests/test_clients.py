import asyncio
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from src.clients import IncompleteModelResponseError, NVIDIA_NIM_Client, get_model_price
from src.config import settings


def test_model_1_payload_uses_configured_nvidia_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "NVIDIA_API_KEY", "test-key")
    _, payload = NVIDIA_NIM_Client()._request_parts(
        settings.MODEL_1_KEY,
        "hello",
        None,
        False,
        128,
    )

    assert payload["model"] == settings.MODEL_1_FLASH
    assert payload["temperature"] == settings.MODEL_1_TEMPERATURE
    assert payload["top_p"] == settings.MODEL_1_TOP_P
    assert "chat_template_kwargs" not in payload


def test_model_2_payload_uses_configured_nvidia_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "NVIDIA_API_KEY", "test-key")
    _, payload = NVIDIA_NIM_Client()._request_parts(
        settings.MODEL_2_KEY,
        "hello",
        None,
        False,
        128,
    )

    assert payload["model"] == settings.MODEL_2_CORE
    assert payload["temperature"] == settings.MODEL_2_TEMPERATURE
    assert payload["top_p"] == settings.MODEL_2_TOP_P
    assert "chat_template_kwargs" not in payload
    assert "thinking" not in payload


@pytest.mark.parametrize("model_key", [settings.MODEL_2_KEY, settings.MODEL_2_CORE])
def test_model_2_identifiers_resolve_to_configured_nvidia_route(
    monkeypatch: pytest.MonkeyPatch,
    model_key: str,
) -> None:
    monkeypatch.setattr(settings, "NVIDIA_API_KEY", "test-key")

    model_name, temperature, top_p, api_key = NVIDIA_NIM_Client()._map_model(model_key)

    assert model_name == settings.MODEL_2_CORE
    assert temperature == settings.MODEL_2_TEMPERATURE
    assert top_p == settings.MODEL_2_TOP_P
    assert api_key == "test-key"


def test_model_2_route_uses_shared_nvidia_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "NVIDIA_API_KEY", "general-key")

    _, _, _, api_key = NVIDIA_NIM_Client()._map_model(settings.MODEL_2_KEY)

    assert api_key == "general-key"


def test_logical_core_role_uses_model_2_pricing() -> None:
    assert get_model_price(settings.MODEL_2_KEY) == {
        "input_1k": settings.MODEL_2_INPUT_PRICE_PER_1K,
        "output_1k": settings.MODEL_2_OUTPUT_PRICE_PER_1K,
    }


def test_unknown_model_identifier_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown NVIDIA NIM model key"):
        NVIDIA_NIM_Client()._map_model("unregistered-provider-model")


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
                "finish_reason": "stop",
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


def test_extract_response_text_rejects_truncated_visible_content() -> None:
    result = {
        "choices": [
            {
                "finish_reason": "length",
                "message": {"role": "assistant", "content": "partial answer"},
            }
        ]
    }

    with pytest.raises(IncompleteModelResponseError, match="truncated"):
        NVIDIA_NIM_Client._extract_response_text(result)


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
