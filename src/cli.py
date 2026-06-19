import os
import sys
import json
import asyncio
import httpx
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

MIDDLEWARE_BASE = "http://127.0.0.1:8000"
SESSION_ID = "cli-tui-session-001"

class TerminalUI:
    def __init__(self):
        self.console = Console()
        self.client = httpx.AsyncClient(timeout=60.0)

    async def initialize_session(self) -> None:
        """Initializes the session with the sc_evm middleware."""
        try:
            await self.client.post(
                f"{MIDDLEWARE_BASE}/api/session/initialize",
                json={"session_id": SESSION_ID}
            )
        except Exception as e:
            self.console.print(f"[bold red]Cannot connect to SC-EVM middleware at {MIDDLEWARE_BASE}[/bold red]")
            self.console.print(f"Error: {e}")
            self.console.print("[bold yellow]Please start the backend server first via 'uv run uvicorn src.main:app'[/bold yellow]")
            sys.exit(1)

    async def burn_session(self) -> None:
        """Burns the session on the middleware."""
        try:
            await self.client.delete(f"{MIDDLEWARE_BASE}/api/session/burn/{SESSION_ID}")
        except Exception as e:
            self.console.print(f"[dim red]Failed to burn session: {e}[/dim red]")

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
        self.console.rule("[bold gold1]⭐ DUAL-LLM THIN CLIENT (SC-EVM) ⭐[/bold gold1]")
        self.console.print(f"[dim cyan]Connected to SC-EVM Middleware at {MIDDLEWARE_BASE}[/dim cyan]\n")
        self.console.print("Commands: [bold yellow]exit[/bold yellow] (quit), [bold yellow]clear[/bold yellow] (clear screen), [bold yellow]memory[/bold yellow] (show facts/vectors), [bold yellow]history[/bold yellow] (show session logs)\n")

    async def run_interactive_loop(self) -> None:
        """Starts the interactive CLI loop."""
        os.system('clear' if os.name == 'posix' else 'cls')
        self.print_header()

        # Initialize session on backend
        await self.initialize_session()

        while True:
            try:
                # Use asyncio.to_thread to prevent blocking the async loop
                user_input = await asyncio.to_thread(Prompt.ask, "\n[bold green]👨 User[/bold green]")
                user_input = user_input.strip()
                
                if not user_input:
                    continue
                    
                if user_input.lower() in ("exit", "quit"):
                    self.console.print("[bold red]Burning session and exiting. Goodbye! 🍄[/bold red]")
                    await self.burn_session()
                    break
                    
                if user_input.lower() == "clear":
                    os.system('clear' if os.name == 'posix' else 'cls')
                    self.print_header()
                    continue
                    
                if user_input.lower() == "memory":
                    await self.display_memory()
                    continue
                    
                if user_input.lower() == "history":
                    await self.display_history()
                    continue

                # Clipboard keyword injections
                keywords = ["clipboard", "copied", "what i copy", "this code", "copied text"]
                if any(kw in user_input.lower() for kw in keywords):
                    import pyperclip
                    try:
                        copied_text = pyperclip.paste()
                        if copied_text and copied_text.strip():
                            user_input += f"\n\n[Clipboard Context]:\n{copied_text}"
                            self.console.print("[dim cyan]📎 Injected active clipboard context...[/dim cyan]")
                    except Exception:
                        pass
                
                # Render query stream
                await self.stream_query_response(user_input)

            except KeyboardInterrupt:
                self.console.print("\n[bold red]Interrupted. Type 'exit' to quit.[/bold red]")
            except Exception as e:
                self.console.print(f"\n[bold red]💥 Error occurred:[/bold red] {e}")
        
        await self.client.aclose()

    async def stream_query_response(self, prompt: str) -> None:
        """Queries the sc_evm middleware and handles Server-Sent Events (SSE)."""
        payload = {
            "session_id": SESSION_ID,
            "prompt": prompt
        }
        
        self.console.print("\n[bold cyan]🤖 Assistant[/bold cyan]")
        
        # Display cognitive telemetries
        reformulated_query = None
        grounded_llm_prompt = None
        retrieved_memories = []
        full_response_text = ""
        action_payload = None
        
        current_event = None
        
        try:
            async with self.client.stream("POST", f"{MIDDLEWARE_BASE}/api/agent/query", json=payload) as response:
                if response.status_code != 200:
                    self.console.print(f"[bold red]Error: Backend returned status {response.status_code}[/bold red]")
                    return
                
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    
                    if line.startswith("event:"):
                        current_event = line[6:].strip()
                    elif line.startswith("data:"):
                        data_content = line[5:].strip()
                        if data_content == "[DONE]":
                            continue
                        
                        try:
                            parsed = json.loads(data_content)
                        except json.JSONDecodeError:
                            parsed = data_content
                        
                        if current_event == "query_reformulation":
                            reformulated_query = parsed.get("search_vector_query")
                            grounded_llm_prompt = parsed.get("grounded_llm_prompt")
                            self.console.print(f"[dim cyan]🔍 [SC-EVM] Search keywords: {reformulated_query}[/dim cyan]")
                        elif current_event == "retrieved_context":
                            retrieved_memories = parsed
                            self.console.print(f"[dim cyan]🧠 [SC-EVM] Retrieved {len(retrieved_memories)} memory blocks from ChromaDB.[/dim cyan]")
                            # Print a separator before assistant response
                            self.console.print("[bold cyan]──────────────────────────────────[/bold cyan]")
                        elif current_event == "token":
                            print(parsed, end="", flush=True)
                            full_response_text += parsed
                        elif current_event == "action":
                            action_payload = parsed
            print() # Print newline after stream completes
            
            # Execute action if returned
            if action_payload and action_payload.get("type") != "none":
                self.handle_action(action_payload)
                
        except Exception as e:
            self.console.print(f"\n[bold red]Stream failure: {e}[/bold red]")

    async def display_memory(self) -> None:
        """Fetches and displays session memory details from the backend."""
        try:
            res = await self.client.get(f"{MIDDLEWARE_BASE}/api/session/memory/{SESSION_ID}")
            res_data = res.json()
            if res_data.get("status") != "success":
                self.console.print("[bold red]Failed to fetch session memory.[/bold red]")
                return
            
            data = res_data.get("data", {})
            self.console.print("\n[bold gold1]🧠 Active Session Memory State:[/bold gold1]")
            
            # Show budget / threshold settings
            self.console.print(f"[bold yellow]Parameters:[/bold yellow]")
            self.console.print(f" - Base Threshold (Similarity): [green]{data.get('base_threshold')}[/green]")
            self.console.print(f" - Token Budget Ceiling: [green]{data.get('token_budget')}[/green]")
            
            # Show pending queue (unindexed buffer)
            pending = data.get("pending_commit_buffer", [])
            if pending:
                self.console.print(f"[bold yellow]Pending Commit Buffer (Unindexed):[/bold yellow]")
                for item in pending:
                    self.console.print(f" - {item}")
            
            # Show ChromaDB indexed documents
            docs = data.get("indexed_documents", [])
            if docs:
                self.console.print(f"[bold yellow]ChromaDB Ephemeral Vector Documents ({len(docs)}):[/bold yellow]")
                for idx, doc in enumerate(docs):
                    self.console.print(f"\n[dim]Document #{idx + 1}:[/dim]")
                    self.console.print(Panel(doc.strip(), border_style="green"))
            else:
                self.console.print("[dim]- No vector documents stored in ChromaDB yet -[/dim]")
                
        except Exception as e:
            self.console.print(f"[bold red]Failed to contact backend memory API: {e}[/bold red]")

    async def display_history(self) -> None:
        """Fetches and displays active session history from the backend."""
        try:
            res = await self.client.get(f"{MIDDLEWARE_BASE}/api/session/history/{SESSION_ID}")
            res_data = res.json()
            if res_data.get("status") != "success":
                self.console.print("[bold red]Failed to fetch session history.[/bold red]")
                return
            
            history = res_data.get("data", [])
            self.console.print("\n[bold yellow]📜 Current session history sliding window (Cap: last 6 turns):[/bold yellow]")
            if not history:
                self.console.print("[dim]- No conversation logs for this session -[/dim]")
                return
                
            for turn in history:
                role = "[green]User[/green]" if turn.get("role") == "user" else "[cyan]Assistant[/cyan]"
                self.console.print(f"{role}: {turn.get('content')}")
        except Exception as e:
            self.console.print(f"[bold red]Failed to contact backend history API: {e}[/bold red]")

    def handle_action(self, action_dict: dict) -> None:
        """Prompts for and executes actions requested by the dual-LLM orchestrator."""
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
                    import subprocess
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
            self.console.print(f"\n[bold blue]🎨 Image generated and saved on the server side![/bold blue]")
                        
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

async def main():
    ui = TerminalUI()
    await ui.run_interactive_loop()

if __name__ == "__main__":
    asyncio.run(main())
