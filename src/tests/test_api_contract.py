import asyncio

import httpx

from src.main import app


def test_session_lifecycle_and_validation():
    async def exercise():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            invalid = await client.post("/api/session/initialize", json={"session_id": "../escape"})
            assert invalid.status_code == 422

            initialized = await client.post(
                "/api/session/initialize",
                json={"session_id": "api-contract", "development_phase": 3},
            )
            assert initialized.status_code == 200
            assert initialized.json()["data"]["development_phase"] == 3

            invalid_phase = await client.post(
                "/api/session/initialize",
                json={"session_id": "api-invalid-phase", "development_phase": 4},
            )
            assert invalid_phase.status_code == 422

            invalid_role = await client.post(
                "/api/session/message",
                json={"session_id": "api-contract", "role": "tool", "content": "not allowed"},
            )
            assert invalid_role.status_code == 422

            appended = await client.post(
                "/api/session/message",
                json={"session_id": "api-contract", "role": "user", "content": "hello"},
            )
            assert appended.status_code == 200

            history = await client.get("/api/session/history/api-contract")
            assert history.status_code == 200
            assert history.json()["data"] == [{"role": "user", "content": "hello"}]

            burned = await client.delete("/api/session/burn/api-contract")
            assert burned.status_code == 200
            assert (await client.get("/api/session/history/api-contract")).status_code == 404

    asyncio.run(exercise())


def test_openai_models_list_endpoint():
    async def exercise():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get("/v1/models")
            assert res.status_code == 200
            data = res.json()
            assert data["object"] == "list"
            assert any(m["id"] == "sc-evm-proxy" for m in data["data"])

    asyncio.run(exercise())


def test_openai_chat_completions_sanitizes_empty_messages():
    async def exercise():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Rejects payloads with only empty or whitespace message contents
            res_empty = await client.post(
                "/v1/chat/completions",
                json={
                    "model": "sc-evm-proxy",
                    "messages": [
                        {"role": "system", "content": ""},
                        {"role": "user", "content": "   "},
                    ],
                },
            )
            assert res_empty.status_code == 400
            assert "Either messages or prompt must be provided" in res_empty.json()["detail"]

    asyncio.run(exercise())
