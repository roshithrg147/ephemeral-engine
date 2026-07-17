from __future__ import annotations

import asyncio
import json
import os
import shlex
import subprocess
import time
from collections.abc import Iterable
from typing import Any

from src.benchmarks.token_utils import estimate_tokens
from src.strategies.base import StrategyAdapter


def _walk_json(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _walk_json(nested)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_json(item)


class AntiGravityCLIAdapter(StrategyAdapter):
    """Benchmark adapter for a locally installed AntiGravity CLI."""

    use_remote_session = False

    def __init__(
        self,
        command: str | None = None,
        *,
        prompt_arg: str | None = None,
        use_stdin: bool = True,
        timeout_seconds: float = 1800.0,
    ):
        super().__init__(name="antigravity_cli")
        self.command = command or os.environ.get("ANTIGRAVITY_COMMAND", "antigravity")
        self.prompt_arg = prompt_arg or os.environ.get("ANTIGRAVITY_PROMPT_ARG")
        self.use_stdin = use_stdin
        self.timeout_seconds = timeout_seconds

    def _build_args(self, prompt: str) -> list[str]:
        args = shlex.split(self.command)
        if self.prompt_arg:
            args.extend([self.prompt_arg, prompt])
        return args

    def _extract_json_payload(self, stdout: str, stderr: str) -> dict[str, Any] | None:
        for blob in (stdout, stderr):
            text = blob.strip()
            if not text:
                continue
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        return None

    def _extract_response_text(self, stdout: str, stderr: str) -> str:
        payload = self._extract_json_payload(stdout, stderr)
        if payload:
            for candidate in (
                payload.get("response_text"),
                payload.get("text"),
                payload.get("content"),
                payload.get("output"),
                payload.get("message"),
            ):
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()

            for node in _walk_json(payload):
                message = node.get("message")
                if isinstance(message, dict):
                    for field in ("content", "text", "output"):
                        value = message.get(field)
                        if isinstance(value, str) and value.strip():
                            return value.strip()
                for field in ("content", "text", "output", "assistant"):
                    value = node.get(field)
                    if isinstance(value, str) and value.strip():
                        return value.strip()

        combined = stdout.strip()
        if combined:
            return combined
        return stderr.strip()

    def _extract_usage_counts(self, stdout: str, stderr: str, response_text: str) -> dict[str, int]:
        payload = self._extract_json_payload(stdout, stderr)
        if payload:
            for node in _walk_json(payload):
                usage = node.get("usage")
                if isinstance(usage, dict):
                    prompt_tokens = usage.get("prompt_tokens") or usage.get("input_tokens")
                    completion_tokens = usage.get("completion_tokens") or usage.get("output_tokens")
                    total_tokens = usage.get("total_tokens")
                    if any(
                        value is not None
                        for value in (prompt_tokens, completion_tokens, total_tokens)
                    ):
                        prompt_val = int(prompt_tokens or 0)
                        completion_val = int(completion_tokens or 0)
                        total_val = int(total_tokens or (prompt_val + completion_val) or 0)
                        return {
                            "tokens_in": prompt_val
                            or estimate_tokens(stdout or stderr or response_text),
                            "tokens_out": completion_val or estimate_tokens(response_text),
                            "total_tokens": total_val or (prompt_val + completion_val),
                        }

                for key in ("prompt_tokens", "input_tokens", "tokens_in"):
                    if node.get(key) is not None:
                        prompt_val = int(node.get(key) or 0)
                        completion_val = int(
                            node.get("completion_tokens")
                            or node.get("output_tokens")
                            or node.get("tokens_out")
                            or 0
                        )
                        total_val = int(
                            node.get("total_tokens") or (prompt_val + completion_val) or 0
                        )
                        return {
                            "tokens_in": prompt_val
                            or estimate_tokens(stdout or stderr or response_text),
                            "tokens_out": completion_val or estimate_tokens(response_text),
                            "total_tokens": total_val or (prompt_val + completion_val),
                        }

        return {
            "tokens_in": estimate_tokens(stdout or stderr or response_text),
            "tokens_out": estimate_tokens(response_text),
            "total_tokens": estimate_tokens(stdout or stderr or response_text)
            + estimate_tokens(response_text),
        }

    def _run_process(
        self, args: list[str], prompt: str, session_id: str
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["ANTIGRAVITY_BENCHMARK_SESSION_ID"] = session_id
        env["ANTIGRAVITY_BENCHMARK_PROMPT"] = prompt
        input_data = prompt if self.use_stdin and not self.prompt_arg else None
        return subprocess.run(
            args,
            input=input_data,
            text=True,
            capture_output=True,
            timeout=self.timeout_seconds,
            env=env,
            check=False,
        )

    async def solve(self, prompt: str, session_id: str) -> dict[str, Any]:
        start = time.perf_counter()
        args = self._build_args(prompt)
        process = await asyncio.to_thread(self._run_process, args, prompt, session_id)
        elapsed = time.perf_counter() - start

        stdout = process.stdout or ""
        stderr = process.stderr or ""
        response_text = self._extract_response_text(stdout, stderr)
        usage = self._extract_usage_counts(stdout, stderr, response_text)
        success = process.returncode == 0 and bool(response_text.strip())

        return {
            "strategy": self.name,
            "session_id": session_id,
            "prompt": prompt,
            "response_text": response_text,
            "tokens_in": usage["tokens_in"],
            "tokens_out": usage["tokens_out"],
            "total_tokens": usage["total_tokens"],
            "total_latency": elapsed,
            "success": success,
            "exit_code": process.returncode,
            "command": args,
            "stdout": stdout,
            "stderr": stderr,
        }

    async def clear_session(self, session_id: str) -> None:
        return None
