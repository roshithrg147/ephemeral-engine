from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import Scenario, SchemaError, Turn


def load_scenario(path: Path, *, requested_length: int, tuning_mode: bool) -> Scenario:
    try:
        payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SchemaError(f"cannot load scenario {path}: {exc}") from exc

    required = {"scenario_id", "version", "category", "split", "dataset_version", "turns"}
    missing = required - payload.keys()
    if missing:
        raise SchemaError(f"scenario missing fields: {sorted(missing)}")

    defaults = payload.get("ground_truth_defaults", {})
    turns = []
    for item in payload["turns"]:
        merged = dict(item)
        merged["ground_truth"] = {**defaults, **item.get("ground_truth", {})}
        turns.append(Turn.from_dict(merged))

    scenario = Scenario(
        scenario_id=str(payload["scenario_id"]),
        version=str(payload["version"]),
        category=str(payload["category"]),
        split=str(payload["split"]),
        dataset_version=str(payload["dataset_version"]),
        turns=turns,
    )
    scenario.validate(requested_length, tuning_mode)
    return scenario
