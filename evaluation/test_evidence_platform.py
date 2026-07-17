import json
from pathlib import Path

import pytest

from src.evidence.artifacts import ImmutableArtifactStore
from src.evidence.baselines import (
    FullReplay,
    OfflineSmokeReasoner,
    StrategyState,
    required_baselines,
)
from src.evidence.certification import certify_run
from src.evidence.loaders import load_scenario
from src.evidence.models import SchemaError
from src.evidence.runner import EvidenceRunner, RunConfig
from src.evidence.statistics import analyze_run, paired_effect

DATASET = Path("evaluation/datasets/development/smoke-software-engineering-v1.json")


def test_loader_rejects_final_evaluation_in_tuning_mode(tmp_path):
    payload = json.loads(DATASET.read_text(encoding="utf-8"))
    payload["split"] = "Final Evaluation"
    path = tmp_path / "final.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(SchemaError, match="cannot execute in tuning mode"):
        load_scenario(path, requested_length=20, tuning_mode=True)


def test_artifact_store_refuses_existing_run_directory(tmp_path):
    ImmutableArtifactStore(tmp_path, "same-run")

    with pytest.raises(FileExistsError):
        ImmutableArtifactStore(tmp_path, "same-run")


def test_checksum_validation_rejects_incomplete_manifest(tmp_path):
    store = ImmutableArtifactStore(tmp_path, "checksums")
    store.write_text("raw/result.json", "{}\n")
    store.write_text("summary.json", "{}\n")
    store.write_checksums()
    lines = (store.run_dir / "checksums.sha256").read_text(encoding="utf-8").splitlines()
    (store.run_dir / "checksums.sha256").write_text(lines[0] + "\n", encoding="utf-8")

    assert store.validate_checksums() is False


def test_required_baselines_include_graphify_pair():
    scenario = load_scenario(DATASET, requested_length=20, tuning_mode=True)
    baselines = required_baselines(OfflineSmokeReasoner())
    by_id = {item.strategy_id: item for item in baselines}

    off = by_id["sc_evm_without_graphify"].build_context(scenario.turns[-1], StrategyState())
    on = by_id["sc_evm_with_graphify"].build_context(scenario.turns[-1], StrategyState())

    assert len(baselines) == 6
    assert off.graphify_trace["enabled"] is False
    assert on.graphify_trace["enabled"] is True
    assert "Atlas -> depends_on -> Borealis" in on.text


def test_schedule_is_reproducible(tmp_path):
    runner = EvidenceRunner(RunConfig(DATASET, tmp_path, seeds=(11, 29), smoke=True))
    ids = [item.strategy_id for item in required_baselines(OfflineSmokeReasoner())]

    assert runner._schedule(ids) == runner._schedule(ids)
    assert runner._schedule(ids)[0][1] != runner._schedule(ids)[1][1]


def test_smoke_run_writes_complete_immutable_artifacts(tmp_path):
    run_dir = EvidenceRunner(
        RunConfig(DATASET, tmp_path, turn_length=20, seeds=(11,), tuning_mode=True, smoke=True)
    ).run()

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    raw_trials = list((run_dir / "raw").rglob("*.json"))
    recorded_turns = sum(len(json.loads(path.read_text(encoding="utf-8"))) for path in raw_trials)

    assert manifest["schema_name"] == "scevm.run-manifest"
    assert manifest["status"] == "completed"
    assert len(manifest["strategies"]) == 6
    assert len(raw_trials) == 6
    assert recorded_turns == 120
    assert summary["publishable"] is False
    assert (run_dir / "environment.json").exists()
    assert (run_dir / "configuration.json").exists()
    assert (run_dir / "checksums.sha256").exists()
    assert (run_dir / "statistics.json").exists()
    assert (run_dir / "certification.json").exists()
    store = object.__new__(ImmutableArtifactStore)
    store.run_dir = run_dir
    assert store.validate_checksums() is True
    analysis = analyze_run(run_dir)
    assert len(analysis["strategies"]) == 6
    assert analysis["failed_run_accounting"] is True
    certification = certify_run(run_dir)
    assert certification["status"] == "FAIL"
    assert certification["checks"]["sample_size"] is False


def test_paired_effect_reports_interval_and_effect_size():
    result = paired_effect([1.0, 2.0, 3.0], [0.5, 1.5, 2.5])

    assert result["count"] == 3
    assert result["mean_difference"] == 0.5
    assert result["standardized_mean_difference"] == 0.0
    assert result["ci95"] == [0.5, 0.5]


def test_baseline_preserves_failed_call_metadata():
    class FailedReasoner:
        provider = "test"
        model = "test"
        version = "1"
        last_metadata = {"attempts": [{"attempt": 1, "error": "TimeoutError"}]}

        def complete(self, **_):
            raise TimeoutError("timed out")

    scenario = load_scenario(DATASET, requested_length=20, tuning_mode=True)
    baseline = FullReplay(FailedReasoner())

    with pytest.raises(TimeoutError):
        baseline.answer(scenario.turns[0], StrategyState(), 11)

    assert baseline.last_call_metadata["attempts"][0]["error"] == "TimeoutError"


def test_runner_closes_resources_when_execution_raises(tmp_path, monkeypatch):
    closed = {"strategy": False, "reasoner": False}

    class ClosingReasoner(OfflineSmokeReasoner):
        def close(self):
            closed["reasoner"] = True

    class ClosingBaseline(FullReplay):
        def close(self):
            closed["strategy"] = True

    reasoner = ClosingReasoner()
    baseline = ClosingBaseline(reasoner)
    runner = EvidenceRunner(
        RunConfig(DATASET, tmp_path, smoke=True),
        reasoner=reasoner,
        strategies=[baseline],
    )

    def fail_execution(**_):
        raise RuntimeError("forced execution failure")

    monkeypatch.setattr(runner, "_execute_turn", fail_execution)

    with pytest.raises(RuntimeError, match="forced execution failure"):
        runner.run()

    assert closed == {"strategy": True, "reasoner": True}
