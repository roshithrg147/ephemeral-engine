import asyncio
import json
import time
import httpx
import uvicorn
from datetime import datetime, timezone
from src.main import app

# --- Configuration Bounds ---
BASE_URL = "http://127.0.0.1:8081"
REPORT_FILE = "sc_evm_validation_report.json"
execution_log = []

class BackgroundUvicornServer(uvicorn.Server):
    """Programmatic wrapper to start and stop Uvicorn server cleanly inside async tests."""
    def install_signal_handlers(self):
        pass

async def run_server(server: BackgroundUvicornServer):
    try:
        await server.serve()
    except Exception as e:
        log_event("ServerException", str(e))

def log_event(event_name: str, detail: any):
    """Encapsulates telemetry captures inside standard format schemas."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "event": event_name,
        "detail": detail
    }
    execution_log.append(entry)
    print(f"🔹 [{event_name}] {detail}")

async def consume_sse_stream(client: httpx.AsyncClient, session_id: str, prompt: str) -> str:
    """Asynchronously consumes and aggregates the Server-Sent Events data chunks."""
    payload = {
        "session_id": session_id,
        "prompt": prompt
    }
    full_response_content = []
    current_event = None
    
    start_time = time.perf_counter()
    async with client.stream("POST", f"{BASE_URL}/api/agent/query", json=payload, timeout=400.0) as response:
        if response.status_code != 200:
            return f"ERROR: Status {response.status_code}"
            
        async_lines = response.aiter_lines()
        async for line in async_lines:
            line = line.strip()
            if not line:
                continue
            
            # SSE event row parsing isolation
            if line.startswith("event:"):
                current_event = line[6:].strip()
            elif line.startswith("data:"):
                data_content = line[5:].strip()
                if data_content == "[DONE]":
                    continue
                
                # Capture and parse data contents defensively
                if current_event == "token" or current_event is None:
                    try:
                        decoded = json.loads(data_content)
                        if isinstance(decoded, str):
                            full_response_content.append(decoded)
                    except json.JSONDecodeError:
                        # Fallback for raw non-JSON text values
                        if not (data_content.startswith("{") or data_content.startswith("[")):
                            full_response_content.append(data_content)
                    
    latency = time.perf_counter() - start_time
    aggregated_text = "".join(full_response_content)
    
    log_event("QueryTelemetry", {
        "session_id": session_id,
        "prompt": prompt,
        "latency_seconds": latency,
        "response_length": len(aggregated_text)
    })
    return aggregated_text

async def run_torture_test():
    log_event("TestStart", "Initiating SC-EVM verification harness")
    
    # 1. Start Programmatic Uvicorn Server in background task
    config = uvicorn.Config(app, host="127.0.0.1", port=8081, log_level="warning")
    server = BackgroundUvicornServer(config)
    server_task = asyncio.create_task(run_server(server))

    # Give server time to bind to port
    await asyncio.sleep(2.0)

    # Session Keys
    session_a = "tenant-session-alpha"
    session_b = "tenant-session-beta"
    
    assertions = []
    
    try:
        async with httpx.AsyncClient() as client:
            # 1. Initialize Parallel Sessions
            log_event("InitSession", f"Initializing: {session_a}")
            await client.post(f"{BASE_URL}/api/session/initialize", json={"session_id": session_a})
            
            log_event("InitSession", f"Initializing: {session_b}")
            await client.post(f"{BASE_URL}/api/session/initialize", json={"session_id": session_b})
            
            # 2. Poison Memory Context Separately (Isolate data states)
            log_event("InjectState", f"Seeding Tenant A context tracking anchors.")
            await client.post(f"{BASE_URL}/api/session/message", json={
                "session_id": session_a,
                "role": "user",
                "content": "Validation ID: [ALPHA-PLATINUM-9982]"
            })
            
            log_event("InjectState", f"Seeding Tenant B context tracking anchors.")
            await client.post(f"{BASE_URL}/api/session/message", json={
                "session_id": session_b,
                "role": "user",
                "content": "Validation ID: [BETA-TITANIUM-1104]"
            })
            
            # 3. System Timing Constraint: Configure an explicit 45-second architectural cooling step window
            log_event("TimingConstraint", "Initiating 45-second architectural cooling step window")
            await asyncio.sleep(45.0)
            
            # 4. Assert Multi-Tenant Boundary Controls (Cross-contamination assertions)
            # Test Query A
            res_a = await consume_sse_stream(client, session_a, "What is my validation ID?")
            assert_a1 = "ALPHA-PLATINUM-9982" in res_a
            assert_a2 = "BETA-TITANIUM-1104" not in res_a
            assertions.append({"assertion": "SessionA Knows Its Secret", "passed": assert_a1})
            assertions.append({"assertion": "SessionA Wont Leak SessionB Secret", "passed": assert_a2})
            
            # Test Query B
            res_b = await consume_sse_stream(client, session_b, "What is my validation ID?")
            assert_b1 = "BETA-TITANIUM-1104" in res_b
            assert_b2 = "ALPHA-PLATINUM-9982" not in res_b
            assertions.append({"assertion": "SessionB Knows Its Secret", "passed": assert_b1})
            assertions.append({"assertion": "SessionB Wont Leak SessionA Secret", "passed": assert_b2})
            
            # 5. Perform Target Compliance Burn Check
            log_event("ResourceCleanlinessInit", f"Issuing DELETE /burn to {session_a}")
            await client.delete(f"{BASE_URL}/api/session/burn/{session_a}")
            
            # Verify Session A is totally blank parametric state, while Session B survives unharmed
            res_a_post_burn = await consume_sse_stream(client, session_a, "What is my validation ID?")
            res_b_post_burn = await consume_sse_stream(client, session_b, "What is my validation ID?")
            
            assert_burn_a = "ALPHA-PLATINUM-9982" not in res_a_post_burn
            assert_burn_b = "BETA-TITANIUM-1104" in res_b_post_burn
            assertions.append({"assertion": "SessionA Forgot Secret Post-Burn", "passed": assert_burn_a})
            assertions.append({"assertion": "SessionB Remains Intact Post-Burn", "passed": assert_burn_b})
            
            # Clean up remaining records
            await client.delete(f"{BASE_URL}/api/session/burn/{session_b}")
            log_event("ResourceCleanlinessComplete", {
                "session_a_post_burn": res_a_post_burn,
                "session_b_post_burn": res_b_post_burn
            })
    finally:
        # Shutdown programmatic server cleanly
        server.should_exit = True
        await server_task

    # --- Write Final Output Verification Report ---
    final_report = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "overall_status": "SUCCESS" if all([a["passed"] for a in assertions]) else "FAILED",
        "port_configured": 8081,
        "session_a_id": session_a,
        "session_b_id": session_b,
        "assertions": assertions,
        "execution_log": execution_log
    }
    
    with open(REPORT_FILE, "w") as f:
        json.dump(final_report, f, indent=2)
        
    print(f"\n🎉 Verification Suite Complete! Summary file written directly to '{REPORT_FILE}'.")

if __name__ == "__main__":
    asyncio.run(run_torture_test())
