import asyncio
import json
import os
import time

import httpx

# Adversarial 50-question suite
TEST_QUESTIONS = [
    "How do I initialize the database schema for a 30k user e-commerce store?",
    "What are the structural dependencies of the PaymentGateway service?",
    "Explain the Kafka backpressure strategy I defined earlier.",
    "Refactor the LedgerService to use a circular buffer instead of a list.",
    "What nodes are directly connected to the UserAuth module?",
    "I'm feeling hungry, how do I boil water in a vacuum chamber?",  # Tangent/Poisoning
    "Revert the previous change to the LedgerService, it broke the Auth node.",  # Dependency Check
    "What is the current phase of the architecture lifecycle?",
    "Add a new field 'discount_code' to the Product schema.",
    "What files will be impacted if I delete the CartService?",  # Graph Search Test
    # ... [Questions 11-40: Repeat similar structural/semantic patterns]
    "How does the Kafka pool scale?",
    "Optimize the query latency for the database-first foundation.",
    "Purge the current session.",  # Memory management test
    "Why is the LedgerService structural map failing to validate?",
    "Generate the final API documentation for the current session.",
]


async def run_test(client: httpx.AsyncClient, session_id: str, prompt: str):
    start_time = time.perf_counter()
    response = await client.post(
        "/api/agent/query",
        json={"session_id": session_id, "prompt": prompt},
    )
    duration = time.perf_counter() - start_time
    return {
        "prompt": prompt,
        "duration": duration,
        "status": response.status_code,
        "response_bytes": len(response.content),
    }


async def main():
    session_id = "stress_test_session_01"
    results = []
    base_url = os.getenv("SC_EVM_BASE_URL", "http://127.0.0.1:8000")

    print(f"Starting 50-turn stress test for session {session_id}...")

    async with httpx.AsyncClient(base_url=base_url, timeout=120.0) as client:
        for i, question in enumerate(TEST_QUESTIONS * 4):
            if i >= 50:
                break
            result = await run_test(client, session_id, question)
            results.append(result)
            print(f"Turn {i + 1}: {result['duration']:.2f}s")
            await asyncio.sleep(0.5)

    report_path = os.getenv("SC_EVM_STRESS_REPORT", "/tmp/sc_evm_validation_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)
    print(f"Test complete. Report saved to {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
