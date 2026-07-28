"""Unit tests for user error message sanitization."""

from __future__ import annotations

import unittest

from src.exceptions.base import EngineError
from src.reliability.failure_policy import FailurePolicy


class TestErrorSanitization(unittest.TestCase):
    def test_engine_error_does_not_leak_stack_trace(self) -> None:
        try:
            raise ValueError("Secret database password db_pass=12345 in /src/db/session.py:84")
        except ValueError as exc:
            err = EngineError(
                "Internal diagnostic details",
                safe_message="A processing error occurred.",
                internal_details={"raw_exception": str(exc)},
            )
            safe_dict = err.to_safe_dict()
            self.assertNotIn("db_pass", json_str := str(safe_dict))
            self.assertNotIn("/src/db/session.py", json_str)
            self.assertEqual(safe_dict["message"], "A processing error occurred.")

    def test_failure_policy_sanitizes_generic_exceptions(self) -> None:
        exc = RuntimeError("Fatal crash in /home/rg/Codebase/src/main.py:500")
        classified = FailurePolicy.classify_exception(exc)
        self.assertEqual(classified["code"], "ERR_INTERNAL_SAFETY")
        self.assertNotIn("/home/rg/Codebase", classified["message"])


if __name__ == "__main__":
    unittest.main()
