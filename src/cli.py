import os
import sys
import json
import socket
import subprocess
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.spinner import SPINNERS
from rich.text import Text
from rich.markdown import Markdown

# Define the custom Mario/Dino spinner
SPINNERS["super_me"] = {
    "interval": 120,
    "frames": [
        "🧱🦖          🍄",
        "🧱 🦖        🍄 ",
        "🧱  🦖      🍄  ",
        "🧱   🦕    🍄   ",
        "🧱    🦖  🍄    ",
        "🧱     🦖🍄     ",
        "🧱      🌟      ",
        "🧱       🌟     ",
        "🧱        🌟    ",
        "🧱         🌟   ",
        "🧱        🌟    ",
        "🧱       🌟     ",
        "🧱      🌟      ",
        "🧱     🌟       ",
        "🧱    🌟        ",
        "🧱   🌟         ",
        "🧱  🌟          ",
        "🧱 🌟           ",
        "🧱🌟            "
    ]
}

SOCKET_PATH = os.path.expanduser("~/.config/anthropic-agent/daemon.sock")

class TerminalUI:
    def __init__(self):
        self.console = Console()

    def _send_ipc(self, payload: dict) -> str:
        if not os.path.exists(SOCKET_PATH):
            raise ConnectionError("Daemon socket not found. Is the unified daemon running?")
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(SOCKET_PATH)
        client.sendall(json.dumps(payload).encode('utf-8'))
        client.shutdown(socket.SHUT_WR)
        
        chunks = []
        while True:
            chunk = client.recv(8192)
            if not chunk: break
            chunks.append(chunk)
        client.close()
        return b"".join(chunks).decode('utf-8', errors='ignore')

    def print_header(self) -> None:
        header_art = r"""
[bold red]   _____                       [/bold red][bold green]  __  __      _ [/bold green]
[bold red]  / ____|                      [/bold red][bold green] |  \/  |    | |[/bold green]
[bold red] | (___  _   _ _ __   ___ _ __ [/bold red][bold green] | \  / | ___| |[/bold green]
[bold red]  \___ \| | | | '_ \ / _ \ '__|[/bold red][bold green] | |\/| |/ _ \ |[/bold green]
[bold red]  ____) | |_| | |_) |  __/ |   [/bold red][bold green] | |  | |  __/_|[/bold green]
[bold red] |_____/ \__,_| .__/ \___|_|   [/bold red][bold green] |_|  |_|\___(_)[/bold green]
[bold red]              | |              [/bold red][bold green]                 [/bold green]
[bold red]              |_|              [/bold red][bold green]                 [/bold green]
        """
        self.console.print(header_art)
        self.console.rule("[bold gold1]⭐ DUAL-LLM THIN CLIENT ⭐[/bold gold1]")
        self.console.print("[dim cyan]Connecting to background Daemon via IPC[/dim cyan]\n")
        self.console.print("Commands: [bold yellow]exit[/bold yellow] (quit), [bold yellow]clear[/bold yellow] (clear screen), [bold yellow]memory[/bold yellow] (show facts), [bold yellow]history[/bold yellow] (show session logs)\n")

    def run_interactive_loop(self) -> None:
        """Starts the interactive CLI loop."""
        os.system('clear' if os.name == 'posix' else 'cls')
        self.print_header()

        # Check connection
        try:
            self._send_ipc({"action": "ping"})
        except Exception as e:
            self.console.print(f"[bold red]Cannot connect to Daemon at {SOCKET_PATH}[/bold red]")
            self.console.print(f"Error: {e}")
            self.console.print("[bold yellow]Please start the daemon first.[/bold yellow]")
            return

        while True:
            try:
                user_input = Prompt.ask("\n[bold green]👨 User[/bold green]")
                user_input = user_input.strip()
                
                if not user_input:
                    continue
                    
                if user_input.lower() in ("exit", "quit"):
                    self.console.print("[bold red]Disconnecting from daemon. Goodbye! 🍄[/bold red]")
                    break
                    
                # Handle /clip commands
                if user_input.lower().startswith("/clip"):
                    parts = user_input.split(maxsplit=2)
                    if len(parts) == 1 or (parts[0].lower() in ("/clip", "/clips") and len(parts) == 1):
                        history = self.fetch_clipboard_history()
                        if not history:
                            self.console.print("[bold yellow]No clipboard history found or daemon not running.[/bold yellow]")
                        else:
                            self.console.print("\n[bold gold1]📋 Recent Clipboard History:[/bold gold1]")
                            from rich.table import Table
                            table = Table(show_header=True, header_style="bold magenta")
                            table.add_column("Index", style="dim", width=6)
                            table.add_column("Content Preview", style="cyan")
                            for idx, val in enumerate(history):
                                preview = val.replace('\n', ' ')
                                if len(preview) > 60:
                                    preview = preview[:57] + "..."
                                table.add_row(str(idx + 1), preview)
                            self.console.print(table)
                        continue
                    
                    index_str = parts[1]
                    try:
                        index = int(index_str)
                    except ValueError:
                        self.console.print("[bold red]Error: Invalid index. Usage: /clip <index> [your question][/bold red]")
                        continue
                        
                    history = self.fetch_clipboard_history()
                    if not history:
                        self.console.print("[bold red]Error: No clipboard history found.[/bold red]")
                        continue
                        
                    if index < 1 or index > len(history):
                        self.console.print(f"[bold red]Error: Clipboard history index out of range (1-{len(history)}).[/bold red]")
                        continue
                        
                    selected_clip = history[index - 1]
                    question = parts[2] if len(parts) > 2 else ""
                    
                    if not question:
                        question = Prompt.ask(f"[bold yellow]What is your question about Clip #{index}?[/bold yellow]")
                        question = question.strip()
                        if not question:
                            self.console.print("[dim]Action cancelled.[/dim]")
                            continue
                            
                    user_input = f"{question}\n\n[Clipboard Context]:\n{selected_clip}"
                    self.console.print(f"[dim cyan]📎 Injected Clip #{index} context...[/dim cyan]")
                    
                keywords = ["clipboard", "copied", "what i copy", "this code", "copied text"]
                if any(kw in user_input.lower() for kw in keywords):
                    import pyperclip
                    try:
                        copied_text = pyperclip.paste()
                        if copied_text and copied_text.strip():
                            user_input += f"\n\n[Clipboard Context]:\n{copied_text}"
                            self.console.print("[dim cyan]📎 Injected active clipboard context...[/dim cyan]")
                    except Exception as e:
                        pass
                    
                if user_input.lower() == "clear":
                    os.system('clear' if os.name == 'posix' else 'cls')
                    self.print_header()
                    continue
                    
                if user_input.lower() == "memory":
                    self.display_memory()
                    continue
                    
                if user_input.lower() == "history":
                    self.display_history()
                    continue
                    
                # Call daemon with animation status
                response_str = None
                with self.console.status("[bold yellow]🪙  Daemon gathering dual-LLM response...[/bold yellow]", spinner="super_me"):
                    response_str = self._send_ipc({"action": "chat", "prompt": user_input})
                
                if not response_str:
                    self.console.print("[bold red]Error: Empty response from daemon.[/bold red]")
                    continue
                    
                try:
                    response_obj = json.loads(response_str)
                    if "error" in response_obj:
                        self.console.print(f"[bold red]Daemon Error:[/bold red] {response_obj['error']}")
                        continue
                        
                    self.display_response(response_obj)
                    
                    action = response_obj.get("action", {})
                    if action and action.get("type") != "none":
                        self.handle_action(action)
                except json.JSONDecodeError:
                    self.console.print(f"[bold red]Failed to decode JSON from daemon:[/bold red] {response_str}")
                    
            except KeyboardInterrupt:
                self.console.print("\n[bold red]Interrupted. Type 'exit' to quit.[/bold red]")
            except Exception as e:
                self.console.print(f"\n[bold red]💥 Error occurred:[/bold red] {e}")

    def fetch_clipboard_history(self) -> list:
        try:
            # We can use the legacy text command for GET_HISTORY or json, 
            # daemon supports both, but we use the JSON api if we want
            # We'll use the JSON payload to daemon.sock
            resp = self._send_ipc({"action": "get_history_clips"})
            return json.loads(resp)
        except Exception:
            # Fallback to direct string if the daemon didn't support get_history_clips
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.connect(SOCKET_PATH)
            client.sendall(b"GET_HISTORY")
            client.shutdown(socket.SHUT_WR)
            chunks = []
            while True:
                chunk = client.recv(4096)
                if not chunk: break
                chunks.append(chunk)
            client.close()
            return json.loads(b"".join(chunks).decode('utf-8', errors='ignore'))

    def display_response(self, response_dict: dict) -> None:
        """Displays the refined text and facts remembered."""
        self.console.print("\n[bold cyan]🤖 Assistant[/bold cyan]")
        self.console.print(Panel(
            Markdown(response_dict.get("text", "").strip()), 
            border_style="cyan",
            title=f"[bold green]Synthesized Response ({response_dict.get('intent', 'unknown')})[/bold green]"
        ))
        
        remember = response_dict.get("remember", [])
        if remember:
            self.console.print("[bold gold1]💡 Facts Learned & Stored in Memory:[/bold gold1]")
            for fact in remember:
                self.console.print(f" - [green]{fact}[/green]")

    def display_memory(self) -> None:
        try:
            mem_str = self._send_ipc({"action": "get_memory"})
            mem_data = json.loads(mem_str)
        except Exception as e:
            self.console.print(f"[bold red]Failed to fetch memory from daemon:[/bold red] {e}")
            return
            
        self.console.print("\n[bold gold1]🧠 Long-term memory state:[/bold gold1]")
        profile = mem_data.get("user_profile", {})
        facts = mem_data.get("learned_facts", [])
        
        if profile:
            self.console.print("[bold yellow]Profile info:[/bold yellow]")
            for k, v in profile.items():
                self.console.print(f" - {k}: [green]{v}[/green]")
        else:
            self.console.print("[dim]- No user profile info stored yet -[/dim]")
            
        if facts:
            self.console.print("[bold yellow]Learned facts:[/bold yellow]")
            for i, fact in enumerate(facts):
                self.console.print(f" {i}. [green]{fact}[/green]")
        else:
            self.console.print("[dim]- No learned facts stored yet -[/dim]")

    def display_history(self) -> None:
        try:
            hist_str = self._send_ipc({"action": "get_history"})
            history = json.loads(hist_str)
        except Exception as e:
            self.console.print(f"[bold red]Failed to fetch history from daemon:[/bold red] {e}")
            return
            
        self.console.print("\n[bold yellow]📜 Current session history:[/bold yellow]")
        if not history:
            self.console.print("[dim]- No conversation logs for this session -[/dim]")
            return
            
        for turn in history:
            role = "[green]User[/green]" if turn.get("role") == "user" else "[cyan]Assistant[/cyan]"
            self.console.print(f"{role}: {turn.get('content')}")

    def handle_action(self, action_dict: dict) -> None:
        action_type = action_dict.get("type")
        payload = action_dict.get("payload", {})
        
        if action_type == "run_command":
            cmd = payload.get("command")
            if not cmd: return
            self.console.print(f"\n[bold orange3]⚠️  Agent requests to execute a terminal command:[/bold orange3]")
            self.console.print(Panel(cmd, title="Proposed Command", border_style="orange3"))
            
            confirm = Confirm.ask("Do you want to run this command?", default=False)
            if confirm:
                self.console.print("[bold yellow]Running command...[/bold yellow]")
                try:
                    res = subprocess.run(cmd, shell=True, text=True, capture_output=True)
                    if res.stdout:
                        self.console.print("[bold green]Output:[/bold green]")
                        self.console.print(res.stdout)
                    if res.stderr:
                        self.console.print("[bold red]Errors/Warnings:[/bold red]")
                        self.console.print(res.stderr)
                except Exception as e:
                    self.console.print(f"[bold red]Command failed to execute:[/bold red] {e}")
            else:
                self.console.print("[dim]Command execution cancelled.[/dim]")
                
        elif action_type == "generate_image":
            prompt = payload.get("prompt")
            if not prompt: return
            self.console.print(f"\n[bold blue]🔵 Agent requests to generate an image:[/bold blue]")
            self.console.print(Panel(prompt, title="Image Prompt", border_style="blue"))
            
            confirm = Confirm.ask("Do you want to generate this image?", default=True)
            if confirm:
                filename = "images/generated_assistant.png"
                with self.console.status("[bold blue]🔵 Mushroom Friend (Imagen 3) is painting via Daemon...[/bold blue]", spinner="super_me"):
                    try:
                        res_str = self._send_ipc({"action": "generate_image", "prompt": prompt, "filename": filename})
                        res_data = json.loads(res_str)
                        if "error" in res_data:
                            self.console.print(f"[bold red]💥 Image generation failed:[/bold red] {res_data['error']}")
                        else:
                            self.console.print(f"\n[bold green]✓ Masterpiece saved to:[/bold green] [underline]{res_data.get('filepath')}[/underline]")
                    except Exception as e:
                        self.console.print(f"[bold red]💥 Image generation IPC failed:[/bold red] {e}")
                        
        elif action_type == "save_file":
            file_path = payload.get("file_path")
            file_content = payload.get("file_content")
            if not file_path or not file_content: return
            self.console.print(f"\n[bold yellow]📁 Agent wants to write to file: [underline]{file_path}[/underline][/bold yellow]")
            confirm = Confirm.ask("Do you want to write this file?", default=False)
            if confirm:
                try:
                    dirname = os.path.dirname(file_path)
                    if dirname:
                        os.makedirs(dirname, exist_ok=True)
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(file_content)
                    self.console.print(f"[bold green]✓ File written successfully.[/bold green]")
                except Exception as e:
                    self.console.print(f"[bold red]File write failed:[/bold red] {e}")
