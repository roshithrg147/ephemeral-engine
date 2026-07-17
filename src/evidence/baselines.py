from __future__ import annotations

import hashlib
import math
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Protocol

from .models import Turn

TOKEN_RE = re.compile(r"[A-Za-z0-9_'-]+")


def tokens(text: str) -> list[str]:
    return [item.lower() for item in TOKEN_RE.findall(text)]


def estimated_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def hashed_vector_diagnostic(text: str, dimensions: int = 64) -> list[float]:
    vector = [0.0] * dimensions
    for token in tokens(text):
        index = int.from_bytes(hashlib.sha256(token.encode()).digest()[:4], "big") % dimensions
        vector[index] += 1.0
    magnitude = math.sqrt(sum(item * item for item in vector)) or 1.0
    return [item / magnitude for item in vector]


def cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


class Reasoner(Protocol):
    provider: str
    model: str
    version: str

    def complete(self, *, prompt: str, context: str, seed: int) -> str: ...


@dataclass
class StrategyState:
    history: list[tuple[str, str]] = field(default_factory=list)
    summary: str = ""
    session_id: str = ""


@dataclass(frozen=True)
class ContextResult:
    text: str
    retrieval_trace: dict
    graphify_trace: dict
    admissions: list[dict]


class Baseline(ABC):
    version = "1.0.0"
    graphify_enabled = False

    def __init__(self, reasoner: Reasoner, *, direct_budget: int = 4096):
        self.reasoner = reasoner
        self.direct_budget = direct_budget
        self.last_call_metadata: dict = {}

    @property
    @abstractmethod
    def strategy_id(self) -> str: ...

    @abstractmethod
    def build_context(self, turn: Turn, state: StrategyState) -> ContextResult: ...

    def answer(self, turn: Turn, state: StrategyState, seed: int) -> tuple[str, ContextResult]:
        context = self.build_context(turn, state)
        try:
            completion = self.reasoner.complete(prompt=turn.prompt, context=context.text, seed=seed)
        finally:
            self.last_call_metadata = dict(getattr(self.reasoner, "last_metadata", {}))
        state.history.append((turn.prompt, completion))
        return completion, context

    def cleanup(self, state: StrategyState) -> dict:
        removed = len(state.history)
        state.history.clear()
        return {"attempted": True, "status": "completed", "state_entries_removed": removed}


def render_history(history: list[tuple[str, str]]) -> str:
    return "\n".join(f"User: {prompt}\nAssistant: {response}" for prompt, response in history)


class FullReplay(Baseline):
    strategy_id = "full_replay"

    def build_context(self, turn: Turn, state: StrategyState) -> ContextResult:
        text = render_history(state.history)
        return ContextResult(
            text, {"mode": "full_replay", "candidates": len(state.history)}, _graph_off(), []
        )


class SlidingWindow(Baseline):
    strategy_id = "sliding_window"

    def __init__(self, reasoner: Reasoner, *, window: int = 3, direct_budget: int = 4096):
        super().__init__(reasoner, direct_budget=direct_budget)
        self.window = window

    def build_context(self, turn: Turn, state: StrategyState) -> ContextResult:
        selected = state.history[-self.window :]
        return ContextResult(
            render_history(selected),
            {"mode": "sliding_window", "window": self.window},
            _graph_off(),
            [],
        )


class RollingSummary(Baseline):
    strategy_id = "rolling_summary"

    def __init__(self, reasoner: Reasoner, *, window: int = 2, direct_budget: int = 4096):
        super().__init__(reasoner, direct_budget=direct_budget)
        self.window = window

    def build_context(self, turn: Turn, state: StrategyState) -> ContextResult:
        older = state.history[: -self.window]
        fact_lines = [
            line
            for prompt, response in older
            for line in (prompt + "\n" + response).splitlines()
            if "FACT:" in line or "CONSTRAINT:" in line
        ]
        state.summary = "\n".join(dict.fromkeys(fact_lines))
        recent = render_history(state.history[-self.window :])
        text = f"Summary:\n{state.summary}\nRecent:\n{recent}".strip()
        return ContextResult(
            text, {"mode": "rolling_summary", "summary_items": len(fact_lines)}, _graph_off(), []
        )


_ONNX_VECTORIZER = None


def get_onnx_vectorizer():
    global _ONNX_VECTORIZER
    if _ONNX_VECTORIZER is None:
        from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

        embed = ONNXMiniLM_L6_V2()
        cache = {}

        def cached_vectorizer(text):
            if text not in cache:
                cache[text] = list(embed([text])[0])
            return cache[text]

        _ONNX_VECTORIZER = cached_vectorizer
    return _ONNX_VECTORIZER


class TopKRetrieval(Baseline):
    strategy_id = "top_k_retrieval"

    def __init__(
        self, reasoner: Reasoner, *, k: int = 3, direct_budget: int = 4096, vectorizer=None
    ):
        super().__init__(reasoner, direct_budget=direct_budget)
        self.k = k
        self.vectorizer = vectorizer if vectorizer is not None else get_onnx_vectorizer()

    def _rank(self, prompt: str, state: StrategyState) -> list[tuple[int, float, str]]:
        query = self.vectorizer(prompt)
        ranked = []
        for index, pair in enumerate(state.history):
            text = render_history([pair])
            # cosine distance = 1.0 - similarity
            dist = float(
                1.0 - sum(a * b for a, b in zip(query, self.vectorizer(text), strict=True))
            )
            ranked.append((index, dist, text))
        return sorted(ranked, key=lambda item: (item[1], item[0]))[: self.k]

    def build_context(self, turn: Turn, state: StrategyState) -> ContextResult:
        ranked = self._rank(turn.prompt, state)
        candidates = [
            {"source_id": f"turn-{index + 1}", "score": float(score), "admitted": True}
            for index, score, _ in ranked
        ]
        return ContextResult(
            "\n".join(item[2] for item in ranked),
            {"mode": "top_k", "candidates": candidates},
            _graph_off(),
            candidates,
        )


class SCEVMWithoutGraphify(TopKRetrieval):
    strategy_id = "sc_evm_without_graphify"

    def build_context(self, turn: Turn, state: StrategyState) -> ContextResult:
        ranked = self._rank(turn.prompt, state)
        admissions = []
        admitted = []
        for index, score, text in ranked:
            # score is cosine distance; similarity >= 0.05 is equivalent to distance <= 0.95
            accepted = bool(score <= 0.95)
            admissions.append(
                {"source_id": f"turn-{index + 1}", "score": float(score), "admitted": accepted}
            )
            if accepted:
                admitted.append(f"<retrieved_memory>\n{text}\n</retrieved_memory>")
        recent = render_history(state.history[-3:])
        if recent:
            admitted.append(f"<recent_history>\n{recent}\n</recent_history>")
        return ContextResult(
            "\n".join(admitted),
            {"mode": "sc_evm", "candidates": admissions},
            _graph_off(),
            admissions,
        )


class SCEVMWithGraphify(SCEVMWithoutGraphify):
    strategy_id = "sc_evm_with_graphify"
    graphify_enabled = True

    def build_context(self, turn: Turn, state: StrategyState) -> ContextResult:
        base = super().build_context(turn, state)
        structural = "\n".join(turn.structural_context)
        graph_trace = {
            "enabled": True,
            "status": "available" if structural else "empty",
            "items": len(turn.structural_context),
            "artifact": "scenario_structural_context",
        }
        text = base.text
        if structural:
            text += f"\n<graphify_context>\n{structural}\n</graphify_context>"
        return ContextResult(text.strip(), base.retrieval_trace, graph_trace, base.admissions)


def _graph_off() -> dict:
    return {"enabled": False, "status": "disabled", "items": 0}


def required_baselines(reasoner: Reasoner) -> list[Baseline]:
    return [
        FullReplay(reasoner),
        SlidingWindow(reasoner),
        RollingSummary(reasoner),
        TopKRetrieval(reasoner),
        SCEVMWithoutGraphify(reasoner),
        SCEVMWithGraphify(reasoner),
    ]


class OfflineSmokeReasoner:
    """Deterministic plumbing validator; never valid for commercial evidence."""

    provider = "offline-smoke"
    model = "fact-extractor"
    version = "1.0.0"

    def complete(self, *, prompt: str, context: str, seed: int) -> str:
        del seed
        facts = re.findall(r"(?:FACT|CONSTRAINT):[^.\n|]+", context + "\n" + prompt)
        facts = [item.strip() for item in facts]
        return " | ".join(dict.fromkeys(facts)) if facts else "NO_SUPPORTED_FACT"
