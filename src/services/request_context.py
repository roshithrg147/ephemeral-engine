"""Immutable RequestContext for SC-EVM Distributed Tracing.

Passes single immutable request context through entire pipeline (HTTP -> Gateway -> Intent -> Retrieval -> Fusion -> Planner -> Prompt -> LLM -> Streaming -> Memory).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class TelemetrySpan:
    span_name: str
    start_time: float
    end_time: float
    latency_ms: float
    status: str  # OK, ERROR, DEGRADED
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RequestContext:
    request_id: str
    session_id: str
    tenant_id: str
    user_id: str
    trace_id: str
    start_time: float = field(default_factory=time.time)
    provider: str = "local"
    embedding_model: str = "local"
    retrieval_mode: str = "hybrid"
    router_decision: str = "local"
    circuit_state: str = "CLOSED"
    token_budget: int = 8192
    latency_budget_ms: float = 10000.0
    spans: list[TelemetrySpan] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        session_id: str,
        tenant_id: str = "default-tenant",
        user_id: str = "anonymous",
        retrieval_mode: str = "hybrid",
        token_budget: int = 8192,
    ) -> RequestContext:
        req_id = f"req-{uuid4().hex[:12]}"
        trace_id = f"trace-{uuid4().hex[:16]}"
        return cls(
            request_id=req_id,
            session_id=session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            trace_id=trace_id,
            retrieval_mode=retrieval_mode,
            token_budget=token_budget,
        )

    def record_span(
        self,
        span_name: str,
        start_time: float,
        status: str = "OK",
        errors: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TelemetrySpan:
        end_time = time.time()
        latency_ms = (end_time - start_time) * 1000.0
        span = TelemetrySpan(
            span_name=span_name,
            start_time=start_time,
            end_time=end_time,
            latency_ms=latency_ms,
            status=status,
            errors=errors or [],
            metadata=metadata or {},
        )
        self.spans.append(span)
        return span

    def elapsed_ms(self) -> float:
        return (time.time() - self.start_time) * 1000.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "session_id": self.session_id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "trace_id": self.trace_id,
            "provider": self.provider,
            "router_decision": self.router_decision,
            "circuit_state": self.circuit_state,
            "elapsed_ms": self.elapsed_ms(),
            "span_count": len(self.spans),
            "spans": [
                {
                    "name": s.span_name,
                    "latency_ms": round(s.latency_ms, 2),
                    "status": s.status,
                    "errors": s.errors,
                }
                for s in self.spans
            ],
        }
