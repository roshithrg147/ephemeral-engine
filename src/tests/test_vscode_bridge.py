"""Tests for the VS Code terminal bridge contract and lifecycle."""

from __future__ import annotations

import asyncio
from io import StringIO

import httpx

from src.vscode_bridge import (
    BridgeConfig,
    SSEDecoder,
    VSCodeBridge,
    build_parser,
    completion_script,
    decode_data,
)


def test_sse_decoder_supports_multiline_data_and_resets_event() -> None:
    decoder = SSEDecoder()

    assert decoder.feed_line("event: response_content") == []
    assert decoder.feed_line('data: {"content":') == []
    assert decoder.feed_line('data: "first"}') == []
    events = decoder.feed_line("")

    assert len(events) == 1
    assert events[0].event == "response_content"
    assert events[0].data == '{"content":\n"first"}'
    assert decode_data(events[0].data) == {"content": "first"}


def test_cli_exposes_help_version_noninteractive_and_completions() -> None:
    parser = build_parser()
    args = parser.parse_args(["--prompt", "hello", "--no-graphify"])

    assert args.prompt == ["hello"]
    assert args.no_graphify is True
    assert "--session-id" in parser.format_help()
    assert "scevm-vscode" in completion_script("bash")


def test_bridge_streams_actual_contract_and_verifies_burn() -> None:
    requests: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path))
        if request.url.path in {"/health", "/"}:
            return httpx.Response(200, json={"status": "online"})
        if request.url.path == "/api/session/initialize":
            return httpx.Response(200, json={"status": "success"})
        if request.url.path == "/api/agent/query":
            body = (
                'event: query_reformulation\ndata: {"search_vector_query":"bridge test"}\n\n'
                'event: response_content\ndata: "Bridge response"\n\n'
                'event: token_usage\ndata: {"m1":7,"m2":11}\n\n'
                "event: done\ndata: [DONE]\n\n"
            )
            return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})
        if request.method == "DELETE":
            return httpx.Response(200, json={"status": "success"})
        if request.url.path.startswith("/api/session/history/"):
            return httpx.Response(404, json={"detail": "Session not found"})
        return httpx.Response(500)

    async def run() -> tuple[str, str, bool]:
        stdout = StringIO()
        stderr = StringIO()
        bridge = VSCodeBridge(
            BridgeConfig(
                base_url="http://test",
                session_id="vscode_test",
                timeout_seconds=5,
                bearer_token=None,
                diagnostic_mode=False,
                graphify_enabled=True,
                show_events=True,
            ),
            stdout=stdout,
            stderr=stderr,
            transport=httpx.MockTransport(handler),
        )
        try:
            await bridge.verify_gateway()
            await bridge.initialize_session()
            assert await bridge.query("hello") == "Bridge response"
            burned = await bridge.burn_session()
            return stdout.getvalue(), stderr.getvalue(), burned
        finally:
            await bridge.close()

    stdout, stderr, burned = asyncio.run(run())

    assert stdout == "Bridge response\n"
    assert "Intent: bridge test" in stderr
    assert "Usage: M1=7 M2=11" in stderr
    assert burned is True
    assert ("DELETE", "/api/session/burn/vscode_test") in requests
