import asyncio
import concurrent.futures
import json
import logging
import threading
import time
from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx

from src.config import settings

logger = logging.getLogger("SC-EVM.Clients")

NVIDIA_TIMEOUT = httpx.Timeout(
    connect=settings.NVIDIA_CONNECT_TIMEOUT_SECONDS,
    read=settings.NVIDIA_READ_TIMEOUT_SECONDS,
    write=settings.NVIDIA_WRITE_TIMEOUT_SECONDS,
    pool=settings.NVIDIA_POOL_TIMEOUT_SECONDS,
)
NVIDIA_LIMITS = httpx.Limits(
    max_connections=settings.NVIDIA_MAX_CONNECTIONS,
    max_keepalive_connections=settings.NVIDIA_MAX_KEEPALIVE_CONNECTIONS,
)
DEFAULT_MAX_TOKENS = settings.NVIDIA_MAX_TOKENS
DEFAULT_MAX_RETRIES = settings.NVIDIA_MAX_RETRIES


class NIMResponse(str):
    usage: dict[str, Any]
    provider_metadata: dict[str, Any]

    def __new__(
        cls,
        text: str,
        usage: dict[str, Any] | None = None,
        provider_metadata: dict[str, Any] | None = None,
    ):
        obj = str.__new__(cls, text)
        obj.usage = usage or {}
        obj.provider_metadata = provider_metadata or {}
        return obj


class IncompleteModelResponseError(RuntimeError):
    """The provider completed a request without returning user-facing text."""


def get_model_price(model_name: str) -> dict[str, float]:
    """Return configured pricing for a physical model ID or logical role alias."""
    normalized = model_name.strip().lower()
    model_2_names = {
        settings.MODEL_2_KEY.lower(),
        settings.MODEL_2_CORE.lower(),
    }
    if normalized in model_2_names:
        return {
            "input_1k": settings.MODEL_2_INPUT_PRICE_PER_1K,
            "output_1k": settings.MODEL_2_OUTPUT_PRICE_PER_1K,
        }
    return {
        "input_1k": settings.MODEL_1_INPUT_PRICE_PER_1K,
        "output_1k": settings.MODEL_1_OUTPUT_PRICE_PER_1K,
    }


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

    def _map_model(self, model_key: str) -> tuple[str, float, float, str]:
        """Map a configured logical role or physical ID to one NVIDIA NIM route."""
        normalized_key = model_key.strip().lower()
        model_1_keys = {
            settings.MODEL_1_KEY.lower(),
            settings.MODEL_1_FLASH.lower(),
        }
        model_2_keys = {
            settings.MODEL_2_KEY.lower(),
            settings.MODEL_2_CORE.lower(),
        }

        if normalized_key in model_1_keys:
            model_name = settings.MODEL_1_FLASH
            temp = settings.MODEL_1_TEMPERATURE
            top_p = settings.MODEL_1_TOP_P
            api_key = settings.NVIDIA_API_KEY
        elif normalized_key in model_2_keys:
            model_name = settings.MODEL_2_CORE
            temp = settings.MODEL_2_TEMPERATURE
            top_p = settings.MODEL_2_TOP_P
            api_key = settings.NVIDIA_API_KEY
        else:
            supported = sorted(model_1_keys | model_2_keys)
            raise ValueError(
                f"Unknown NVIDIA NIM model key {model_key!r}; configured keys: {supported}"
            )

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
        seed: int | None = None,
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

        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": temp,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        if seed is not None:
            payload["seed"] = seed
        return payload

    def _request_parts(
        self,
        model_key: str,
        prompt: str | list[dict[str, str]],
        system_prompt: str | None,
        stream: bool,
        max_tokens: int | None,
        seed: int | None = None,
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
            seed,
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
        finish_reason = first_choice.get("finish_reason")

        if finish_reason == "length":
            raise IncompleteModelResponseError(
                "provider response was truncated (finish_reason='length')"
            )

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

        flattened_content = _flatten_reasoning(content)
        if flattened_content:
            return flattened_content

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

        choice_text = first_choice.get("text")
        if isinstance(choice_text, str) and choice_text.strip():
            return choice_text

        reasoning_present = bool(_flatten_reasoning(message.get("reasoning_content")))
        raise IncompleteModelResponseError(
            "provider returned no user-facing assistant content "
            f"(finish_reason={finish_reason!r}, reasoning_present={reasoning_present})"
        )

    def call_llm(
        self,
        model_key: str,
        prompt: str | list[dict[str, str]],
        system_prompt: str | None = None,
        stream: bool = False,
        max_tokens: int | None = None,
        request_timeout_seconds: float | None = None,
        max_retries: int | None = None,
        seed: int | None = None,
    ) -> str | Iterator[str]:
        """Synchronously calls the pooled async NVIDIA client for legacy callers."""
        if stream:
            raise RuntimeError(
                "Synchronous streaming is disabled; use call_llm_async(..., stream=True)."
            )

        headers, payload = self._request_parts(
            model_key,
            prompt,
            system_prompt,
            stream=False,
            max_tokens=max_tokens,
            seed=seed,
        )
        return self._submit_to_pool(
            self._call_with_retries(
                headers=headers,
                payload=payload,
                request_timeout_seconds=request_timeout_seconds,
                max_retries=max_retries,
            )
        ).result()

    async def call_llm_async(
        self,
        model_key: str,
        prompt: str | list[dict[str, str]],
        system_prompt: str | None = None,
        stream: bool = False,
        max_tokens: int | None = None,
        request_timeout_seconds: float | None = None,
        max_retries: int | None = None,
        seed: int | None = None,
    ) -> str | AsyncIterator[str]:
        """Asynchronously calls the NVIDIA completions endpoint through the shared pool."""
        headers, payload = self._request_parts(
            model_key,
            prompt,
            system_prompt,
            stream,
            max_tokens=max_tokens,
            seed=seed,
        )
        if stream:
            return self._stream_from_pool(headers=headers, payload=payload)
        return await asyncio.wrap_future(
            self._submit_to_pool(
                self._call_with_retries(
                    headers=headers,
                    payload=payload,
                    request_timeout_seconds=request_timeout_seconds,
                    max_retries=max_retries,
                )
            )
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
        self,
        *,
        headers: dict[str, str],
        payload: dict[str, Any],
        request_timeout_seconds: float | None = None,
        max_retries: int | None = None,
    ) -> NIMResponse:
        retry_count = DEFAULT_MAX_RETRIES if max_retries is None else max_retries
        backoff = 1.0
        client = await self._get_async_client()
        started = time.perf_counter()
        attempts: list[dict[str, Any]] = []

        for attempt in range(retry_count + 1):
            attempt_started = time.perf_counter()
            try:
                request_options: dict[str, Any] = {
                    "headers": headers,
                    "json": payload,
                }
                if request_timeout_seconds is not None:
                    request_options["timeout"] = request_timeout_seconds
                response = await client.post(
                    settings.NVIDIA_NIM_CHAT_COMPLETIONS_URL,
                    **request_options,
                )
                attempts.append(
                    {
                        "attempt": attempt + 1,
                        "status": response.status_code,
                        "seconds": time.perf_counter() - attempt_started,
                    }
                )
                if response.status_code == 200:
                    result = response.json()
                    usage = result.get("usage")
                    first_choice = (result.get("choices") or [{}])[0] or {}
                    try:
                        text = self._extract_response_text(result)
                        return NIMResponse(
                            text,
                            usage,
                            {
                                "attempts": attempts,
                                "latency_seconds": time.perf_counter() - started,
                                "provider_request_id": response.headers.get("x-request-id"),
                                "finish_reason": first_choice.get("finish_reason"),
                            },
                        )
                    except IncompleteModelResponseError:
                        logger.warning(
                            "NVIDIA response missing assistant text",
                            extra={
                                "finish_reason": first_choice.get("finish_reason"),
                                "message_keys": list((first_choice.get("message") or {}).keys()),
                            },
                        )
                        raise

                if response.status_code in {429, 500, 502, 503, 504} and attempt < retry_count:
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
                            "max_retries": retry_count,
                        },
                    )
                    await asyncio.sleep(sleep_time)
                    backoff *= 2
                    continue

                raise RuntimeError(
                    f"NVIDIA API Error: Status {response.status_code}, Detail: {response.text}"
                )
            except httpx.HTTPError as exc:
                attempts.append(
                    {
                        "attempt": attempt + 1,
                        "error": type(exc).__name__,
                        "seconds": time.perf_counter() - attempt_started,
                    }
                )
                retry_limit = retry_count
                if isinstance(exc, httpx.ReadTimeout):
                    retry_limit = min(retry_count, settings.NVIDIA_READ_TIMEOUT_RETRIES)
                if attempt < retry_count:
                    if attempt >= retry_limit:
                        raise
                    logger.warning(
                        "NVIDIA request failed; retrying",
                        extra={
                            "attempt": attempt + 1,
                            "retry_limit": retry_limit,
                            "error_type": type(exc).__name__,
                        },
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
                    "POST",
                    settings.NVIDIA_NIM_CHAT_COMPLETIONS_URL,
                    headers=headers,
                    json=payload,
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
