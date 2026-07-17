import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
import requests

pytestmark = pytest.mark.live

BASE_URL = "http://localhost:8000"  # Update to your local service port
ASSESSMENT_RESULTS = []
ASSESSMENT_TRANSCRIPT = []


def write_assessment_outputs(results, transcript, output_json_path=None, output_txt_path=None):
    """Persist user/engine assessment results into a JSON report and text transcript."""
    base_dir = Path(__file__).resolve().parent
    json_path = Path(output_json_path) if output_json_path else base_dir / "assmnt_test_result.json"
    txt_path = Path(output_txt_path) if output_txt_path else base_dir / "assmnt_test_result.txt"

    report = {
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "results": results,
    }
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    txt_path.write_text("\n\n".join(transcript), encoding="utf-8")
    return json_path, txt_path


def record_result(test_name, prompt, response_text, passed):
    ASSESSMENT_RESULTS.append(
        {
            "test_name": test_name,
            "prompt": prompt,
            "response": response_text,
            "passed": passed,
        }
    )
    ASSESSMENT_TRANSCRIPT.append(f"User: {prompt}\nEngine: {response_text}")


def extract_sse_response(response):
    if response.status_code != 200:
        return str(response.text)
    full_text = ""
    for line in response.iter_lines():
        if line:
            line_str = line.decode("utf-8")
            if line_str.startswith("data: "):
                data_str = line_str[6:]
                if data_str == "[DONE]":
                    continue
                try:
                    data = json.loads(data_str)
                    if isinstance(data, str):
                        full_text += data
                except Exception:
                    pass
    return full_text


def test_multi_tenant_isolation():
    """Verify that Tenant A cannot access Tenant B's memory."""
    prompt = "What is the project codename?"
    try:
        requests.post(f"{BASE_URL}/api/session/initialize", json={"session_id": "A"}, timeout=10)
        requests.post(
            f"{BASE_URL}/api/agent/query",
            json={"session_id": "A", "prompt": "Project codename is ALPHA"},
            stream=True,
            timeout=10,
        )
        requests.post(f"{BASE_URL}/api/session/initialize", json={"session_id": "B"}, timeout=10)
        response = requests.post(
            f"{BASE_URL}/api/agent/query",
            json={"session_id": "B", "prompt": prompt},
            stream=True,
            timeout=10,
        )
        response_text = extract_sse_response(response)
    except Exception as exc:
        response_text = f"ERROR: {exc}"

    print(f"Response: {response_text}")
    passed = "ALPHA" not in response_text
    record_result("test_multi_tenant_isolation", prompt, response_text, passed)
    assert passed, "Cross-tenant leakage detected!"


def test_phase_gating():
    """Verify Architect-First gating logic."""
    prompt = "Write the UI header component"
    try:
        response = requests.post(
            f"{BASE_URL}/api/agent/query", json={"session_id": "A", "prompt": prompt}, stream=True
        )
        response_text = extract_sse_response(response).lower()
    except Exception as exc:
        response_text = f"ERROR: {exc}".lower()

    print(f"Response: {response_text}")
    passed = "refuse" in response_text or "cannot" in response_text
    record_result("test_phase_gating", prompt, response_text, passed)
    assert passed, "Engine failed to enforce phase gate."


def test_burn_command():
    """Verify complete memory teardown."""
    prompt = "What was the project codename?"
    try:
        requests.delete(f"{BASE_URL}/api/session/burn/A", timeout=10)
        response = requests.post(
            f"{BASE_URL}/api/agent/query",
            json={"session_id": "A", "prompt": prompt},
            stream=True,
            timeout=10,
        )
        response_text = extract_sse_response(response)
    except Exception as exc:
        response_text = f"ERROR: {exc}"

    print(f"Response: {response_text}")
    passed = "ALPHA" not in response_text
    record_result("test_burn_command", prompt, response_text, passed)
    assert passed, "Memory not purged after /burn."


if __name__ == "__main__":
    try:
        test_multi_tenant_isolation()
        test_phase_gating()
        test_burn_command()
        print("All tests passed successfully.")
    except AssertionError as exc:
        print(f"Assessment failed: {exc}")
    finally:
        json_path, txt_path = write_assessment_outputs(ASSESSMENT_RESULTS, ASSESSMENT_TRANSCRIPT)
        print(f"Saved assessment JSON to: {json_path}")
        print(f"Saved assessment transcript to: {txt_path}")
