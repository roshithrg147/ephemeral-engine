from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

SCHEMA_VERSION = "1.0.0"
ALLOWED_SPLITS = {"Development", "Validation", "Final Evaluation"}
ALLOWED_LENGTHS = {20, 50, 100, 250, 500}
ALLOWED_STATUSES = {"planned", "running", "completed", "partial", "invalid", "failed"}


class SchemaError(ValueError):
    """Raised when evidence input or output violates the frozen schema."""


@dataclass(frozen=True)
class GroundTruth:
    required_facts: list[str]
    forbidden_facts: list[str]
    required_constraints: list[str]
    expired_constraints: list[str]
    rubric: dict[str, Any]
    adjudication: dict[str, Any]
    failure_expectations: list[str]
    source_provenance: list[dict[str, str]]

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> GroundTruth:
        required = {
            "required_facts",
            "forbidden_facts",
            "required_constraints",
            "expired_constraints",
            "rubric",
            "adjudication",
            "failure_expectations",
            "source_provenance",
        }
        missing = required - value.keys()
        if missing:
            raise SchemaError(f"ground truth missing fields: {sorted(missing)}")
        return cls(**{key: value[key] for key in required})


@dataclass(frozen=True)
class Turn:
    turn_id: str
    prompt: str
    ground_truth: GroundTruth
    structural_context: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Turn:
        for key in ("turn_id", "prompt", "ground_truth"):
            if key not in value:
                raise SchemaError(f"turn missing field: {key}")
        return cls(
            turn_id=str(value["turn_id"]),
            prompt=str(value["prompt"]),
            ground_truth=GroundTruth.from_dict(value["ground_truth"]),
            structural_context=[str(item) for item in value.get("structural_context", [])],
        )


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    version: str
    category: str
    split: str
    dataset_version: str
    turns: list[Turn]

    def validate(self, requested_length: int, tuning_mode: bool) -> None:
        if self.split not in ALLOWED_SPLITS:
            raise SchemaError(f"unsupported dataset split: {self.split}")
        if tuning_mode and self.split == "Final Evaluation":
            raise SchemaError("Final Evaluation cannot execute in tuning mode")
        if requested_length not in ALLOWED_LENGTHS:
            raise SchemaError(f"unsupported turn length: {requested_length}")
        if len(self.turns) < requested_length:
            raise SchemaError(
                f"scenario {self.scenario_id} has {len(self.turns)} turns; "
                f"{requested_length} required"
            )
        ids = [turn.turn_id for turn in self.turns]
        if len(ids) != len(set(ids)):
            raise SchemaError(f"duplicate turn IDs in scenario {self.scenario_id}")


@dataclass(frozen=True)
class FailureRecord:
    primary: str
    secondary: list[str]
    scope: str
    severity: str
    evidence: str
    partial: bool = False


@dataclass
class TurnEvidence:
    schema_name: str
    schema_version: str
    run_id: str
    trial_id: str
    strategy_id: str
    blind_strategy_id: str
    scenario_id: str
    turn_id: str
    ordinal: int
    seed: int
    raw_prompt: str
    raw_completion: str
    status: str
    context: str
    retrieval_trace: dict[str, Any]
    graphify_trace: dict[str, Any]
    context_admission: list[dict[str, Any]]
    latency: dict[str, Any]
    usage: dict[str, Any]
    evaluator_input: dict[str, Any]
    evaluator_outputs: list[dict[str, Any]]
    agreement: dict[str, Any]
    failures: list[FailureRecord]
    indexing: dict[str, Any]
    burn: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_status(status: str) -> None:
    if status not in ALLOWED_STATUSES:
        raise SchemaError(f"invalid run status: {status}")
