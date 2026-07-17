import argparse
import asyncio
import json
from pathlib import Path

from src.benchmarks.runner import BenchmarkRunner, load_default_prompts
from src.strategies.antigravity_cli_adapter import AntiGravityCLIAdapter

DEFAULT_REPORT_DIR = Path("benchmarks/single_model")
DEFAULT_COMMAND = "antigravity"


async def run_benchmark(
    *,
    command: str,
    report_dir: Path,
    prompt_arg: str | None,
    use_stdin: bool,
    timeout_seconds: float,
    limit: int,
) -> dict:
    prompts = load_default_prompts()[:limit]
    strategy = AntiGravityCLIAdapter(
        command=command,
        prompt_arg=prompt_arg,
        use_stdin=use_stdin,
        timeout_seconds=timeout_seconds,
    )
    runner = BenchmarkRunner(
        [strategy],
        prompts=prompts,
        report_dir=report_dir,
    )
    return await runner.run()


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the benchmark suite against a local AntiGravity CLI."
    )
    parser.add_argument(
        "--command",
        default=DEFAULT_COMMAND,
        help="CLI command to execute. Defaults to 'antigravity'.",
    )
    parser.add_argument(
        "--prompt-arg",
        default=None,
        help="Optional flag name used to pass the prompt as an argument.",
    )
    parser.add_argument(
        "--no-stdin", action="store_true", help="Disable sending the prompt on stdin."
    )
    parser.add_argument(
        "--timeout-seconds", type=float, default=1800.0, help="Per-turn timeout in seconds."
    )
    parser.add_argument(
        "--limit", type=int, default=50, help="Maximum number of benchmark prompts to run."
    )
    parser.add_argument(
        "--report-dir", default=str(DEFAULT_REPORT_DIR), help="Directory for benchmark JSON output."
    )
    args = parser.parse_args()

    result = await run_benchmark(
        command=args.command,
        report_dir=Path(args.report_dir),
        prompt_arg=args.prompt_arg,
        use_stdin=not args.no_stdin,
        timeout_seconds=args.timeout_seconds,
        limit=args.limit,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
