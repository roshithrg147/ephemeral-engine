"""Multi-Level Fallback Cache for SC-EVM Resilience.

Implements cascading fallback hierarchy:
Cloud LLM -> Local Model -> Warm Memory Cache -> Cold Disk Cache -> Minimal Retrieval -> Coherent Degraded Response.
"""
from __future__ import annotations

import json
import logging
import time
from collections import OrderedDict, deque
from pathlib import Path
from typing import Any

from src.services.error_taxonomy import ResilientRuntimeError, RuntimeErrorCode

logger = logging.getLogger("SC-EVM.FallbackCache")


class FallbackCacheManager:
    """Multi-tiered cache and minimal retrieval fallback manager."""

    def __init__(self, warm_capacity: int = 100, cold_store_dir: str = ".cold_cache"):
        self.warm_capacity = warm_capacity
        self.cold_store_dir = Path(cold_store_dir)
        self.cold_store_dir.mkdir(parents=True, exist_ok=True)
        # Warm in-memory LRU cache (key -> payload)
        self._warm_cache: OrderedDict[str, dict[str, Any]] = OrderedDict()

    def _key(self, session_id: str, query: str) -> str:
        import hashlib

        h = hashlib.sha256(f"{session_id}::{query.strip().lower()}".encode("utf-8")).hexdigest()[:16]
        return f"{session_id}_{h}"

    def put_warm(self, session_id: str, query: str, payload: dict[str, Any]) -> None:
        """Store recent retrieval or prompt expansion in Warm Memory Cache."""
        key = self._key(session_id, query)
        payload["cached_at"] = time.time()
        self._warm_cache[key] = payload
        self._warm_cache.move_to_end(key)
        if len(self._warm_cache) > self.warm_capacity:
            self._warm_cache.popitem(last=False)

    def get_warm(self, session_id: str, query: str) -> dict[str, Any] | None:
        """Fetch from Warm Memory Cache."""
        key = self._key(session_id, query)
        if key in self._warm_cache:
            self._warm_cache.move_to_end(key)
            return self._warm_cache[key]
        return None

    def put_cold(self, session_id: str, query: str, payload: dict[str, Any]) -> None:
        """Persist query reformulation or summary into Cold Disk Cache."""
        key = self._key(session_id, query)
        file_path = self.cold_store_dir / f"{key}.json"
        try:
            payload["cached_at"] = time.time()
            file_path.write_text(json.dumps(payload, default=str), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to write cold cache '{key}': {e}")

    def get_cold(self, session_id: str, query: str) -> dict[str, Any] | None:
        """Fetch from Cold Disk Cache."""
        key = self._key(session_id, query)
        file_path = self.cold_store_dir / f"{key}.json"
        if file_path.exists():
            try:
                return json.loads(file_path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning(f"Failed to read cold cache '{key}': {e}")
        return None

    def get_minimal_retrieval(self, history: list[dict[str, str]]) -> list[dict[str, Any]]:
        """Fallback level: extract minimal recent conversation history without vector/BM25 retrieval."""
        recent_history = history[-3:] if history else []
        return [
            {
                "doc_id": f"min-hist-{idx}",
                "text": f"{turn.get('role', 'user').capitalize()}: {turn.get('content', '')}",
                "metadata": {"source": "minimal_retrieval"},
            }
            for idx, turn in enumerate(recent_history, 1)
        ]

    def build_degraded_response(
        self,
        query: str,
        reason: str = "Provider outage",
    ) -> dict[str, Any]:
        """Final fallback level: generate a graceful degraded response."""
        return {
            "status": "degraded",
            "content": f"[SC-EVM Degraded Mode]: Currently operating under limited connectivity ({reason}). Query '{query}' recorded safely.",
            "mode": "degraded_fallback",
        }
