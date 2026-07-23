import asyncio
from pathlib import Path

from src.clients import NIMResponse
from src.config import settings
from src.memory import MemoryManager, MultiTenantSessionRegistry
from src.sc_evm import SCEVMEngine


class RewriteConnector:
    def __init__(self):
        self.last_request = {}

    async def call_async(self, **kwargs):
        self.last_request = kwargs
        return NIMResponse(
            '{"search_vector_query":"stable query","grounded_llm_prompt":"grounded prompt"}',
            {"prompt_tokens": 4, "completion_tokens": 7},
            {"latency_seconds": 0.4, "finish_reason": "stop", "attempts": []},
        )


def test_reformulation_preserves_provider_usage():
    connector = RewriteConnector()
    engine = SCEVMEngine(model_connector=connector)

    search_query, grounded_prompt, usage = asyncio.run(
        engine.run_query_reformulation_async("original", [])
    )

    assert search_query == "stable query"
    assert grounded_prompt == "grounded prompt"
    assert usage == {"prompt_tokens": 4, "completion_tokens": 7}
    assert usage.provider_metadata["latency_seconds"] == 0.4
    assert connector.last_request["model_key"] == settings.MODEL_1_KEY
    assert connector.last_request["max_tokens"] == settings.MODEL_REFORMULATION_MAX_TOKENS


def test_memory_manager_persists_relative_path_atomically(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    manager = MemoryManager("memory.json")
    manager.add_fact("atomic fact")

    assert Path("memory.json").exists()
    assert not list(tmp_path.glob(".memory-*.tmp"))


def test_registry_stops_gc_task():
    async def exercise():
        registry = MultiTenantSessionRegistry()
        await registry.start_daemons()
        task = registry._gc_task

        await registry.stop_daemons()

        assert task is not None
        assert task.cancelled()
        assert registry._gc_task is None

    asyncio.run(exercise())
