"""Provider Health Manager for SC-EVM Resilience.

Tracks real-time heartbeats, rolling latency windows, success %, timeout %, retry counts,
and cooldown timers across OpenAI, NVIDIA, Vertex, and Local model providers.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProviderHealthState:
    provider_name: str
    status: str = "Healthy"  # Healthy, Degraded, Unhealthy, Cooldown
    success_count: int = 0
    failure_count: int = 0
    timeout_count: int = 0
    rate_limit_count: int = 0
    cooldown_until: float = 0.0
    last_success_time: float | None = None
    last_error_time: float | None = None
    latencies_ms: deque[float] = field(default_factory=lambda: deque(maxlen=100))

    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        if total == 0:
            return 100.0
        return (self.success_count / total) * 100.0

    def avg_latency_ms(self) -> float:
        if not self.latencies_ms:
            return 0.0
        return sum(self.latencies_ms) / len(self.latencies_ms)

    def p95_latency_ms(self) -> float:
        if not self.latencies_ms:
            return 0.0
        sorted_lats = sorted(self.latencies_ms)
        idx = int(len(sorted_lats) * 0.95)
        return sorted_lats[min(idx, len(sorted_lats) - 1)]

    def is_available(self) -> bool:
        now = time.time()
        if now < self.cooldown_until:
            return False
        return self.status in {"Healthy", "Degraded"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "status": self.status,
            "success_rate_pct": round(self.success_rate(), 2),
            "avg_latency_ms": round(self.avg_latency_ms(), 2),
            "p95_latency_ms": round(self.p95_latency_ms(), 2),
            "total_successes": self.success_count,
            "total_failures": self.failure_count,
            "rate_limit_429s": self.rate_limit_count,
            "cooldown_active": time.time() < self.cooldown_until,
            "cooldown_remaining_s": max(0.0, round(self.cooldown_until - time.time(), 1)),
        }


class ProviderHealthManager:
    """Central registry & monitor for LLM & Embedding provider operational health."""

    def __init__(self, cooldown_duration_s: float = 30.0):
        self._lock = threading.RLock()
        self.cooldown_duration_s = cooldown_duration_s
        self.providers: dict[str, ProviderHealthState] = {
            "openai": ProviderHealthState("openai"),
            "nvidia": ProviderHealthState("nvidia"),
            "vertex": ProviderHealthState("vertex"),
            "local": ProviderHealthState("local"),
        }

    def get_health(self, provider_name: str) -> ProviderHealthState:
        with self._lock:
            if provider_name not in self.providers:
                self.providers[provider_name] = ProviderHealthState(provider_name)
            st = self.providers[provider_name]
            # Check cooldown expiry
            if st.status == "Cooldown" and time.time() >= st.cooldown_until:
                st.status = "Degraded"
            return st

    def record_success(self, provider_name: str, latency_ms: float) -> None:
        with self._lock:
            st = self.get_health(provider_name)
            st.success_count += 1
            st.last_success_time = time.time()
            st.latencies_ms.append(latency_ms)

            # Auto-recover to Healthy if success rate improves
            if st.success_rate() >= 90.0:
                st.status = "Healthy"
            elif st.success_rate() >= 70.0:
                st.status = "Degraded"

    def record_failure(
        self,
        provider_name: str,
        error_type: str = "generic",
        latency_ms: float = 0.0,
    ) -> None:
        with self._lock:
            st = self.get_health(provider_name)
            st.failure_count += 1
            st.last_error_time = time.time()
            if latency_ms > 0:
                st.latencies_ms.append(latency_ms)

            if error_type == "429_rate_limit":
                st.rate_limit_count += 1
                st.status = "Cooldown"
                st.cooldown_until = time.time() + self.cooldown_duration_s
            elif error_type == "timeout":
                st.timeout_count += 1

            if st.status != "Cooldown":
                s_rate = st.success_rate()
                if s_rate < 50.0:
                    st.status = "Unhealthy"
                    st.cooldown_until = time.time() + self.cooldown_duration_s
                elif s_rate < 80.0:
                    st.status = "Degraded"

    def trigger_cooldown(self, provider_name: str, duration_s: float | None = None) -> None:
        with self._lock:
            st = self.get_health(provider_name)
            st.status = "Cooldown"
            dur = duration_s if duration_s is not None else self.cooldown_duration_s
            st.cooldown_until = time.time() + dur

    def snapshot_all(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return {p: st.to_dict() for p, st in self.providers.items()}


_global_health_manager: ProviderHealthManager | None = None


def get_health_manager() -> ProviderHealthManager:
    global _global_health_manager
    if _global_health_manager is None:
        _global_health_manager = ProviderHealthManager()
    return _global_health_manager
