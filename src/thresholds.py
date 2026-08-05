"""Adaptive threshold engine for retrieval calibration.

Provides per-(embedding_model, repository, session) rolling statistics,
persistence, and decision APIs for admission/rejection of vector candidates.
"""
from __future__ import annotations

import json
import math
import statistics
import threading
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from src.config import settings


class StatsWindow:
    def __init__(self, maxlen: int = 1024):
        self._d = deque(maxlen=maxlen)

    def add_all(self, values: list[float]) -> None:
        for v in values:
            self._d.append(float(v))

    def snapshot(self) -> list[float]:
        return list(self._d)


class AdaptiveThresholdEngine:
    def __init__(self, store_path: str | None = None, window_maxlen: int = 1024):
        self._lock = threading.RLock()
        self._store_path = Path(store_path or settings.CALIBRATION_STORE_PATH)
        self._windows: dict[str, StatsWindow] = defaultdict(lambda: StatsWindow(window_maxlen))
        self._meta: dict[str, Any] = {}
        self._load()

    def _key(self, embedding_model: str, repository: str | None, session_id: str | None) -> str:
        repo = repository or "default"
        sess = session_id or "global"
        return f"{embedding_model}::{repo}::{sess}"

    def add_observation(self, embedding_model: str, repository: str | None, session_id: str | None, distances: list[float]) -> None:
        key = self._key(embedding_model, repository, session_id)
        with self._lock:
            self._windows[key].add_all(distances)

    def _compute_stats(self, samples: list[float]) -> dict:
        if not samples:
            return {
                "count": 0,
                "mean": None,
                "median": None,
                "stddev": None,
                "mad": None,
                "percentiles": {},
            }
        pct = lambda p: statistics.quantiles(samples, n=100)[int(p) - 1] if len(samples) >= 100 else statistics.median(samples)
        mean = statistics.mean(samples)
        median = statistics.median(samples)
        stddev = statistics.pstdev(samples) if len(samples) > 1 else 0.0
        mad = statistics.median([abs(x - median) for x in samples])
        percentiles = {
            "10": min(samples),
            "25": statistics.quantiles(samples, n=4)[0] if len(samples) >= 4 else median,
            "50": median,
            "75": statistics.quantiles(samples, n=4)[2] if len(samples) >= 4 else median,
            "90": max(samples),
        }
        return {
            "count": len(samples),
            "mean": mean,
            "median": median,
            "stddev": stddev,
            "mad": mad,
            "percentiles": percentiles,
        }

    def get_stats(self, embedding_model: str, repository: str | None = None, session_id: str | None = None) -> dict:
        key = self._key(embedding_model, repository, session_id)
        with self._lock:
            samples = self._windows[key].snapshot()
        return self._compute_stats(samples)

    def get_percentile(self, embedding_model: str, percentile: int, repository: str | None = None, session_id: str | None = None) -> float | None:
        stats = self.get_stats(embedding_model, repository, session_id)
        p = stats.get("percentiles", {}).get(str(percentile))
        return p

    def score_candidate(self, embedding_model: str, candidate_distance: float, repository: str | None = None, session_id: str | None = None) -> dict:
        stats = self.get_stats(embedding_model, repository, session_id)
        mean = stats.get("mean")
        stddev = stats.get("stddev")
        median = stats.get("median")
        mad = stats.get("mad")
        score = None
        if mean is not None and stddev is not None and stddev > 0:
            # z-score in distance space: lower distance -> more similar
            z = (candidate_distance - mean) / stddev
            score = -z
        return {"distance": candidate_distance, "score": score, "stats": stats}

    def get_acceptance_threshold(self, embedding_model: str, repository: str | None = None, session_id: str | None = None) -> float | None:
        # Default to median if available
        stats = self.get_stats(embedding_model, repository, session_id)
        if stats.get("median") is not None:
            return stats["median"]
        return None

    def get_rejection_threshold(self, embedding_model: str, repository: str | None = None, session_id: str | None = None) -> float | None:
        # Default to 75th percentile (more distant) if available
        p75 = self.get_percentile(embedding_model, 75, repository, session_id)
        return p75

    def calibrate_from_anchors(self, embedding_model: str, repository: str | None, session_id: str | None, embedding_fn, positive_anchors: list[str], negative_anchors: list[str]) -> float | None:
        """Perform startup calibration using provided positive/negative anchors.

        Stores sample distances and returns derived base threshold.
        """
        # compute embeddings
        if not positive_anchors:
            return None
        pos_embs = embedding_fn(positive_anchors)
        neg_embs = embedding_fn(negative_anchors or []) if negative_anchors else []
        # collect pairwise distances from positives and negatives
        samples: list[float] = []
        def cosdist(a, b):
            dot = sum(x * y for x, y in zip(a, b))
            na = math.sqrt(sum(x * x for x in a))
            nb = math.sqrt(sum(x * x for x in b))
            if na == 0 or nb == 0:
                return 1.0
            return 1.0 - (dot / (na * nb))

        # positive pairwise
        for i in range(len(pos_embs)):
            for j in range(i + 1, len(pos_embs)):
                samples.append(cosdist(pos_embs[i], pos_embs[j]))

        # negatives relative to first positive
        if neg_embs:
            for n in neg_embs:
                samples.append(cosdist(pos_embs[0], n))

        with self._lock:
            key = self._key(embedding_model, repository, session_id)
            self._windows[key].add_all(samples)
            self._meta[key] = {"calibrated_at": time.time(), "positive_count": len(pos_embs), "negative_count": len(neg_embs)}
            self._save()

        # return median as base threshold proxy
        return self.get_stats(embedding_model, repository, session_id).get("median")

    def _load(self) -> None:
        try:
            if not self._store_path.exists():
                return
            data = json.loads(self._store_path.read_text())
            with self._lock:
                for key, items in data.get("windows", {}).items():
                    self._windows[key] = StatsWindow()
                    self._windows[key].add_all(items)
                self._meta = data.get("meta", {})
        except Exception:
            # best-effort, do not fail startup
            return

    def _save(self) -> None:
        try:
            payload = {"windows": {}, "meta": self._meta}
            with self._lock:
                for key, w in self._windows.items():
                    payload["windows"][key] = w.snapshot()
            self._store_path.write_text(json.dumps(payload))
        except Exception:
            return


# Singleton engine instance
_ENGINE: AdaptiveThresholdEngine | None = None


def get_engine() -> AdaptiveThresholdEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = AdaptiveThresholdEngine()
    return _ENGINE
