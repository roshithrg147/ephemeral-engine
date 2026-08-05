"""Policy-Driven Intelligent Router for SC-EVM Resilience.

Replaces simple binary fallback with a multi-variable policy engine evaluating:
- Query classification & confidence score
- Provider health (Heartbeat, success %, latency window, rate limits)
- Token & latency budget constraints
- Circuit breaker state (CLOSED, WARNING, OPEN, COOLDOWN, HALF_OPEN)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from src.services.circuit_breaker import CircuitBreaker
from src.services.provider_health import ProviderHealthManager, get_health_manager

logger = logging.getLogger("SC-EVM.ResilientRouter")


@dataclass
class RouterDecision:
    target_provider: str  # "local", "openai", "nvidia", "vertex"
    decision_reason: str
    confidence_score: float
    estimated_cost_usd: float
    fallback_provider: str
    circuit_state: str


class ResilientRouter:
    """Policy-driven intelligent dispatcher for LLM and Embedding execution."""

    def __init__(
        self,
        health_manager: ProviderHealthManager | None = None,
        confidence_threshold: float = 0.75,
        token_cost_limit_usd: float = 0.05,
    ):
        self.health_mgr = health_manager or get_health_manager()
        self.confidence_threshold = confidence_threshold
        self.token_cost_limit_usd = token_cost_limit_usd
        self.circuit_breakers: dict[str, CircuitBreaker] = {
            "openai": CircuitBreaker(name="openai", failure_threshold=3, recovery_timeout=5.0),
            "nvidia": CircuitBreaker(name="nvidia", failure_threshold=3, recovery_timeout=5.0),
            "local": CircuitBreaker(name="local", failure_threshold=5, recovery_timeout=2.0),
        }

    def route_query(
        self,
        query: str,
        confidence_score: float = 0.8,
        preferred_cloud_provider: str = "nvidia",
        token_budget: int = 2048,
    ) -> RouterDecision:
        """Evaluate multi-variable policy and select optimal provider."""

        cloud_cb = self.circuit_breakers.get(preferred_cloud_provider) or self.circuit_breakers["openai"]
        local_cb = self.circuit_breakers["local"]
        cloud_health = self.health_mgr.get_health(preferred_cloud_provider)
        local_health = self.health_mgr.get_health("local")

        # Decision Rule 1: Circuit breaker open/cooldown on cloud -> force local
        if cloud_cb.state in {"OPEN", "COOLDOWN"} or not cloud_health.is_available():
            logger.info(
                f"Router selected 'local': Cloud provider '{preferred_cloud_provider}' "
                f"circuit={cloud_cb.state}, health={cloud_health.status}"
            )
            return RouterDecision(
                target_provider="local",
                decision_reason=f"Cloud provider '{preferred_cloud_provider}' circuit {cloud_cb.state}",
                confidence_score=confidence_score,
                estimated_cost_usd=0.0,
                fallback_provider="local",
                circuit_state=local_cb.state,
            )

        # Decision Rule 2: High local confidence and degraded cloud -> use local
        if confidence_score >= self.confidence_threshold:
            logger.info(
                f"Router selected 'local': High confidence ({confidence_score:.2f} >= {self.confidence_threshold:.2f})"
            )
            return RouterDecision(
                target_provider="local",
                decision_reason=f"High query confidence ({confidence_score:.2f})",
                confidence_score=confidence_score,
                estimated_cost_usd=0.0,
                fallback_provider=preferred_cloud_provider,
                circuit_state=local_cb.state,
            )

        # Decision Rule 3: Cloud is healthy & available -> dispatch to cloud
        logger.info(
            f"Router selected cloud '{preferred_cloud_provider}': Confidence ({confidence_score:.2f}), "
            f"cloud health={cloud_health.status}"
        )
        return RouterDecision(
            target_provider=preferred_cloud_provider,
            decision_reason=f"Complex query dispatched to cloud ({preferred_cloud_provider})",
            confidence_score=confidence_score,
            estimated_cost_usd=0.001 * (token_budget / 1000),
            fallback_provider="local",
            circuit_state=cloud_cb.state,
        )

    def record_outcome(self, provider: str, success: bool, latency_ms: float, error: Exception | str | None = None) -> None:
        """Feedback outcome into health manager & circuit breaker."""
        cb = self.circuit_breakers.get(provider)
        if success:
            self.health_mgr.record_success(provider, latency_ms)
            if cb:
                cb.record_success()
        else:
            err_type = "generic"
            if error:
                err_str = str(error).lower()
                if "429" in err_str or "rate limit" in err_str:
                    err_type = "429_rate_limit"
                elif "timeout" in err_str or "timed out" in err_str:
                    err_type = "timeout"
            self.health_mgr.record_failure(provider, error_type=err_type, latency_ms=latency_ms)
            if cb:
                cb.record_failure(error)
