import asyncio
import json
import time
from datetime import datetime
from typing import Any

import httpx
import uvicorn

from src.main import app

PORT = 8089
BASE_URL = f"http://127.0.0.1:{PORT}"

# Global telemetry logs collector for the report JSON
telemetry_log = []


def log_event(name: str, detail: Any):
    log_entry = {"timestamp": datetime.utcnow().isoformat() + "Z", "event": name, "detail": detail}
    telemetry_log.append(log_entry)
    print(f"[{name}] {detail}")


class BackgroundUvicornServer(uvicorn.Server):
    """Programmatic wrapper to start and stop Uvicorn server cleanly inside async tests."""

    def install_signal_handlers(self):
        pass


async def run_server(server: BackgroundUvicornServer):
    try:
        await server.serve()
    except Exception as e:
        log_event("ServerException", str(e))


async def consume_sse_tokens(client: httpx.AsyncClient, session_id: str, prompt: str) -> str:
    """Helper to post query, consume SSE streams, and extract synthesized response tokens."""
    url = f"{BASE_URL}/api/agent/query"
    payload = {"session_id": session_id, "prompt": prompt}

    full_text = ""
    current_event = None
    start_time = time.perf_counter()

    async with client.stream("POST", url, json=payload, timeout=400.0) as response:
        if response.status_code != 200:
            err_msg = f"Query request failed with status {response.status_code}"
            log_event("QueryError", {"session_id": session_id, "error": err_msg})
            raise RuntimeError(err_msg)

        async for line in response.aiter_lines():
            line = line.strip()
            if line.startswith("event: "):
                current_event = line[len("event: ") :].strip()
            elif line.startswith("data: "):
                data_str = line[len("data: ") :].strip()
                if current_event in ("token", "response_content"):
                    try:
                        token = json.loads(data_str)
                        if isinstance(token, str):
                            full_text += token
                    except Exception as e:
                        log_event(
                            "TokenParseError",
                            {
                                "session_id": session_id,
                                "error": str(e),
                                "payload": data_str,
                            },
                        )

    latency = time.perf_counter() - start_time
    log_event(
        "QueryTelemetry",
        {
            "session_id": session_id,
            "prompt": prompt,
            "latency_seconds": latency,
            "response_length": len(full_text),
        },
    )
    return full_text


async def main():
    log_event("TestStart", "Initiating SC-EVM verification harness")

    # 1. Start Programmatic Uvicorn Server in background task
    config = uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning")
    server = BackgroundUvicornServer(config)
    server_task = asyncio.create_task(run_server(server))

    # Give server time to bind to port
    await asyncio.sleep(2.0)

    report_status = "FAILED"
    assertions_log = []

    try:
        async with httpx.AsyncClient() as client:
            session_a = "tenant-session-alpha"
            session_b = "tenant-session-beta"

            # 2. Initialize both sessions
            log_event("InitSession", f"Initializing: {session_a}")
            resp_init_a = await client.post(
                f"{BASE_URL}/api/session/initialize", json={"session_id": session_a}
            )
            assert resp_init_a.json()["status"] == "success"

            log_event("InitSession", f"Initializing: {session_b}")
            resp_init_b = await client.post(
                f"{BASE_URL}/api/session/initialize", json={"session_id": session_b}
            )
            assert resp_init_b.json()["status"] == "success"

            # 3. Simulate concurrent speed-typing operations injecting different context
            log_event(
                "ConcurrentInjections",
                "Firing concurrent context prompts to Session A and Session B",
            )
            prompt_a = "Please remember: The primary capital city for the region of Alpha is GargantuanApple77."
            prompt_b = "Please remember: The primary capital city for the region of Beta is MicroscopicBanana88."

            task_a = asyncio.create_task(consume_sse_tokens(client, session_a, prompt_a))
            task_b = asyncio.create_task(consume_sse_tokens(client, session_b, prompt_b))

            response_a, response_b = await asyncio.gather(task_a, task_b)
            log_event(
                "InjectionsCompleted",
                {"session_a_response": response_a, "session_b_response": response_b},
            )

            # Sleep momentarily to let background indexing tasks commit to ChromaDB
            log_event("PipelineWait", "Sleeping to allow background ingestion to complete")
            await asyncio.sleep(3.0)

            # 4. Assert Session Isolation: Query Session A for Session B secrets
            log_event("IsolationCheckStart", "Verifying strict session isolation boundaries")
            verify_prompt_a = "What is the primary capital city for the region of Alpha? Also, do you know anything about Beta's capital city?"
            verify_prompt_b = "What is the primary capital city for the region of Beta? Also, do you know anything about Alpha's capital city?"

            check_response_a = await consume_sse_tokens(client, session_a, verify_prompt_a)
            check_response_b = await consume_sse_tokens(client, session_b, verify_prompt_b)

            log_event(
                "IsolationCheckComplete",
                {
                    "session_a_verification": check_response_a,
                    "session_b_verification": check_response_b,
                },
            )

            # Assertions
            assert_1 = "GargantuanApple77" in check_response_a
            assert_2 = "MicroscopicBanana88" not in check_response_a
            assert_3 = "MicroscopicBanana88" in check_response_b
            assert_4 = "GargantuanApple77" not in check_response_b

            assertions_log.append(
                {"assertion": "SessionA Knows Its Secret", "passed": bool(assert_1)}
            )
            assertions_log.append(
                {"assertion": "SessionA Wont Leak SessionB Secret", "passed": bool(assert_2)}
            )
            assertions_log.append(
                {"assertion": "SessionB Knows Its Secret", "passed": bool(assert_3)}
            )
            assertions_log.append(
                {"assertion": "SessionB Wont Leak SessionA Secret", "passed": bool(assert_4)}
            )

            assert assert_1, "Session A failed to retrieve its own secret"
            assert assert_2, "CRITICAL ERROR: Session A leaked Session B secret!"
            assert assert_3, "Session B failed to retrieve its own secret"
            assert assert_4, "CRITICAL ERROR: Session B leaked Session A secret!"

            log_event(
                "IsolationVerificationPassed",
                "Strict multi-tenant isolation validated. Zero leakages.",
            )

            # 5. Flush/Burn Session A
            log_event("SessionBurn", f"Burning Session A: {session_a}")
            resp_burn_a = await client.delete(f"{BASE_URL}/api/session/burn/{session_a}")
            assert resp_burn_a.json()["status"] == "success"

            # 6. Verify Session A is cleanly wiped while Session B remains active
            log_event("ResourceCleanlinessCheck", "Verifying selective burn resource cleanup")
            wipe_check_a = await consume_sse_tokens(
                client, session_a, "What was the primary capital city for the region of Alpha?"
            )
            still_active_b = await consume_sse_tokens(
                client, session_b, "What was the primary capital city for the region of Beta?"
            )

            log_event(
                "ResourceCleanlinessComplete",
                {"session_a_post_burn": wipe_check_a, "session_b_post_burn": still_active_b},
            )

            assert_5 = "GargantuanApple77" not in wipe_check_a
            assert_6 = "MicroscopicBanana88" in still_active_b

            assertions_log.append(
                {"assertion": "SessionA Forgot Secret Post-Burn", "passed": bool(assert_5)}
            )
            assertions_log.append(
                {"assertion": "SessionB Remains Intact Post-Burn", "passed": bool(assert_6)}
            )

            assert assert_5, "CRITICAL ERROR: Session A still remembers secret after /burn flush!"
            assert assert_6, "Session B lost context after Session A burn!"

            log_event(
                "WipeVerificationPassed",
                "Burn verification successful. RAM footprint and Chroma vector space cleared.",
            )
            report_status = "SUCCESS"

    except Exception as e:
        log_event("TestHarnessFailure", str(e))
        report_status = "FAILED"
    finally:
        # Shutdown programmatic server cleanly
        server.should_exit = True
        await server_task
        log_event("TestFinish", f"Harness run completed. Status: {report_status}")

        # Write final structured report to sc_evm_validation_report.json
        report_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "overall_status": report_status,
            "port_configured": PORT,
            "session_a_id": "tenant-session-alpha",
            "session_b_id": "tenant-session-beta",
            "assertions": assertions_log,
            "execution_log": telemetry_log,
        }

        with open("sc_evm_validation_report.json", "w") as rf:
            json.dump(report_data, rf, indent=2)

        print("\n[Harness] Saved structured validation report to: sc_evm_validation_report.json")


if __name__ == "__main__":
    asyncio.run(main())
