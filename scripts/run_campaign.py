import asyncio
import json
import shutil
from pathlib import Path

from src.evidence.runner import EvidenceRunner, RunConfig
from src.evidence.security import SecurityBenchmarkExecutor


async def main():
    dataset_path = Path("evaluation/datasets/development/smoke-software-engineering-v1.json")
    output_root = Path("evaluation-results/campaign-run")

    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    print("Executing Controlled Scientific Validation Campaign...")

    # 1. Run the main evaluation campaign across the 3 seeds
    config = RunConfig(
        dataset_path=dataset_path,
        output_root=output_root,
        turn_length=20,
        seeds=(11, 42, 101),
        tuning_mode=True,
        smoke=True,
    )

    runner = EvidenceRunner(config)
    run_dir = runner.run()
    print(f"Main campaign executed successfully. Output directory: {run_dir}")

    # 2. Run the Security validation benchmark executor
    print("Executing Security Validation Benchmark...")
    security_executor = SecurityBenchmarkExecutor("http://127.0.0.1:8000")
    security_results = security_executor.run()

    security_output_path = output_root / "security_validation_report.json"
    security_output_path.write_text(
        json.dumps(security_results, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Security validation report written to {security_output_path}")

    # Save the output directory location in a temporary config
    info_path = Path("evaluation-results/campaign_info.json")
    info_path.write_text(
        json.dumps({"run_dir": str(run_dir), "security_results": security_results}, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    asyncio.run(main())
