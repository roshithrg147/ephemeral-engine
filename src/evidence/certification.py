from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .artifacts import ImmutableArtifactStore


def certify_run(
    run_dir: Path,
    *,
    minimum_scenarios: int = 30,
    checksum_validation_override: bool | None = None,
) -> dict[str, Any]:
    checks = {
        "manifest": (run_dir / "manifest.json").exists(),
        "environment": (run_dir / "environment.json").exists(),
        "configuration": (run_dir / "configuration.json").exists(),
        "raw": any((run_dir / "raw").glob("*.json")),
        "evaluations": any((run_dir / "evaluations").glob("*.json")),
        "traces": any((run_dir / "traces").glob("*.json")),
        "failure_accounting": (run_dir / "failures.jsonl").exists(),
        "statistics": (run_dir / "statistics.json").exists(),
        "checksums": (run_dir / "checksums.sha256").exists()
        or checksum_validation_override is True,
    }
    manifest = (
        json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        if checks["manifest"]
        else {}
    )
    statistics_payload = (
        json.loads((run_dir / "statistics.json").read_text(encoding="utf-8"))
        if checks["statistics"]
        else {}
    )
    checks["schema"] = manifest.get("schema_name") == "scevm.run-manifest"
    checks["provenance"] = bool(
        manifest.get("code") and manifest.get("dataset") and manifest.get("models")
    )
    checks["confidence_intervals"] = _contains_key(statistics_payload, "ci95")
    checks["effect_sizes"] = _contains_key(statistics_payload, "standardized_mean_difference")
    checks["evaluator_outputs"] = checks["evaluations"]
    checks["sample_size"] = (
        len(manifest.get("dataset", {}).get("scenario_ids", [])) >= minimum_scenarios
    )
    if checksum_validation_override is not None:
        checks["checksum_validation"] = checksum_validation_override
    elif (run_dir / "checksums.sha256").exists():
        store = object.__new__(ImmutableArtifactStore)
        store.run_dir = run_dir
        checks["checksum_validation"] = store.validate_checksums()
    else:
        checks["checksum_validation"] = False
    return {
        "schema_name": "scevm.execution-certification",
        "schema_version": "1.0.0",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "publication_allowed": all(checks.values()),
    }


def _contains_key(value: Any, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(_contains_key(item, key) for item in value.values())
    if isinstance(value, list):
        return any(_contains_key(item, key) for item in value)
    return False
