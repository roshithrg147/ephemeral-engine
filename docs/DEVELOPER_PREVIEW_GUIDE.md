# SC-EVM Developer Preview Guide

Welcome to the **SC-EVM Developer Preview Release**. SC-EVM is a production-grade, statistically adaptive, hybrid retrieval, and context-planned AI engine.

---

## 1. Quick Start with OpenAI SDK

SC-EVM exposes a 100% OpenAI-compatible endpoint at `/v1/chat/completions`. You can drop SC-EVM into any codebase using standard OpenAI SDKs:

```python
import openai

client = openai.OpenAI(
    base_url="http://127.0.0.1:8000/v1",
    api_key="development-token-demo"
)

response = client.chat.completions.create(
    model="sc-evm-proxy",
    messages=[
        {"role": "system", "content": "You are a helpful coding assistant."},
        {"role": "user", "content": "Where is the function get_user_profile defined?"}
    ],
    stream=True
)

for chunk in response:
    if chunk.choices and chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
```

---

## 2. Core Capabilities

1. **Statistically Adaptive Calibration:** No hardcoded similarity thresholds. Admission cutoffs calibrate dynamically via rolling distributions (`mean`, `stddev`, `MAD`, `percentiles`).
2. **Hybrid Semantic + Lexical + Structural Search:** Fuses ChromaDB vectors, BM25 text index, and AST symbol graphs using Reciprocal Rank Fusion (RRF).
3. **Intent Routing:** Only structural requests (`Code lookup`, `Architecture`, `Dependency analysis`, `Refactoring`) trigger AST graph traversal.
4. **Context Control Plane:** Manages token allocation dynamically with `ContextPlanner`, `ContextBudgetManager`, and `ContextOptimizer` under 10 ms overhead.
5. **Local Resilience & Circuit Breaker:** Local embedding fallback (`LocalEmbeddingEngine`) ensures cloud outages never interrupt user sessions.
