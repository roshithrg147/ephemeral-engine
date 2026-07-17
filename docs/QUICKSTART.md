# Quickstart Guide

This guide describes how to run SC-EVM locally in a trusted environment.

## 1. Configure Environment
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Populate `NVIDIA_API_KEY` with your credentials.

## 2. Start REST API Backend
```bash
uv run uvicorn src.main:app --host 127.0.0.1 --port 8000
```

## 3. Run Reference CLI Client
In a separate terminal:
```bash
uv run assistant
```

## 4. Start Dashboard

```bash
cd engine-dashboard
npm ci
npm start
```

Open `http://127.0.0.1:3000`.

## 5. Run Tests

```bash
uv run pytest
cd engine-dashboard && npm test -- --watchAll=false
```
