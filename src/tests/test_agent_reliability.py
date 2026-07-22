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
            )

        self.model_2_calls += 1
        if self.model_2_calls == 1:
            return NIMResponse(
                "Model 2 candidate",
                usage={"prompt_tokens": 9, "completion_tokens": 5},
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
