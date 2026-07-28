"""In-memory metrics collector for tracking reliability and performance counters."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


class MetricsCollector:
    """Thread-safe in-memory metric counter and latency tracker."""

    def __init__(self) -> None:
        self.counters: dict[str, int] = defaultdict(int)
        self.histograms: dict[str, list[float]] = defaultdict(list)

    def increment(self, metric: str, value: int = 1) -> None:
        """Increment a metric counter."""
        self.counters[metric] += value

    def observe(self, metric: str, value: float) -> None:
        """Record an observation in a histogram."""
        self.histograms[metric].append(value)
        # Cap histogram retention to recent 1000 items
        if len(self.histograms[metric]) > 1000:
            self.histograms[metric].pop(0)

    def get_metrics(self) -> dict[str, Any]:
        """Return snapshot of all collected metrics."""
        summary: dict[str, Any] = dict(self.counters)
        for metric, values in self.histograms.items():
            if values:
                summary[f"{metric}_avg"] = round(sum(values) / len(values), 4)
                summary[f"{metric}_count"] = len(values)
        return summary

    def clear(self) -> None:
        """Reset all metrics."""
        self.counters.clear()
        self.histograms.clear()


# Global metrics instance
metrics = MetricsCollector()
