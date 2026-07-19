import argparse
import asyncio
import json
from pathlib import Path

from src.benchmarks.runner import (
    BenchmarkRunner,
    discover_strategy_instances,
    load_default_prompts,
    select_strategies,
)
from src.config import settings

DEFAULT_BASE_URL = settings.SC_EVM_SINGLE_MODEL_BASE_URL
DEFAULT_REPORT_DIR = Path("benchmarks/single_model")


async def run_benchmark(base_url: str, report_dir: Path) -> dict:
    prompts = load_default_prompts()
    strategies = select_strategies(
        discover_strategy_instances(base_url=base_url),
        ["single_model"],
    )
    runner = BenchmarkRunner(
        strategies,
        base_url=base_url,
        prompts=prompts,
        report_dir=report_dir,
    )
    return await runner.run()


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the single-model benchmark against a local SC-EVM server."
    )
    parser.add_argument(
        "--base-url", default=DEFAULT_BASE_URL, help="Base URL for the running SC-EVM API."
    )
    parser.add_argument(
        "--report-dir",
        default=str(DEFAULT_REPORT_DIR),
        help="Directory to write benchmark JSON files.",
    )
    args = parser.parse_args()

    result = await run_benchmark(args.base_url, Path(args.report_dir))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
