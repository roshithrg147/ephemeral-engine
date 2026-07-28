"""Normalized multi-provider adapter contract (Claude, GPT, Gemini, NVIDIA NIM)."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from src.capability_broker import CapabilityBroker
from src.security_context import SecurityContext

logger = logging.getLogger("SC-EVM.ProviderAdapter")


class BaseProviderAdapter(ABC):
    """Abstract provider adapter ensuring identical policy enforcement across LLM providers."""

    def __init__(self, provider_name: str, default_model: str):
        self.provider_name = provider_name
        self.default_model = default_model

    @abstractmethod
    async def generate(
        self,
        sec_ctx: SecurityContext,
        prompt: str,
        system_prompt: str,
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Generate model completion under enforced SecurityContext boundary."""
        pass

    def get_allowed_tool_manifest(self, sec_ctx: SecurityContext) -> list[str]:
        """Return workflow-allowed tools for model manifest presentation."""
        return CapabilityBroker.filter_manifest_tools(sec_ctx)


class MultiProviderRegistry:
    """Registry maintaining uniform provider adapters."""

    def __init__(self) -> None:
        self._adapters: dict[str, BaseProviderAdapter] = {}

    def register(self, name: str, adapter: BaseProviderAdapter) -> None:
        self._adapters[name.lower()] = adapter

    def get(self, name: str) -> BaseProviderAdapter | None:
        return self._adapters.get(name.lower())


# Global provider registry instance
provider_registry = MultiProviderRegistry()
