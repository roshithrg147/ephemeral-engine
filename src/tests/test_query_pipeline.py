import asyncio
import json

from src import main
from src.agent import Action, RefinedResponse


class FakeEngine:
    def __init__(self):
        self.graphify_values = []

    async def run_query_reformulation_async(self, prompt, history):
        return (
            f"search:{prompt}",
            f"grounded:{prompt}",
            {
                "prompt_tokens": 3,
                "completion_tokens": 4,
            },
        )

    async def evaluate_query_context(self, **kwargs):
        from src.retrieval.trace import ContextTrace
        from src.workflow_policy import WorkflowClass
        self.graphify_values.append(kwargs["graphify_enabled"])
        return "<retrieved_memory>trusted context</retrieved_memory>", ContextTrace(
            correlation_id="test",
            workflow=WorkflowClass.PUBLIC_CHAT,
            principal_id="test_principal",
            query_intent="test_intent"
        )

    @staticmethod
    def check_phase_gate(*_):
        return True


class FakeOrchestrator:
    def generate_response(self, memory_snapshot, prompt):
        assert "trusted context" in prompt
        return RefinedResponse(
            text="pipeline response",
            intent="test",
            action=Action(type="none"),
            remember=["remembered fact"],
            usage_records=[],
        )


class FailedOrchestrator:
    def generate_response(self, memory_snapshot, prompt):
        raise RuntimeError("provider details must stay internal")


class DegradedOrchestrator:
    def generate_response(self, memory_snapshot, prompt):
        return RefinedResponse(
            text="degraded response",
            intent="test",
            action=Action(type="none"),
            remember=[],
            usage_records=[],
            degraded=True,
            degradation_reasons=["model_2_synthesis_failed"],
        )


def test_query_pipeline_emits_response_and_commits_state(monkeypatch):
    async def exercise():
        fake_engine = FakeEngine()

        async def fake_get_orchestrator():
            return FakeOrchestrator()

        async def fake_run_orchestrator(orchestrator, memory_snapshot, prompt, **kwargs):
            return orchestrator.generate_response(memory_snapshot, prompt)

        async def fake_embed_text(record, text):
            return [1.0, 0.0]

        async def fake_get_indexed_documents(record, session_id):
            return []

        indexed = []

        async def fake_index_interaction(record, session_id, chunk):
            indexed.append(chunk)

        def run_index_immediately(coro):
            return asyncio.create_task(coro)

        monkeypatch.setattr(main, "sc_evm_engine", fake_engine)
        monkeypatch.setattr(main, "get_orchestrator", fake_get_orchestrator)
        monkeypatch.setattr(main, "run_orchestrator", fake_run_orchestrator)
        monkeypatch.setattr(main, "embed_text", fake_embed_text)
        monkeypatch.setattr(main, "get_indexed_documents", fake_get_indexed_documents)
        monkeypatch.setattr(main, "index_interaction", fake_index_interaction)
        monkeypatch.setattr(main, "create_tracked_task", run_index_immediately)

        session_id = "query-pipeline"
        chunks = [
            chunk
            async for chunk in main.sse_query_generator(
                session_id,
                "hello",
                graphify_enabled=False,
            )
        ]
        await asyncio.sleep(0)

        events = "".join(chunks)
        assert "event: response_content" in events
        assert json.dumps("pipeline response") in events
        assert "event: done" in events
        assert fake_engine.graphify_values == [False]
        assert indexed == ["User: hello\nAssistant: pipeline response"]

        record = await main.session_registry.get_session(session_id)
        assert list(record.chat_history) == [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "pipeline response"},
        ]
        assert record.metadata_registry["learned_facts"] == ["remembered fact"]
        await main.session_registry.flush_session(session_id)

    asyncio.run(asyncio.wait_for(exercise(), timeout=10))


def test_failed_query_does_not_commit_empty_history(monkeypatch):
    async def exercise():
        fake_engine = FakeEngine()

        async def fake_get_orchestrator():
            return FailedOrchestrator()

        async def fake_run_orchestrator(orchestrator, memory_snapshot, prompt, **kwargs):
            return orchestrator.generate_response(memory_snapshot, prompt)

        async def no_documents(record, session_id):
            return []

        async def fake_embed_text(record, text):
            return [1.0, 0.0]

        monkeypatch.setattr(main, "sc_evm_engine", fake_engine)
        monkeypatch.setattr(main, "get_orchestrator", fake_get_orchestrator)
        monkeypatch.setattr(main, "run_orchestrator", fake_run_orchestrator)
        monkeypatch.setattr(main, "get_indexed_documents", no_documents)
        monkeypatch.setattr(main, "embed_text", fake_embed_text)

        session_id = "query-failure"
        events = "".join([chunk async for chunk in main.sse_query_generator(session_id, "hello")])

        assert "Response generation failed" in events
        assert "provider details must stay internal" not in events
        record = await main.session_registry.get_session(session_id)
        assert list(record.chat_history) == []
        await main.session_registry.flush_session(session_id)

    asyncio.run(asyncio.wait_for(exercise(), timeout=10))


def test_query_pipeline_emits_degradation_event(monkeypatch):
    async def exercise():
        fake_engine = FakeEngine()

        async def fake_get_orchestrator():
            return DegradedOrchestrator()

        async def fake_run_orchestrator(orchestrator, memory_snapshot, prompt, **kwargs):
            return orchestrator.generate_response(memory_snapshot, prompt)

        async def no_documents(record, session_id):
            return []

        async def fake_embed_text(record, text):
            return [1.0, 0.0]

        def discard_indexing(coro):
            coro.close()
            return None

        monkeypatch.setattr(main, "sc_evm_engine", fake_engine)
        monkeypatch.setattr(main, "get_orchestrator", fake_get_orchestrator)
        monkeypatch.setattr(main, "run_orchestrator", fake_run_orchestrator)
        monkeypatch.setattr(main, "get_indexed_documents", no_documents)
        monkeypatch.setattr(main, "embed_text", fake_embed_text)
        monkeypatch.setattr(main, "create_tracked_task", discard_indexing)

        session_id = "query-degraded"
        events = "".join([chunk async for chunk in main.sse_query_generator(session_id, "hello")])

        assert "event: degradation" in events
        assert "model_2_synthesis_failed" in events
        await main.session_registry.flush_session(session_id)

    asyncio.run(asyncio.wait_for(exercise(), timeout=10))


def test_burn_waits_for_in_flight_query_and_prevents_state_resurrection(monkeypatch):
    async def exercise():
        fake_engine = FakeEngine()
        generation_started = asyncio.Event()
        release_generation = asyncio.Event()

        async def fake_get_orchestrator():
            return FakeOrchestrator()

        async def blocking_run(orchestrator, memory_snapshot, prompt, **kwargs):
            generation_started.set()
            await release_generation.wait()
            return orchestrator.generate_response(memory_snapshot, prompt)

        async def no_documents(record, session_id):
            return []

        async def fake_embed_text(record, text):
            return [1.0, 0.0]

        def discard_indexing(coro):
            coro.close()
            return None

        monkeypatch.setattr(main, "sc_evm_engine", fake_engine)
        monkeypatch.setattr(main, "get_orchestrator", fake_get_orchestrator)
        monkeypatch.setattr(main, "run_orchestrator", blocking_run)
        monkeypatch.setattr(main, "get_indexed_documents", no_documents)
        monkeypatch.setattr(main, "embed_text", fake_embed_text)
        monkeypatch.setattr(main, "create_tracked_task", discard_indexing)

        session_id = "query-burn-race"

        async def consume_query():
            return "".join([chunk async for chunk in main.sse_query_generator(session_id, "hello")])

        query_task = asyncio.create_task(consume_query())
        await generation_started.wait()
        burn_task = asyncio.create_task(main.session_registry.flush_session(session_id))
        await asyncio.sleep(0)
        assert burn_task.done() is False

        release_generation.set()
        events, burned = await asyncio.gather(query_task, burn_task)

        assert "pipeline response" in events
        assert burned is True
        assert await main.session_registry.get_session(session_id) is None

    asyncio.run(asyncio.wait_for(exercise(), timeout=10))
