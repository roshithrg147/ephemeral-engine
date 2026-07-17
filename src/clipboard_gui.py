import importlib.util
import json
import logging
import os
import queue
import signal
import sys
import threading
import tkinter as tk
import tkinter.ttk as ttk

import pystray
from PIL import Image

from src.clipboard_service import ClipboardService

try:
    from pynput import keyboard
except ImportError:
    logging.warning("pynput package is missing. Global hotkeys will be disabled.")
    keyboard = None

try:
    from src.telemetry_sink import log_error
except ImportError:

    def log_error(ctx, msg):
        return None


logger = logging.getLogger(__name__)

CONFIG_PATH = os.environ.get(
    "MYCLIPBOARD_CONFIG_PATH", os.path.expanduser("~/.config/anthropic-agent/config.json")
)


def verify_environment():
    system = sys.platform
    if system.startswith("linux"):
        from shutil import which

        if not (which("xclip") or which("xsel") or which("wl-clipboard")):
            logger.warning(
                "System dependency missing: xclip, xsel, or wl-clipboard is required on Linux. Pyperclip might fail."
            )
    elif system == "darwin":
        if importlib.util.find_spec("tkinter") is None:
            logger.warning("Tkinter is missing.")


verify_environment()

THEME = {
    "bg": "#0A0A0A",
    "fg": "#00FF41",
    "accent": "#FF0055",
    "status_ok": "#00FF41",
    "status_err": "#FF0000",
    "font": ("JetBrains Mono", 10),
    "font_bold": ("JetBrains Mono", 10, "bold"),
}


class ClipboardConsumerApp:
    def __init__(self, root: tk.Tk, agent_orchestrator, memory_manager=None):
        self.root = root
        self.root.configure(bg=THEME["bg"])
        self.update_queue = queue.Queue()
        self.service = ClipboardService(
            agent_orchestrator, update_queue=self.update_queue, memory_manager=memory_manager
        )

        self.history: list[str] = []
        self.filtered_history: list[tuple[int, str]] = []

        self.config = self._load_config()
        self.templates = self.service.get_templates()
        self.filtered_templates: list[tuple[int, str]] = []

        self._setup_ui()
        self._setup_signals()
        self._setup_tray()
        self._setup_hotkeys()

        self.service.start()
        self._check_for_updates()

    def _load_config(self):
        default_config = {
            "hotkey_show": "<ctrl>+<alt>+c" if sys.platform != "darwin" else "<cmd>+<alt>+c",
            "hotkey_multi_paste": "<ctrl>+<alt>+v" if sys.platform != "darwin" else "<cmd>+<alt>+v",
            "is_enterprise": True,
        }
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH) as f:
                    user_config = json.load(f)
                    default_config.update(user_config)
            except Exception as e:
                logger.error(f"Failed to load config: {e}")
        return default_config

    def _save_config(self):
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        try:
            with open(CONFIG_PATH, "w") as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def _decrypt_history_item(self, original_idx: int) -> tuple[str, str]:
        encrypted_item = self.service.history[original_idx]
        plaintext = self.service._cipher.decrypt(encrypted_item).decode("utf-8", errors="ignore")
        item_hash = self.service._get_hash(plaintext)
        return plaintext, item_hash

    def _format_insight_block(self, item_hash: str) -> str:
        if not hasattr(self.service, "ai_insights") or item_hash not in self.service.ai_insights:
            return ""
        enc_insight = self.service.ai_insights[item_hash]
        insight_text = self.service._cipher.decrypt(enc_insight).decode("utf-8", errors="ignore")
        return f"✨ AI Insight:\n{insight_text}\n\n---\n\n"

    def _update_sync_status(self, status: str) -> None:
        self.sync_status_label.config(
            text=f"STATUS: {status}",
            fg=THEME["status_ok"] if "Connected" in status else THEME["status_err"],
        )

    def _selected_history_original_index(self) -> int | None:
        selection = self.listbox.curselection()
        if not selection:
            return None

        filtered_index = selection[0]
        if filtered_index >= len(self.filtered_history):
            return None
        return self.filtered_history[filtered_index][0]

    def _setup_ui(self):
        self.root.title("MyClipboard Enterprise [GHOST]")
        self.root.geometry("500x700")
        self.root.attributes("-alpha", 0.95)

        self.root.bind("<<NewClip>>", lambda e: self._render_listbox())

        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("TNotebook", background=THEME["bg"], borderwidth=0)
        self.style.configure(
            "TNotebook.Tab",
            background=THEME["bg"],
            foreground=THEME["fg"],
            font=THEME["font_bold"],
            padding=[10, 5],
        )
        self.style.map(
            "TNotebook.Tab",
            background=[("selected", THEME["fg"])],
            foreground=[("selected", THEME["bg"])],
        )

        self.style.configure(
            "TCheckbutton", background=THEME["bg"], foreground=THEME["fg"], font=THEME["font"]
        )
        self.style.configure(
            "TButton", background=THEME["bg"], foreground=THEME["fg"], font=THEME["font_bold"]
        )

        search_frame = tk.Frame(self.root, bg=THEME["bg"])
        search_frame.pack(fill=tk.X, padx=10, pady=(15, 5))

        tk.Label(
            search_frame, text="> SEARCH:", font=THEME["font_bold"], bg=THEME["bg"], fg=THEME["fg"]
        ).pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._on_search_change)

        self.search_entry = tk.Entry(
            search_frame,
            textvariable=self.search_var,
            font=THEME["font"],
            bg=THEME["bg"],
            fg=THEME["fg"],
            insertbackground=THEME["fg"],
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=THEME["fg"],
            highlightcolor=THEME["fg"],
        )
        self.search_entry.pack(fill=tk.X, expand=True, padx=(10, 0))
        self.root.bind("<Map>", lambda e: self.search_entry.focus_set())

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_change)

        self.history_frame = tk.Frame(self.notebook, bg=THEME["bg"])
        self.notebook.add(self.history_frame, text="[HISTORY]")

        self.listbox = tk.Listbox(
            self.history_frame,
            font=THEME["font"],
            bg=THEME["bg"],
            fg=THEME["fg"],
            selectbackground=THEME["fg"],
            selectforeground=THEME["bg"],
            borderwidth=0,
            highlightthickness=0,
            selectborderwidth=0,
        )
        self.listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.listbox.bind("<Double-Button-1>", self.on_double_click)
        self.listbox.bind("<Return>", self.on_double_click)
        self.listbox.bind("<Button-3>", self.on_right_click)
        self.listbox.bind("<<ListboxSelect>>", self._on_listbox_select)

        self.details_text = tk.Text(
            self.history_frame,
            height=6,
            font=THEME["font"],
            bg=THEME["bg"],
            fg=THEME["fg"],
            insertbackground=THEME["fg"],
            state=tk.DISABLED,
            wrap=tk.WORD,
            highlightthickness=1,
            highlightbackground=THEME["fg"],
        )
        self.details_text.pack(fill=tk.X, padx=5, pady=(0, 5))

        self.templates_frame = tk.Frame(self.notebook, bg=THEME["bg"])
        self.notebook.add(self.templates_frame, text="[TEMPLATES]")
        self.template_listbox = tk.Listbox(
            self.templates_frame,
            font=THEME["font"],
            bg=THEME["bg"],
            fg=THEME["fg"],
            selectbackground=THEME["fg"],
            selectforeground=THEME["bg"],
            borderwidth=0,
            highlightthickness=0,
        )
        self.template_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.template_listbox.bind("<Double-Button-1>", self.on_template_double_click)
        self.template_listbox.bind("<Return>", self.on_template_double_click)

        self.settings_frame = tk.Frame(self.notebook, bg=THEME["bg"])
        self.notebook.add(self.settings_frame, text="[SETTINGS]")

        self.ai_enabled_var = tk.BooleanVar(value=False)
        self.ai_toggle = ttk.Checkbutton(
            self.settings_frame,
            text="PRO: ENABLE AI INSIGHTS",
            variable=self.ai_enabled_var,
            command=self._on_ai_toggle,
            style="TCheckbutton",
        )
        self.ai_toggle.pack(anchor=tk.W, padx=10, pady=(15, 5))

        tk.Label(
            self.settings_frame,
            text="GLOBAL HOTKEYS:",
            font=THEME["font_bold"],
            bg=THEME["bg"],
            fg=THEME["fg"],
        ).pack(anchor=tk.W, padx=10, pady=(15, 0))

        tk.Label(
            self.settings_frame,
            text="Show Window:",
            font=THEME["font"],
            bg=THEME["bg"],
            fg=THEME["fg"],
        ).pack(anchor=tk.W, padx=20, pady=(5, 0))
        self.hk_show_var = tk.StringVar(value=self.config["hotkey_show"])
        self.hk_show_entry = tk.Entry(
            self.settings_frame,
            textvariable=self.hk_show_var,
            font=THEME["font"],
            bg=THEME["bg"],
            fg=THEME["fg"],
            insertbackground=THEME["fg"],
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=THEME["fg"],
        )
        self.hk_show_entry.pack(fill=tk.X, padx=20, pady=(0, 5))

        tk.Label(
            self.settings_frame,
            text="Multi-Paste:",
            font=THEME["font"],
            bg=THEME["bg"],
            fg=THEME["fg"],
        ).pack(anchor=tk.W, padx=20, pady=(5, 0))
        self.hk_mp_var = tk.StringVar(value=self.config["hotkey_multi_paste"])
        self.hk_mp_entry = tk.Entry(
            self.settings_frame,
            textvariable=self.hk_mp_var,
            font=THEME["font"],
            bg=THEME["bg"],
            fg=THEME["fg"],
            insertbackground=THEME["fg"],
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=THEME["fg"],
        )
        self.hk_mp_entry.pack(fill=tk.X, padx=20, pady=(0, 10))

        self.save_settings_btn = ttk.Button(
            self.settings_frame,
            text="SAVE & RELOAD SETTINGS",
            command=self._save_all_settings,
            style="TButton",
        )
        self.save_settings_btn.pack(anchor=tk.W, padx=10, pady=10)

        tk.Label(
            self.settings_frame,
            text="DANGER ZONE:",
            font=THEME["font_bold"],
            bg=THEME["bg"],
            fg=THEME["accent"],
        ).pack(anchor=tk.W, padx=10, pady=(20, 0))
        self.kill_btn = tk.Button(
            self.settings_frame,
            text="TERMINATE SERVICE COMPLETELY",
            command=self.shutdown,
            font=THEME["font_bold"],
            bg=THEME["bg"],
            fg=THEME["accent"],
            activebackground=THEME["accent"],
            activeforeground=THEME["bg"],
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=THEME["accent"],
        )
        self.kill_btn.pack(fill=tk.X, padx=10, pady=10)

        self.sync_frame = tk.Frame(self.notebook, bg=THEME["bg"])
        self.notebook.add(self.sync_frame, text="[SYNC]")

        self.sync_enabled_var = tk.BooleanVar(value=False)
        self.sync_toggle = ttk.Checkbutton(
            self.sync_frame,
            text="ENABLE E2EE SYNC (BYOB)",
            variable=self.sync_enabled_var,
            command=self._on_sync_config_change,
            style="TCheckbutton",
        )
        self.sync_toggle.pack(anchor=tk.W, padx=10, pady=(20, 5))

        tk.Label(
            self.sync_frame,
            text="SYNC SECRET KEY:",
            font=THEME["font_bold"],
            bg=THEME["bg"],
            fg=THEME["fg"],
        ).pack(anchor=tk.W, padx=10, pady=(15, 0))
        self.sync_key_var = tk.StringVar()
        self.sync_key_entry = tk.Entry(
            self.sync_frame,
            textvariable=self.sync_key_var,
            show="*",
            font=THEME["font"],
            bg=THEME["bg"],
            fg=THEME["fg"],
            insertbackground=THEME["fg"],
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=THEME["fg"],
        )
        self.sync_key_entry.pack(fill=tk.X, padx=10, pady=(5, 10))

        self.sync_status_label = tk.Label(
            self.sync_frame,
            text="STATUS: Disconnected",
            font=THEME["font_bold"],
            bg=THEME["bg"],
            fg=THEME["status_err"],
        )
        self.sync_status_label.pack(anchor=tk.W, padx=10, pady=10)

        self.last_synced_label = tk.Label(
            self.sync_frame,
            text="LAST SYNCED: Never",
            font=THEME["font"],
            bg=THEME["bg"],
            fg=THEME["fg"],
        )
        self.last_synced_label.pack(anchor=tk.W, padx=10, pady=(0, 10))

        self.save_sync_btn = ttk.Button(
            self.sync_frame,
            text="APPLY SYNC CONFIG",
            command=self._on_sync_config_change,
            style="TButton",
        )
        self.save_sync_btn.pack(anchor=tk.W, padx=10, pady=5)

        self.context_menu = tk.Menu(self.root, tearoff=0)
        try:
            self.context_menu.configure(
                bg=THEME["bg"],
                fg=THEME["fg"],
                activebackground=THEME["fg"],
                activeforeground=THEME["bg"],
            )
        except tk.TclError as e:
            log_error("clipboard_gui.context_menu_style", str(e))

        self.context_menu.add_command(
            label="> QUEUE FOR MULTI-PASTE", command=self._trigger_multi_paste_queue
        )
        self.context_menu.add_separator()
        self.context_menu.add_command(
            label="> GENERATE AI INSIGHT", command=self._trigger_ai_insight
        )
        self.context_menu.add_separator()
        self.context_menu.add_command(
            label="> SMART: FORMAT JSON", command=lambda: self._trigger_transform("json")
        )
        self.context_menu.add_command(
            label="> SMART: TO CAMELCASE", command=lambda: self._trigger_transform("camel")
        )
        self.context_menu.add_command(
            label="> SMART: TO SNAKE_CASE", command=lambda: self._trigger_transform("snake")
        )
        self.context_menu.add_command(
            label="> SMART: ENCODE BASE64", command=lambda: self._trigger_transform("base64")
        )
        self.context_menu.add_separator()
        self.context_menu.add_command(
            label="> REFACTOR: TO PYTHONIC",
            command=lambda: self._trigger_transform("refactor_pythonic"),
        )
        self.context_menu.add_command(
            label="> REFACTOR: TO RUST", command=lambda: self._trigger_transform("refactor_rust")
        )
        self.context_menu.add_command(
            label="> REFACTOR: FIX BUG", command=lambda: self._trigger_transform("refactor_bug")
        )
        self.context_menu.add_command(
            label="> REFACTOR: PY-TO-RUST LOGIC CHECK",
            command=lambda: self._trigger_transform("logic_check_rust"),
        )

        self.root.withdraw()
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)

        self._render_templates()

    def _save_all_settings(self):
        self.config["hotkey_show"] = self.hk_show_var.get()
        self.config["hotkey_multi_paste"] = self.hk_mp_var.get()
        self._save_config()
        self._setup_hotkeys()

        import tkinter.messagebox

        tkinter.messagebox.showinfo("Ghost Settings", "Configuration saved and hotkeys reloaded.")

    def _on_sync_config_change(self):
        self.service.sync_service.set_config(self.sync_enabled_var.get(), self.sync_key_var.get())
        self._update_sync_status(self.service.sync_service.get_status())

    def _on_ai_toggle(self):
        self.service.ai_enabled = self.ai_enabled_var.get()

    def _setup_hotkeys(self):
        if keyboard is None:
            return

        if hasattr(self, "hotkey_listener"):
            self.hotkey_listener.stop()

        def on_activate_h():
            self.root.after(0, self.show_window)

        def on_activate_multi_paste():
            self.service.pop_multi_paste()

        try:
            hotkeys = {
                self.config["hotkey_show"]: on_activate_h,
                self.config["hotkey_multi_paste"]: on_activate_multi_paste,
            }
            self.hotkey_listener = keyboard.GlobalHotKeys(hotkeys)
            self.hotkey_listener.start()
        except Exception as e:
            logger.error(f"Failed to bind hotkeys: {e}")

    def _on_search_change(self, *args):
        current_tab = self.notebook.index(self.notebook.select())
        if current_tab == 0:
            self._render_listbox()
        else:
            self._render_templates()

    def _on_tab_change(self, event):
        self._on_search_change()

    def hide_window(self):
        self.root.withdraw()

    def show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.8)
        self.search_entry.focus_set()

    def _setup_signals(self):
        def _signal_handler(sig, frame):
            self.shutdown()

        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)

    def _setup_tray(self):
        image = Image.new("RGB", (64, 64), color=(73, 109, 137))

        def on_quit(icon, item):
            icon.stop()
            self.root.after(0, self.shutdown)

        def on_show(icon, item):
            self.root.after(0, self.show_window)

        def on_toggle_pause(icon, item):
            self.service.toggle_pause()

        def on_toggle_ai(icon, item):
            self.service.ai_enabled = not self.service.ai_enabled
            self.ai_enabled_var.set(self.service.ai_enabled)

        menu = pystray.Menu(
            pystray.MenuItem("Show MyClipboard", on_show, default=True),
            pystray.MenuItem("Pause/Resume Recording", on_toggle_pause),
            pystray.MenuItem("Pro: Toggle AI Insights", on_toggle_ai),
            pystray.MenuItem("Quit", on_quit),
        )
        self.icon = pystray.Icon("MyClipboard", image, "MyClipboard", menu)
        self.tray_thread = threading.Thread(target=self.icon.run, daemon=True)
        self.tray_thread.start()

    def _check_for_updates(self):
        try:
            while True:
                msg = self.update_queue.get_nowait()
                if msg["type"] == "new_clip":
                    self.history = msg["data"]
                    self.root.event_generate("<<NewClip>>")
                    self.show_window()
                elif msg["type"] == "remote_sync":
                    self.service.ingest_remote_clip(msg["data"], msg["timestamp"])
                    from datetime import datetime

                    dt_object = datetime.fromtimestamp(msg["timestamp"])
                    self.last_synced_label.config(
                        text=f"LAST SYNCED: {dt_object.strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                elif msg["type"] == "sync_conflict":
                    import tkinter.messagebox

                    tkinter.messagebox.showinfo(
                        "Sync Conflict",
                        "A remote update arrived but was superseded by a newer local copy.",
                    )
        except queue.Empty:
            return
        except Exception as e:
            log_error("clipboard_gui._check_for_updates", str(e))

        self._update_sync_status(self.service.sync_service.get_status())

        self.root.after(200, self._check_for_updates)

    def _render_listbox(self):
        query = self.search_var.get().lower()
        self.listbox.delete(0, tk.END)
        self.filtered_history.clear()
        for original_idx, display_text in enumerate(self.history):
            if query in display_text.lower():
                self.filtered_history.append((original_idx, display_text))
                self.listbox.insert(tk.END, f"[{original_idx + 1}]  {display_text}")

    def _render_templates(self):
        query = self.search_var.get().lower()
        self.template_listbox.delete(0, tk.END)
        self.filtered_templates.clear()
        for original_idx, template_dict in enumerate(self.templates):
            title = template_dict.get("title", "Untitled")
            if query in title.lower():
                self.filtered_templates.append((original_idx, title))
                self.template_listbox.insert(tk.END, f"★  {title}")

    def _on_listbox_select(self, event):
        original_idx = self._selected_history_original_index()
        if original_idx is None:
            return

        try:
            plaintext, item_hash = self._decrypt_history_item(original_idx)
            content_to_show = self._format_insight_block(item_hash)
            content_to_show += f"Original Clip:\n{plaintext}"

            self.details_text.config(state=tk.NORMAL)
            self.details_text.delete(1.0, tk.END)
            self.details_text.insert(tk.END, content_to_show)
            self.details_text.config(state=tk.DISABLED)
        except Exception as e:
            log_error("clipboard_gui._on_listbox_select", str(e))

    def on_double_click(self, event):
        original_idx = self._selected_history_original_index()
        if original_idx is not None:
            self.service.restore_from_index(original_idx)
            self.hide_window()

    def on_template_double_click(self, event):
        selection = self.template_listbox.curselection()
        if selection:
            filtered_index = selection[0]
            if filtered_index < len(self.filtered_templates):
                self.service.restore_template(self.filtered_templates[filtered_index][0])
                self.hide_window()

    def on_right_click(self, event):
        clicked_index = self.listbox.nearest(event.y)
        if clicked_index not in self.listbox.curselection():
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(clicked_index)
            self.listbox.activate(clicked_index)
        self.context_menu.tk_popup(event.x_root, event.y_root)

    def _trigger_multi_paste_queue(self):
        selections = self.listbox.curselection()
        if selections:
            original_indices = [
                self.filtered_history[idx][0]
                for idx in selections
                if idx < len(self.filtered_history)
            ]
            self.service.queue_multi_paste(original_indices)
            self.hide_window()

    def _trigger_ai_insight(self):
        import tkinter.messagebox

        if not self.service.ai_enabled:
            tkinter.messagebox.showwarning(
                "Not Enabled",
                "Please enable 'Pro: AI Insights' from the Settings or Tray menu first.",
            )
            return

        selections = self.listbox.curselection()
        if selections:
            original_idx = self._selected_history_original_index()
            if original_idx is not None:
                try:
                    plaintext, item_hash = self._decrypt_history_item(original_idx)
                    self.service.ai_queue.put((item_hash, plaintext))
                except Exception as e:
                    log_error("clipboard_gui._trigger_ai_insight", str(e))

    def _trigger_transform(self, transform_type: str):
        original_idx = self._selected_history_original_index()
        if original_idx is not None:
            self.service.transform_item(original_idx, transform_type)
            self.hide_window()

    def shutdown(self):
        self.service.stop()
        if hasattr(self, "icon"):
            self.icon.stop()
        if hasattr(self, "hotkey_listener"):
            self.hotkey_listener.stop()
        self.root.destroy()
        sys.exit(0)
