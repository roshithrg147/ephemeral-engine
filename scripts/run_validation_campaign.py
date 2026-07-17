import asyncio
import json
import shutil
from pathlib import Path

from src.evidence.certification import certify_run
from src.evidence.runner import EvidenceRunner, RunConfig
from src.evidence.statistics import analyze_run


async def main():
    scenarios = [
        # (filename, turn_length)
        ("val-software-001-v1.json", 100),
        ("val-software-002-v1.json", 50),
        ("val-software-003-v1.json", 20),
        ("val-legal-001-v1.json", 100),
        ("val-legal-002-v1.json", 50),
        ("val-legal-003-v1.json", 20),
        ("val-sop-001-v1.json", 100),
        ("val-sop-002-v1.json", 50),
        ("val-sop-003-v1.json", 20),
        ("val-knowledge-001-v1.json", 100),
        ("val-knowledge-002-v1.json", 50),
        ("val-knowledge-003-v1.json", 20),
    ]

    root_dir = Path(__file__).resolve().parents[1]
    datasets_dir = root_dir / "evaluation/datasets/validation"
    output_root = root_dir / "evaluation-results/validation-run"

    # 1. Clean previous validation run outputs
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    combined_dir = output_root / "combined"
    (combined_dir / "raw").mkdir(parents=True, exist_ok=True)
    (combined_dir / "evaluations").mkdir(parents=True, exist_ok=True)
    (combined_dir / "traces").mkdir(parents=True, exist_ok=True)

    print("Executing Day 8 Validation Campaign across 12 scenarios...")

    for filename, length in scenarios:
        dataset_path = datasets_dir / filename
        scenario_id = filename.rsplit("-v1", 1)[0]
        print(f"Running scenario: {scenario_id} with {length} turns...")

        config = RunConfig(
            dataset_path=dataset_path,
            output_root=output_root / scenario_id,
            turn_length=length,
            seeds=(11, 42, 101),
            tuning_mode=True,
            smoke=True,
        )

        runner = EvidenceRunner(config)
        run_dir = runner.run()

        # Copy to combined directory
        for f in (run_dir / "raw").glob("*.json"):
            shutil.copy2(f, combined_dir / "raw")
        for f in (run_dir / "evaluations").glob("*.json"):
            shutil.copy2(f, combined_dir / "evaluations")
        for f in (run_dir / "traces").glob("*.json"):
            shutil.copy2(f, combined_dir / "traces")

    print("Combining validation outcomes and running statistical analysis...")

    # Run analysis on combined outputs
    stats = analyze_run(combined_dir)
    stats_path = combined_dir / "statistics.json"
    stats_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")

    certification = certify_run(combined_dir)
    cert_path = combined_dir / "certification.json"
    cert_path.write_text(json.dumps(certification, indent=2), encoding="utf-8")

    print(f"Validation Campaign stats written to: {stats_path}")
    print(f"Validation Campaign certification written to: {cert_path}")


if __name__ == "__main__":
    asyncio.run(main())
