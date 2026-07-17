import argparse
import asyncio
import importlib
import inspect
import json
import logging
import pkgutil
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from src.benchmarks.token_utils import estimate_tokens
from src.strategies.base import StrategyAdapter

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_REPORT_DIR = Path("benchmarks")
DEFAULT_SUITE_PATH = Path(__file__).resolve().with_name("benchmark_suite.json")
logger = logging.getLogger("SC-EVM.BenchmarkRunner")


def load_default_prompts() -> list[str]:
    if DEFAULT_SUITE_PATH.exists():
        payload = json.loads(DEFAULT_SUITE_PATH.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return [str(item) for item in payload][:50]
        questions = payload.get("questions", [])
        prompts: list[str] = []
        for item in questions:
            if isinstance(item, str):
                prompts.append(item)
            elif isinstance(item, dict):
                prompt = item.get("prompt")
                if prompt:
                    prompts.append(str(prompt))
        if prompts:
            return prompts[:50]

    raise FileNotFoundError(f"benchmark prompt suite not found or invalid: {DEFAULT_SUITE_PATH}")


def discover_strategy_instances(base_url: str = DEFAULT_BASE_URL) -> list[StrategyAdapter]:
    import src.strategies as strategies_pkg

    for module_info in pkgutil.iter_modules(strategies_pkg.__path__):
        importlib.import_module(f"{strategies_pkg.__name__}.{module_info.name}")

    instances: list[StrategyAdapter] = []
    for cls in StrategyAdapter.__subclasses__():
        if inspect.isabstract(cls):
            continue
        try:
            try:
                instances.append(cls(base_url=base_url))
            except TypeError:
                instances.append(cls())
        except TypeError:
            continue
    return instances


@dataclass
class TurnRecord:
    turn: int
    prompt: str
    tokens_in: int
    tokens_out: int
    total_latency: float
    success: bool
    running_success_rate: float
    response_excerpt: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyReport:
    strategy: str
    session_id: str
    started_at: str
    finished_at: str
    total_turns: int
    success_rate: float
    turns: list[TurnRecord]


class BenchmarkRunner:
    def __init__(
        self,
        strategies: Sequence[StrategyAdapter],
        *,
        base_url: str = DEFAULT_BASE_URL,
        prompts: Sequence[str] | None = None,
        report_dir: Path = DEFAULT_REPORT_DIR,
    ):
        self.strategies = list(strategies)
        self.base_url = base_url.rstrip("/")
        self.prompts = list(prompts) if prompts is not None else load_default_prompts()
        self.report_dir = report_dir

    async def _burn_session(self, client: httpx.AsyncClient, session_id: str) -> None:
        try:
            await client.delete(f"{self.base_url}/api/session/burn/{session_id}", timeout=30.0)
        except Exception:
            logger.error(
                "Failed to burn benchmark session", extra={"session_id": session_id}, exc_info=True
            )

    async def _initialize_session(self, client: httpx.AsyncClient, session_id: str) -> None:
        response = await client.post(
            f"{self.base_url}/api/session/initialize",
            json={"session_id": session_id},
            timeout=30.0,
        )
        response.raise_for_status()

    async def run_strategy(self, strategy: StrategyAdapter, *, session_id: str) -> StrategyReport:
        started_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        completed_turns: list[TurnRecord] = []
        success_count = 0

        use_remote_session = getattr(strategy, "use_remote_session", True)
        client: httpx.AsyncClient | None = None
        try:
            if use_remote_session:
                client = httpx.AsyncClient()
                await self._initialize_session(client, session_id)

            for idx, prompt in enumerate(self.prompts, start=1):
                try:
                    turn_result = await strategy.solve(prompt, session_id)
                except Exception as exc:
                    logger.error(
                        "Strategy turn failed",
                        extra={"strategy": strategy.name, "session_id": session_id, "turn": idx},
                        exc_info=True,
                    )
                    turn_result = {
                        "strategy": strategy.name,
                        "session_id": session_id,
                        "prompt": prompt,
                        "response_text": "",
                        "tokens_in": estimate_tokens(prompt),
                        "tokens_out": 0,
                        "total_latency": 0.0,
                        "success": False,
                        "error": str(exc),
                    }

                success = bool(
                    turn_result.get("success", bool(turn_result.get("response_text", "").strip()))
                )
                success_count += int(success)
                running_success_rate = success_count / idx
                response_text = str(turn_result.get("response_text", ""))
                completed_turns.append(
                    TurnRecord(
                        turn=idx,
                        prompt=prompt,
                        tokens_in=int(turn_result.get("tokens_in", estimate_tokens(prompt))),
                        tokens_out=int(
                            turn_result.get("tokens_out", estimate_tokens(response_text))
                        ),
                        total_latency=float(turn_result.get("total_latency", 0.0)),
                        success=success,
                        running_success_rate=running_success_rate,
                        response_excerpt=response_text[:180],
                        raw=turn_result,
                    )
                )
        finally:
            if client is not None:
                await self._burn_session(client, session_id)
                await client.aclose()
            clear_session = getattr(strategy, "clear_session", None)
            if callable(clear_session):
                await clear_session(session_id)

        finished_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        overall_success_rate = success_count / max(1, len(completed_turns))
        return StrategyReport(
            strategy=strategy.name,
            session_id=session_id,
            started_at=started_at,
            finished_at=finished_at,
            total_turns=len(completed_turns),
            success_rate=overall_success_rate,
            turns=completed_turns,
        )

    async def run(self) -> dict[str, Any]:
        self.report_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        reports = []

        for strategy in self.strategies:
            session_id = f"benchmark-{strategy.name}-{timestamp}"
            try:
                report = await self.run_strategy(strategy, session_id=session_id)
                reports.append(
                    {
                        "strategy": report.strategy,
                        "session_id": report.session_id,
                        "started_at": report.started_at,
                        "finished_at": report.finished_at,
                        "total_turns": report.total_turns,
                        "success_rate": report.success_rate,
                        "turns": [
                            {
                                "turn": turn.turn,
                                "prompt": turn.prompt,
                                "tokens_in": turn.tokens_in,
                                "tokens_out": turn.tokens_out,
                                "total_latency": turn.total_latency,
                                "success": turn.success,
                                "running_success_rate": turn.running_success_rate,
                                "response_excerpt": turn.response_excerpt,
                            }
                            for turn in report.turns
                        ],
                    }
                )
            finally:
                aclose = getattr(strategy, "aclose", None)
                if callable(aclose):
                    await aclose()

        payload = {
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "base_url": self.base_url,
            "total_strategies": len(reports),
            "turns_per_strategy": len(self.prompts),
            "strategies": reports,
        }

        report_path = self.report_dir / f"results_{timestamp}.json"
        report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        payload["report_path"] = str(report_path)

        analysis_path = self.report_dir / "analysis_report.json"
        analysis_path.write_text(
            json.dumps(build_analysis_report(payload), indent=2),
            encoding="utf-8",
        )
        payload["analysis_path"] = str(analysis_path)
        return payload


def build_analysis_report(payload: dict[str, Any]) -> dict[str, Any]:
    analysis = {
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "report_path": payload.get("report_path"),
        "base_url": payload.get("base_url"),
        "turns_per_strategy": payload.get("turns_per_strategy"),
        "strategies": [],
    }

    for strategy in payload.get("strategies", []):
        turns = strategy.get("turns", [])
        latencies = [float(turn.get("total_latency", 0.0)) for turn in turns]
        latencies_sorted = sorted(latencies)
        p95_index = (
            max(0, min(len(latencies_sorted) - 1, int(round(len(latencies_sorted) * 0.95)) - 1))
            if latencies_sorted
            else 0
        )
        analysis["strategies"].append(
            {
                "strategy": strategy.get("strategy"),
                "session_id": strategy.get("session_id"),
                "turns": len(turns),
                "success_rate": strategy.get("success_rate", 0.0),
                "avg_latency": sum(latencies) / len(latencies) if latencies else 0.0,
                "p95_latency": latencies_sorted[p95_index] if latencies_sorted else 0.0,
                "min_latency": min(latencies) if latencies else 0.0,
                "max_latency": max(latencies) if latencies else 0.0,
                "tokens_in": sum(int(turn.get("tokens_in", 0)) for turn in turns),
                "tokens_out": sum(int(turn.get("tokens_out", 0)) for turn in turns),
                "failed_turns": [turn.get("turn") for turn in turns if not turn.get("success")],
            }
        )

    return analysis


def select_strategies(
    strategies: Sequence[StrategyAdapter],
    strategy_names: Sequence[str] | None,
) -> list[StrategyAdapter]:
    if not strategy_names:
        return list(strategies)
    allowed = {name.strip() for name in strategy_names if name.strip()}
    return [strategy for strategy in strategies if strategy.name in allowed]


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run SC-EVM benchmark suite against local or live strategies."
    )
    parser.add_argument(
        "--base-url", default=DEFAULT_BASE_URL, help="Base URL for the live FastAPI backend."
    )
    parser.add_argument(
        "--report-dir",
        default=str(DEFAULT_REPORT_DIR),
        help="Directory to write benchmark JSON reports.",
    )
    parser.add_argument(
        "--strategy",
        action="append",
        dest="strategies",
        help="Strategy name to run. Repeat to run multiple. Defaults to all discovered strategies.",
    )
    args = parser.parse_args()

    discovered = discover_strategy_instances(base_url=args.base_url)
    strategies = select_strategies(discovered, args.strategies)
    if not strategies:
        raise SystemExit("No strategies selected for benchmarking.")

    runner = BenchmarkRunner(
        strategies,
        base_url=args.base_url,
        report_dir=Path(args.report_dir),
    )
    result = await runner.run()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
