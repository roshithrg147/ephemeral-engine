import os
import sys
import json
import threading
import queue
import time
import logging
import hashlib
import re
import subprocess
from collections import deque
import pyperclip
try:
    from pyperclip import PyperclipException
except ImportError:
    class PyperclipException(Exception): pass

_mock_clipboard = ""

def safe_paste():
    global _mock_clipboard
    try:
        return pyperclip.paste()
    except (PyperclipException, Exception):
        return _mock_clipboard

def safe_copy(text):
    global _mock_clipboard
    _mock_clipboard = text
    try:
        pyperclip.copy(text)
    except (PyperclipException, Exception):
        pass

from src.sync import SyncService

try:
    from cryptography.fernet import Fernet
except ImportError:
    logging.error("cryptography package is missing. Install with: pip install cryptography")
    raise

logger = logging.getLogger(__name__)

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class AIService:
    def __init__(self, agent_orchestrator):
        self.agent = agent_orchestrator

    def generate_summary(self, text: str) -> str:
        if not self.agent:
            return "Error: Dual-LLM Agent not configured."
        try:
            prompt = f"Analyze the copied text and provide a very brief, useful insight, summary, or extracted data. Be concise.\n\nCopied Text:\n{text}"
            response = self.agent.generate_response(prompt)
            return response.text.strip()
        except Exception as e:
            return f"AI Error: {str(e)}"

    def transform_code(self, text: str, transform_type: str) -> str:
        if not self.agent:
            return "Error: Dual-LLM Agent not configured."
        
        prompts = {
            "refactor_pythonic": "Refactor the following code to be more 'Pythonic' and idiomatic Python. Return only the refactored code.\n\n",
            "refactor_rust": "Convert the following code logic to Rust. Return only the Rust code.\n\n",
            "refactor_bug": "Identify and fix potential bugs in the following code. Return only the fixed code.\n\n",
            "logic_check_rust": "Perform a logic check on the following Python code and explain how to implement it correctly in Rust to avoid common pitfalls (like memory safety). Return a brief analysis and Rust snippet.\n\n"
        }
        
        prompt_prefix = prompts.get(transform_type, "Refactor the following code:\n\n")
        try:
            response = self.agent.generate_response(f"{prompt_prefix}{text}")
            return response.text.strip()
        except Exception as e:
            return f"AI Transformation Error: {str(e)}"

class ClipboardService:
    def __init__(self, agent_orchestrator, update_queue: queue.Queue, history_limit: int = 10, max_clip_size: int = 1024 * 1024):
        self.update_queue = update_queue
        self.history_limit = history_limit
        self.max_clip_size = max_clip_size
        self.history = deque(maxlen=history_limit)
        self.lock = threading.Lock()
        
        self._key = Fernet.generate_key()
        self._cipher = Fernet(self._key)
        
        self.dlp_patterns = {
            "AWS_KEY": re.compile(r'(?<![A-Z0-9])[A-Z0-9]{20}(?![A-Z0-9])'),
            "SSH_PRIVATE_KEY": re.compile(r'-----BEGIN (RSA|OPENSSH|DSA|EC|PGP) PRIVATE KEY-----'),
            "JWT_TOKEN": re.compile(r'eyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*'),
            "KUBECONFIG": re.compile(r'client-certificate-data:\s*[A-Za-z0-9+/=]+'),
            "CREDIT_CARD": re.compile(r'\b(?:\d[ -]*?){13,16}\b')
        }
        
        self.multi_paste_buffer = deque()
        self._running = False
        self._thread = None
        self._last_clip_hash = None
        self.is_paused = False
        self.templates = []
        
        self.sensitive_apps = ['vault', 'sudo', 'keepass', '1password', 'bitwarden']
        
        self.agent_orchestrator = agent_orchestrator
        self.ai_enabled = False
        self.ai_insights = {}
        self.ai_queue = queue.Queue()
        self.ai_service = AIService(self.agent_orchestrator)
        self._ai_thread = None
        
        # E2EE Sync Service
        self.sync_service = SyncService(update_queue=self.update_queue)
        
        self._load_templates()

    def _load_templates(self):
        template_file = os.path.expanduser("~/.config/anthropic-agent/templates.json")
        if not os.path.exists(os.path.dirname(template_file)):
            os.makedirs(os.path.dirname(template_file), exist_ok=True)
            
        if not os.path.exists(template_file):
            default_templates = [
                {"title": "Weekly Update Template", "content": "Hi Team,\n\nHere is my update:\n- Done:\n- Blockers:\n- Next:\n\nThanks,"},
                {"title": "Zoom Meeting Link", "content": "Join Zoom Meeting\nhttps://zoom.us/j/1234567890\nPasscode: 123456"},
                {"title": "Reject Email (Polite)", "content": "Thank you for reaching out. Unfortunately, we are not able to proceed at this time."}
            ]
            with open(template_file, "w") as f:
                json.dump(default_templates, f, indent=4)
                
        try:
            with open(template_file, "r") as f:
                self.templates = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load templates: {e}")

    def get_templates(self):
        return self.templates

    def restore_template(self, index: int):
        if 0 <= index < len(self.templates):
            self.copy_to_clipboard(self.templates[index]["content"])

    def toggle_pause(self):
        self.is_paused = not self.is_paused
        logger.info(f"Clipboard recording paused: {self.is_paused}")

    def start(self):
        if self._running: return
        self._running = True
        self._thread = threading.Thread(target=self._observe_clipboard, daemon=True)
        self._thread.start()
        
        self._ai_thread = threading.Thread(target=self._process_ai_insights, daemon=True)
        self._ai_thread.start()

        if self.sync_service.enabled:
            self.sync_service.start()

    def _process_ai_insights(self):
        while self._running:
            try:
                clip_hash, text = self.ai_queue.get(timeout=1.0)
            except queue.Empty:
                continue
                
            if not self.ai_enabled or self.is_paused:
                continue
                
            insight = self.ai_service.generate_summary(text)
            if self._cipher:
                encrypted_insight = self._cipher.encrypt(insight.encode('utf-8'))
                self.ai_insights[clip_hash] = encrypted_insight
                self._push_update_to_ui()

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive(): self._thread.join(timeout=0.1)
        if self._ai_thread and self._ai_thread.is_alive(): self._ai_thread.join(timeout=0.1)
        self.sync_service.stop()
        self.clear_memory()

    def clear_memory(self):
        with self.lock:
            self._key = b"\x00" * 44
            self._cipher = None
            while self.history:
                item = self.history.pop()
                del item
            self._last_clip_hash = None
            
            if hasattr(self, 'ai_insights'):
                self.ai_insights.clear()
                while not self.ai_queue.empty():
                    try:
                        item = self.ai_queue.get_nowait()
                        del item
                    except queue.Empty: break
        import gc
        gc.collect()

    def _get_hash(self, text: str) -> str:
        return hashlib.sha256(text.encode('utf-8', errors='ignore')).hexdigest() if text else None

    def _is_sensitive_or_invalid(self, text: str) -> bool:
        if not text or len(text) < 3: return True
        for pattern in self.dlp_patterns.values():
            if pattern.search(text):
                return True

        # Bypass entropy checks for URLs and file paths
        if text.startswith(("http://", "https://", "~/", "./")) or "/" in text or "\\" in text:
            return False

        def get_entropy(s):
            import math
            if not s: return 0
            entropy = 0
            encoded = s.encode('utf-8', errors='ignore')
            total_len = len(encoded)
            if total_len == 0: return 0
            counts = [0] * 256
            for b in encoded:
                counts[b] += 1
            for count in counts:
                if count > 0:
                    p_x = float(count) / total_len
                    entropy += -p_x * math.log(p_x, 2)
            return entropy

        if len(text) > 8 and get_entropy(text) > 4.5 and " " not in text:
            return True

        return False

    def _mask_sensitive_data(self, text: str) -> str:
        masked_text = text
        for label, pattern in self.dlp_patterns.items():
            masked_text = pattern.sub(f"[*** MASKED {label} ***]", masked_text)
        return masked_text

    def _push_update_to_ui(self):
        display_list = []
        with self.lock:
            history_copy = list(self.history)
            
        for encrypted_item in history_copy:
            try:
                plaintext = self._cipher.decrypt(encrypted_item).decode('utf-8', errors='ignore')
                item_hash = self._get_hash(plaintext)
                display_text = self._mask_sensitive_data(plaintext.replace('\n', ' '))
                if len(display_text) > 80: display_text = display_text[:77] + "..."
                if hasattr(self, 'ai_insights') and item_hash in self.ai_insights:
                    display_text += " [✨ AI]"
                display_list.append(display_text)
                del plaintext
            except Exception as e:
                logger.error(f"Error decrypting item for UI: {e}")
                display_list.append("[Encrypted Data]")
        
        if self.update_queue:
            self.update_queue.put({"type": "new_clip", "data": display_list})

    def ingest_remote_clip(self, text: str, timestamp: float):
        if not text: return
        current_hash = self._get_hash(text)
        
        with self.lock:
            if self._last_clip_hash == current_hash: return
            
            encrypted_clip = self._cipher.encrypt(text.encode('utf-8'))
            self.history.appendleft(encrypted_clip)
            self._last_clip_hash = current_hash
            
            if self.ai_enabled:
                self.ai_queue.put((current_hash, text))
                
        self._push_update_to_ui()

    def add_external_clip(self, text: str):
        if not text or len(text.encode('utf-8', errors='ignore')) > self.max_clip_size: return
        
        is_agent = False
        if text.startswith("AGENT_RESPONSE:"):
            text = text[len("AGENT_RESPONSE:"):]
            is_agent = True
            
        if is_agent or not self._is_sensitive_or_invalid(text):
            stored_text = f"[🤖 Agent] {text}" if is_agent else text
            current_hash = self._get_hash(stored_text)
            
            with self.lock:
                if self._last_clip_hash == current_hash: return
                
                encrypted_clip = self._cipher.encrypt(stored_text.encode('utf-8'))
                self.history.appendleft(encrypted_clip)
                self._last_clip_hash = current_hash
                
                if self.ai_enabled and not is_agent:
                    self.ai_queue.put((current_hash, stored_text))
            
            if self.sync_service.enabled and not is_agent:
                self.sync_service.push(text)

            self._push_update_to_ui()
            self.copy_to_clipboard(text)

    def _is_terminal_or_vault_active(self):
        try:
            window_name = ""
            import platform
            sys_name = platform.system()
            
            if sys_name == "Darwin":
                cmd = ['osascript', '-e', 'tell application "System Events" to get name of first process whose frontmost is true']
                output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
                window_name = output.decode('utf-8').strip().lower()
            elif sys_name == "Linux":
                try:
                    cmd = ['gdbus', 'call', '--session', '--dest', 'org.gnome.Shell', '--object-path', '/org/gnome/Shell', '--method', 'org.gnome.Shell.Eval', 'global.get_window_actors().map(a => a.get_meta_window()).find(w => w.has_focus()).get_title()']
                    output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
                    window_name = output.decode('utf-8').split("'")[1].lower()
                except Exception:
                    try:
                        cmd = ['qdbus', 'org.kde.KWin', '/KWin', 'org.kde.KWin.activeWindow']
                        output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
                        window_name = output.decode('utf-8').lower()
                    except Exception:
                        try:
                            output = subprocess.check_output(['xdotool', 'getactivewindow', 'getwindowname'], stderr=subprocess.DEVNULL)
                            window_name = output.decode('utf-8').lower()
                        except Exception: pass
            elif sys_name == "Windows":
                try:
                    import pygetwindow as gw
                    window = gw.getActiveWindow()
                    if window: window_name = window.title.lower()
                except ImportError: pass

            if any(term in window_name for term in self.sensitive_apps):
                return True
        except Exception: pass
        return False

    def _observe_clipboard(self):
        while self._running:
            try:
                if self.is_paused or self._is_terminal_or_vault_active():
                    time.sleep(1.0)
                    continue
                    
                current_clip = safe_paste()
                current_hash = self._get_hash(current_clip)
                
                if current_hash != self._last_clip_hash:
                    if len(current_clip.encode('utf-8', errors='ignore')) > self.max_clip_size:
                        self._last_clip_hash = current_hash
                        continue
                    if not self._is_sensitive_or_invalid(current_clip):
                        encrypted_clip = self._cipher.encrypt(current_clip.encode('utf-8'))
                        with self.lock:
                            self.history.appendleft(encrypted_clip)
                        if self.ai_enabled:
                            self.ai_queue.put((current_hash, current_clip))
                        
                        if self.sync_service.enabled:
                            self.sync_service.push(current_clip)

                        self._push_update_to_ui()
                    self._last_clip_hash = current_hash
            except Exception as e:
                logger.error(f"Clipboard observer error: {e}")
            time.sleep(0.5)

    def restore_from_index(self, index: int):
        with self.lock:
            if 0 <= index < len(self.history):
                try:
                    encrypted_item = self.history[index]
                    plaintext = self._cipher.decrypt(encrypted_item).decode('utf-8', errors='ignore')
                    if plaintext.startswith("[🤖 Agent] "):
                        plaintext = plaintext[len("[🤖 Agent] "):]
                    self.copy_to_clipboard(plaintext)
                    del plaintext
                except Exception as e:
                    logger.error(f"Error restoring from index {index}: {e}")

    def queue_multi_paste(self, indices: list):
        with self.lock:
            self.multi_paste_buffer.clear()
            for idx in indices:
                if 0 <= idx < len(self.history):
                    self.multi_paste_buffer.append(self.history[idx])

    def pop_multi_paste(self):
        if self.multi_paste_buffer:
            try:
                encrypted_item = self.multi_paste_buffer.popleft()
                plaintext = self._cipher.decrypt(encrypted_item).decode('utf-8', errors='ignore')
                self.copy_to_clipboard(plaintext)
                del plaintext
            except Exception as e:
                logger.error(f"Error popping multi-paste: {e}")

    def transform_item(self, index: int, transform_type: str):
        plaintext = None
        with self.lock:
            if 0 <= index < len(self.history):
                try:
                    encrypted_item = self.history[index]
                    plaintext = self._cipher.decrypt(encrypted_item).decode('utf-8', errors='ignore')
                except Exception as e:
                    logger.error(f"Error decrypting item for transform at index {index}: {e}")
                    return

        if plaintext is None: return

        transformed_text = plaintext
        try:
            if transform_type == "json":
                try:
                    parsed = json.loads(plaintext)
                    transformed_text = json.dumps(parsed, indent=4)
                except json.JSONDecodeError: return
            elif transform_type == "camel":
                parts = plaintext.replace('_', ' ').replace('-', ' ').split()
                if parts: transformed_text = parts[0].lower() + ''.join(word.capitalize() for word in parts[1:])
            elif transform_type == "snake":
                s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', plaintext)
                transformed_text = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
                transformed_text = transformed_text.replace('-', '_').replace(' ', '_')
            elif transform_type == "base64":
                import base64
                transformed_text = base64.b64encode(plaintext.encode('utf-8')).decode('utf-8')
            elif transform_type == "base64_decode":
                import base64
                try: transformed_text = base64.b64decode(plaintext.strip()).decode('utf-8')
                except Exception: return
            elif transform_type.startswith("refactor_") or transform_type == "logic_check_rust":
                transformed_text = self.ai_service.transform_code(plaintext, transform_type)
        except Exception as e:
            logger.error(f"Error transforming item at index {index}: {e}")
            return
        finally:
            del plaintext

        self.add_external_clip(transformed_text)

    def copy_to_clipboard(self, text: str):
        try:
            safe_copy(text)
            self._last_clip_hash = self._get_hash(text)
        except Exception: pass
