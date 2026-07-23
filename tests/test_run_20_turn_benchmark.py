from scripts.run_20_turn_benchmark import (
    QUESTIONS,
    build_summary,
    evaluate_accuracy,
    percentile,
)


def test_question_set_contains_twenty_unique_independent_cases() -> None:
    assert len(QUESTIONS) == 20
    assert len({item["id"] for item in QUESTIONS}) == 20
    assert len({item["prompt"] for item in QUESTIONS}) == 20


def test_accuracy_accepts_expected_alternative_case_insensitively() -> None:
    assert evaluate_accuracy("Use GIT SWITCH -C FEATURE-X.", ["git switch -c feature-x"])[0]
    assert not evaluate_accuracy("I do not know.", ["443"])[0]


def test_percentile_interpolates_ordered_values() -> None:
    assert percentile([1.0, 2.0, 3.0, 4.0], 0.5) == 2.5
    assert percentile([], 0.95) is None


def test_summary_counts_completed_accuracy_and_degradation() -> None:
    turns = [
        {
            "status": "completed",
            "accuracy": {"passed": True},
            "degradation": None,
            "timing": {"total_seconds": 2.0, "time_to_first_response_seconds": 1.0},
            "usage_report": [],
            "burn": {"http_status": 200},
        },
        {
            "status": "completed",
            "accuracy": {"passed": False},
            "degradation": {"degraded": True},
            "timing": {"total_seconds": 4.0, "time_to_first_response_seconds": 2.0},
            "usage_report": [],
            "burn": {"http_status": 500},
        },
    ]

    summary = build_summary(turns, 6.0)

    assert summary["questions_completed"] == 2
    assert summary["accuracy_rate"] == 0.5
    assert summary["degraded_turns"] == 1
    assert summary["session_burns_succeeded"] == 1
    assert summary["session_burns_failed"] == 1
