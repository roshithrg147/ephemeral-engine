"""Unit tests for frontend SSE stream contract compliance."""

from __future__ import annotations

import unittest

from src.main import sse_query_generator
from src.memory import session_registry
from src.security_context import SecurityContextResolver


class TestFrontendStreamContract(unittest.IsolatedAsyncioTestCase):
    async def test_stream_contract_on_valid_session(self) -> None:
        session_id = "contract-test-session"
        sec_ctx = SecurityContextResolver.resolve(principal=None, request=None)
        await session_registry.initialize_session(
            session_id, tenant_id=sec_ctx.tenant_id, owner_subject=sec_ctx.user_id
        )

        events: list[str] = []
        async for event in sse_query_generator(session_id, prompt="Hello", create_session=False):
            events.append(event)

        # Stream must terminate with event: done \n data: [DONE]
        self.assertTrue(any("data: [DONE]" in e for e in events))

        await session_registry.flush_session(session_id)


if __name__ == "__main__":
    unittest.main()
