"""VS Code terminal bridge for the local SC-EVM FastAPI gateway."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from typing import Any, TextIO

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_SESSION_ID = "vscode_local_session_01"
SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


class BridgeError(RuntimeError):
    """A safe, user-facing bridge failure."""


@dataclass(frozen=True, slots=True)
class SSEEvent:
    """One decoded Server-Sent Event."""

    event: str
    data: str


class SSEDecoder:
    """Incrementally decode SSE fields, including multiline data payloads."""

    def __init__(self) -> None:
        self._event = "message"
        self._data_lines: list[str] = []

    def feed_line(self, line: str) -> list[SSEEvent]:
        if line == "":
            return self._dispatch()
        if line.startswith(":"):
            return []

        field, separator, value = line.partition(":")
        if separator and value.startswith(" "):
            value = value[1:]
        if field == "event":
            self._event = value or "message"
        elif field == "data":
            self._data_lines.append(value)
        return []

    def finish(self) -> list[SSEEvent]:
        return self._dispatch()

    def _dispatch(self) -> list[SSEEvent]:
        if not self._data_lines:
            self._event = "message"
            return []
        event = SSEEvent(self._event, "\n".join(self._data_lines))
        self._event = "message"
        self._data_lines = []
        return [event]


def decode_data(raw_data: str) -> Any:
    """Decode JSON SSE data while preserving plain-text markers."""

    if raw_data == "[DONE]":
        return raw_data
    try:
        return json.loads(raw_data)
    except json.JSONDecodeError:
        return raw_data


@dataclass(frozen=True, slots=True)
class BridgeConfig:
    base_url: str
    session_id: str
    timeout_seconds: float
    bearer_token: str | None
    diagnostic_mode: bool
    graphify_enabled: bool
    show_events: bool

    @property
    def headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        return headers


class VSCodeBridge:
    """Own one SC-EVM session and expose it through a terminal workflow."""

    def __init__(
        self,
        config: BridgeConfig,
        *,
        stdout: TextIO = sys.stdout,
        stderr: TextIO = sys.stderr,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.config = config
        self.stdout = stdout
        self.stderr = stderr
        timeout = httpx.Timeout(config.timeout_seconds, connect=5.0)
        self.client = httpx.AsyncClient(
            base_url=config.base_url,
            timeout=timeout,
            headers=config.headers,
            transport=transport,
        )
        self.initialized = False
        self._response_line_open = False

    def _status(self, message: str) -> None:
        if self.config.show_events:
            print(f"[SC-EVM] {message}", file=self.stderr, flush=True)

    async def verify_gateway(self) -> str:
        checks: list[str] = []
        for path in ("/health", "/"):
            try:
                response = await self.client.get(path)
            except httpx.RequestError as exc:
                checks.append(f"{path}: {type(exc).__name__}")
                continue
            checks.append(f"{path}: HTTP {response.status_code}")
            if response.status_code == 200:
                self._status(f"Gateway ready via {path}")
                return path
        raise BridgeError(f"Gateway unavailable at {self.config.base_url} ({', '.join(checks)})")

    async def initialize_session(self) -> None:
        response = await self.client.post(
            "/api/session/initialize",
            json={"session_id": self.config.session_id},
        )
        self._raise_for_status(response, "Session initialization failed")
        self.initialized = True
        self._status(f"Session initialized: {self.config.session_id}")

    async def burn_session(self) -> bool:
        if not self.initialized:
            return True
        try:
            response = await self.client.delete(f"/api/session/burn/{self.config.session_id}")
            if response.status_code not in {200, 404}:
                self._raise_for_status(response, "Session burn failed")
            history = await self.client.get(f"/api/session/history/{self.config.session_id}")
            verified = history.status_code == 404
            if verified:
                self._status(f"Burn verified: {self.config.session_id}")
            else:
                print(
                    f"[SC-EVM] Burn could not be verified (history HTTP {history.status_code})",
                    file=self.stderr,
                    flush=True,
                )
            return verified
        except httpx.HTTPError as exc:
            print(f"[SC-EVM] Burn failed: {exc}", file=self.stderr, flush=True)
            return False
        finally:
            self.initialized = False

    async def query(self, prompt: str) -> str:
        payload = {
            "session_id": self.config.session_id,
            "prompt": prompt,
            "graphify_enabled": self.config.graphify_enabled,
            "diagnostic_mode": self.config.diagnostic_mode,
        }
        response_parts: list[str] = []
        decoder = SSEDecoder()
        self._response_line_open = False

        try:
            async with asyncio.timeout(self.config.timeout_seconds):
                async with self.client.stream(
                    "POST",
                    "/api/agent/query",
                    json=payload,
                    headers={"Accept": "text/event-stream"},
                ) as response:
                    self._raise_for_status(response, "Query failed")
                    content_type = response.headers.get("content-type", "")
                    if "text/event-stream" not in content_type:
                        raise BridgeError(f"Expected SSE response, received {content_type!r}")
                    async for line in response.aiter_lines():
                        for event in decoder.feed_line(line):
                            if self._render_event(event, response_parts):
                                return "".join(response_parts)
                    for event in decoder.finish():
                        self._render_event(event, response_parts)
        except TimeoutError as exc:
            raise BridgeError(
                f"Query exceeded the {self.config.timeout_seconds:g}-second timeout"
            ) from exc
        except httpx.RequestError as exc:
            raise BridgeError(f"Gateway request failed: {exc}") from exc
        return "".join(response_parts)

    def _render_event(self, event: SSEEvent, response_parts: list[str]) -> bool:
        value = decode_data(event.data)
        if event.event in {"token", "response_content"}:
            content = value.get("content", "") if isinstance(value, dict) else value
            if isinstance(content, str):
                print(content, end="", file=self.stdout, flush=True)
                response_parts.append(content)
                self._response_line_open = bool(content) and not content.endswith("\n")
        elif event.event == "query_reformulation" and isinstance(value, dict):
            self._status(f"Intent: {value.get('search_vector_query', '')}")
        elif event.event == "token_usage" and isinstance(value, dict):
            self._finish_response_line()
            self._status(f"Usage: M1={value.get('m1')} M2={value.get('m2')}")
        elif event.event == "degradation":
            self._finish_response_line()
            self._status(f"Degraded response: {value}")
        elif event.event == "action" and isinstance(value, dict):
            if value.get("type") not in {None, "none"}:
                self._finish_response_line()
                self._status(f"Action proposed (not executed): {value.get('type')}")
        elif event.event == "error":
            self._finish_response_line()
            raise BridgeError(f"Engine stream error: {value}")
        done = event.event == "done" or value == "[DONE]"
        if done:
            self._finish_response_line()
        return done

    def _finish_response_line(self) -> None:
        if self._response_line_open:
            print(file=self.stdout, flush=True)
            self._response_line_open = False

    @staticmethod
    def _raise_for_status(response: httpx.Response, context: str) -> None:
        if response.is_success:
            return
        detail = ""
        try:
            payload = response.json()
            if isinstance(payload, dict) and isinstance(payload.get("detail"), str):
                detail = f": {payload['detail']}"
        except (json.JSONDecodeError, ValueError):
            pass
        raise BridgeError(f"{context} (HTTP {response.status_code}){detail}")

    async def close(self) -> None:
        await self.client.aclose()


def package_version() -> str:
    try:
        return version("ephemeral-engine")
    except PackageNotFoundError:
        return "0.1.0"


def completion_script(shell: str) -> str:
    options = (
        "--base-url --session-id --timeout --token --prompt --diagnostic "
        "--no-graphify --quiet-events --print-completion --help --version"
    )
    if shell == "bash":
        return f"complete -W '{options}' scevm-vscode"
    if shell == "zsh":
        return f"compdef '_arguments *: :({options})' scevm-vscode"
    return "\n".join(f"complete -c scevm-vscode -l {item[2:]}" for item in options.split())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scevm-vscode",
        description="Interactive or one-shot VS Code terminal bridge for SC-EVM.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {package_version()}")
    parser.add_argument(
        "--base-url",
        default=os.getenv("SC_EVM_BASE_URL", DEFAULT_BASE_URL),
        help="SC-EVM gateway URL (default: %(default)s)",
    )
    parser.add_argument(
        "--session-id",
        default=os.getenv("SC_EVM_SESSION_ID", DEFAULT_SESSION_ID),
        help="Ephemeral session identifier (default: %(default)s)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.getenv("SC_EVM_BRIDGE_TIMEOUT", "120")),
        help="Per-query timeout in seconds (default: %(default)s)",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("SC_EVM_BEARER_TOKEN"),
        help="OIDC bearer token; prefer SC_EVM_BEARER_TOKEN",
    )
    parser.add_argument(
        "--prompt",
        action="append",
        help="Run a non-interactive prompt; repeat for multiple turns",
    )
    parser.add_argument("--diagnostic", action="store_true", help="Request diagnostic SSE events")
    parser.add_argument(
        "--no-graphify", action="store_true", help="Disable graph context for this bridge"
    )
    parser.add_argument(
        "--quiet-events", action="store_true", help="Print only assistant response content"
    )
    parser.add_argument(
        "--print-completion",
        choices=("bash", "zsh", "fish"),
        help="Print a shell completion definition and exit",
    )
    return parser


def validate_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if not SESSION_ID_PATTERN.fullmatch(args.session_id):
        parser.error("--session-id must match [A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")
    if not args.base_url.startswith(("http://", "https://")):
        parser.error("--base-url must be an HTTP or HTTPS URL")


async def run_bridge(config: BridgeConfig, prompts: list[str] | None) -> int:
    bridge = VSCodeBridge(config)
    burn_verified = True
    try:
        await bridge.verify_gateway()
        await bridge.initialize_session()
        if prompts:
            for prompt in prompts:
                if not prompt.strip():
                    continue
                await bridge.query(prompt.strip())
        else:
            print(
                "SC-EVM VS Code bridge active. Type exit or quit to finish and burn.",
                file=bridge.stderr,
            )
            while True:
                try:
                    prompt = (await asyncio.to_thread(input, "\nSC-EVM Agent > ")).strip()
                except EOFError:
                    break
                if prompt.lower() in {"exit", "quit"}:
                    break
                if prompt:
                    await bridge.query(prompt)
    finally:
        burn_verified = await bridge.burn_session()
        await bridge.close()
    return 0 if burn_verified else 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.print_completion:
        print(completion_script(args.print_completion))
        return 0
    validate_args(args, parser)
    config = BridgeConfig(
        base_url=args.base_url.rstrip("/"),
        session_id=args.session_id,
        timeout_seconds=args.timeout,
        bearer_token=args.token,
        diagnostic_mode=args.diagnostic,
        graphify_enabled=not args.no_graphify,
        show_events=not args.quiet_events,
    )
    try:
        return asyncio.run(run_bridge(config, args.prompt))
    except KeyboardInterrupt:
        print("\n[SC-EVM] Interrupted; session cleanup requested.", file=sys.stderr)
        return 130
    except BridgeError as exc:
        print(f"[SC-EVM] Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
