import asyncio
import json
import os
import sys
import time
from typing import Any

# Add parent directory to sys.path so we can import src.sc_evm
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from google.genai import types
from rich.console import Console

from src.sc_evm import (
    buffer_lock,
    conversation_history_verbatim,
    get_genai_client,
    index_in_background,
    purge_memory,
    rewrite_query_async,
    search_memory_async,
    stream_grounded_response,
)

# Create a quiet dummy console that writes to devnull to suppress direct terminal printouts
dummy_console = Console(file=open(os.devnull, "w") if hasattr(os, "devnull") else None)


def count_tokens(text: str) -> int:
    """Offline token estimation (approx. 4 characters per token)."""
    return max(1, len(text) // 4)


async def test_sc_evm_turn(prompt: str) -> dict[str, Any]:
    """Executes a turn using the SC-EVM pipeline and returns performance metrics."""
    start_time = time.perf_counter()

    # 1. Intent realignment
    intent_payload = await rewrite_query_async(prompt)

    # 2. Vector search memory retrieval
    retrieved_context = await search_memory_async(intent_payload["search_vector_query"])

    # 3. Grounded Stream Reasoner
    response_text = await stream_grounded_response(
        user_input=intent_payload["grounded_llm_prompt"],
        retrieved_context=retrieved_context,
        console=dummy_console,
    )

    # 4. Save to verbatim history sliding window
    with buffer_lock:
        conversation_history_verbatim.append({"role": "user", "content": prompt})
        conversation_history_verbatim.append({"role": "assistant", "content": response_text})
        while len(conversation_history_verbatim) > 6:
            conversation_history_verbatim.pop(0)

    # 5. Background indexing (index turn in ChromaDB)
    index_chunk = f"User: {prompt}\nAssistant: {response_text}"
    index_in_background(index_chunk)

    total_latency = time.perf_counter() - start_time

    # Calculate exact input context tokens sent to model
    context_str = "\n\n".join(retrieved_context)
    history_str = "".join(
        f"{t['role']}: {t['content']}\n" for t in conversation_history_verbatim[-6:]
    )
    full_input = f"--- RETRIEVED CONTEXT ---\n{context_str}\n\n--- CONVERSATION HISTORY ---\n{history_str}\n\n--- CURRENT USER PROMPT ---\n{intent_payload['grounded_llm_prompt']}\n"

    return {
        "total_latency": total_latency,
        "output_tokens": count_tokens(response_text),
        "input_context_tokens": count_tokens(full_input),
        "response_sample": response_text[:120],
        "search_vector_query": intent_payload["search_vector_query"],
        "grounded_llm_prompt": intent_payload["grounded_llm_prompt"],
    }


async def test_baseline_llm_turn(prompt: str, history: list[dict[str, str]]) -> dict[str, Any]:
    """Executes a standard linear rolling history call to simulate raw LLM behavior."""
    history.append({"role": "user", "content": prompt})

    # Build linear history payload
    formatted_contents = []
    for turn in history:
        formatted_contents.append(
            types.Content(
                role="user" if turn["role"] == "user" else "model",
                parts=[types.Part.from_text(text=turn["content"])],
            )
        )

    input_tokens = sum(count_tokens(msg["content"]) for msg in history)

    client = get_genai_client()
    start_time = time.perf_counter()

    # Direct Gemini 2.5 Pro generation without vector indexing/ RAG
    response = await client.aio.models.generate_content(
        model="publishers/google/models/gemini-2.5-pro",
        contents=formatted_contents,
        config=types.GenerateContentConfig(temperature=0.7),
    )

    total_latency = time.perf_counter() - start_time
    output_text = response.text.strip()
    history.append({"role": "assistant", "content": output_text})

    return {
        "total_latency": total_latency,
        "output_tokens": count_tokens(output_text),
        "input_context_tokens": input_tokens,
        "response_sample": output_text[:120],
    }


async def main():
    print("🚀 Initializing Offline End-to-End Performance Benchmark Suite...")

    # Parse the 100-turn adversarial benchmark questionnaire
    prompts_file = os.path.join(os.path.dirname(__file__), "gemini-code-1780778542696.txt")
    raw_prompts = []
    with open(prompts_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(". ", 1)
            if len(parts) > 1 and parts[0].isdigit():
                raw_prompts.append(parts[1])
            else:
                raw_prompts.append(line)

    # Select a balanced sequence of 20 turns representing all 4 phases:
    # Phase 1: 0, 2, 4, 9, 24
    # Phase 2: 25, 27, 29, 34, 49
    # Phase 3: 50, 53, 56, 59, 74
    # Phase 4: 75, 76, 77, 79, 99
    selected_indices = [
        0,
        2,
        4,
        9,
        24,  # Phase 1: Ledger Configuration
        25,
        27,
        29,
        34,
        49,  # Phase 2: Kubernetes Deployment
        50,
        53,
        56,
        59,
        74,  # Phase 3: Smart Fridge & Coffee Noise
        75,
        76,
        77,
        79,
        99,  # Phase 4: Hybrid Synthesis & Compaction
    ]

    prompts = [raw_prompts[i] for i in selected_indices]

    print(f"Loaded {len(prompts)} selected test turns from {prompts_file}.")
    print("Wiping memory prior to benchmark...")
    purge_memory()

    sc_evm_stats = []
    baseline_stats = []
    rolling_raw_history = []

    # Sequential execution loop
    for idx, prompt in enumerate(prompts, 1):
        print(f"\n🔄 Turn {idx}/{len(prompts)} | Input Prompt: '{prompt[:45]}...'")

        # 1. Run SC-EVM Engine
        try:
            print("  [SC-EVM] Running pipeline...")
            engine_metrics = await test_sc_evm_turn(prompt)
            sc_evm_stats.append(engine_metrics)
            print(
                f"  [SC-EVM] Completed in {engine_metrics['total_latency']:.2f}s | Context: {engine_metrics['input_context_tokens']} tokens."
            )
        except Exception as e:
            print(f"  ❌ [SC-EVM] Turn failed: {str(e)}", file=sys.stderr)

        # 2. Run Baseline Raw LLM
        try:
            print("  [Baseline] Running pipeline...")
            baseline_metrics = await test_baseline_llm_turn(prompt, rolling_raw_history)
            baseline_stats.append(baseline_metrics)
            print(
                f"  [Baseline] Completed in {baseline_metrics['total_latency']:.2f}s | Context: {baseline_metrics['input_context_tokens']} tokens."
            )
        except Exception as e:
            print(f"  ❌ [Baseline] Turn failed: {str(e)}", file=sys.stderr)

        # Sleep momentarily to let background worker index and Vertex AI cool down
        await asyncio.sleep(2.0)

    # Export telemetry logs to benchmark_analysis_report.json
    report_data = {
        "session_meta": {"total_turns": len(sc_evm_stats)},
        "sc_evm_telemetry": sc_evm_stats,
        "baseline_telemetry": baseline_stats,
    }

    report_path = os.path.join(os.path.dirname(__file__), "benchmark_analysis_report.json")
    with open(report_path, "w") as rf:
        json.dump(report_data, rf, indent=4)

    print(f"\n💾 Telemetry analysis logs saved to: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
