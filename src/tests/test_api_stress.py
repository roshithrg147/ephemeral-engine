import asyncio
import os
import uuid

import httpx

from src.config import settings
from src.main import app


def test_concurrent_session_isolation_and_burn(monkeypatch):
    monkeypatch.setattr(settings, "TELEMETRY_ENABLED", False)

    async def exercise():
        prefix = f"stress-{uuid.uuid4().hex[:8]}"
        session_count = int(os.getenv("SC_EVM_STRESS_SESSIONS", "24"))
        messages_per_session = int(os.getenv("SC_EVM_STRESS_MESSAGES", "8"))
        session_ids = [f"{prefix}-{index}" for index in range(session_count)]
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            initialized = await asyncio.gather(
                *[
                    client.post("/api/session/initialize", json={"session_id": session_id})
                    for session_id in session_ids
                ]
            )
            assert all(response.status_code == 200 for response in initialized)

            writes = []
            for session_id in session_ids:
                for message_index in range(messages_per_session):
                    writes.append(
                        client.post(
                            "/api/session/message",
                            json={
                                "session_id": session_id,
                                "role": "user",
                                "content": f"{session_id}-message-{message_index}",
                            },
                        )
                    )
            written = await asyncio.gather(*writes)
            assert all(response.status_code == 200 for response in written)

            histories = await asyncio.gather(
                *[client.get(f"/api/session/history/{session_id}") for session_id in session_ids]
            )
            for session_id, response in zip(session_ids, histories, strict=True):
                assert response.status_code == 200
                contents = {message["content"] for message in response.json()["data"]}
                assert contents == {
                    f"{session_id}-message-{message_index}"
                    for message_index in range(
                        max(0, messages_per_session - settings.MAX_HISTORY_TURNS),
                        messages_per_session,
                    )
                }

            burned = await asyncio.gather(
                *[client.delete(f"/api/session/burn/{session_id}") for session_id in session_ids]
            )
            assert all(response.status_code == 200 for response in burned)

            remaining = (await client.get("/api/session/list")).json()["data"]
            assert not set(session_ids).intersection(remaining)

            reinitialized = await asyncio.gather(
                *[
                    client.post("/api/session/initialize", json={"session_id": session_id})
                    for session_id in session_ids
                ]
            )
            assert all(response.status_code == 200 for response in reinitialized)
            histories = await asyncio.gather(
                *[client.get(f"/api/session/history/{session_id}") for session_id in session_ids]
            )
            assert all(response.json()["data"] == [] for response in histories)
            await asyncio.gather(
                *[client.delete(f"/api/session/burn/{session_id}") for session_id in session_ids]
            )

    asyncio.run(exercise())
