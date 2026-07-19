from __future__ import annotations

import argparse
from pathlib import Path

from src.config import settings

from .runner import EvidenceRunner, RunConfig


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the governed SC-EVM evidence engine.")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=Path("evaluation-results"))
    parser.add_argument("--turn-length", type=int, default=20, choices=[20, 50, 100, 250, 500])
    parser.add_argument("--seed", type=int, action="append", dest="seeds")
    parser.add_argument("--tuning", action="store_true")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--smoke", action="store_true")
    mode.add_argument("--live", action="store_true")
    parser.add_argument("--base-url", default=settings.SC_EVM_BASE_URL)
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument("--max-retries", type=int, default=3)
    args = parser.parse_args()
    config = RunConfig(
        dataset_path=args.dataset,
        output_root=args.output_root,
        turn_length=args.turn_length,
        seeds=tuple(args.seeds or [11]),
        tuning_mode=args.tuning,
        timeout_seconds=args.timeout,
        max_retries=args.max_retries,
        smoke=args.smoke,
    )
    if args.live:
        from .live import NvidiaReasoner, required_live_baselines

        reasoner = NvidiaReasoner(timeout=args.timeout, max_retries=args.max_retries)
        runner = EvidenceRunner(
            config,
            reasoner=reasoner,
            strategies=required_live_baselines(reasoner, base_url=args.base_url),
        )
    else:
        runner = EvidenceRunner(config)
    print(runner.run())


if __name__ == "__main__":
    main()
