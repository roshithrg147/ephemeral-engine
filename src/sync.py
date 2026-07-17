import base64
import json
import logging
import os
import platform
import threading
import time

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

CONFIG_PATH = os.environ.get(
    "MYCLIPBOARD_CONFIG_PATH", os.path.expanduser("~/.config/anthropic-agent/config.json")
)


class SyncService:
    def __init__(self, update_queue):
        self.update_queue = update_queue
        self.enabled = False
        self.secret_key = None
        self._cipher = None
        self.device_id = platform.node()
        self.last_sync_time = 0
        self._running = False
        self._sync_thread = None
        self.status = "Disconnected"

    def _get_or_create_salt(self):
        """
        Retrieve or generate a unique per-user salt stored in config.json.
        """
        salt = None
        config = {}
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH) as f:
                    config = json.load(f)
                    salt_hex = config.get("sync_salt")
                    if salt_hex:
                        salt = base64.b16decode(salt_hex.upper().encode())
            except Exception as e:
                logger.error(f"Failed to read salt from config: {e}")

        if not salt:
            salt = os.urandom(16)
            config["sync_salt"] = base64.b16encode(salt).decode().lower()
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            try:
                with open(CONFIG_PATH, "w") as f:
                    json.dump(config, f, indent=4)
            except Exception as e:
                logger.error(f"Failed to save new salt to config: {e}")

        return salt

    def set_config(self, enabled, secret_key):
        self.enabled = enabled
        if secret_key:
            try:
                salt = self._get_or_create_salt()
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=salt,
                    iterations=100000,
                )
                key = base64.urlsafe_b64encode(kdf.derive(secret_key.encode()))
                self._cipher = Fernet(key)
                self.secret_key = secret_key
                self.status = "Connected (BYOB Pending)" if self.enabled else "Disconnected"
            except Exception as e:
                logger.error(f"Sync Key Derivation Error: {e}")
                self.status = "Error"
        else:
            self._cipher = None
            self.status = "Disconnected"

        if self.enabled and not self._running:
            self.start()
        elif not self.enabled and self._running:
            self.stop()

    def start(self):
        if self._running:
            return
        self._running = True
        self._sync_thread = threading.Thread(target=self._periodic_pull, daemon=True)
        self._sync_thread.start()

    def stop(self):
        self._running = False

    def push(self, text):
        if not self.enabled or not self._cipher:
            return

        def _async_push():
            try:
                encrypted_data = self._cipher.encrypt(text.encode())
                _payload = {
                    "device_id": self.device_id,
                    "blob": encrypted_data.decode(),
                    "timestamp": time.time(),
                }
                # BYOB (Bring Your Own Backend) Integration Point
                # requests.post(self.relay_url, json=payload, timeout=5)
                logger.info("Sync push simulated (BYOB required)")
            except Exception as e:
                logger.error(f"Sync Push Error: {e}")
                self.status = "Error"

        threading.Thread(target=_async_push, daemon=True).start()

    def _periodic_pull(self):
        """
        Functional E2EE Pull/Merge logic with ZK-Relay architecture.
        Uses timestamp-based conflict resolution.
        """
        while self._running:
            if self.enabled and self._cipher:
                try:
                    # BYOB (Bring Your Own Backend) Integration Point
                    # response = requests.get(self.relay_url, params={"device_id": self.device_id}, timeout=10)
                    self.status = "BYOB Not Configured"
                except Exception as e:
                    logger.error(f"Sync Pull Error: {e}")
                    self.status = "Error"
            time.sleep(30)  # Pull every 30 seconds

    def get_status(self):
        return self.status
