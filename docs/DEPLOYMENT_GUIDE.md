# SC-EVM Production Deployment Guide

* **Version:** Developer Preview 1.0
* **Target Audience:** Systems Engineers, DevOps Engineers, and Platform Developers

---

## 1. Environment & Prerequisites

### Minimum System Requirements
* **OS:** Linux (Ubuntu 22.04 LTS or higher recommended)
* **Python:** Python 3.11+
* **CPU:** 4+ Cores
* **RAM:** 8 GB Minimum (16 GB Recommended)
* **Node.js:** Node.js 18+ (for `engine-dashboard`)

---

## 2. Fast Deployment via `uv`

```bash
# 1. Clone repository
git clone https://github.com/roshithrg147/ephemeral-engine.git
cd ephemeral-engine

# 2. Synchronize virtualenv dependencies via uv
uv sync

# 3. Configure environment variables
cp .env.example .env

# Edit .env to set NVIDIA_API_KEY and AUTH_MODE
# AUTH_MODE=disabled (for local dev) or AUTH_MODE=firebase

# 4. Start the FastAPI Context Engine
uv run python -m uvicorn src.main:app --host 127.0.0.1 --port 8000
```

---

## 3. Dashboard Deployment (`engine-dashboard`)

```bash
cd engine-dashboard
npm install
npm run build
npm start
```

---

## 4. Health & Verification Endpoints

Verify deployment using standard probes:
* **Liveness:** `GET http://127.0.0.1:8000/health/liveness`
* **Readiness:** `GET http://127.0.0.1:8000/health/readiness`
* **Metrics:** `GET http://127.0.0.1:8000/metrics`
* **OpenAI Proxy:** `POST http://127.0.0.1:8000/v1/chat/completions`
