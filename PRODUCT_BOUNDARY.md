# SC-EVM Product Boundary and Commercial Definition

> **Governance:** This is the authoritative source for SC-EVM product scope. Changes require formal product review, and every scope change must identify the superseded classification and supporting evidence. It conforms to the [Product Manifesto](MANIFESTO.md) and should be read with the current [Architecture](ARCHITECTURE.md) and [RFC process](rfcs/README.md).

**Status:** Official product boundary baseline

**Effective date:** 2026-07-11

**Scope:** Repository at commit `6e7993d5229ba97371a720864d22a1b89a087909`, including the working-tree implementation, documentation, tests, benchmark artifacts, dashboard, Graphify artifacts, and deployment files.

**Change control:** The classifications in this document are controlled. A change requires formal product and architecture review through a superseding RFC.

## 1. Executive Summary

SC-EVM is context-control middleware for multi-turn AI applications. Its commercial hypothesis is that application teams will buy a bounded, isolated, relevant context plane that lets long-running sessions retain useful continuity without repeatedly sending an ever-growing transcript to the reasoning model. The product's essential chain is session isolation, dual-purpose intent realignment, locally embedded ephemeral retrieval, dual-anchor context gating, protected context assembly, bounded active history, and secure session burn. Dual-model synthesis can strengthen answer quality, but the memory plane—not a particular model pairing, user interface, or clipboard workflow—is the product boundary.

The repository also contains an agent action layer, persistent learned facts, Graphify structural retrieval, a React control plane, terminal and clipboard clients, IDE context tooling, lifecycle hooks, benchmarks, telemetry, and deployment support. These are classified below as core architecture, supporting infrastructure, experimental capabilities, or deprecated paths; their existence does not make all of them part of the MVP or the primary commercial promise.

The evidence base has limits. The dual-model benchmark records 50/50 successful turns, but it measures transport success, estimated tokens, and latency—not answer correctness, context retention, hallucination rate, or Graphify uplift. The current SSE path emits a completed response word by word rather than streaming provider tokens. Consequently, this document distinguishes implemented mechanisms from commercially validated outcomes and does not claim that token cost is constant, that Graphify improves quality, or that dual-model synthesis is superior without controlled comparative evidence.

## 2. Official Product Definition

**SC-EVM is a session-isolated context-control layer that keeps multi-turn AI applications grounded in relevant memory while bounding the conversation history sent to their reasoning models.**

### Elevator Pitch

SC-EVM replaces ever-growing chat transcripts with an isolated, retrieval-driven context plane for each active session. It realigns ambiguous prompts, selects relevant prior interactions through confidence gating, and supplies grounded context to the application's reasoning model while keeping active history bounded. Application teams gain more predictable context usage, safer session separation, and explicit memory destruction without being locked to a particular user interface or model combination.

### Executive Summary

SC-EVM sits between a conversational application and its reasoning models. For every session it maintains an ephemeral vector collection, bounded dialogue state, pending-write interception, integrity metadata, and lifecycle controls; on each turn it reformulates the user's intent for retrieval and reasoning, filters recalled content using dual-anchor rules, encloses recalled data as untrusted context, invokes the reasoning pipeline, and asynchronously indexes the completed interaction. Its defensible technical center is not “chat with two models”; it is the policy-controlled conversion of growing conversation state into a compact, isolated, relevance-filtered context payload.

### What SC-EVM Is NOT

SC-EVM is not a foundation model, a general-purpose vector database, a complete autonomous coding agent, an enterprise knowledge graph, a durable system of record, a clipboard product, an IDE, or a finished analytics platform. It does not currently prove constant total token cost, true provider-token streaming, Graphify-driven accuracy gains, multi-device synchronization, image generation, or production-grade multi-tenant authentication and authorization. The React dashboard, terminal client, clipboard suite, action executor, and deployment files are access, demonstration, or operational surfaces around the context-control product rather than the product definition itself.

## 3. Repository Analysis and Feature Classification Matrix

The “Description and purpose” field explicitly covers both what the feature does and why it exists. Commercial Visibility uses exactly one of: **Primary Value Proposition**, **Differentiating Capability**, or **Internal Implementation Detail**. “External placement” is handled separately in section 8.

| # | Name | Description and purpose | Customer value | Engineering value | Dependencies | Required for MVP | Future expansion value | Commercial Visibility |
|---:|---|---|---|---|---|:---:|:---:|---|
| 1 | Session-isolated ephemeral vector memory | Creates one in-memory Chroma collection per session and stores completed turns for retrieval; prevents cross-session context mixing. | Private, relevant continuity without a shared transcript store. | Establishes the state boundary used by retrieval, burn, TTL, and concurrency. | ChromaDB, ONNXMiniLM embedding, session registry | Yes | High | **Primary Value Proposition** |
| 2 | Bounded active conversation window | Retains the latest six messages for reformulation and reasoning rather than forwarding unlimited history. | More predictable prompt growth over long sessions. | Places an explicit upper bound on direct transcript context. | Session history, prompt manager | Yes | High | **Primary Value Proposition** |
| 3 | Dual-purpose intent realignment | Produces a dense retrieval query and a pronoun-resolved grounded prompt from recent history. | Better continuity for fragmented follow-ups and better retrieval targeting. | Separates retrieval language from answer-generation language. | PromptManager, ModelConnector, Kimi configuration | Yes | High | **Differentiating Capability** |
| 4 | Dual-anchor context gating | Filters retrieved documents using absolute distance limits, top/neighbor deltas, and similarity to accepted anchors. | Reduces irrelevant memory entering the answer context. | Implements a deterministic admission policy above nearest-neighbor search. | Embeddings, vector query results, calibrated threshold | Yes | High | **Differentiating Capability** |
| 5 | Dynamic threshold calibration | Derives a per-session retrieval threshold from positive and negative embedded phrases, with a safe fallback. | Adapts retrieval strictness without customer tuning. | Avoids relying solely on one static threshold. | Local embedding function | No | Medium | **Internal Implementation Detail** |
| 6 | Pending-memory interceptor | Includes not-yet-indexed interaction text from `pending_commit_buffer` in the next reasoning pass. | Prevents rapid follow-ups from losing very recent context. | Bridges asynchronous indexing latency without blocking the turn. | Session metadata, background indexing | Yes | High | **Differentiating Capability** |
| 7 | Protected context enclosure | Wraps retrieved and pending content in explicit XML sections and prompts the reasoner to treat it as reference data. | Lowers the risk that remembered text silently overrides current instructions. | Creates a trust boundary between control prompts and retrieved data. | Prompt templates, retrieval fusion | Yes | High | **Differentiating Capability** |
| 8 | Session burn | Deletes the session collection and in-memory record through an explicit API/CLI lifecycle action. | Provides an understandable “forget this session” control. | Completes the ephemeral-state lifecycle and testable cleanup contract. | Session registry, Chroma client, API/CLI | Yes | High | **Primary Value Proposition** |
| 9 | TTL and capacity eviction | Removes stale sessions and limits active-session count. | Reduces unintended retention and resource exhaustion. | Supplies lifecycle governance for an in-memory multi-session service. | Registry GC task, settings | Yes | High | **Internal Implementation Detail** |
| 10 | Session concurrency isolation | Uses per-session writer-preferring read/write locks and registry-scoped state transitions. | Prevents one busy session from corrupting or leaking another session's state. | Makes concurrent mutation and burn behavior deterministic. | `SessionLock`, registry | Yes | High | **Differentiating Capability** |
| 11 | State manifest integrity | Checksums manifested chat history and refreshes the manifest on mutation. | Supports detection of unexpected in-memory state changes. | Adds an integrity invariant around session history. | `StateManifest`, `ManifestedHistory` | No | Medium | **Internal Implementation Detail** |
| 12 | Asynchronous interaction indexing | Embeds and stores a completed turn after response delivery in a tracked background task. | Keeps memory ingestion from extending perceived response completion. | Decouples serving latency from vector writes and handles burn races. | Session runtime, embedding function, ChromaDB | Yes | High | **Internal Implementation Detail** |
| 13 | Graphify structural context | Queries an external Graphify CLI for code dependency/usage context and fuses it with vector memories. | Potentially improves code-context structure when the graph exists and the query maps to it. | Adds a deterministic structural-retrieval plane beside semantic retrieval. | Graphify CLI and graph artifacts; bridge; context fusion | No | High | **Differentiating Capability** |
| 14 | Dual-model parallel reasoning and synthesis | Calls Kimi and Qwen concurrently, then uses Kimi to produce one structured response, intent, action, and memory list. | May improve response robustness by combining independent outputs. | Separates candidate generation from synthesis and exposes a stable response schema. | NVIDIA NIM, ModelConnector, prompts, thread pool | No | High | **Differentiating Capability** |
| 15 | Single-model reasoning strategy | Performs a complete structured turn with one Qwen call and local bounded history; currently used as an alternate strategy/benchmark path. | Lower-complexity operating option. | Provides a comparator and fallback architectural path. | ModelConnector, PromptManager | Yes | High | **Internal Implementation Detail** |
| 16 | Structured intent/action response contract | Returns typed text, intent, action payload, and facts-to-remember. | Allows host applications to consume answers and proposed actions predictably. | Validates model output at a stable Pydantic boundary with fallback behavior. | Agent models, response parsing | No | High | **Differentiating Capability** |
| 17 | Development phase gate | Blocks file/command actions that occur before configured backend or UI phases. | Reduces premature execution in the included coding-agent workflow. | Applies a deterministic policy after probabilistic action selection. | Session metadata, settings, action contract | No | Medium | **Differentiating Capability** |
| 18 | Persistent learned-fact memory | Stores user profile and learned facts in JSON for the daemon, while the web path keeps facts in session metadata. | Supports personalization across turns or daemon restarts. | Provides a separate durable memory plane with file locking and deduplication. | MemoryManager, JSON file, FileLock | No | High | **Differentiating Capability** |
| 19 | NVIDIA NIM model connector | Centralizes sync/async calls, pooled HTTP transport, retries, timeouts, authentication, and configured model IDs. | Model access reliability and configurable deployment. | Isolates provider transport from memory and orchestration logic. | httpx, NVIDIA credentials, settings | Yes | High | **Internal Implementation Detail** |
| 20 | Prompt management and response parsing | Owns rewrite, context, orchestration, and synthesis templates plus code-fence stripping. | Consistent grounding and response behavior. | Keeps prompt policy out of routes and model transport. | PromptManager, parser | Yes | Medium | **Internal Implementation Detail** |
| 21 | FastAPI session and query API | Exposes initialization, list, message, history, memory, burn, SSE query, and direct dual-model endpoints. | Gives products a network integration surface. | Defines the service contract and lifecycle boundary. | FastAPI, session runtime, engine, orchestrator | Yes | High | **Primary Value Proposition** |
| 22 | SSE event protocol | Emits reformulation, retrieved context, word chunks, action, token estimates, intent, error, and done events. | Enables progressive UI feedback and diagnostic visibility. | Decouples frontends through typed event stages; current “token” events are simulated after completion. | FastAPI StreamingResponse, web/CLI clients | No | Medium | **Differentiating Capability** |
| 23 | React control plane | Provides chat, session selection/burn, memory display, and dashboard visualizations; some metrics are placeholders. | Makes the engine demonstrable and operable without custom integration. | Exercises the service API and SSE contract. | React, API, SSE, Recharts | No | Medium | **Differentiating Capability** |
| 24 | Terminal client | Initializes sessions, consumes SSE, shows history/memory, burns sessions, and prompts before executing proposed actions. | Developer-friendly local access and human approval for actions. | Supplies an end-to-end reference client for API behavior. | Backend API, httpx/rich-style terminal UI | No | Medium | **Differentiating Capability** |
| 25 | Local action and diff tooling | Validates file edit payloads, creates previews, applies edits, and supports proposed command/file/image actions. | Enables controlled coding-assistant workflows around SC-EVM. | Separates edit validation/preview from model output and supports dry runs. | Action contract, CLI, filesystem | No | Medium | **Differentiating Capability** |
| 26 | Clipboard suite and local daemon | Encrypts clipboard history, provides a Tk GUI, exposes a permission-restricted UNIX socket, and receives agent responses. | Local productivity convenience for desktop users. | Demonstrates local IPC and an alternate host surface. | Tkinter, pyperclip, cryptography, UNIX sockets | No | Low | **Internal Implementation Detail** |
| 27 | Clipboard synchronization scaffold | Derives an encryption key and simulates push/pull, but has no configured relay backend. | No complete customer value in current form. | Preserves a researched BYOB/E2EE integration seam. | Cryptography, clipboard service; missing relay | No | Medium | **Internal Implementation Detail** |
| 28 | VS Code workspace context provider | Scans, chunks, embeds, updates, and queries workspace files in a local Chroma index. | Supplies relevant code snippets to IDE-oriented workflows. | Reuses local embeddings for incremental code context. | ChromaDB, filesystem, CLI input | No | High | **Differentiating Capability** |
| 29 | Session rehydration hook | Loads recent history and editor context, retries the backend, and queues failed hydration in SQLite. | Restores working context after tool or backend restarts. | Makes IDE/session handoff resilient to startup ordering. | Backend API, SQLite queue, VS Code caller | No | High | **Differentiating Capability** |
| 30 | Secure lifecycle manager | Calls burn, resets registry state, deletes registered preview files, and verifies cleanup. | Extends explicit deletion to local artifacts. | Coordinates cleanup across service and filesystem boundaries. | Burn API, preview registry, local filesystem | No | High | **Differentiating Capability** |
| 31 | Telemetry and audit sink | Appends interactions and errors as JSON lines at a configured local path. | Supports traceability in local operation. | Provides a minimal cross-module diagnostic sink. | Filesystem, settings | No | Medium | **Internal Implementation Detail** |
| 32 | Strategy benchmark framework | Discovers adapters and records turn success, estimated tokens, and latency for dual-model, single-model, and external CLI strategies. | Enables evidence-based operating-mode comparisons once quality scoring is added externally. | Creates a repeatable execution and artifact schema. | Live models/backend or external CLI, JSON reports | No | High | **Differentiating Capability** |
| 33 | Configuration and error boundaries | Centralizes environment settings and converts unhandled API errors into structured responses/logs. | Safer, more portable operation. | Removes configuration and failure handling from feature logic. | pydantic-settings, FastAPI | Yes | Medium | **Internal Implementation Detail** |
| 34 | Container deployment assets | Defines backend/frontend images and local composition. | Shortens evaluation and deployment setup. | Provides reproducible service packaging. | Docker, Uvicorn, npm | No | Medium | **Internal Implementation Detail** |
| 35 | Image generation stub | Returns a local path without generating an image. | No current customer value. | Marks an incomplete action branch. | Agent action contract | No | Low | **Internal Implementation Detail** |

## 4. Graphify Evaluation

### Decision

**Graphify is classified as a Differentiating Capability, not an Internal Implementation Detail.** It is not part of the MVP and must not yet be marketed as a proven accuracy improvement.

### Evidence

- The integration is a real runtime branch, not merely a generated report: `SCEVMEngine.evaluate_query_context` runs semantic retrieval and the Graphify lookup concurrently, then injects structural results inside a separate `<graphify_context>` enclosure (`src/sc_evm.py`).
- The bridge asks the Graphify CLI for dependencies and usages, giving SC-EVM a structural retrieval mode distinct from fuzzy vector similarity (`src/graphify_bridge.py`).
- The checked-in graph was built from the current commit and reports 591 nodes, 974 edges, 44 communities, 91% extracted relationships, no import cycles, and multiple cross-community hubs (`graphify-out/GRAPH_REPORT.md`). This demonstrates a maintained structural asset and practical future extensibility for code-oriented context.
- The graph's own report labels inferred relationships and knowledge gaps rather than presenting all edges as facts. That provenance is strategically useful for future evidence-aware retrieval.

### Outcome-by-outcome assessment

| Outcome | Current evidence | Judgment |
|---|---|---|
| Retrieval precision | Structural dependency queries can return relationships that vector similarity does not encode, but no relevance-labeled ablation exists. | Plausible, unmeasured |
| Contextual relevance | Structural output is fused into the live prompt, but relevance and downstream use are not scored. | Plausible, unmeasured |
| Structural reasoning | The graph explicitly represents dependencies, usages, hubs, communities, and provenance. | Supported as a capability; downstream answer uplift unmeasured |
| Long-horizon constraint retention | Graphify models repository structure, not conversational constraint retention. | Not supported |
| Hallucination resistance | Extracted relationships could ground answers, but the reasoner is not required to cite or verify them. | Not supported by present tests |
| Token efficiency | Graph output may be targeted, but its prompt size is neither budgeted nor compared with alternatives. | Not supported |
| Future extensibility | A parallel structural-retrieval plane, bridge boundary, cached artifacts, and provenance metadata already exist. | Supported |

Graphify therefore earns differentiator status because structural reasoning and future extensibility are implemented and strategically distinct. Commercial claims about precision, relevance, hallucination resistance, or efficiency remain prohibited until a Graphify-on/off benchmark evaluates identical tasks with relevance and answer-quality scoring.

## 5. Strategic Asset Assessment

“Open source” and “commercial” below are product packaging recommendations for existing assets, not license changes made by this review.

| Strategic asset | Why difficult to replicate | Proprietary? | Open-source edition | Commercial edition | Customer interest | Investor value |
|---|---|---|---|---|---|---|
| SC-EVM context admission policy | Value lies in the combined thresholds, anchor relationships, asynchronous state handling, and accumulated evaluation data—not the cosine formula alone. | Keep policy tuning, calibration data, and evaluation corpus proprietary; base algorithm may remain open. | Reference gating implementation and safe defaults. | Tuned policies, controls, evaluation evidence, and support. | High if tied to measurable relevance and cost outcomes. | High; it is closest to defensible product IP. |
| Session-isolated ephemeral memory lifecycle | Correct isolation spans collection creation, locking, pending state, TTL/capacity eviction, burn, and race handling. | Core implementation can remain open; hardened operational policy can differentiate commercially. | Single-node engine, lifecycle API, burn semantics. | Governance, scale controls, operational assurance, support. | High for privacy- and compliance-sensitive teams. | High if backed by independent isolation and deletion evidence. |
| Dual-purpose intent realignment | Requires a reliable schema, history-window policy, model behavior, fallback semantics, and retrieval/answer alignment. | Keep optimized prompts and evaluation data proprietary if commercialized. | Contract and baseline prompt. | Tuned prompt/model routing and measured task performance. | Medium to high; experienced teams recognize ambiguity failures. | Medium; replicable without a data/evaluation flywheel. |
| Protected context construction | Combines provenance enclosures, pending-state labeling, trust instructions, and deterministic admission. | Security policy and red-team corpus should remain proprietary; baseline pattern can be open. | Basic enclosure and trust boundary. | Hardened policies, auditability, and security validation. | High when framed as safer memory grounding. | Medium to high if validated against prompt injection. |
| Graphify-enhanced structural retrieval | Replication requires a maintained code graph, extraction/provenance quality, runtime query bridge, and evidence that structural context helps. | The generic bridge may be open; product-specific ranking/fusion and evaluation should be proprietary. | Optional bridge and local artifact format. | Validated ranking/fusion, supported graph pipeline, quality analytics. | Medium today; high for code intelligence if uplift is proven. | High upside, currently pre-validation. |
| Multi-model synthesis policy | The API calls are easy to copy; robust model selection, conflict resolution, cost/latency routing, and evaluation data are not. | Keep synthesis/routing policy and comparative data proprietary. | Basic adapter contract and reference strategy. | Supported models, policies, benchmark evidence, operational controls. | Medium; buyers care about outcome/cost, not model count. | Medium unless superior quality is demonstrated. |
| Integrity and secure destruction controls | Requires end-to-end semantics across in-memory state, vector collections, background work, preview files, and verification. | Assurance tooling and validation reports can be commercial; core deletion semantics should be open for trust. | Burn API, manifest checks, local cleanup reference. | Policy, audit evidence, deployment assurance, support. | High in regulated and sensitive deployments. | Medium to high as an enterprise trust wedge. |
| Strategy benchmark and evidence framework | A credible moat emerges from longitudinal workloads, labels, regressions, and comparable operating modes—not the runner alone. | Keep proprietary benchmark corpus, labels, and longitudinal results; open the harness/schema. | Runner, adapters, report format. | Curated workloads, quality judges, dashboards, regression gates. | Indirect but essential to credible purchasing claims. | High as the measurement flywheel behind defensibility. |

## 6. Official MVP Definition

The commercial hypothesis to validate is: **application teams will adopt and pay for a session-isolated, bounded context layer because it preserves useful multi-turn continuity while giving them predictable context growth and explicit deletion controls.**

Only the following features belong in the official MVP:

| MVP feature | Reason for inclusion | Customer impact | Engineering justification |
|---|---|---|---|
| FastAPI session and query contract | A host application needs a stable way to create, query, inspect, and burn a session. | Makes SC-EVM integrable rather than a demonstration script. | It is the narrow service boundary around the product hypothesis. |
| Isolated ephemeral vector memory | This is the state substrate the customer is buying. | Provides relevant continuity without a shared durable transcript store. | Every retrieval and lifecycle guarantee depends on per-session collections. |
| Bounded active history | Predictable prompt growth is central to the stated problem. | Prevents direct conversation payloads from growing without limit. | Establishes the measurable bound independently of retrieval quality. |
| Dual-purpose intent realignment | Follow-up prompts must remain usable after older transcript text leaves the active window. | Resolves references and improves recall targeting. | Connects bounded history to useful retrieval and grounded reasoning. |
| Dual-anchor gated retrieval | Unfiltered nearest-neighbor recall would undermine the relevance claim. | Reduces context creep from semantically adjacent but irrelevant turns. | It is the product-specific admission layer above commodity vector search. |
| Pending-memory interceptor and asynchronous indexing | Rapid successive turns must not observe an indexing gap. | Preserves immediate continuity without forcing users to wait for memory commits. | Maintains correctness while keeping ingestion off the synchronous completion path. |
| Protected context enclosure | Retrieved memory is user-controlled data and needs a visible trust boundary. | Reduces instruction-confusion risk from recalled text. | Makes context fusion safe enough to validate with real applications. |
| Session locking, TTL/capacity eviction, and burn | Isolation and ephemerality are lifecycle properties, not just storage choices. | Provides concurrency safety, bounded retention, and explicit deletion. | Required to test the product under concurrent sessions and termination races. |
| One supported reasoning strategy via the model connector | The context layer must produce an end-to-end answer, but model plurality is not required to test the memory hypothesis. | Gives adopters a working reference path with fewer cost and latency variables. | The implemented single-model adapter is sufficient; provider transport remains abstracted internally. |
| Configuration and structured error boundaries | External evaluation must be repeatable and failures diagnosable. | Reduces setup friction and ambiguous service failures. | Required operational minimum for a networked MVP. |

### MVP success evidence required

The existing repository does not yet validate the commercial hypothesis. MVP validation should use the already implemented benchmark framework and tests to measure: cross-session leakage rate; burn/TTL deletion behavior; answer correctness on long-horizon reference tasks; retrieved-context precision; direct prompt tokens versus turn count; failure rate; and end-to-end latency. This is a validation requirement, not a new product feature.

## 7. Version Placement

These placements classify existing implemented, partial, or scaffolded capabilities. They do not authorize new features.

### Version 2

Version 2 expands the validated memory core into an operable developer product:

- Dual-model parallel reasoning and synthesis.
- Structured intent/action response contract and development phase gate.
- Persistent learned-fact memory as a clearly separate, opt-in durable plane.
- Real SSE stage protocol, including current reformulation/context/action/intent events; the current simulated token emission must not be described as provider streaming.
- React control plane and terminal reference client.
- Local action/diff tooling with human approval.
- VS Code context provider and session rehydration hook.
- Secure lifecycle manager across session and preview artifacts.
- Strategy benchmark framework and stored comparative reports.
- Container deployment assets and local audit sink.

### Version 3

Version 3 contains implemented differentiators whose commercial role depends on Version 2 usage evidence:

- Graphify structural retrieval and graph/vector context fusion.
- Productized use of state-manifest integrity signals.
- Broader supported strategy surface, including the external CLI adapter.
- Dashboard telemetry visualizations once backed by real engine data rather than placeholders.
- Clipboard daemon integration only if validated as a demanded local workflow.

### Future Research

- Clipboard cross-device synchronization scaffold: key derivation exists, but transport is intentionally unimplemented (“BYOB pending”).
- Image generation action: present only as a stub and not a product capability.
- Whether Graphify improves precision, relevance, hallucination resistance, retention, or token efficiency: requires controlled ablation.
- Whether dual-model synthesis improves quality enough to justify its observed latency and token use: requires quality-scored comparison with the implemented single-model strategy.
- Whether persistent user facts should share any commercial boundary with ephemeral session memory: current web and daemon paths use different persistence semantics.

## 8. Architectural Boundary and Commercial Visibility Matrix

Every subsystem receives exactly one permanent architectural classification and exactly one external placement. “Core Product” is directly purchased behavior; “Core Architecture” is essential machinery behind that behavior; “Supporting Infrastructure” enables operation or access; “Experimental” is implemented or scaffolded but not product-validated; “Deprecated” must not guide future positioning. External placement uses exactly one of: Public Homepage, Technical Documentation, Architecture Whitepaper, Developer Documentation, or Internal Only.

| Subsystem | Architectural classification | External placement | External rationale |
|---|---|---|---|
| Session-isolated ephemeral vector memory | **Core Product** | **Public Homepage** | It is the central customer outcome and product boundary. |
| Bounded active conversation window | **Core Product** | **Public Homepage** | It expresses predictable context growth in customer language. |
| Dual-purpose intent realignment | **Core Architecture** | **Architecture Whitepaper** | It is meaningful differentiation, but buyers purchase continuity rather than a rewrite schema. |
| Dual-anchor context gating | **Core Architecture** | **Architecture Whitepaper** | The algorithm explains why retrieval is selective without leading the commercial message. |
| Dynamic threshold calibration | **Core Architecture** | **Internal Only** | Calibration details should be evaluated and tuned, not marketed. |
| Pending-memory interceptor | **Core Architecture** | **Architecture Whitepaper** | It explains correctness under asynchronous ingestion. |
| Protected context enclosure | **Core Architecture** | **Technical Documentation** | Integrators need the trust model; homepage-level security claims require validation. |
| Session burn | **Core Product** | **Public Homepage** | Explicit deletion is directly understandable customer value. |
| TTL and capacity eviction | **Core Architecture** | **Technical Documentation** | Operators need retention and capacity semantics. |
| Session concurrency isolation | **Core Architecture** | **Architecture Whitepaper** | It is a material isolation differentiator with architectural substance. |
| State manifest integrity | **Core Architecture** | **Architecture Whitepaper** | Relevant to state integrity, but not a purchasing headline. |
| Asynchronous interaction indexing | **Core Architecture** | **Developer Documentation** | Integrators need timing and consistency semantics. |
| Graphify structural context | **Experimental** | **Architecture Whitepaper** | Strategically distinctive, but customer outcomes are not yet measured. |
| Dual-model reasoning and synthesis | **Experimental** | **Technical Documentation** | Available and benchmarked for execution, but not proven superior. |
| Single-model strategy | **Core Architecture** | **Developer Documentation** | It is the MVP reasoning path and comparison baseline, not the product promise. |
| Structured intent/action contract | **Supporting Infrastructure** | **Developer Documentation** | Host applications need the schema; it is not core memory value. |
| Development phase gate | **Supporting Infrastructure** | **Developer Documentation** | Relevant only to the included coding-agent workflow. |
| Persistent learned-fact memory | **Experimental** | **Technical Documentation** | Its durable semantics must be clearly separated from ephemeral claims. |
| NVIDIA NIM model connector | **Supporting Infrastructure** | **Developer Documentation** | Provider setup belongs in integration documentation, not product identity. |
| Prompt manager and response parser | **Core Architecture** | **Internal Only** | Prompt text and parsing are policy implementation details. |
| FastAPI service contract | **Core Product** | **Developer Documentation** | It is the purchased integration surface, documented for builders. |
| SSE event protocol | **Supporting Infrastructure** | **Developer Documentation** | Consumers need event semantics and the simulated-streaming limitation. |
| React control plane | **Supporting Infrastructure** | **Technical Documentation** | It is a reference operations surface, not SC-EVM itself. |
| Terminal client | **Supporting Infrastructure** | **Developer Documentation** | It is a reference client and evaluation tool. |
| Local action/diff tooling | **Supporting Infrastructure** | **Developer Documentation** | It supports a coding-agent use case outside the memory core. |
| Clipboard suite and daemon | **Experimental** | **Internal Only** | It is peripheral, platform-specific, and not commercially validated. |
| Clipboard synchronization scaffold | **Experimental** | **Internal Only** | No relay exists, so external presentation would overstate capability. |
| VS Code context provider | **Supporting Infrastructure** | **Developer Documentation** | It is an optional code-context integration. |
| Session rehydration hook | **Supporting Infrastructure** | **Developer Documentation** | IDE and restart integration behavior belongs with developer setup. |
| Secure lifecycle manager | **Supporting Infrastructure** | **Technical Documentation** | It extends deletion assurance beyond the API and matters operationally. |
| Telemetry and audit sink | **Supporting Infrastructure** | **Developer Documentation** | Operators need paths and formats; current telemetry is minimal. |
| Strategy benchmark framework | **Supporting Infrastructure** | **Technical Documentation** | Benchmark methodology and limitations should be transparent. |
| Configuration and global error handling | **Supporting Infrastructure** | **Developer Documentation** | These are deployment and integration mechanics. |
| Container deployment assets | **Supporting Infrastructure** | **Developer Documentation** | Packaging is useful to adopters but not a product differentiator. |
| Image generation stub | **Deprecated** | **Internal Only** | It performs no generation and must not appear as a capability. |
| Deleted legacy HTML dashboard and VS Code bridge paths | **Deprecated** | **Internal Only** | They are superseded by `engine-dashboard/` and `vscode_context_provider.py`. |

## 9. Commercial Visibility Matrix

This matrix translates implementation into a coherent narrative without hiding innovation.

| External placement | Customer-facing value | Technical differentiation | Implementation detail excluded from the narrative |
|---|---|---|---|
| Public Homepage | Relevant continuity with bounded direct history; isolated sessions; explicit burn; network integration. | Mention confidence-gated memory and protected grounding only as supporting proof. | Model IDs, ChromaDB, thresholds, thread pools, prompt strings, Graphify performance claims. |
| Technical Documentation | Persistence boundaries, security model, lifecycle behavior, optional dual-model mode, dashboard, secure cleanup, benchmark scope and limitations. | Explain protected enclosures, strategy choices, and optional durable facts. | Private prompt templates and low-level retry/lock mechanics unless operationally necessary. |
| Architecture Whitepaper | Intent realignment, dual-anchor admission, pending-write interception, concurrency isolation, manifests, and Graphify's structural retrieval plane. | Show how the mechanisms combine into a context-control architecture and identify unvalidated hypotheses. | UI styling, clipboard behavior, Docker packaging, provider marketing. |
| Developer Documentation | API schemas, SSE events, configuration, provider connector, strategy adapters, CLI/IDE hooks, action schema, deployment, telemetry paths. | Explain extension boundaries and consistency semantics. | Commercial superiority claims not supported by benchmarks. |
| Internal Only | Calibration values and tuning rationale, prompt text, clipboard/sync experiments, image stub, deprecated paths, placeholder dashboard metrics. | Retain as engineering knowledge and research assets. | All material here is excluded from sales claims until reclassified. |

## 10. Commercial Narrative Rules

1. Lead with session-isolated, bounded, relevance-filtered context—not “two LLMs,” “ChromaDB,” “Graphify,” or “clipboard AI.”
2. Describe token behavior precisely: direct chat-history payload is bounded; total tokens are not constant because retrieved context, reformulation, synthesis, and outputs vary.
3. Describe SSE precisely: the API emits staged SSE events, but current response chunks are generated after the complete model response and are not true provider-token streaming.
4. Describe ephemerality precisely: web session vector state is in memory and burnable; the daemon's learned-fact JSON and local audit log are durable, separate planes.
5. Describe Graphify as optional structural context and an architectural differentiator; do not claim measured accuracy, hallucination, or efficiency gains before ablation.
6. Describe dual-model synthesis as an available strategy; the existing 50-turn run proves execution success only, not answer superiority.
7. Do not present image generation, cross-device sync, authentication, placeholder dashboard telemetry, or production-scale tenancy as current capabilities.

## 11. Evidence Register and Decision Caveats

- `README.md`: original SC-EVM problem statement, architecture claims, engineering features, and burn behavior.
- `src/sc_evm.py`: intent realignment, gating math, vector/Graphify fusion, and phase policy.
- `src/memory.py`: session isolation, locks, calibrated thresholds, manifests, GC/capacity, burn, and persistent fact storage.
- `src/main.py` and `src/services/session_runtime.py`: API lifecycle, staged SSE, pending buffer, bounded history, background indexing, and action gating.
- `src/agent.py`, `src/services/prompt_manager.py`, and `src/services/model_connector.py`: dual-model synthesis, structured actions, protected prompt construction, and provider access.
- `src/graphify_bridge.py` and `graphify-out/GRAPH_REPORT.md`: structural query implementation, graph freshness, graph size, extraction/inference provenance, and gaps.
- `src/strategies/` and `src/benchmarks/runner.py`: implemented strategy variants and benchmark methodology.
- `benchmarks/dual_model/analysis_reportduo-mode.json`: 50 dual-model turns, 100% transport-level success, approximately 68.52-second average latency, 156.56-second p95, 13,023 recorded input tokens, and 101,742 recorded output-token metric; these token fields are estimates produced by current adapters and are not billing-grade measurements.
- `benchmarks/single_model/analysis_reportmono-mode.json`: despite its directory name, the artifact records the AntiGravity CLI strategy with 0/50 successful turns and therefore provides no single-model quality comparison.
- `src/tests/`: implementation evidence for gating, isolation, lifecycle, rehydration, endpoints, stress behavior, diff handling, and IDE context; it does not contain outcome-scored Graphify or dual-vs-single quality tests.
- `engine-dashboard/`: reference UI with chat/session behavior and partially placeholder metrics.
- `src/clipboard_service.py`, `src/clipboard_gui.py`, `src/daemon.py`, and `src/sync.py`: peripheral local productivity capabilities and incomplete synchronization.
- `Dockerfile.backend`, `Dockerfile.frontend`, and `docker-compose.yml`: packaging support, not evidence of production readiness.

This boundary is definitive for product and messaging classification, but it does not convert unmeasured mechanisms into validated outcomes. Any future review that changes a frozen classification must cite new implementation or customer evidence, state the superseded row, and update the official definition only if the core purchasing reason has changed.
