import os
import sys
import socket
import json
import threading
import logging
import tkinter as tk
from src.memory import MemoryManager
from src.agent import AgentOrchestrator
from src.clipboard_gui import ClipboardConsumerApp

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

SOCKET_PATH = os.path.expanduser("~/.config/anthropic-agent/daemon.sock")

class UnifiedDaemon:
    def __init__(self):
        # 1. Initialize Memory & Agent
        self.memory = MemoryManager()
        self.agent = AgentOrchestrator(memory_manager=self.memory)

        # 2. Setup Tkinter UI & Clipboard App
        self.root = tk.Tk()
        self.app = ClipboardConsumerApp(self.root, self.agent)

        # 3. Setup IPC Server
        self.server = None
        self._ipc_thread = threading.Thread(target=self._ipc_listener, daemon=True)
        self._ipc_thread.start()

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
                    while True:
                        chunk = conn.recv(8192)
                        if not chunk: break
                        chunks.append(chunk)
                    data = b"".join(chunks).decode('utf-8', errors='ignore')
                    
                    if not data:
                        conn.close()
                        continue

                    # Determine if JSON payload (from thin CLI) or legacy clipboard command
                    try:
                        payload = json.loads(data)
                        if payload.get("action") == "chat":
                            prompt = payload.get("prompt", "")
                            # Run agent in background thread to not block IPC accept loop
                            threading.Thread(target=self._handle_chat_request, args=(conn, prompt), daemon=True).start()
                            continue # Thread handles closing
                        elif payload.get("action") == "get_memory":
                            mem_data = {
                                "user_profile": self.memory.long_term_data.get("user_profile", {}),
                                "learned_facts": self.memory.long_term_data.get("learned_facts", [])
                            }
                            conn.sendall(json.dumps(mem_data).encode('utf-8'))
                        elif payload.get("action") == "get_history":
                            history = self.memory.get_short_term_history()
                            conn.sendall(json.dumps(history).encode('utf-8'))
                        elif payload.get("action") == "get_history_clips":
                            history_list = []
                            with self.app.service.lock:
                                history_copy = list(self.app.service.history)[:5]
                            for enc in history_copy:
                                try:
                                    plain = self.app.service._cipher.decrypt(enc).decode('utf-8', errors='ignore')
                                    history_list.append(plain)
                                except: pass
                            conn.sendall(json.dumps(history_list).encode('utf-8'))
                        elif payload.get("action") == "generate_image":
                            filepath = self.agent.generate_image(payload.get("prompt"), payload.get("filename"))
                            conn.sendall(json.dumps({"filepath": filepath}).encode('utf-8'))
                    except json.JSONDecodeError:
                        # Legacy string commands
                        if data == "SHOW":
                            self.root.after(0, self.app.show_window)
                        elif data in ("QUIT", "SHUTDOWN"):
                            self.root.after(0, self.app.shutdown)
                        elif data.startswith("ADD:"):
                            self.app.service.add_external_clip(data[4:])
                        elif data == "GET_HISTORY":
                            history_list = []
                            with self.app.service.lock:
                                history_copy = list(self.app.service.history)[:5]
                            for enc in history_copy:
                                try:
                                    plain = self.app.service._cipher.decrypt(enc).decode('utf-8', errors='ignore')
                                    history_list.append(plain)
                                except: pass
                            conn.sendall(json.dumps(history_list).encode('utf-8'))
                    
                    conn.close()
                except Exception as e:
                    logger.error(f"IPC listener connection error: {e}")
        except Exception as e:
            logger.error(f"IPC listener fatal error: {e}")
        finally:
            if self.server: self.server.close()
            if os.path.exists(SOCKET_PATH):
                try: os.remove(SOCKET_PATH)
                except OSError: pass

    def _handle_chat_request(self, conn, prompt):
        try:
            response = self.agent.generate_response(prompt)
            # Response is a RefinedResponse model. Convert to JSON string.
            resp_json = response.model_dump_json()
            conn.sendall(resp_json.encode('utf-8'))
        except Exception as e:
            err_json = json.dumps({"error": str(e)})
            conn.sendall(err_json.encode('utf-8'))
        finally:
            conn.close()

    def run(self):
        logger.info("Starting Unified Daemon...")
        self.root.mainloop()

if __name__ == "__main__":
    daemon = UnifiedDaemon()
    daemon.run()
