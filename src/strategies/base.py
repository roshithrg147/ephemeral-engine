from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class StrategyAdapter(ABC):
    """Contract for benchmarkable agent strategies."""

    name: str

    def __init__(self, name: str | None = None):
        self.name = name or self.__class__.__name__

    @abstractmethod
    async def solve(self, prompt: str, session_id: str) -> dict[str, Any]:
        """Return a normalized strategy result for a single turn."""
