# SC-EVM (State-Cached Ephemeral Vector Memory)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Manager: uv](https://img.shields.io/badge/managed%20by-uv-purple.svg)](https://github.com/astral-sh/uv)

SC-EVM is a session-isolated context-control middleware for multi-turn AI applications. It optimizes context retention, limits prompt growth, and provides logical session boundaries.

---

## 1. Frequently Asked Questions (FAQ)

### What is SC-EVM?
SC-EVM stands for **State-Cached Ephemeral Vector Memory**. It is a developer-preview middleware that sits between your application and large language models (LLMs) to manage conversation history, context retrieval, and memory isolation.

### What problem does it solve?
In long-running multi-turn conversations, standard chat histories grow linearly, leading to:
1. Unbounded token usage and high costs.
2. Context window saturation.
3. Context blindness (where relevant earlier facts are lost or ignored).

SC-EVM solves this by replacing linear append-only history with a bounded active-history window and dynamic vector-based retrieval.

### What can it do today?
- **Logical Session Isolation:** Isolates conversation history and vector embeddings per session.
- **Dynamic Outlier Gating:** Admits or rejects previous memories based on cosine distance thresholds.
- **Async Query Reformulation:** Translates conversational prompts into search queries and grounded instructions.
- **Logical State Deletion (Burn):** Purges volatile memory and session-scoped vector collections via the `/burn` command or API.
- **NVIDIA NIM Support:** Integrates with the NVIDIA NIM API for LLM completions.

### What can it not do?
- **No Shared Multi-Replica Sessions:** Authenticated ownership is enforced in production mode, but active sessions remain process-local.
- **No Physical Memory Sanitization:** Session burn purges logical collections and registry mappings but does not sanitize the physical server RAM.
- **No Provider Independence:** The LLM transport is currently implemented only for the NVIDIA NIM completions API.

### How do I run it locally?
1. Copy `.env.example` to `.env` and fill in `NVIDIA_API_KEY`.
2. Start the REST API backend:
   ```bash
   uv run uvicorn src.main:app --host 127.0.0.1 --port 8000
   ```
3. Run the interactive CLI assistant:
   ```bash
   uv run assistant
   ```

### How is production authentication configured?

Production mode uses OIDC bearer JWTs. Configure `DEPLOYMENT_MODE=production`,
`AUTH_MODE=oidc`, issuer, audience, JWKS URL, and explicit HTTPS CORS origins. Startup fails when
required identity settings are absent or unsafe. Session IDs identify state but never authorize it;
each active session is bound to verified `tenant_id` and `sub` claims.

Development defaults keep authentication disabled for existing localhost workflows. Do not expose
development mode to untrusted networks.

### How do I test it?
Run the pytest test suite:
```bash
uv run pytest
```

### What is Graphify?
Graphify is an experimental capability that injects structured relationship definitions (e.g. `STRUCTURE: A -> depends_on -> B`) into the LLM context. Offline validation-preview results showed no correctness difference; no live quality conclusion is certified.

### What evidence exists?
SC-EVM's execution plumbing has been exercised over 12,240 offline deterministic turns across 12 validation-preview scenarios. Those runs used the `offline-smoke` fact extractor and are marked `publishable: false`; they do not establish live answer quality, latency, cost, or provider behavior.

See [Final Statistical Report](evaluation/final/FINAL_STATISTICAL_REPORT.md) together with [Final Limitations](evaluation/final/FINAL_LIMITATIONS.md) and [Claim Certification](evaluation/CLAIM_CERTIFICATION.md).

### What claims are not being made?
We do **NOT** claim that SC-EVM is:
- **Production-ready** or **Enterprise-grade**.
- **Provider-independent** (requires NVIDIA NIM).
- **Leakage-proof** (authentication and logical isolation reduce risk but cannot prove zero leakage).

### How can I provide feedback?
Please see [Feedback and Triage](docs/FEEDBACK_AND_TRIAGE.md) for how to submit bug reports, feature requests, or reproduction results.

---

## 🏗️ Architecture Overview

For a code-derived takeover and clean-room replication reference, see the
[System Architecture and Workflow Specification](docs/SYSTEM_ARCHITECTURE_AND_WORKFLOW_SPECIFICATION.md).

See the [20-Turn, 20-Session Lifecycle](docs/20-TURN-20-SESSION-LIFECYCLE.md) for a
plain-language explanation of how twenty isolated sessions move through twenty turns each.

For planning work through issues, RFCs, pull requests, and the project board, see the
[GitHub Projects Operating Guide](docs/GITHUB_PROJECTS_OPERATING_GUIDE.md).

```
                  ┌──────────────────────────┐
                  │       User Prompt        │
                  └────────────┬─────────────┘
                               │
                               ▼
                  ┌──────────────────────────┐
                  │ Async Intent Realigner   │
                  └────────────┬─────────────┘
                               │
                ┌──────────────┴──────────────┐
                ▼                             ▼
   ┌──────────────────────────┐  ┌──────────────────────────┐
   │    Transient ChromaDB    │  │ Grounded Stream Reasoner │
   │ (Dual-Anchor Protection) │  │  (Secure XML Enclosures) │
   └──────────────────────────┘  └──────────────────────────┘
```

---

## 🛡️ License

SC-EVM is licensed under the MIT License. See [LICENSE](LICENSE) for details.
