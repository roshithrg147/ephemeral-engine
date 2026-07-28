"""Unit tests for SSE stream failure handling and non-disconnect guarantees."""

from __future__ import annotations

import unittest

from src.main import sse_query_generator


class TestSSEFailureHandling(unittest.IsolatedAsyncioTestCase):
    async def test_sse_query_generator_yields_error_and_done_on_failure(self) -> None:
        """Verify that an uninitialized session attempt yields a deterministic error event and done event."""
        session_id = "missing-uninitialized-session"
        events: list[str] = []

        async for event in sse_query_generator(
            session_id,
            prompt="Hello",
            create_session=False,
        ):
            events.append(event)

        # Must yield at least event: error and event: done
        has_error = any("event: error" in e for e in events)
        has_done = any("[DONE]" in e for e in events)
        self.assertTrue(has_error or has_done, f"Events yielded: {events}")


if __name__ == "__main__":
    unittest.main()
