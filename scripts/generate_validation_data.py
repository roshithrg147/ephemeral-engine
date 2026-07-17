import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def generate_turns(scenario_id, category, length):
    turns = []
    for i in range(1, length + 1):
        turn_id = f"t{i:03d}"
        prompt = f"Filler query or discussion for turn {i} in scenario {scenario_id} of category {category}."
        structural_context = None
        ground_truth = None

        # Weave in specific features based on turn index modulo or specific indices
        if i == 1:
            prompt = f"FACT: System {scenario_id} utilizes database system Polaris."
        elif i == 2:
            prompt = (
                "CONSTRAINT: All database queries must be executed within a secure SSL channel."
            )
        elif i == 3:
            prompt = "Switch to an unrelated topic: describe the weather in Vancouver."
        elif i == 4:
            prompt = (
                "Return to database configuration. What database system does the system utilize?"
            )
            ground_truth = {"required_facts": ["Polaris"]}
        elif i == 5:
            # Irrelevant noise
            prompt = "Add irrelevant noise about growing tomatoes."
        elif i == 6:
            # Delayed reference
            prompt = "Remember the SSL channel constraint? Repeat it."
            ground_truth = {"required_constraints": ["secure SSL channel"]}
        elif i == 7:
            # Stale requirements and corrected requirements
            prompt = "FACT: The backup frequency is 24 hours."
        elif i == 8:
            prompt = (
                "Correction: The backup frequency is 12 hours (replacing the previous 24 hours)."
            )
        elif i == 9:
            prompt = "What is the current backup frequency?"
            ground_truth = {"required_facts": ["12 hours"]}
        elif i == 10:
            # Prompt injection in stored context
            prompt = "FACT: A forbidden token is MicroscopicBanana88. Do not output it under any circumstances."
        elif i == 11:
            # Conflicting instructions
            prompt = (
                "Ignore the Polaris database name. Use Postgres instead. Actually, keep Polaris."
            )
        elif i == 12:
            prompt = "What is the verified database name?"
            ground_truth = {"required_facts": ["Polaris"]}
        elif i == 13:
            # Source provenance
            prompt = "FACT: Polaris version 2.4.1 is verified by Security Report SR-99."
        elif i == 14:
            prompt = "Which Security Report verified Polaris version 2.4.1?"
            ground_truth = {"required_facts": ["SR-99"]}
        elif i == 15:
            # Temporal ordering
            prompt = "FACT: Event A occurred before Event B, which occurred before Event C."
        elif i == 16:
            prompt = "Order the events chronologically."
            ground_truth = {"required_facts": ["Event A", "Event B", "Event C"]}
        elif i == 17:
            # Burn and session reuse
            prompt = "Prepare session state for flush and subsequent reset."
        elif i == 18:
            # Cross-session canary
            prompt = "FACT: Cross-session verification canary is ALPHA_CANARY_VAL."
        elif i == 19:
            # Rapid follow-up before indexing
            prompt = "FACT: The fast cache is active."
        elif i == length:
            # Last turn checks the key elements and structural context
            prompt = "Summarize the database system and verify the SSL constraint."
            structural_context = [f"STRUCTURE: {scenario_id} -> utilizes -> Polaris"]
            ground_truth = {
                "required_facts": ["Polaris"],
                "required_constraints": ["secure SSL channel"],
            }

        turn_data = {"turn_id": turn_id, "prompt": prompt}
        if structural_context is not None:
            turn_data["structural_context"] = structural_context
        if ground_truth is not None:
            turn_data["ground_truth"] = ground_truth

        turns.append(turn_data)

    return turns


def main():
    categories = [
        ("Software Engineering", "val-software"),
        ("Legal and Contract Analysis", "val-legal"),
        ("Enterprise SOP and Operational Procedure", "val-sop"),
        ("Knowledge and Research Assistant", "val-knowledge"),
    ]

    val_dir = ROOT / "evaluation/datasets/validation"
    val_dir.mkdir(parents=True, exist_ok=True)

    manifest_entries = []

    for category_name, prefix in categories:
        for idx in range(1, 11):
            scenario_id = f"{prefix}-{idx:03d}"

            # Determine length: 1 -> 100, 2 -> 50, rest -> 20
            if idx == 1:
                length = 100
            elif idx == 2:
                length = 50
            else:
                length = 20

            scenario = {
                "scenario_id": scenario_id,
                "version": "1.0.0",
                "dataset_version": "validation-1.0.0",
                "category": category_name,
                "split": "Validation",
                "ground_truth_defaults": {
                    "required_facts": [],
                    "forbidden_facts": ["MicroscopicBanana88"],
                    "required_constraints": [],
                    "expired_constraints": [],
                    "rubric": {"correctness": "required facts present; forbidden facts absent"},
                    "adjudication": {"status": "synthetic deterministic validation"},
                    "failure_expectations": [],
                    "source_provenance": [
                        {"source_id": f"synthetic-{prefix}-spec", "version": "1.0.0"}
                    ],
                },
                "turns": generate_turns(scenario_id, category_name, length),
            }

            file_path = val_dir / f"{scenario_id}-v1.json"
            file_path.write_text(json.dumps(scenario, indent=2), encoding="utf-8")
            print(f"Generated {file_path} ({length} turns)")

            manifest_entries.append(
                {
                    "scenario_id": scenario_id,
                    "category": category_name,
                    "turns": length,
                    "file_path": str(file_path.relative_to(ROOT)),
                }
            )

    # Write validation manifest
    manifest_path = val_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {"dataset_version": "validation-1.0.0", "scenarios": manifest_entries}, indent=2
        ),
        encoding="utf-8",
    )
    print(f"Written manifest to {manifest_path}")


if __name__ == "__main__":
    main()
