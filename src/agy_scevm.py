"""Anti-Gravity-style command wrapper for the SC-EVM HTTP/SSE gateway."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    import httpx

VERSION = "0.1.0"
DEFAULT_BASE_URL = os.environ.get("SC_EVM_BASE_URL", "http://127.0.0.1:8000")
CORE_MODEL = os.environ.get("MODEL_2_CORE", "openai/gpt-oss-120b")


@dataclass(slots=True)
class QueryResult:
    """Normalized result from one SC-EVM SSE query."""

    response_text: str = ""
    errors: list[str] = field(default_factory=list)
    degradation_reasons: list[str] = field(default_factory=list)
    usage_report: list[dict[str, Any]] = field(default_factory=list)

    @property
    def core_model_used(self) -> bool:
        """Return whether exact usage proves that configured Model 2 synthesized."""
        return not self.degradation_reasons and any(
            record.get("measurement_type") == "exact"
            and record.get("status") == "completed"
            and record.get("stage") == "model_2_synthesis"
            and record.get("model") == CORE_MODEL
            for record in self.usage_report
        )


def decode_sse_data(raw_data: str) -> Any:
    """Decode a Server-Sent Events data field."""
    if raw_data == "[DONE]":
        return raw_data
    try:
        return json.loads(raw_data)
    except json.JSONDecodeError:
        return raw_data


class SCEVMGatewayClient:
    """Small async client for the SC-EVM lifecycle and query endpoints."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def initialize(self, session_id: str) -> None:
        """Initialize an isolated SC-EVM session."""
        response = await self.client.post(
            "/api/session/initialize", json={"session_id": session_id}
        )
        response.raise_for_status()

    async def query(self, session_id: str, prompt: str) -> QueryResult:
        """Send one prompt and normalize the gateway's SSE response."""
        result = QueryResult()
        current_event = "message"
        async with self.client.stream(
            "POST",
            "/api/agent/query",
            json={"session_id": session_id, "prompt": prompt},
            headers={"Accept": "text/event-stream"},
        ) as response:
            response.raise_for_status()
            async for raw_line in response.aiter_lines():
                line = raw_line.strip()
                if not line:
                    continue
                if line.startswith("event:"):
                    current_event = line[6:].strip()
                    continue
                if not line.startswith("data:"):
                    continue

                value = decode_sse_data(line[5:].strip())
                if current_event == "response_content":
                    result.response_text += str(value)
                elif current_event == "error":
                    result.errors.append(str(value))
                elif current_event == "degradation" and isinstance(value, dict):
                    reasons = value.get("reasons") or []
                    result.degradation_reasons.extend(str(reason) for reason in reasons)
                elif current_event == "usage_report" and isinstance(value, list):
                    result.usage_report = [item for item in value if isinstance(item, dict)]

        if result.errors:
            raise RuntimeError("; ".join(result.errors))
        if not result.response_text.strip():
            raise RuntimeError("SC-EVM returned no response content")
        return result

    async def burn(self, session_id: str) -> None:
        """Purge an SC-EVM session."""
        response = await self.client.delete(f"/api/session/burn/{session_id}")
        response.raise_for_status()


class GatewayProtocol(Protocol):
    """Lifecycle/query contract used by the command runner."""

    async def initialize(self, session_id: str) -> None: ...

    async def query(self, session_id: str, prompt: str) -> QueryResult: ...

    async def burn(self, session_id: str) -> None: ...


async def execute_prompt(
    gateway: GatewayProtocol,
    *,
    session_id: str,
    prompt: str,
    strict_core: bool,
    keep_session: bool,
) -> QueryResult:
    """Execute one prompt with lifecycle cleanup."""
    await gateway.initialize(session_id)
    try:
        result = await gateway.query(session_id, prompt)
        if strict_core and not result.core_model_used:
            raise RuntimeError(f"Configured core model {CORE_MODEL!r} did not return exact usage")
        return result
    finally:
        if not keep_session:
            await gateway.burn(session_id)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        prog="agy-scevm",
        description="Send Anti-Gravity-style prompts through the SC-EVM gateway.",
    )
    parser.add_argument("-p", "--print", "--prompt", dest="prompt")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="SC-EVM gateway URL.",
    )
    parser.add_argument("--session-id", help="Reuse an explicit SC-EVM session ID.")
    parser.add_argument("--timeout", type=float, default=180.0, help="Request timeout in seconds.")
    parser.add_argument(
        "--strict-core",
        action="store_true",
        help="Fail unless exact usage proves that configured Model 2 ran.",
    )
    parser.add_argument(
        "--keep-session", action="store_true", help="Do not burn the session after exit."
    )
    parser.add_argument(
        "--completion", choices=("bash", "zsh", "fish"), help="Print a shell completion snippet."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser


def completion_script(shell: str) -> str:
    """Return a minimal shell completion definition."""
    flags = "-p --print --prompt --base-url --session-id --timeout --strict-core --keep-session"
    if shell == "bash":
        return f"complete -W '{flags}' agy-scevm"
    if shell == "zsh":
        return f"compdef '_arguments {flags}' agy-scevm"
    return "\n".join(
        f"complete -c agy-scevm -l {flag[2:]}" for flag in flags.split() if flag.startswith("--")
    )


async def run(args: argparse.Namespace) -> int:
    """Run print, piped-input, or interactive mode."""
    if args.completion:
        print(completion_script(args.completion))
        return 0

    import httpx

    session_id = args.session_id or f"agy-scevm-{uuid.uuid4().hex}"
    timeout = httpx.Timeout(args.timeout)
    async with httpx.AsyncClient(base_url=args.base_url.rstrip("/"), timeout=timeout) as client:
        gateway = SCEVMGatewayClient(client)

        if args.prompt is not None:
            result = await execute_prompt(
                gateway,
                session_id=session_id,
                prompt=args.prompt,
                strict_core=args.strict_core,
                keep_session=args.keep_session,
            )
            print(result.response_text)
            return 0

        if not sys.stdin.isatty():
            prompt = sys.stdin.read().strip()
            if not prompt:
                raise ValueError("stdin did not contain a prompt")
            result = await execute_prompt(
                gateway,
                session_id=session_id,
                prompt=prompt,
                strict_core=args.strict_core,
                keep_session=args.keep_session,
            )
            print(result.response_text)
            return 0

        await gateway.initialize(session_id)
        try:
            while True:
                prompt = (await asyncio.to_thread(input, "you> ")).strip()
                if prompt.lower() in {"exit", "quit", "/quit"}:
                    return 0
                if not prompt:
                    continue
                result = await gateway.query(session_id, prompt)
                if args.strict_core and not result.core_model_used:
                    raise RuntimeError(
                        f"Configured core model {CORE_MODEL!r} did not return exact usage"
                    )
                print(result.response_text)
        finally:
            if not args.keep_session:
                await gateway.burn(session_id)


def main() -> None:
    """CLI entry point with stable exit codes and interrupt handling."""
    args = build_parser().parse_args()
    import httpx

    try:
        raise SystemExit(asyncio.run(run(args)))
    except KeyboardInterrupt:
        print("agy-scevm: interrupted", file=sys.stderr)
        raise SystemExit(130) from None
    except (httpx.HTTPError, RuntimeError, ValueError) as exc:
        print(f"agy-scevm: {exc}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
