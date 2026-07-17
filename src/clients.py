import asyncio
import concurrent.futures
import json
import logging
import threading
from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx

from src.config import settings

logger = logging.getLogger("SC-EVM.Clients")

NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NVIDIA_TIMEOUT = httpx.Timeout(connect=3.0, read=45.0, write=45.0, pool=5.0)
NVIDIA_LIMITS = httpx.Limits(max_connections=64, max_keepalive_connections=64)
DEFAULT_MAX_TOKENS = settings.NVIDIA_MAX_TOKENS
DEFAULT_MAX_RETRIES = settings.NVIDIA_MAX_RETRIES


class NIMResponse(str):
    def __new__(cls, text: str, usage: dict[str, Any] | None = None):
        obj = str.__new__(cls, text)
        obj.usage = usage or {}
        return obj


PRICE_TABLE = {
    "qwen/qwen3.5-122b-a10b": {"input_1k": 0.0003, "output_1k": 0.0004},
    "moonshotai/kimi-k2.6": {"input_1k": 0.0005, "output_1k": 0.0006},
}


def get_model_price(model_name: str) -> dict[str, float]:
    for key, val in PRICE_TABLE.items():
        if key in model_name or model_name in key:
            return val
    return {"input_1k": 0.0003, "output_1k": 0.0004}


class NVIDIA_NIM_Client:
    """Standardized pooled client for NVIDIA NIM chat completions."""

    _async_client: httpx.AsyncClient | None = None
    _client_lock: asyncio.Lock | None = None
    _background_loop: asyncio.AbstractEventLoop | None = None
    _background_thread: threading.Thread | None = None
    _background_lock = threading.Lock()

    @classmethod
    def _ensure_background_loop(cls) -> asyncio.AbstractEventLoop:
        with cls._background_lock:
            if cls._background_loop and cls._background_loop.is_running():
                return cls._background_loop

            loop = asyncio.new_event_loop()

            def run_loop() -> None:
                asyncio.set_event_loop(loop)
                loop.run_forever()

            thread = threading.Thread(target=run_loop, name="nvidia-nim-httpx-pool", daemon=True)
            thread.start()
            cls._background_loop = loop
            cls._background_thread = thread
            return loop

    @classmethod
    def _submit_to_pool(cls, coro) -> concurrent.futures.Future:
        loop = cls._ensure_background_loop()
        return asyncio.run_coroutine_threadsafe(coro, loop)

    @classmethod
    async def _get_async_client(cls) -> httpx.AsyncClient:
        if cls._client_lock is None:
            cls._client_lock = asyncio.Lock()

        if cls._async_client is None or cls._async_client.is_closed:
            async with cls._client_lock:
                if cls._async_client is None or cls._async_client.is_closed:
                    cls._async_client = httpx.AsyncClient(
                        timeout=NVIDIA_TIMEOUT,
                        limits=NVIDIA_LIMITS,
                    )
        return cls._async_client

    @classmethod
    async def aclose(cls) -> None:
        async def _close() -> None:
            if cls._async_client and not cls._async_client.is_closed:
                await cls._async_client.aclose()
                cls._async_client = None

        if cls._background_loop and cls._background_loop.is_running():
            try:
                await asyncio.wrap_future(cls._submit_to_pool(_close()))
            except Exception as e:
                logger.error(f"Error during async client close: {e}")

            cls._background_loop.call_soon_threadsafe(cls._background_loop.stop)
            if cls._background_thread and cls._background_thread.is_alive():
                cls._background_thread.join(timeout=2.0)
            cls._background_loop = None
            cls._background_thread = None

    def _map_model(self, model_key: str):
        """Maps a model key to the official NVIDIA NIM model name, parameters, and API key."""
        key_lower = model_key.lower()
        if "qwen" in key_lower:
            model_name = settings.MODEL_1_FLASH
            temp = 0.60
            top_p = 0.95
            api_key = settings.NVIDIA_API_KEY or settings.NVIDIA_API_KEY_QWEN
        elif "kimi" in key_lower or "kiwi" in key_lower or "moonshot" in key_lower:
            model_name = settings.MODEL_2_CORE
            temp = 1.00
            top_p = 1.00
            api_key = settings.NVIDIA_API_KEY or settings.NVIDIA_API_KEY_KIWI
        else:
            model_name = settings.MODEL_1_FLASH
            temp = 0.60
            top_p = 0.95
            api_key = settings.NVIDIA_API_KEY

        if not api_key:
            raise ValueError(f"NVIDIA API Key not found in environment for key: {model_key}")

        return model_name, temp, top_p, api_key

    def _prepare_payload(
        self,
        model_name: str,
        temp: float,
        top_p: float,
        prompt: str | list[dict[str, str]],
        system_prompt: str | None,
        stream: bool,
        max_tokens: int,
    ) -> dict[str, Any]:
        """Prepares the request payload for the NVIDIA completions endpoint."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if isinstance(prompt, list):
            for msg in prompt:
                role = msg.get("role", "user")
                if role == "model":
                    role = "assistant"
                messages.append({"role": role, "content": msg.get("content", "")})
        else:
            messages.append({"role": "user", "content": prompt})

        return {
            "model": model_name,
            "messages": messages,
            "temperature": temp,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "stream": stream,
        }

    def _request_parts(
        self,
        model_key: str,
        prompt: str | list[dict[str, str]],
        system_prompt: str | None,
        stream: bool,
        max_tokens: int | None,
    ) -> tuple[dict[str, str], dict[str, Any]]:
        model_name, temp, top_p, api_key = self._map_model(model_key)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = self._prepare_payload(
            model_name,
            temp,
            top_p,
            prompt,
            system_prompt,
            stream,
            max_tokens or DEFAULT_MAX_TOKENS,
        )
        return headers, payload

    @staticmethod
    def _extract_response_text(result: dict[str, Any]) -> str:
        """Extracts assistant text from NVIDIA/OpenAI-compatible payload variants."""
        choices = result.get("choices") or []
        if not choices:
            raise KeyError("choices")

        first_choice = choices[0] or {}
        message = first_choice.get("message") or {}

        def _flatten_reasoning(value: Any) -> str:
            if isinstance(value, str):
                return value.strip()
            if isinstance(value, list):
                parts: list[str] = []
                for item in value:
                    if isinstance(item, str):
                        if item.strip():
                            parts.append(item.strip())
                    elif isinstance(item, dict):
                        text = item.get("text") or item.get("content") or item.get("reasoning")
                        if isinstance(text, str) and text.strip():
                            parts.append(text.strip())
                return "\n".join(parts).strip()
            if isinstance(value, dict):
                text = value.get("text") or value.get("content") or value.get("reasoning")
                if isinstance(text, str) and text.strip():
                    return text.strip()
                return json.dumps(value)
            return ""

        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content

        reasoning_content = message.get("reasoning_content")
        flattened_reasoning = _flatten_reasoning(reasoning_content)
        if flattened_reasoning:
            return flattened_reasoning

        text = message.get("text")
        if isinstance(text, str) and text.strip():
            return text

        tool_calls = message.get("tool_calls")
        if tool_calls:
            return json.dumps(tool_calls)

        delta = first_choice.get("delta") or {}
        delta_content = delta.get("content")
        if isinstance(delta_content, str) and delta_content.strip():
            return delta_content

        raise KeyError(f"content fields missing: {list(message.keys())}")

    def call_llm(
        self,
        model_key: str,
        prompt: str | list[dict[str, str]],
        system_prompt: str | None = None,
        stream: bool = False,
        max_tokens: int | None = None,
    ) -> str | Iterator[str]:
        """Synchronously calls the pooled async NVIDIA client for legacy callers."""
        if stream:
            raise RuntimeError(
                "Synchronous streaming is disabled; use call_llm_async(..., stream=True)."
            )

        headers, payload = self._request_parts(
            model_key, prompt, system_prompt, stream=False, max_tokens=max_tokens
        )
        return self._submit_to_pool(
            self._call_with_retries(headers=headers, payload=payload)
        ).result()

    async def call_llm_async(
        self,
        model_key: str,
        prompt: str | list[dict[str, str]],
        system_prompt: str | None = None,
        stream: bool = False,
        max_tokens: int | None = None,
    ) -> str | AsyncIterator[str]:
        """Asynchronously calls the NVIDIA completions endpoint through the shared pool."""
        headers, payload = self._request_parts(
            model_key, prompt, system_prompt, stream, max_tokens=max_tokens
        )
        if stream:
            return self._stream_from_pool(headers=headers, payload=payload)
        return await asyncio.wrap_future(
            self._submit_to_pool(self._call_with_retries(headers=headers, payload=payload))
        )

    async def _stream_from_pool(
        self,
        *,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> AsyncIterator[str]:
        caller_loop = asyncio.get_running_loop()
        queue: asyncio.Queue[Any] = asyncio.Queue()
        sentinel = object()

        async def _produce() -> None:
            try:
                async for item in self._stream_response(headers=headers, payload=payload):
                    caller_loop.call_soon_threadsafe(queue.put_nowait, item)
            except Exception as exc:
                caller_loop.call_soon_threadsafe(queue.put_nowait, exc)
            finally:
                caller_loop.call_soon_threadsafe(queue.put_nowait, sentinel)

        self._submit_to_pool(_produce())

        while True:
            item = await queue.get()
            if item is sentinel:
                return
            if isinstance(item, Exception):
                raise item
            yield item

    async def _call_with_retries(
        self, *, headers: dict[str, str], payload: dict[str, Any]
    ) -> NIMResponse:
        max_retries = DEFAULT_MAX_RETRIES
        backoff = 1.0
        client = await self._get_async_client()

        for attempt in range(max_retries + 1):
            try:
                response = await client.post(NVIDIA_URL, headers=headers, json=payload)
                if response.status_code == 200:
                    result = response.json()
                    usage = result.get("usage")
                    try:
                        text = self._extract_response_text(result)
                        return NIMResponse(text, usage)
                    except Exception:
                        logger.error(
                            "NVIDIA response missing assistant text",
                            extra={"payload_keys": list(result.keys())},
                            exc_info=True,
                        )
                        raise

                if response.status_code in {429, 500, 502, 503, 504} and attempt < max_retries:
                    retry_after = response.headers.get("Retry-After")
                    if retry_after and retry_after.isdigit():
                        sleep_time = int(retry_after)
                    else:
                        sleep_time = backoff
                    logger.warning(
                        "NVIDIA returned retryable status",
                        extra={
                            "status_code": response.status_code,
                            "attempt": attempt + 1,
                            "max_retries": max_retries,
                        },
                    )
                    await asyncio.sleep(sleep_time)
                    backoff *= 2
                    continue

                raise RuntimeError(
                    f"NVIDIA API Error: Status {response.status_code}, Detail: {response.text}"
                )
            except (httpx.HTTPError, httpx.TimeoutException):
                if attempt < max_retries:
                    logger.warning(
                        "NVIDIA request failed; retrying",
                        extra={"attempt": attempt + 1, "max_retries": max_retries},
                        exc_info=True,
                    )
                    await asyncio.sleep(backoff)
                    backoff *= 2
                    continue
                raise

        raise RuntimeError("NVIDIA API request exhausted retries")

    async def _stream_response(
        self,
        *,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> AsyncIterator[str]:
        max_retries = DEFAULT_MAX_RETRIES
        backoff = 1.0
        client = await self._get_async_client()
        emitted_content = False

        for attempt in range(max_retries + 1):
            try:
                async with client.stream(
                    "POST", NVIDIA_URL, headers=headers, json=payload
                ) as response:
                    if response.status_code in {429, 500, 502, 503, 504} and attempt < max_retries:
                        retry_after = response.headers.get("Retry-After")
                        if retry_after and retry_after.isdigit():
                            sleep_time = int(retry_after)
                        else:
                            sleep_time = backoff
                        logger.warning(
                            "NVIDIA stream returned retryable status",
                            extra={
                                "status_code": response.status_code,
                                "attempt": attempt + 1,
                                "max_retries": max_retries,
                            },
                        )
                        await response.aread()
                        await asyncio.sleep(sleep_time)
                        backoff *= 2
                        continue

                    if response.status_code != 200:
                        detail = await response.aread()
                        raise RuntimeError(
                            f"NVIDIA API Error: Status {response.status_code}, Detail: {detail.decode('utf-8')}"
                        )

                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line or not line.startswith("data: "):
                            continue

                        data_str = line[len("data: ") :]
                        if data_str == "[DONE]":
                            return

                        try:
                            chunk = json.loads(data_str)
                            content = chunk["choices"][0]["delta"].get("content", "")
                        except (KeyError, IndexError, json.JSONDecodeError):
                            logger.warning(
                                "Malformed NVIDIA stream chunk skipped",
                                extra={"chunk": data_str},
                                exc_info=True,
                            )
                            continue

                        if content:
                            emitted_content = True
                            yield content
                return
            except (httpx.HTTPError, httpx.TimeoutException):
                if not emitted_content and attempt < max_retries:
                    logger.warning(
                        "NVIDIA stream failed; retrying",
                        extra={"attempt": attempt + 1, "max_retries": max_retries},
                        exc_info=True,
                    )
                    await asyncio.sleep(backoff)
                    backoff *= 2
                    continue
                raise
