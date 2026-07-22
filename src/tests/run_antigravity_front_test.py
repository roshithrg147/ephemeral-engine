"""Run a compatibility probe with SC-EVM Model 1 in front of Anti-Gravity CLI."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Any

from src.config import settings
from src.sc_evm import SCEVMEngine
from src.strategies.antigravity_cli_adapter import AntiGravityCLIAdapter

DEFAULT_PROMPT = "Explain in two sentences why an API gateway should enforce request timeouts."
DEFAULT_OUTPUT = Path("antigravity_front_test_log.json")
SESSION_ID = "sc_evm_antigravity_front_test"


async def run_probe(prompt: str) -> dict[str, Any]:
    """Reformulate one user turn with Model 1, then invoke Anti-Gravity."""
    started = time.perf_counter()
    engine = SCEVMEngine()
    reformulation_started = time.perf_counter()
    search_query, grounded_prompt, reformulation_usage = await engine.run_query_reformulation_async(
        prompt, []
    )
    reformulation_latency = time.perf_counter() - reformulation_started

    if reformulation_usage is None:
        raise RuntimeError("Model 1 reformulation failed; Anti-Gravity was not invoked")

    downstream_prompt = (
        "Do not use tools or modify files. Respond only to this grounded user request:\n\n"
        f"{grounded_prompt}"
    )
    adapter = AntiGravityCLIAdapter(
        command="agy --sandbox",
        prompt_arg="-p",
        use_stdin=False,
        timeout_seconds=45.0,
    )
    downstream = await adapter.solve(downstream_prompt, SESSION_ID)
    if not downstream["success"]:
        raise RuntimeError(
            "Anti-Gravity invocation failed "
            f"with exit code {downstream['exit_code']}: {downstream['stderr'].strip()}"
        )

    return {
        "session_id": SESSION_ID,
        "model_1": settings.MODEL_1_FLASH,
        "model_2": "Anti-Gravity CLI (configured Gemini model)",
        "user_prompt": prompt,
        "search_vector_query": search_query,
        "grounded_llm_prompt": grounded_prompt,
        "model_1_usage": reformulation_usage,
        "model_1_latency_seconds": round(reformulation_latency, 3),
        "antigravity_response": downstream["response_text"],
        "antigravity_estimated_usage": {
            "input_tokens": downstream["tokens_in"],
            "output_tokens": downstream["tokens_out"],
            "total_tokens": downstream["total_tokens"],
        },
        "antigravity_latency_seconds": round(downstream["total_latency"], 3),
        "total_latency_seconds": round(time.perf_counter() - started, 3),
        "success": True,
    }


async def main() -> None:
    """Parse arguments, execute the probe, and write the JSON evidence file."""
    parser = argparse.ArgumentParser(
        description="Test SC-EVM Model 1 as a front-end interpreter for Anti-Gravity CLI."
    )
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    result = await run_probe(args.prompt)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
