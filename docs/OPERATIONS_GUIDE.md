# SC-EVM Operations & Observability Guide

---

## 1. Prometheus Metrics Exposition (`/metrics`)

SC-EVM exports Prometheus metrics at `GET /metrics` or `GET /api/metrics`:

| Metric Name | Type | Description |
| :--- | :--- | :--- |
| `scevm_http_requests_total` | Counter | Total HTTP requests handled |
| `scevm_retrieval_latency_seconds_sum` | Counter | Total retrieval latency (seconds) |
| `scevm_retrieval_latency_seconds_count` | Counter | Number of retrieval operations |
| `scevm_tokens_consumed_total` | Counter | Cumulative tokens consumed |
| `scevm_circuit_breaker_state` | Gauge | Circuit breaker state (0=CLOSED, 1=HALF_OPEN, 2=OPEN) |

---

## 2. Health Probes

- **Liveness:** `GET /health/liveness` — Returns `200 OK` when event loop is responsive.
- **Readiness:** `GET /health/readiness` — Returns `200 OK` when session registry and local embedding engine are ready.

---

## 3. Circuit Breaker & Failover Management

- **States:** `CLOSED` (normal), `OPEN` (tripped), `HALF_OPEN` (probing recovery).
- **Behavior:** When `OPEN`, requests fail fast or route to local fallback without downstream network timeouts.
- **Auto-Recovery:** Resets to `CLOSED` after consecutive successful probes in `HALF_OPEN` state.
