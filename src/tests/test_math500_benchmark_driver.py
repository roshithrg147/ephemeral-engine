"""Unit tests for the MATH500-style live benchmark parser helpers."""

from math500_benchmark_driver import extract_boxed_answer, parse_sse_data


def test_parse_sse_data_preserves_usage_and_response() -> None:
    raw_stream = "\n".join(
        [
            "event: response_content",
            r'data: "The answer is \\\\boxed{1007}."',
            "",
            "event: usage_report",
            'data: [{"measurement_type": "exact", "input_tokens": 42}]',
            "",
            "event: done",
            "data: [DONE]",
            "",
        ]
    )

    parsed = parse_sse_data(raw_stream)

    assert parsed["response_content"] == r"The answer is \\boxed{1007}."
    assert parsed["usage_report"][0]["input_tokens"] == 42
    assert parsed["done"] == "[DONE]"


def test_extract_boxed_answer_normalizes_integer() -> None:
    assert extract_boxed_answer(r"Therefore \boxed{1,007}.") == "1007"


def test_extract_boxed_answer_normalizes_fraction() -> None:
    assert extract_boxed_answer(r"Thus \boxed{\frac{9}{64}}.") == "9/64"


def test_extract_boxed_answer_returns_last_box() -> None:
    assert extract_boxed_answer(r"\boxed{1} then \boxed{2}") == "2"


def test_extract_boxed_answer_returns_none_without_box() -> None:
    assert extract_boxed_answer("No final answer was supplied.") is None
