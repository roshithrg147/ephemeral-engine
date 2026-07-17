import asyncio
import json
import os
import tempfile
import time
import unittest

import httpx
import pytest
import uvicorn

from src.apply_diff_engine import generate_preview
from src.main import app
from src.secure_lifecycle_manager import (
    REGISTRY_PATH,
    purge_local_temp_previews,
    trigger_session_burn,
)

PORT = 8092
API_URL = f"http://127.0.0.1:{PORT}"
pytestmark = pytest.mark.network


class BackgroundUvicornServer(uvicorn.Server):
    def install_signal_handlers(self):
        pass


@unittest.skipUnless(
    os.getenv("SC_EVM_RUN_NETWORK_TESTS") == "1",
    "set SC_EVM_RUN_NETWORK_TESTS=1 to run localhost lifecycle tests",
)
class TestSecureLifecycle(unittest.TestCase):
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
            try:
                loop.run_until_complete(server.serve())
            finally:
                loop.close()

        cls.thread = threading.Thread(target=start_loop, args=(cls.loop, cls.server), daemon=True)
        cls.thread.start()

        # Wait until uvicorn backend is fully ready
        ready = False
        for _ in range(10):
            try:
                response = httpx.get(API_URL, timeout=1.0)
                if response.status_code in (200, 404):
                    ready = True
                    break
            except Exception:
                pass
            time.sleep(1.0)
        if not ready:
            raise RuntimeError("Failed to start background test server")

    @classmethod
    def tearDownClass(cls):
        cls.loop.call_soon_threadsafe(setattr, cls.server, "should_exit", True)
        cls.thread.join(timeout=5.0)
        if cls.thread.is_alive():
            raise RuntimeError("Background test server did not stop cleanly")

    def setUp(self):
        self.session_id = "lifecycle-test-session"
        # Backup existing registry path if it exists
        self.registry_backup = None
        if os.path.exists(REGISTRY_PATH):
            try:
                with open(REGISTRY_PATH) as f:
                    self.registry_backup = f.read()
                os.remove(REGISTRY_PATH)
            except Exception:
                pass

    def tearDown(self):
        # Clean up and restore registry backup
        if os.path.exists(REGISTRY_PATH):
            try:
                os.remove(REGISTRY_PATH)
            except Exception:
                pass
        if self.registry_backup is not None:
            try:
                os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
                with open(REGISTRY_PATH, "w") as f:
                    f.write(self.registry_backup)
            except Exception:
                pass

    def test_temp_file_registration_and_purge(self):
        # Create a sample file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Original line 1\nOriginal line 2\n")
            sample_path = f.name

        try:
            # Generate preview (which triggers registration)
            diff_data = {
                "file_path": sample_path,
                "start_line": 1,
                "end_line": 1,
                "new_content": "Modified line 1\n",
            }
            preview_path = generate_preview(diff_data)
            self.assertTrue(os.path.exists(preview_path))

            # Check registration in temp_previews.json
            self.assertTrue(os.path.exists(REGISTRY_PATH))
            with open(REGISTRY_PATH) as rf:
                registered_paths = json.load(rf)
            self.assertIn(preview_path, registered_paths)

            # Execute local purge
            purged = purge_local_temp_previews()
            self.assertEqual(purged, 1)

            # Verify preview file and registry file are deleted
            self.assertFalse(os.path.exists(preview_path))
            self.assertFalse(os.path.exists(REGISTRY_PATH))

        finally:
            if os.path.exists(sample_path):
                os.remove(sample_path)

    def test_session_burn_integration(self):
        # 1. Initialize session on backend
        with httpx.Client(base_url=API_URL) as client:
            resp = client.post("/api/session/initialize", json={"session_id": self.session_id})
            self.assertEqual(resp.status_code, 200)

            # Verify session exists
            resp = client.get(f"/api/session/history/{self.session_id}")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json()["status"], "success")

        # 2. Trigger secure lifecycle burn
        success = trigger_session_burn(API_URL, self.session_id)
        self.assertTrue(success)

        with httpx.Client(base_url=API_URL) as client:
            resp = client.get(f"/api/session/history/{self.session_id}")
            self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
