import json
import logging
import os
import socket
import threading
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor

from src.agent import AgentOrchestrator, MemorySnapshot
from src.clipboard_gui import ClipboardConsumerApp
from src.config import settings
from src.memory import MemoryManager

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

SOCKET_PATH = os.path.expanduser("~/.config/anthropic-agent/daemon.sock")


class UnifiedDaemon:
    def __init__(self):
        # 1. Initialize Memory & Agent
        self.memory = MemoryManager()
        self.agent = AgentOrchestrator()

        # 2. Setup Tkinter UI & Clipboard App
        self.root = tk.Tk()
        self.app = ClipboardConsumerApp(self.root, self.agent, self.memory)

        # 3. Setup IPC Server
        self.server = None
        self._request_pool = ThreadPoolExecutor(
            max_workers=settings.MAX_WORKER_THREADS,
            thread_name_prefix="sc-evm-ipc",
        )
        self._ipc_thread = threading.Thread(target=self._ipc_listener, daemon=True)
        self._ipc_thread.start()

    @staticmethod
    def _send_json(conn, payload) -> None:
        conn.sendall(json.dumps(payload).encode("utf-8"))

    def _recent_history_clips(self, limit: int = 5) -> list[str]:
        history_list = []
        with self.app.service.lock:
            history_copy = list(self.app.service.history)[:limit]
        for enc in history_copy:
            try:
                plain = self.app.service._cipher.decrypt(enc).decode("utf-8", errors="ignore")
                history_list.append(plain)
            except Exception as exc:
                logger.warning(
                    "Failed to decrypt history clip", exc_info=True, extra={"error": str(exc)}
                )
        return history_list

    def _setup_socket(self):
        os.makedirs(os.path.dirname(SOCKET_PATH), exist_ok=True)
        if os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(SOCKET_PATH)
        os.chmod(SOCKET_PATH, 0o600)  # Extremely strict local permissions for security
        self.server.listen(5)
        logger.info(f"IPC socket listening securely at {SOCKET_PATH}")

    def _ipc_listener(self):
        try:
            self._setup_socket()
            while True:
                try:
                    conn, _ = self.server.accept()
                    chunks = []
                    received = 0
                    while True:
                        chunk = conn.recv(8192)
                        if not chunk:
                            break
                        received += len(chunk)
                        if received > settings.IPC_MAX_PAYLOAD_BYTES:
                            self._send_json(conn, {"error": "IPC payload too large"})
                            conn.close()
                            break
                        chunks.append(chunk)
                    if received > settings.IPC_MAX_PAYLOAD_BYTES:
                        continue
                    data = b"".join(chunks).decode("utf-8", errors="ignore")

                    if not data:
                        conn.close()
                        continue

                    # Determine if JSON payload (from thin CLI) or legacy clipboard command
                    try:
                        payload = json.loads(data)
                        if payload.get("action") == "chat":
                            prompt = payload.get("prompt", "")
                            # Run agent in background thread to not block IPC accept loop
                            self._request_pool.submit(self._handle_chat_request, conn, prompt)
                            continue  # Worker handles closing.
                        elif payload.get("action") == "get_memory":
                            mem_data = {
                                "user_profile": self.memory.long_term_data.get("user_profile", {}),
                                "learned_facts": self.memory.long_term_data.get(
                                    "learned_facts", []
                                ),
                            }
                            self._send_json(conn, mem_data)
                        elif payload.get("action") == "get_history":
                            self._send_json(conn, self.memory.get_short_term_history())
                        elif payload.get("action") == "get_history_clips":
                            self._send_json(conn, self._recent_history_clips())
                        elif payload.get("action") == "generate_image":
                            filepath = self.agent.generate_image(
                                payload.get("prompt"), payload.get("filename")
                            )
                            self._send_json(conn, {"filepath": filepath})
                    except json.JSONDecodeError:
                        # Legacy string commands
                        if data == "SHOW":
                            self.root.after(0, self.app.show_window)
                        elif data in ("QUIT", "SHUTDOWN"):
                            self.root.after(0, self.app.shutdown)
                        elif data.startswith("ADD:"):
                            self.app.service.add_external_clip(data[4:])
                        elif data == "GET_HISTORY":
                            self._send_json(conn, self._recent_history_clips())

                    conn.close()
                except Exception as e:
                    logger.error(f"IPC listener connection error: {e}")
        except Exception as e:
            logger.error(f"IPC listener fatal error: {e}")
        finally:
            if self.server:
                self.server.close()
            self._request_pool.shutdown(wait=False, cancel_futures=True)
            if os.path.exists(SOCKET_PATH):
                try:
                    os.remove(SOCKET_PATH)
                except OSError as exc:
                    logger.warning(
                        "Failed to remove IPC socket during shutdown",
                        exc_info=True,
                        extra={"error": str(exc)},
                    )

    def _handle_chat_request(self, conn, prompt):
        try:
            snapshot = MemorySnapshot(
                long_term_context=self.memory.get_long_term_context(),
                short_term_history=list(self.memory.get_short_term_history()),
            )
            response = self.agent.generate_response(snapshot, prompt)
            for fact in response.remember:
                self.memory.add_fact(fact)
            self.memory.add_interaction(prompt, response.text)
            self._send_json(conn, response.model_dump())
        except Exception as e:
            self._send_json(conn, {"error": str(e)})
        finally:
            conn.close()

    def run(self):
        logger.info("Starting Unified Daemon...")
        self.root.mainloop()


if __name__ == "__main__":
    daemon = UnifiedDaemon()
    daemon.run()
