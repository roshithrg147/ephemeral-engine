import asyncio
import json
from pathlib import Path

from src.evidence.certification import certify_run
from src.evidence.runner import EvidenceRunner, RunConfig
from src.evidence.statistics import analyze_run


async def main():
    dataset = Path("evaluation/datasets/development/smoke-software-engineering-v1.json")
    output_dir = Path("evaluation-results/live-cert")

    # Clean output dir if exists
    if output_dir.exists():
        import shutil

        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Starting Live Development Certification Run...")
    config = RunConfig(
        dataset_path=dataset,
        output_root=output_dir,
        turn_length=20,
        seeds=(11,),
        tuning_mode=True,
        smoke=True,
    )

    runner = EvidenceRunner(config)

    # Run the evaluation campaign
    run_dir = runner.run()
    print(f"Campaign completed successfully. Outputs written to: {run_dir}")

    # Analyze results
    analysis = analyze_run(run_dir)
    print("Analysis results:")
    print(json.dumps(analysis, indent=2))

    # Certify run
    certification = certify_run(run_dir)
    print("Certification results:")
    print(json.dumps(certification, indent=2))

    # Save certification results to evaluation-results/certification.json
    cert_path = Path("evaluation-results/live_certification_report.json")
    cert_path.write_text(json.dumps(certification, indent=2), encoding="utf-8")
    print(f"Certification report saved to {cert_path}")


if __name__ == "__main__":
    asyncio.run(main())
