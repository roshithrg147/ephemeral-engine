"""Focused unit tests for the manual SSE harness helpers."""

from tests.run_manual_test import decode_sse_data, is_provider_failure


def test_decode_sse_data_parses_json() -> None:
    assert decode_sse_data('{"value": 7}') == {"value": 7}


def test_decode_sse_data_preserves_done_marker() -> None:
    assert decode_sse_data("[DONE]") == "[DONE]"


def test_is_provider_failure_detects_gateway_placeholder() -> None:
    assert is_provider_failure("[Model 2 failed: upstream timeout]")
    assert is_provider_failure("[DEGRADED: model_2_synthesis_failed]")


def test_is_provider_failure_rejects_normal_response() -> None:
    assert not is_provider_failure("CREATE TABLE ledger (...);")
