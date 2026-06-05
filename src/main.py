import sys
import os
import time
import socket
import subprocess
import argparse
import atexit
import signal
import json
from rich.console import Console
from src.cli import TerminalUI, SOCKET_PATH

DAEMON_PROCESS = None

def parse_args():
    parser = argparse.ArgumentParser(description="Dual-LLM Personal Assistant with Memory and CLI.")
    parser.add_argument(
        "--test-mode",
        action="store_true",
        help="Run a quick automated API test and exit immediately."
    )
    return parser.parse_args()

def trigger_clipboard_show():
    """Sends the SHOW command to the clipboard daemon Unix socket."""
    if os.path.exists(SOCKET_PATH):
        try:
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.connect(SOCKET_PATH)
            client.sendall(b"SHOW")
            client.close()
        except Exception:
            pass

def shutdown_daemon():
    """Sends the QUIT command to the daemon Unix socket and terminates the process if spawned."""
    global DAEMON_PROCESS
    
    # Try sending QUIT socket command first for clean shutdown
    if os.path.exists(SOCKET_PATH):
        try:
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.connect(SOCKET_PATH)
            client.sendall(b"QUIT")
            client.close()
            time.sleep(0.5)
        except Exception:
            pass
            
    # Fallback to terminating the process if we spawned it and it's still alive
    if DAEMON_PROCESS is not None:
        try:
            if DAEMON_PROCESS.poll() is None:
                DAEMON_PROCESS.terminate()
                try:
                    DAEMON_PROCESS.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    DAEMON_PROCESS.kill()
        except Exception:
            pass

def check_and_start_daemon(console: Console):
    """Checks if the daemon socket is active, and boots the unified daemon if missing."""
    global DAEMON_PROCESS
    is_running = False
    if os.path.exists(SOCKET_PATH):
        try:
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.connect(SOCKET_PATH)
            client.close()
            is_running = True
        except Exception:
            try:
                os.remove(SOCKET_PATH)
            except OSError:
                pass
    
    if not is_running:
        console.print("[bold yellow]🚀 Launching Unified Background Daemon...[/bold yellow]")
        try:
            # We run it using sys.executable with -m src.daemon
            DAEMON_PROCESS = subprocess.Popen(
                [sys.executable, "-m", "src.daemon"],
                cwd=os.path.abspath("."),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # Wait dynamically up to 10 seconds for socket
            timeout = 10
            while timeout > 0:
                if os.path.exists(SOCKET_PATH):
                    break
                time.sleep(0.5)
                timeout -= 0.5
                
            if not os.path.exists(SOCKET_PATH):
                console.print("[bold red]⚠️  Daemon started but socket not found after timeout.[/bold red]")
            else:
                console.print("[bold green]✓ Unified Daemon successfully running in background.[/bold green]")
        except Exception as e:
            console.print(f"[bold red]⚠️  Failed to start Unified Daemon: {e}[/bold red]")

def main():
    args = parse_args()
    console = Console()

    # Register exit handlers unless running in test-mode
    if not args.test_mode:
        def sigterm_handler(signum, frame):
            sys.exit(0)
        signal.signal(signal.SIGTERM, sigterm_handler)
        atexit.register(shutdown_daemon)

    try:
        # 1. Check and start the daemon
        check_and_start_daemon(console)

        if args.test_mode:
            console.print("[bold yellow]🤖 Running in automated test-mode via IPC...[/bold yellow]")
            test_prompt = "What is the capital of France? Answer in 3 words."
            console.print(f"User test prompt: '[cyan]{test_prompt}[/cyan]'")
            
            ui = TerminalUI()
            response_str = ui._send_ipc({"action": "chat", "prompt": test_prompt})
            
            try:
                response = json.loads(response_str)
                console.print("\n[bold green]Refined Synthesis Response:[/bold green]")
                console.print(f"Text: [cyan]{response.get('text')}[/cyan]")
                console.print(f"Intent: [cyan]{response.get('intent')}[/cyan]")
                action = response.get('action', {})
                console.print(f"Action Type: [cyan]{action.get('type')}[/cyan]")
                console.print(f"Remembered facts: [cyan]{response.get('remember')}[/cyan]")
                console.print("\n[bold green]✓ Test passed successfully![/bold green]")
                sys.exit(0)
            except json.JSONDecodeError:
                console.print(f"[bold red]Failed to decode daemon JSON: {response_str}[/bold red]")
                sys.exit(1)

        # Trigger the show window immediately to display it to the user
        trigger_clipboard_show()

        # 2. Initialize and run Terminal UI
        ui = TerminalUI()
        ui.run_interactive_loop()

    except KeyboardInterrupt:
        console.print("\n[bold red]Assistant execution interrupted. Goodbye![/bold red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[bold red]💥 Initialization failed:[/bold red] {e}")
        console.print("[bold yellow]\nTroubleshooting steps:[/bold yellow]")
        console.print("1. Ensure Application Default Credentials (ADC) are configured. Run:")
        console.print("   [bold]gcloud auth application-default login[/bold]")
        console.print("2. Ensure Vertex AI User permission is granted on the project.")
        console.print("3. Check your internet connection.")
        sys.exit(1)

if __name__ == "__main__":
    main()
