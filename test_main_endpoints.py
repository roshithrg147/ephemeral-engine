from fastapi.testclient import TestClient
from src.main import app
import json

def run_tests():
    print("Testing SC-EVM Endpoints...")
    client = TestClient(app)

    session_id = "test_phase3_session"

    # Test 1: POST /api/session/initialize
    print("\n--- Test: Initialize Session ---")
    res_init = client.post("/api/session/initialize", json={"session_id": session_id})
    assert res_init.status_code == 200, f"Init failed: {res_init.text}"
    print("Response:", res_init.json())
    print("Initialize successful.")

    # Test 2: POST /api/session/message
    print("\n--- Test: Append Message ---")
    res_msg = client.post("/api/session/message", json={"session_id": session_id, "role": "user", "content": "Hello World"})
    assert res_msg.status_code == 200, f"Message append failed: {res_msg.text}"
    print("Response:", res_msg.json())
    print("Append message successful.")

    # Test 3: POST /api/agent/query (SSE)
    print("\n--- Test: Agent Query (SSE Stream) ---")
    # Using 'with' block for streaming response
    with client.stream("POST", "/api/agent/query", json={"session_id": session_id, "prompt": "Tell me a joke"}) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        
        events = []
        for line in response.iter_lines():
            if line:
                events.append(line)
                if "event: done" in line:
                    break

    print(f"Captured {len(events)} SSE lines.")
    assert len(events) > 0, "No SSE events captured"
    print("SSE stream established and completed successfully.")

    # Test 4: DELETE /api/session/burn/{session_id}
    print("\n--- Test: Burn Session ---")
    res_burn = client.delete(f"/api/session/burn/{session_id}")
    assert res_burn.status_code == 200, f"Burn failed: {res_burn.text}"
    print("Response:", res_burn.json())
    print("Burn session successful.")

    print("\nSuccess: Connectivity, SSE streams, and parameter handling verified.")

if __name__ == "__main__":
    run_tests()
