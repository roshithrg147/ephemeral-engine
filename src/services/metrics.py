"""Metrics Exporter and OpenTelemetry Tracing Helpers for SC-EVM.

Exposes Prometheus counters, histograms, gauges, and OpenTelemetry trace helpers.
"""
from __future__ import annotations

import time
from typing import Any


class Counter:
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.value = 0.0

    def inc(self, amount: float = 1.0) -> None:
        self.value += amount


class Gauge:
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.value = 0.0

    def set(self, val: float) -> None:
        self.value = val


class MetricsRegistry:
    """Singleton metrics registry providing Prometheus metrics exposition."""

    _instance: MetricsRegistry | None = None

    def __init__(self):
        self.http_requests_total = Counter(
            "scevm_http_requests_total", "Total HTTP requests received"
        )
        self.retrieval_latency_sum = Counter(
            "scevm_retrieval_latency_seconds_sum", "Total retrieval latency seconds"
        )
        self.retrieval_latency_count = Counter(
            "scevm_retrieval_latency_seconds_count", "Total retrieval operations count"
        )
        self.tokens_consumed_total = Counter(
            "scevm_tokens_consumed_total", "Total tokens consumed"
        )
        self.circuit_breaker_state = Gauge(
            "scevm_circuit_breaker_state", "Circuit Breaker State (0=CLOSED, 1=HALF_OPEN, 2=OPEN)"
        )

    @classmethod
    def get_instance(cls) -> MetricsRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def record_request(self) -> None:
        self.http_requests_total.inc(1)

    def record_retrieval_latency(self, latency_ms: float) -> None:
        self.retrieval_latency_sum.inc(latency_ms / 1000.0)
        self.retrieval_latency_count.inc(1)

    def record_tokens(self, tokens: int) -> None:
        self.tokens_consumed_total.inc(float(tokens))

    def set_circuit_breaker_state(self, state: str) -> None:
        val = 0.0 if state == "CLOSED" else (1.0 if state == "HALF_OPEN" else 2.0)
        self.circuit_breaker_state.set(val)

    def export_prometheus_metrics(self) -> str:
        """Generate Prometheus exposition text format payload."""
        lines = [
            f"# HELP {self.http_requests_total.name} {self.http_requests_total.description}",
            f"# TYPE {self.http_requests_total.name} counter",
            f"{self.http_requests_total.name} {self.http_requests_total.value:.0f}",
            "",
            f"# HELP {self.retrieval_latency_sum.name} {self.retrieval_latency_sum.description}",
            f"# TYPE {self.retrieval_latency_sum.name} counter",
            f"{self.retrieval_latency_sum.name} {self.retrieval_latency_sum.value:.6f}",
            f"{self.retrieval_latency_count.name} {self.retrieval_latency_count.value:.0f}",
            "",
            f"# HELP {self.tokens_consumed_total.name} {self.tokens_consumed_total.description}",
            f"# TYPE {self.tokens_consumed_total.name} counter",
            f"{self.tokens_consumed_total.name} {self.tokens_consumed_total.value:.0f}",
            "",
            f"# HELP {self.circuit_breaker_state.name} {self.circuit_breaker_state.description}",
            f"# TYPE {self.circuit_breaker_state.name} gauge",
            f"{self.circuit_breaker_state.name} {self.circuit_breaker_state.value:.1f}",
        ]
        return "\n".join(lines) + "\n"
