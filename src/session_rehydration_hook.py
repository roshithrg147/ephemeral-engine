import os
import sys
import json
import time
import argparse
import logging
from typing import List, Dict, Any, Optional

import httpx

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("SessionRehydrationHook")

def wait_for_backend(api_url: str, max_retries: int = 5) -> bool:
    """
    Pings the backend with exponential backoff (1s, 2s, 4s, 8s, 16s).
    Returns True if connection succeeded, False otherwise.
    """
    delay = 1
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempting to connect to backend {api_url} (Attempt {attempt+1}/{max_retries})...")
            response = httpx.get(api_url, timeout=2.0)
            # Accept any standard startup status (e.g. 200 UI page or 404 for unmapped endpoints)
            if response.status_code in (200, 404):
                logger.info("Successfully connected to backend.")
                return True
        except httpx.RequestError as e:
            logger.warning(f"Connection attempt failed: {e}")
        
        if attempt < max_retries - 1:
            logger.info(f"Sleeping for {delay}s before retrying...")
            time.sleep(delay)
            delay *= 2
            
    return False

def load_history(history_source: str, max_turns: int = 6) -> List[Dict[str, str]]:
    """
    Loads conversation history turns from a JSON file, raw JSON string, or plain text logs.
    Restricts to the last max_turns to stay within token footprint thresholds.
    """
    if not history_source:
        return []
        
    # Check if it's a file path
    if os.path.exists(history_source):
        try:
            with open(history_source, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read().strip()
        except Exception as e:
            logger.error(f"Failed to read history file {history_source}: {e}")
            return []
    else:
        content = history_source.strip()
        
    if not content:
        return []
        
    turns = []
    # Try parsing as JSON first
    try:
        data = json.loads(content)
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "role" in item and "content" in item:
                    turns.append({"role": item["role"], "content": item["content"]})
    except json.JSONDecodeError:
        # Fallback to plain text logs: "User: <msg>\nAssistant: <msg>"
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("User:"):
                turns.append({"role": "user", "content": line[5:].strip()})
            elif line.startswith("Assistant:"):
                turns.append({"role": "assistant", "content": line[10:].strip()})
            elif line.startswith("System:"):
                turns.append({"role": "user", "content": f"[System: {line[7:].strip()}]"})
                
    # Return only the last N turns
    return turns[-max_turns:]

def rehydrate_session(api_url: str, session_id: str, history: List[Dict[str, str]], active_file_context: Optional[str]) -> bool:
    """
    Initializes a session and seeds it with history and active editor focus context.
    """
    try:
        # Use httpx Client to manage connection pooling
        with httpx.Client(base_url=api_url, timeout=10.0) as client:
            # 1. Initialize the session registry
            logger.info(f"Initializing session record for '{session_id}'...")
            resp = client.post("/api/session/initialize", json={"session_id": session_id})
            resp.raise_for_status()
            
            # 2. Add history turns
            logger.info(f"Seeding {len(history)} messages to the session history...")
            for turn in history:
                resp = client.post("/api/session/message", json={
                    "session_id": session_id,
                    "role": turn["role"],
                    "content": turn["content"]
                })
                resp.raise_for_status()
                
            # 3. Add active file seed
            if active_file_context:
                logger.info("Seeding active file context message...")
                resp = client.post("/api/session/message", json={
                    "session_id": session_id,
                    "role": "user",
                    "content": active_file_context
                })
                resp.raise_for_status()
                
            logger.info("Session rehydration completed successfully.")
            return True
            
    except Exception as e:
        logger.error(f"Rehydration HTTP operation failed: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="SC-EVM Session Rehydration Hook")
    parser.add_argument("--session-id", type=str, required=True, help="Session ID to rehydrate")
    parser.add_argument("--history", type=str, help="Dialogue history JSON string, file path, or plain text log")
    parser.add_argument("--active-file", type=str, help="Absolute path of the currently active file in editor")
    parser.add_argument("--cursor-line", type=int, help="1-based line position of the cursor")
    parser.add_argument("--cursor-char", type=int, help="1-based character position of the cursor")
    parser.add_argument("--api-url", type=str, default="http://127.0.0.1:8000", help="Base URL of the FastAPI microservice")
    parser.add_argument("--max-turns", type=int, default=6, help="Maximum number of historical dialogue turns to restore")
    parser.add_argument("--max-retries", type=int, default=5, help="Maximum connection retry count before abandoning")
    
    args = parser.parse_args()
    
    # 1. Backoff Ping
    backend_ready = wait_for_backend(args.api_url, max_retries=args.max_retries)
    if not backend_ready:
        logger.error(f"Abandoning rehydration: backend {args.api_url} is unreachable.")
        sys.exit(1)
        
    # 2. Load History
    history = load_history(args.history, max_turns=args.max_turns)
    
    # 3. Build Active File Seed prompt
    active_file_context = None
    if args.active_file:
        active_file_context = f"[System Notification: Editor Focus Re-established]\nUser is currently editing file: {os.path.abspath(args.active_file)}"
        if args.cursor_line is not None:
            active_file_context += f"\nCursor location: Line {args.cursor_line}"
            if args.cursor_char is not None:
                active_file_context += f", Column {args.cursor_char}"
                
    # 4. Execute Rehydration
    success = rehydrate_session(args.api_url, args.session_id, history, active_file_context)
    if not success:
        sys.exit(1)
        
    # Output success metadata
    print(json.dumps({
        "status": "success",
        "session_id": args.session_id,
        "history_turns_seeded": len(history),
        "has_active_file": active_file_context is not None
    }))

if __name__ == "__main__":
    main()
