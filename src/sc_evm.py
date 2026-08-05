import asyncio
import json
import logging
import math
import time
from typing import Any

from src.config import settings
from src.services.model_connector import ModelConnector
from src.services.prompt_manager import PromptManager
from src.services.response_parsing import strip_code_fences


class ProviderUsage(dict[str, Any]):
    """Provider token usage with transport metadata kept outside the mapping contract."""

    def __init__(self, values: dict[str, Any], provider_metadata: dict[str, Any]):
        super().__init__(values)
        self.provider_metadata = provider_metadata


class SCEVMEngine:
    """Pure logic calculation engine for query reformulation and confidence gating calculations."""

    def __init__(
        self,
        model_connector: ModelConnector | None = None,
        prompt_manager: PromptManager | None = None,
    ):
        self.model_connector = model_connector or ModelConnector()
        self.prompt_manager = prompt_manager or PromptManager()

    def reformulate_query(self, current_input: str, history: list[dict[str, str]]) -> str:
        """Cleanly compiles a sliding historical turn window to fix potential conversational blindness."""
        return self.prompt_manager.build_rewrite_prompt(current_input, history)

    async def run_query_reformulation_async(
        self,
        current_input: str,
        history: list[dict[str, str]],
    ) -> tuple[str, str, dict[str, Any] | None]:
        """Run query reformulation through the configured NVIDIA NIM Model 1 role."""
        # Reformulation logic uses prompt from prompt_manager
        compiled_prompt = self.reformulate_query(current_input, history)
        try:
            response_text = await self.model_connector.call_async(
                model_key=settings.MODEL_1_KEY,
                prompt=compiled_prompt,
                system_prompt=self.prompt_manager.REWRITE_SYSTEM_PROMPT,
                max_tokens=settings.MODEL_REFORMULATION_MAX_TOKENS,
            )
            text_clean = strip_code_fences(response_text)
            usage = ProviderUsage(
                dict(getattr(response_text, "usage", None) or {}),
                dict(getattr(response_text, "provider_metadata", None) or {}),
            )

            if not text_clean:
                return current_input, current_input, usage

            try:
                result_json = json.loads(text_clean)
                return (
                    result_json.get("search_vector_query", current_input),
                    result_json.get("grounded_llm_prompt", current_input),
                    usage,
                )
            except json.JSONDecodeError:
                logging.getLogger("SC-EVM.Error").error(
                    f"JSON Decode Error on reformulation string: {text_clean}"
                )
                return current_input, current_input, usage

        except Exception as e:
            logging.getLogger("SC-EVM.Error").error(
                f"Query reformulation failed: {e}", exc_info=True
            )
            return current_input, current_input, None

    @staticmethod
    def cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute the mathematical cosine similarity between two vectors."""
        mag_a = math.sqrt(sum(x * x for x in a))
        mag_b = math.sqrt(sum(x * x for x in b))
        if mag_a < 1e-9 or mag_b < 1e-9:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b, strict=True))
        return dot / (mag_a * mag_b)

    @staticmethod
    def cosine_distance(a: list[float], b: list[float]) -> float:
        """Compute the mathematical cosine distance between two vectors."""
        return 1.0 - SCEVMEngine.cosine_similarity(a, b)

    @staticmethod
    def calculate_dual_anchor_gating(
        query_vector: list[float],
        anchor_a: list[float],
        anchor_b: list[float],
        maximum_admitted_anchor_distance: float | None = None,
    ) -> tuple[float, bool]:
        """Compute the mathematical cosine distance against dual tracking anchor targets to establish structural confidence gating.

        Includes standard safe vector-magnitude verification boundaries to isolate against divide-by-zero errors.
        """
        if maximum_admitted_anchor_distance is None:
            maximum_admitted_anchor_distance = settings.RETRIEVAL_ABSOLUTE_DISTANCE_CEILING or 1.0

        dist_a = SCEVMEngine.cosine_distance(query_vector, anchor_a)
        dist_b = SCEVMEngine.cosine_distance(query_vector, anchor_b)

        min_distance = min(dist_a, dist_b)
        passes_gate = min_distance <= maximum_admitted_anchor_distance

        return min_distance, passes_gate

    @staticmethod
    def filter_documents_via_gating(
        query_vector: list[float],
        documents: list[str],
        distances: list[float],
        embeddings: list[list[float]],
        *,
        base_threshold: float | None = None,
        absolute_ceiling: float | None = None,
        absolute_floor: float | None = None,
        neighboring_delta_limit: float | None = None,
        top_anchor_delta_limit: float | None = None,
    ) -> list[str]:
        """Filters retrieved documents through the dual-anchor gating rules.

        Uses floor, ceiling, and neighbor delta limits to prevent irrelevant context creep.
        All inputs and logic operate on cosine_distance.
        """
        if not documents:
            return []

        stats: dict[str, Any] = {}
        try:
            from src.thresholds import get_engine as _get_engine

            _eng = _get_engine()
            model = settings.CHROMA_EMBEDDING_MODEL
            stats = _eng.get_stats(model)
            if absolute_ceiling is None:
                absolute_ceiling = _eng.get_percentile(model, 90)
            if absolute_floor is None:
                absolute_floor = _eng.get_percentile(model, 10)
            if neighboring_delta_limit is None:
                configured = settings.RETRIEVAL_NEIGHBOR_DELTA_LIMIT
                if configured is not None:
                    neighboring_delta_limit = configured
                else:
                    median = stats.get("percentiles", {}).get("50")
                    p75 = stats.get("percentiles", {}).get("75")
                    if median is not None and p75 is not None:
                        neighboring_delta_limit = max(0.0, p75 - median)
            if top_anchor_delta_limit is None:
                configured = settings.RETRIEVAL_TOP_ANCHOR_DELTA_LIMIT
                if configured is not None:
                    top_anchor_delta_limit = configured
                else:
                    median = stats.get("percentiles", {}).get("50")
                    p90 = stats.get("percentiles", {}).get("90")
                    if median is not None and p90 is not None:
                        top_anchor_delta_limit = max(0.0, p90 - median)
            eng_val = _eng.get_acceptance_threshold(model)
            maximum_admitted_distance = base_threshold if base_threshold is not None else eng_val
        except Exception:
            pass

        # Fallbacks when engine/config produced None
        if absolute_ceiling is None:
            absolute_ceiling = 1.0
        if absolute_floor is None:
            absolute_floor = 0.0
        if neighboring_delta_limit is None:
            neighboring_delta_limit = absolute_ceiling
        if top_anchor_delta_limit is None:
            top_anchor_delta_limit = absolute_ceiling
        if maximum_admitted_distance is None:
            maximum_admitted_distance = 0.45

        matched_docs: list[str] = []
        matched_dists: list[float] = []
        matched_embs: list[list[float]] = []

        top_dist = distances[0]
        # Absolute ceiling exclusion check (dist > absolute_ceiling -> rejected)
        if top_dist > absolute_ceiling:
            # emit observability
            try:
                import time as _time

                _lat = 0.0
                _stats = {}
                from src.thresholds import get_engine as _get_engine

                _eng = _get_engine()
                _stats = _eng.get_stats(settings.CHROMA_EMBEDDING_MODEL)
                logger.info(
                    "retrieval_decision",
                    extra={
                        "query": None,
                        "candidate_count": len(documents),
                        "accepted_count": 0,
                        "mean": _stats.get("mean"),
                        "stddev": _stats.get("stddev"),
                        "mad": _stats.get("mad"),
                        "percentiles": _stats.get("percentiles"),
                        "chosen_threshold": maximum_admitted_distance,
                        "rejected_threshold": absolute_ceiling,
                        "latency_ms": _lat,
                    },
                )
            except Exception:
                pass
            return []

        _start = time.time()
        for doc, dist, emb in zip(documents, distances, embeddings, strict=True):
            if dist > absolute_ceiling:
                continue

            # Rule 1: Absolute Confidence Floor
            if dist <= absolute_floor:
                matched_docs.append(doc)
                matched_dists.append(dist)
                matched_embs.append(emb)
            # Rule 2: Dual-Anchor Gating Delta Evaluation
            else:
                if matched_dists:
                    prev_accepted_dist = matched_dists[-1]
                    neighboring_delta = dist - prev_accepted_dist
                    top_anchor_delta = dist - top_dist

                    # Run core gated validation logic using cosine_distance
                    _, passes_gate = SCEVMEngine.calculate_dual_anchor_gating(
                        emb,
                        matched_embs[0],  # Anchor A
                        matched_embs[-1],  # Anchor B
                        maximum_admitted_anchor_distance=maximum_admitted_distance,
                    )
                    if (
                        passes_gate
                        and neighboring_delta <= neighboring_delta_limit
                        and top_anchor_delta <= top_anchor_delta_limit
                    ):
                        matched_docs.append(doc)
                        matched_dists.append(dist)
                        matched_embs.append(emb)
                else:
                    # Accept top match if it is within absolute ceiling
                    matched_docs.append(doc)
                    matched_dists.append(dist)
                    matched_embs.append(emb)

        _lat = (time.time() - _start) * 1000.0
        # emit observability
        try:
            from src.thresholds import get_engine as _get_engine

            _eng = _get_engine()
            _stats = _eng.get_stats(settings.CHROMA_EMBEDDING_MODEL)
            logger.info(
                "retrieval_decision",
                extra={
                    "query": None,
                    "candidate_count": len(documents),
                    "accepted_count": len(matched_docs),
                    "mean": _stats.get("mean"),
                    "stddev": _stats.get("stddev"),
                    "mad": _stats.get("mad"),
                    "percentiles": _stats.get("percentiles"),
                    "chosen_threshold": maximum_admitted_distance,
                    "rejected_threshold": absolute_ceiling,
                    "latency_ms": _lat,
                },
            )
        except Exception:
            pass

        return matched_docs

    async def evaluate_query_context(
        self,
        query_vector: list[float],
        collection: Any,
        session_id: str,
        base_threshold: float | None,
        entity_id: str,
        graphify_enabled: bool = True,
        query_text: str = "",
    ) -> str:
        """Executes Hybrid Semantic (Vector), Lexical (BM25), and Structural (AST) retrieval.

        Fuses candidates using RetrievalFusionEngine based on prompt intent routing.
        """
        import shutil

        from src.graphify_bridge import get_structural_context
        from src.services.ast_indexer import ASTIndexer
        from src.services.bm25_indexer import BM25Indexer
        from src.services.fusion_engine import RetrievalFusionEngine
        from src.services.intent_router import IntentRouter

        query_str = query_text or entity_id or ""
        intent = IntentRouter.classify_intent(query_str)
        requires_ast = IntentRouter.requires_structural_ast(intent)
        start_time = time.perf_counter()

        # Pipeline 1: Semantic Vector Search
        def do_semantic_search() -> tuple[list[dict[str, Any]], list[str]]:
            try:
                results = collection.query(
                    query_embeddings=[query_vector],
                    n_results=settings.RETRIEVAL_RESULT_LIMIT,
                    where={"session_id": session_id},
                    include=["documents", "distances", "embeddings"],
                )
                if results and "documents" in results and results["documents"]:
                    docs = results["documents"][0]
                    distances = (
                        results["distances"][0] if "distances" in results else [0.0] * len(docs)
                    )
                    embeddings = (
                        results["embeddings"][0] if "embeddings" in results else [[]] * len(docs)
                    )

                    filtered_docs = self.filter_documents_via_gating(
                        query_vector=query_vector,
                        documents=docs,
                        distances=distances,
                        embeddings=embeddings,
                        base_threshold=base_threshold,
                    )
                    cands = [
                        {"doc_id": f"sem-{idx}", "text": doc, "metadata": {"source": "vector"}}
                        for idx, doc in enumerate(filtered_docs)
                    ]
                    return cands, filtered_docs
            except Exception as e:
                logging.getLogger("SC-EVM.Error").error(
                    f"Vector DB lookup failed: {e}", exc_info=True
                )
            return [], []

        # Pipeline 2: Lexical BM25 Search
        def do_lexical_search() -> list[dict[str, Any]]:
            try:
                bm25 = BM25Indexer()
                # Synchronize sample memory text into lexical index
                if collection and hasattr(collection, "get"):
                    existing = collection.get(where={"session_id": session_id}, include=["documents"])
                    if existing and "documents" in existing and existing["documents"]:
                        for idx, d_text in enumerate(existing["documents"]):
                            bm25.add_document(f"mem-{idx}", d_text)
                bm25_results = bm25.search(query_str, top_k=settings.RETRIEVAL_RESULT_LIMIT)
                return [
                    {
                        "doc_id": r.doc_id,
                        "text": r.text,
                        "score": r.score,
                        "metadata": {"source": "bm25"},
                    }
                    for r in bm25_results
                ]
            except Exception as e:
                logging.getLogger("SC-EVM.Error").error(f"BM25 lookup failed: {e}")
                return []

        # Pipeline 3: Structural AST & Graph Lookup (Intent-Gated)
        def do_structural_search() -> tuple[list[dict[str, Any]], str]:
            ast_candidates: list[dict[str, Any]] = []
            graph_text = ""

            if not requires_ast:
                return [], ""

            try:
                ast_idx = ASTIndexer()
                ast_res = ast_idx.search_symbols(query_str, top_k=settings.RETRIEVAL_RESULT_LIMIT)
                ast_candidates = [
                    {
                        "doc_id": f"ast-{res.symbol.file_path}:{res.symbol.line_number}",
                        "text": f"{res.symbol.signature} (File: {res.symbol.file_path}:L{res.symbol.line_number})",
                        "metadata": {"source": "ast", "symbol_type": res.symbol.symbol_type},
                    }
                    for res in ast_res
                ]
            except Exception as e:
                logging.getLogger("SC-EVM.Error").error(f"AST search failed: {e}")

            if graphify_enabled and shutil.which("graphify"):
                try:
                    graph_text = get_structural_context(entity_id)
                except Exception:
                    graph_text = ""
            elif graphify_enabled:
                logging.getLogger("SC-EVM.Graphify").info(
                    "Graphify CLI not found; skipping structural context retrieval."
                )

            return ast_candidates, graph_text

        # Execute pipelines concurrently
        sem_task = asyncio.to_thread(do_semantic_search)
        lex_task = asyncio.to_thread(do_lexical_search)
        struct_task = asyncio.to_thread(do_structural_search)

        (sem_cands, sem_filtered_docs), lex_cands, (struct_cands, graph_context) = (
            await asyncio.gather(sem_task, lex_task, struct_task)
        )

        # Retrieval Fusion via RRF
        fusion_engine = RetrievalFusionEngine()
        fused_results, fusion_lat = fusion_engine.fuse(
            sem_cands,
            lex_cands,
            struct_cands if requires_ast else [],
            limit=settings.RETRIEVAL_RESULT_LIMIT,
        )

        total_lat = (time.perf_counter() - start_time) * 1000.0

        # Structured Observability Telemetry
        retrievers_used = ["semantic", "lexical"]
        if requires_ast:
            retrievers_used.append("structural")

        logging.getLogger("SC-EVM.Fusion").info(
            "hybrid_retrieval_fusion",
            extra={
                "query": query_str,
                "intent": intent,
                "retrievers_used": retrievers_used,
                "fusion_weights": {
                    "semantic": fusion_engine.semantic_weight,
                    "lexical": fusion_engine.lexical_weight,
                    "structural": fusion_engine.structural_weight if requires_ast else 0.0,
                },
                "candidate_counts": {
                    "semantic": len(sem_cands),
                    "lexical": len(lex_cands),
                    "structural": len(struct_cands),
                },
                "fusion_latency_ms": fusion_lat,
                "retrieval_latency_ms": total_lat,
                "chosen_evidence": [cand.text[:80] for cand in fused_results],
            },
        )

        # Build fused context block
        fused_context = []
        if graph_context:
            fused_context.append(f"<graphify_context>\n{graph_context}\n</graphify_context>")

        if fused_results:
            for cand in fused_results:
                fused_context.append(f"<retrieved_memory>\n{cand.text}\n</retrieved_memory>")
        else:
            for doc in sem_filtered_docs:
                fused_context.append(f"<retrieved_memory>\n{doc}\n</retrieved_memory>")

        return "\n\n".join(fused_context)

    @staticmethod
    def check_phase_gate(
        current_phase: int | None, action_type: str, action_payload: dict[str, Any] | None = None
    ) -> bool:
        """
        Enforces strict phase-gating to prevent premature code generation.
        Validates the action against the current phase.
        """
        import logging

        if current_phase is None:
            current_phase = settings.DEVELOPMENT_PHASE

        # PHASES: 0=INIT, 1=DATABASE_DESIGN, 2=BACKEND_READY, 3=UI_READY

        if action_type == "none" or action_type == "update_memory":
            return True

        if action_type == "save_file":
            payload_dict = action_payload or {}
            file_path = (payload_dict.get("file_path") or "").lower()

            # Identify UI code by extensions or path
            is_ui_code = (
                any(
                    file_path.endswith(ext)
                    for ext in [".js", ".jsx", ".ts", ".tsx", ".css", ".html"]
                )
                or "frontend" in file_path
                or "dashboard" in file_path
            )

            # Identify DB/Backend code
            is_backend = (
                any(file_path.endswith(ext) for ext in [".py"])
                or "backend" in file_path
                or "api" in file_path
            )

            if is_ui_code and current_phase < 3:
                logging.getLogger("SC-EVM.Gate").warning(
                    f"Phase-gate blocked UI code generation for '{file_path}' in phase {current_phase}"
                )
                return False

            if is_backend and current_phase < 2:
                # Assuming phase 1 is database, phase 2 is backend logic.
                logging.getLogger("SC-EVM.Gate").warning(
                    f"Phase-gate blocked Backend code generation for '{file_path}' in phase {current_phase}"
                )
                return False

        # For run_command, we might want to prevent npm start if UI is not ready, etc.
        if action_type == "run_command":
            payload_dict = action_payload or {}
            cmd = (payload_dict.get("command") or "").lower()
            if ("npm" in cmd or "npx" in cmd or "react" in cmd) and current_phase < 3:
                logging.getLogger("SC-EVM.Gate").warning(
                    f"Phase-gate blocked UI command '{cmd}' in phase {current_phase}"
                )
                return False

        return True
