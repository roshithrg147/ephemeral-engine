import os
import json
import time
import asyncio
import unittest
import tempfile
import uvicorn
import httpx
from src.main import app
from src.session_rehydration_hook import (
    load_history,
    wait_for_backend,
    rehydrate_session
)

PORT = 8091
API_URL = f"http://127.0.0.1:{PORT}"

class BackgroundUvicornServer(uvicorn.Server):
    def install_signal_handlers(self):
        pass

async def run_server(server: BackgroundUvicornServer):
    try:
        await server.serve()
    except Exception:
        pass

class TestSessionRehydration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Start uvicorn server in a separate event loop
        cls.loop = asyncio.new_event_loop()
        config = uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning")
        cls.server = BackgroundUvicornServer(config)
        
        # Start server in thread
        import threading
        def start_loop(loop, server):
            asyncio.set_event_loop(loop)
            loop.run_until_complete(server.serve())
            
        cls.thread = threading.Thread(target=start_loop, args=(cls.loop, cls.server), daemon=True)
        cls.thread.start()
        
        # Wait until uvicorn backend is fully ready
        if not wait_for_backend(API_URL, max_retries=10):
            raise RuntimeError("Failed to start background test server")

    @classmethod
    def tearDownClass(cls):
        cls.server.should_exit = True
        cls.loop.call_soon_threadsafe(cls.loop.stop)
        cls.thread.join(timeout=2.0)

    def setUp(self):
        self.session_id = "rehydrate-test-session"

    def test_load_history_json_string(self):
        history_json = '[{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]'
        turns = load_history(history_json, max_turns=6)
        self.assertEqual(len(turns), 2)
        self.assertEqual(turns[0]["role"], "user")
        self.assertEqual(turns[1]["content"], "hi")

    def test_load_history_plain_text(self):
        history_text = "User: hello\nAssistant: hi\nSystem: notification"
        turns = load_history(history_text, max_turns=6)
        self.assertEqual(len(turns), 3)
        self.assertEqual(turns[0]["role"], "user")
        self.assertEqual(turns[1]["role"], "assistant")
        self.assertEqual(turns[2]["role"], "user")
        self.assertIn("notification", turns[2]["content"])

    def test_load_history_from_file(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            f.write('[{"role": "user", "content": "file_msg"}]')
            temp_path = f.name
            
        try:
            turns = load_history(temp_path, max_turns=6)
            self.assertEqual(len(turns), 1)
            self.assertEqual(turns[0]["content"], "file_msg")
        except Exception as e:
            self.fail(f"test_load_history_from_file raised Exception: {e}")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_wait_for_backend(self):
        # Test active URL
        success = wait_for_backend(API_URL, max_retries=2)
        self.assertTrue(success)

        # Test inactive URL with quick failure
        success = wait_for_backend("http://127.0.0.1:9999", max_retries=2)
        self.assertFalse(success)

    def test_rehydrate_session_integration(self):
        history = [
            {"role": "user", "content": "Who made you?"},
            {"role": "assistant", "content": "I am an agent middleware."}
        ]
        active_context = "User is currently looking at main.py line 25"
        
        success = rehydrate_session(API_URL, self.session_id, history, active_context)
        self.assertTrue(success)
        
        # Verify from backend via GET api
        with httpx.Client(base_url=API_URL) as client:
            resp = client.get(f"/api/session/history/{self.session_id}")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["status"], "success")
            
            chat_history = data["data"]
            # Total turns should be: 2 history + 1 active file context = 3 messages
            self.assertEqual(len(chat_history), 3)
            self.assertEqual(chat_history[0]["content"], "Who made you?")
            self.assertEqual(chat_history[1]["content"], "I am an agent middleware.")
            self.assertIn("main.py", chat_history[2]["content"])

if __name__ == "__main__":
    unittest.main()
