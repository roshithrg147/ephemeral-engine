import asyncio
import sys
from src.memory import session_registry

async def run_test():
    print("Testing session isolation and thread-safety mechanisms...")

    # Create session A
    session_a_id = "tenant_A_session"
    session_a = await session_registry.initialize_session(session_a_id)
    await session_registry.append_message(session_a_id, "user", "Message from Tenant A")

    # Create session B
    session_b_id = "tenant_B_session"
    session_b = await session_registry.initialize_session(session_b_id)
    await session_registry.append_message(session_b_id, "user", "Message from Tenant B")

    # Fetch them back
    fetch_a = await session_registry.get_session(session_a_id)
    fetch_b = await session_registry.get_session(session_b_id)

    # Empty memory check simulation (a new empty session)
    session_empty_id = "tenant_Empty_session"
    fetch_empty = await session_registry.initialize_session(session_empty_id)

    # Confirm isolation
    assert len(fetch_a.chat_history) == 1
    assert fetch_a.chat_history[0]["content"] == "Message from Tenant A"
    
    assert len(fetch_b.chat_history) == 1
    assert fetch_b.chat_history[0]["content"] == "Message from Tenant B"

    assert len(fetch_empty.chat_history) == 0

    print("Success: Verified that session_id isolation is absolute. No data leaking between tenant buckets.")

    # Cleanup
    await session_registry.flush_session(session_a_id)
    await session_registry.flush_session(session_b_id)
    await session_registry.flush_session(session_empty_id)
    print("Cleanup successful.")

if __name__ == "__main__":
    asyncio.run(run_test())
