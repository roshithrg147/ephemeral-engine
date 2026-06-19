import asyncio
import unittest
from src.memory import MultiTenantSessionRegistry

class TestConcurrencyStress(unittest.IsolatedAsyncioTestCase):
    async def test_stress_concurrent_operations(self):
        registry = MultiTenantSessionRegistry()
        session_id = "stress-session-123"
        
        # 1. Initialize session
        await registry.initialize_session(session_id)
        
        # 2. Simulate 10 concurrent tasks (mix of reads and writes)
        results = []
        
        async def read_task(idx):
            await asyncio.sleep(0.005 * idx)  # Slight stagger to overlap calls
            session = await registry.get_session(session_id)
            history_len = len(session.chat_history)
            results.append(f"read_{idx}_len_{history_len}")
            
        async def write_task(idx):
            await asyncio.sleep(0.005 * idx)
            await registry.append_message(session_id, "user", f"message_{idx}")
            results.append(f"write_{idx}")
            
        # Create a mix of 5 writes and 5 reads
        tasks = []
        for i in range(10):
            if i % 2 == 0:
                tasks.append(write_task(i))
            else:
                tasks.append(read_task(i))
                
        await asyncio.gather(*tasks)
        
        # 3. Verify final state
        session = await registry.get_session(session_id)
        self.assertEqual(len(session.chat_history), 5)
        
        # Confirm all 5 messages are in history
        messages = [turn["content"] for turn in session.chat_history]
        for idx in range(0, 10, 2):
            self.assertIn(f"message_{idx}", messages)
            
        # Verify execution log
        self.assertEqual(len(results), 10)

if __name__ == "__main__":
    unittest.main()
