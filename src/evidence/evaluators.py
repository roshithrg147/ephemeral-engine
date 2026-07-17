from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Protocol

from .models import FailureRecord, GroundTruth


def blind_label(strategy_id: str, seed: int) -> str:
    value = hashlib.sha256(f"{strategy_id}:{seed}".encode()).hexdigest()[:10]
    return f"strategy-{value}"


class Judge(Protocol):
    evaluator_id: str
    version: str

    def evaluate(
        self, *, prompt: str, completion: str, ground_truth: GroundTruth
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class DeterministicEvaluator:
    evaluator_id: str = "deterministic-ground-truth"
    version: str = "1.0.0"

    def evaluate(
        self, *, prompt: str, completion: str, ground_truth: GroundTruth
    ) -> dict[str, Any]:
        del prompt
        required = {
            fact: fact.lower() in completion.lower() for fact in ground_truth.required_facts
        }
        forbidden = {
            fact: fact.lower() in completion.lower() for fact in ground_truth.forbidden_facts
        }
        constraints = {
            item: item.lower() in completion.lower() for item in ground_truth.required_constraints
        }
        passed = (
            all(required.values()) and not any(forbidden.values()) and all(constraints.values())
        )
        return {
            "evaluator_id": self.evaluator_id,
            "version": self.version,
            "type": "deterministic",
            "passed": passed,
            "required_facts": required,
            "forbidden_facts": forbidden,
            "required_constraints": constraints,
        }


@dataclass(frozen=True)
class RuleEvaluator:
    evaluator_id: str = "rule-rubric"
    version: str = "1.0.0"

    def evaluate(
        self, *, prompt: str, completion: str, ground_truth: GroundTruth
    ) -> dict[str, Any]:
        del prompt
        nonempty = bool(completion.strip())
        unsupported = completion == "NO_SUPPORTED_FACT" and bool(ground_truth.required_facts)
        return {
            "evaluator_id": self.evaluator_id,
            "version": self.version,
            "type": "rule",
            "passed": nonempty and not unsupported,
            "rubric": ground_truth.rubric,
            "unsupported_placeholder": unsupported,
        }


@dataclass(frozen=True)
class HumanEvaluatorPlaceholder:
    evaluator_id: str = "human-review-required"
    version: str = "1.0.0"

    def evaluate(
        self, *, prompt: str, completion: str, ground_truth: GroundTruth
    ) -> dict[str, Any]:
        del prompt, completion
        return {
            "evaluator_id": self.evaluator_id,
            "version": self.version,
            "type": "human_placeholder",
            "status": "pending",
            "adjudication": ground_truth.adjudication,
        }


@dataclass(frozen=True)
class LLMJudge:
    judge: Judge
    evaluator_id: str = "llm-judge"
    version: str = "1.0.0"

    def evaluate(
        self, *, prompt: str, completion: str, ground_truth: GroundTruth
    ) -> dict[str, Any]:
        result = self.judge.evaluate(
            prompt=prompt, completion=completion, ground_truth=ground_truth
        )
        return {**result, "type": "llm_judge", "trusted_as_sole_evaluator": False}


def evaluate_all(
    prompt: str, completion: str, ground_truth: GroundTruth
) -> tuple[list[dict], dict, list[FailureRecord]]:
    results = [
        DeterministicEvaluator().evaluate(
            prompt=prompt, completion=completion, ground_truth=ground_truth
        ),
        RuleEvaluator().evaluate(prompt=prompt, completion=completion, ground_truth=ground_truth),
        HumanEvaluatorPlaceholder().evaluate(
            prompt=prompt, completion=completion, ground_truth=ground_truth
        ),
    ]
    decided = [item["passed"] for item in results if "passed" in item]
    agreement = {
        "decided_evaluators": len(decided),
        "unanimous": len(set(decided)) <= 1,
        "agreement_rate": 1.0 if len(set(decided)) <= 1 else 0.0,
    }
    failures = []
    if decided and not all(decided):
        failures.append(
            FailureRecord(
                primary="CTX-CONSTRAINT-FORGOTTEN",
                secondary=[],
                scope="turn",
                severity="High",
                evidence="deterministic or rule evaluator failed",
                partial=any(decided),
            )
        )
    return results, agreement, failures
