from __future__ import annotations

import json
import os
import platform
import random
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .artifacts import ImmutableArtifactStore, sha256_file
from .baselines import (
    OfflineSmokeReasoner,
    Reasoner,
    StrategyState,
    estimated_tokens,
    required_baselines,
)
from .certification import certify_run
from .evaluators import blind_label, evaluate_all
from .loaders import load_scenario
from .models import SCHEMA_VERSION, FailureRecord, TurnEvidence, validate_status
from .statistics import analyze_run


@dataclass(frozen=True)
class RunConfig:
    dataset_path: Path
    output_root: Path
    turn_length: int = 20
    seeds: tuple[int, ...] = (11,)
    tuning_mode: bool = True
    timeout_seconds: float = 30.0
    max_retries: int = 0
    smoke: bool = False


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _git(command: list[str]) -> str:
    try:
        return subprocess.check_output(
            ["git", *command], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _run_id(dataset_version: str, commit: str) -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    nonce = uuid.uuid4().hex[:8]
    safe_dataset = "".join(
        character if character.isalnum() else "-" for character in dataset_version
    ).strip("-")
    return f"scevm-eval-{timestamp}-{safe_dataset}-{commit[:8]}-{nonce}"


class EvidenceRunner:
    def __init__(self, config: RunConfig, *, reasoner: Reasoner | None = None, strategies=None):
        self.config = config
        self.reasoner = reasoner or OfflineSmokeReasoner()
        self.strategies = strategies
        self._active_strategies = ()

    def run(self) -> Path:
        try:
            return self._run()
        finally:
            self._close_resources()

    def _close_resources(self) -> None:
        for strategy in self._active_strategies:
            close = getattr(strategy, "close", None)
            if callable(close):
                close()
        close_reasoner = getattr(self.reasoner, "close", None)
        if callable(close_reasoner):
            close_reasoner()

    def _run(self) -> Path:
        scenario = load_scenario(
            self.config.dataset_path,
            requested_length=self.config.turn_length,
            tuning_mode=self.config.tuning_mode,
        )
        commit = _git(["rev-parse", "HEAD"])
        run_id = _run_id(scenario.dataset_version, commit)
        store = ImmutableArtifactStore(self.config.output_root, run_id)
        started = _utc_now()

        environment = self._environment(commit)
        configuration = self._configuration(scenario)
        strategies = self.strategies or required_baselines(self.reasoner)
        self._active_strategies = tuple(strategies)
        schedule = self._schedule([item.strategy_id for item in strategies])
        planned = self._manifest(run_id, scenario, schedule, environment, "planned", started)
        store.write_json("manifest.planned.json", planned)
        store.write_json("environment.json", environment)
        store.write_json("configuration.json", configuration)
        store.write_json(
            "dataset.json",
            {
                "scenario_id": scenario.scenario_id,
                "scenario_version": scenario.version,
                "dataset_version": scenario.dataset_version,
                "split": scenario.split,
                "source": str(self.config.dataset_path),
                "checksum": sha256_file(self.config.dataset_path),
            },
        )
        store.write_json(
            "prompts.json",
            {
                "schema_version": SCHEMA_VERSION,
                "prompt_policy": "scenario prompts supplied verbatim",
                "reasoner_version": self.reasoner.version,
            },
        )
        store.write_json(
            "models.json",
            {
                "provider": self.reasoner.provider,
                "model": self.reasoner.model,
                "version": self.reasoner.version,
                "parameters": {"temperature": 0, "offline_smoke": self.config.smoke},
            },
        )

        all_failures: list[dict[str, Any]] = []
        strategy_summaries = []
        execution_failed = False
        for seed, ordered_ids in schedule:
            by_id = {item.strategy_id: item for item in strategies}
            blind = {item: blind_label(item, seed) for item in ordered_ids}
            for strategy_id in ordered_ids:
                strategy = by_id[strategy_id]
                trial_id = f"{scenario.scenario_id}-{self.config.turn_length}-{seed}-{strategy_id}"
                state = StrategyState(session_id=trial_id)
                trial_failures = 0
                turns = []
                evaluations = []
                traces = []
                for ordinal, turn in enumerate(scenario.turns[: self.config.turn_length], start=1):
                    evidence = self._execute_turn(
                        run_id=run_id,
                        trial_id=trial_id,
                        strategy=strategy,
                        state=state,
                        turn=turn,
                        scenario_id=scenario.scenario_id,
                        ordinal=ordinal,
                        seed=seed,
                        blind_id=blind[strategy_id],
                    )
                    turns.append(evidence.to_dict())
                    trial_failures += len(evidence.failures)
                    all_failures.extend(
                        {**asdict(failure), "trial_id": trial_id, "turn_id": turn.turn_id}
                        for failure in evidence.failures
                    )
                    evaluations.append(
                        {
                            "turn_id": turn.turn_id,
                            "outputs": evidence.evaluator_outputs,
                            "agreement": evidence.agreement,
                        }
                    )
                    traces.append(
                        {
                            "turn_id": turn.turn_id,
                            "retrieval": evidence.retrieval_trace,
                            "graphify": evidence.graphify_trace,
                            "admission": evidence.context_admission,
                        }
                    )
                    if evidence.status != "completed":
                        execution_failed = True
                store.write_json(f"raw/{trial_id}.json", turns)
                store.write_json(f"evaluations/{trial_id}.json", evaluations)
                store.write_json(f"traces/{trial_id}.json", traces)
                burn = strategy.cleanup(state)
                strategy_summaries.append(
                    {
                        "strategy_id": strategy_id,
                        "strategy_version": strategy.version,
                        "blind_strategy_id": blind[strategy_id],
                        "trial_id": trial_id,
                        "seed": seed,
                        "turns": len(turns),
                        "execution_failures": sum(item["status"] != "completed" for item in turns),
                        "evaluation_failures": trial_failures,
                        "burn": burn,
                    }
                )

        if all_failures:
            store.write_text(
                "failures.jsonl",
                "".join(json.dumps(item, sort_keys=True) + "\n" for item in all_failures),
            )
        else:
            store.write_text("failures.jsonl", "")
        status = "partial" if execution_failed else "completed"
        validate_status(status)
        summary = {
            "schema_name": "scevm.summary",
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "status": status,
            "publishable": False if self.config.smoke else None,
            "strategies": strategy_summaries,
            "failure_records": len(all_failures),
            "methodology_note": "Smoke results validate execution plumbing only"
            if self.config.smoke
            else "",
        }
        store.write_json("summary.json", summary)
        store.write_json(
            "manifest.json",
            self._manifest(
                run_id, scenario, schedule, environment, status, started, finished=_utc_now()
            ),
        )
        store.write_json("statistics.json", analyze_run(store.run_dir))
        store.write_json(
            "certification.json",
            certify_run(store.run_dir, checksum_validation_override=True),
        )
        store.write_checksums()
        if not store.validate_checksums():
            raise RuntimeError(f"artifact checksum validation failed for {run_id}")
        return store.run_dir

    def _execute_turn(
        self,
        *,
        run_id: str,
        trial_id: str,
        strategy,
        state,
        turn,
        scenario_id: str,
        ordinal: int,
        seed: int,
        blind_id: str,
    ) -> TurnEvidence:
        start = time.perf_counter()
        failures: list[FailureRecord] = []
        completion = ""
        context_text = ""
        retrieval_trace: dict[str, Any] = {}
        graphify_trace: dict[str, Any] = {
            "enabled": strategy.graphify_enabled,
            "status": "not_started",
        }
        admissions: list[dict[str, Any]] = []
        status = "completed"
        try:
            completion, context = strategy.answer(turn, state, seed)
            context_text = context.text
            retrieval_trace = context.retrieval_trace
            graphify_trace = context.graphify_trace
            admissions = context.admissions
        except TimeoutError as exc:
            status = "failed"
            failures.append(FailureRecord("PROVIDER-TIMEOUT", [], "turn", "High", str(exc)))
        except Exception as exc:  # Evidence must retain unexpected failures.
            status = "failed"
            failures.append(FailureRecord("PROVIDER-FAILURE", [], "turn", "Medium", repr(exc)))

        evaluator_input = {
            "prompt": turn.prompt,
            "completion": completion,
            "ground_truth": asdict(turn.ground_truth),
            "blind_strategy_id": blind_id,
        }
        evaluator_outputs, agreement, evaluator_failures = evaluate_all(
            turn.prompt, completion, turn.ground_truth
        )
        failures.extend(evaluator_failures)
        elapsed = time.perf_counter() - start
        call_metadata = dict(getattr(strategy, "last_call_metadata", {}))
        usage = call_metadata.get("usage") or {
            "provider_reported": None,
            "calculated": None,
            "estimated": {
                "input_tokens": estimated_tokens(context_text + turn.prompt),
                "output_tokens": estimated_tokens(completion),
            },
            "cost": None,
            "cost_missing_reason": "provider usage unavailable",
        }
        return TurnEvidence(
            schema_name="scevm.turn-result",
            schema_version=SCHEMA_VERSION,
            run_id=run_id,
            trial_id=trial_id,
            strategy_id=strategy.strategy_id,
            blind_strategy_id=blind_id,
            scenario_id=scenario_id,
            turn_id=turn.turn_id,
            ordinal=ordinal,
            seed=seed,
            raw_prompt=turn.prompt,
            raw_completion=completion,
            status=status,
            context=context_text,
            retrieval_trace=retrieval_trace,
            graphify_trace=graphify_trace,
            context_admission=admissions,
            latency={
                "end_to_end_seconds": call_metadata.get("latency_seconds", elapsed),
                "time_to_first_meaningful_response_seconds": call_metadata.get(
                    "time_to_first_meaningful_response_seconds", elapsed if completion else None
                ),
                "measurement": "monotonic",
                "attempts": call_metadata.get("attempts", []),
            },
            usage=usage,
            evaluator_input=evaluator_input,
            evaluator_outputs=evaluator_outputs,
            agreement=agreement,
            failures=failures,
            indexing=call_metadata.get(
                "indexing",
                {"status": "completed", "lag_seconds": 0.0, "mode": "in_process_smoke"},
            ),
        )

    def _schedule(self, strategy_ids: list[str]) -> list[tuple[int, list[str]]]:
        schedule = []
        for seed in self.config.seeds:
            order = list(strategy_ids)
            random.Random(seed).shuffle(order)
            schedule.append((seed, order))
        return schedule

    def _environment(self, commit: str) -> dict[str, Any]:
        lock = Path("uv.lock")
        tracked_dirty = bool(_git(["status", "--porcelain", "--untracked-files=no"]))
        return {
            "schema_name": "scevm.environment",
            "schema_version": SCHEMA_VERSION,
            "python": sys.version,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "timezone": time.tzname,
            "git_commit": commit,
            "git_dirty": tracked_dirty,
            "git_dirty_scope": "tracked files only; untracked files not scanned",
            "dependency_lock": str(lock),
            "dependency_lock_sha256": sha256_file(lock) if lock.exists() else None,
            "cwd": os.getcwd(),
        }

    def _configuration(self, scenario) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "turn_length": self.config.turn_length,
            "seeds": self.config.seeds,
            "tuning_mode": self.config.tuning_mode,
            "timeout_seconds": self.config.timeout_seconds,
            "max_retries": self.config.max_retries,
            "split": scenario.split,
            "smoke": self.config.smoke,
        }

    def _manifest(
        self, run_id, scenario, schedule, environment, status, started, finished=None
    ) -> dict[str, Any]:
        validate_status(status)
        return {
            "schema_name": "scevm.run-manifest",
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "created_at": started,
            "finished_at": finished,
            "status": status,
            "hypotheses": ["execution platform produces complete immutable evidence artifacts"],
            "claim_ids": [],
            "acceptance_thresholds": {"commercial_claims": "not applicable to smoke"},
            "dataset": {
                "version": scenario.dataset_version,
                "split": scenario.split,
                "scenario_ids": [scenario.scenario_id],
                "checksum": sha256_file(self.config.dataset_path),
            },
            "strategies": [
                item.strategy_id for item in (self.strategies or required_baselines(self.reasoner))
            ],
            "trials": [
                {"seed": seed, "order": order, "turn_length": self.config.turn_length}
                for seed, order in schedule
            ],
            "models": [
                {
                    "provider": self.reasoner.provider,
                    "model": self.reasoner.model,
                    "version": self.reasoner.version,
                }
            ],
            "prompts": {"policy": "scenario prompts verbatim", "version": scenario.version},
            "evaluators": [
                "deterministic-ground-truth/1.0.0",
                "rule-rubric/1.0.0",
                "human-review-required/1.0.0",
            ],
            "analysis": {"version": "smoke-summary/1.0.0"},
            "code": {
                "git_commit": environment["git_commit"],
                "git_dirty": environment["git_dirty"],
                "dependency_lock_sha256": environment["dependency_lock_sha256"],
            },
            "environment": "environment.json",
            "timeouts": {"turn_seconds": self.config.timeout_seconds},
            "retry_policy": {"max_retries": self.config.max_retries},
            "warmup": {"performed": False, "reason": "offline deterministic provider"},
            "exclusion_rules": [],
            "stopping_rules": {"turns": self.config.turn_length, "seeds": list(self.config.seeds)},
            "execution_metadata": {
                "smoke": self.config.smoke,
                "publishable": False if self.config.smoke else None,
            },
        }
