from collections.abc import AsyncIterator, Iterator

from src.clients import NVIDIA_NIM_Client

PromptPayload = str | list[dict[str, str]]


class ModelConnector:
    """Service boundary for NVIDIA NIM model calls."""

    def __init__(self, client: NVIDIA_NIM_Client | None = None):
        self.client = client or NVIDIA_NIM_Client()

    def call(
        self,
        *,
        model_key: str,
        prompt: PromptPayload,
        system_prompt: str | None = None,
        stream: bool = False,
        max_tokens: int | None = None,
    ) -> str | Iterator[str]:
        return self.client.call_llm(
            model_key=model_key,
            prompt=prompt,
            system_prompt=system_prompt,
            stream=stream,
            max_tokens=max_tokens,
        )

    async def call_async(
        self,
        *,
        model_key: str,
        prompt: PromptPayload,
        system_prompt: str | None = None,
        stream: bool = False,
        max_tokens: int | None = None,
    ) -> str | AsyncIterator[str]:
        return await self.client.call_llm_async(
            model_key=model_key,
            prompt=prompt,
            system_prompt=system_prompt,
            stream=stream,
            max_tokens=max_tokens,
        )
