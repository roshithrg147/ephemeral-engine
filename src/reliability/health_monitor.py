"""Health monitor for tracking component health and operational diagnostics."""

from __future__ import annotations

import time
from typing import Any

from src.reliability.circuit_breaker import _CIRCUIT_BREAKERS, CircuitState


class HealthMonitor:
    """Provides high-level component health monitoring for operator read workflows."""

    _start_time: float = time.time()

    @classmethod
    def get_system_health(cls) -> dict[str, Any]:
        """Return high-level, sanitized operational component health summary."""
        circuit_statuses: dict[str, str] = {}
        overall_healthy = True

        for name, breaker in _CIRCUIT_BREAKERS.items():
            circuit_statuses[name] = breaker.state.value
            if breaker.state == CircuitState.OPEN:
                overall_healthy = False

        return {
            "status": "healthy" if overall_healthy else "degraded",
            "uptime_seconds": round(time.time() - cls._start_time, 2),
            "circuits": circuit_statuses,
        }
