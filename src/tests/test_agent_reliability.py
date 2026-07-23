import json

from src.agent import AgentOrchestrator, MemorySnapshot
from src.clients import NIMResponse
from src.config import settings


class FailingCoreConnector:
    def call(self, *, model_key, prompt, system_prompt=None, stream=False, max_tokens=None):
        if model_key == settings.MODEL_2_KEY:
            raise RuntimeError("secret provider detail")
        return NIMResponse(
            "complete Model 1 candidate",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
        )


class SuccessfulConnector:
    def __init__(self) -> None:
        self.model_2_calls = 0

    def call(self, *, model_key, prompt, system_prompt=None, stream=False, max_tokens=None):
        if model_key == settings.MODEL_1_KEY:
            return NIMResponse(
                "Model 1 candidate",
                usage={"prompt_tokens": 8, "completion_tokens": 4},
                provider_metadata={
                    "latency_seconds": 0.8,
                    "attempts": [{"attempt": 1, "status": 200, "seconds": 0.8}],
                    "finish_reason": "stop",
                },
            )

        self.model_2_calls += 1
        if self.model_2_calls == 1:
            return NIMResponse(
                "Model 2 candidate",
                usage={"prompt_tokens": 9, "completion_tokens": 5},
                provider_metadata={
                    "latency_seconds": 0.9,
                    "attempts": [{"attempt": 1, "status": 200, "seconds": 0.9}],
                    "finish_reason": "stop",
                },
            )
        return NIMResponse(
            json.dumps(
                {
                    "text": "Model 2 synthesis",
                    "intent": "chat",
                    "action": {"type": "none", "payload": None},
                    "remember": [],
                }
            ),
            usage={"prompt_tokens": 20, "completion_tokens": 7},
            provider_metadata={
                "latency_seconds": 1.2,
                "attempts": [{"attempt": 1, "status": 200, "seconds": 1.2}],
                "finish_reason": "stop",
            },
        )


def test_model_2_failure_returns_explicit_degraded_result(monkeypatch) -> None:
    monkeypatch.setattr(settings, "NVIDIA_API_KEY", "test-key")
    orchestrator = AgentOrchestrator(model_connector=FailingCoreConnector())

    result = orchestrator.generate_response(MemorySnapshot(), "hello")

    assert result.degraded is True
    assert result.degradation_reasons == [
        "model_2_candidate_failed",
        "model_2_synthesis_failed",
    ]
    assert result.text.startswith("[DEGRADED:")
    assert "complete Model 1 candidate" in result.text
    assert "secret provider detail" not in result.text

    failure_records = [
        record for record in result.usage_records or [] if record["status"] == "failed"
    ]
    assert [record["stage"] for record in failure_records] == [
        "model_2_candidate",
        "model_2_synthesis",
    ]


def test_successful_model_2_synthesis_records_all_stages(monkeypatch) -> None:
    monkeypatch.setattr(settings, "NVIDIA_API_KEY", "test-key")
    orchestrator = AgentOrchestrator(model_connector=SuccessfulConnector())

    result = orchestrator.generate_response(MemorySnapshot(), "hello")

    assert result.text == "Model 2 synthesis"
    assert result.degraded is False
    assert [record["stage"] for record in result.usage_records or []] == [
        "model_2_candidate",
        "model_1_candidate",
        "model_2_synthesis",
    ]
    assert all(record["measurement_type"] == "exact" for record in result.usage_records or [])
    assert [record["latency_seconds"] for record in result.usage_records or []] == [0.9, 0.8, 1.2]
    assert all(record["finish_reason"] == "stop" for record in result.usage_records or [])
