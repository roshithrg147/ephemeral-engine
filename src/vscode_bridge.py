import requests
import json
import sys

# Configuration
BASE_URL = "http://127.0.0.1:8000"
SESSION_ID = "vscode_local_session_01"

def initialize_session():
    response = requests.post(f"{BASE_URL}/api/session/initialize", 
                             json={"session_id": SESSION_ID})
    print(f"Session Status: {response.json().get('message')}")

def burn_session():
    requests.delete(f"{BASE_URL}/api/session/burn/{SESSION_ID}")
    print("\nSession burned. Memory cleared.")
    sys.exit(0)

def query_engine(prompt):
    url = f"{BASE_URL}/api/agent/query"
    payload = {"session_id": SESSION_ID, "prompt": prompt}
    
    # Streaming POST request
    with requests.post(url, json=payload, stream=True) as r:
        for line in r.iter_lines():
            if line:
                decoded = line.decode('utf-8')
                if decoded.startswith("data: "):
                    content = decoded[6:]
                    if content != "[DONE]":
                        print(content.strip('"'), end="", flush=True)
    print("\n")

if __name__ == "__main__":
    initialize_session()
    try:
        while True:
            user_input = input("SC-EVM Agent > ")
            query_engine(user_input)
    except KeyboardInterrupt:
        burn_session()