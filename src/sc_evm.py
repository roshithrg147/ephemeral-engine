import asyncio
import json
import logging
import math
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
        maximum_admitted_anchor_distance: float = (settings.RETRIEVAL_ABSOLUTE_DISTANCE_CEILING),
    ) -> tuple[float, bool]:
        """Compute the mathematical cosine distance against dual tracking anchor targets to establish structural confidence gating.

        Includes standard safe vector-magnitude verification boundaries to isolate against divide-by-zero errors.
        """
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
        base_threshold: float = settings.RETRIEVAL_BASE_DISTANCE_THRESHOLD,
        absolute_ceiling: float = settings.RETRIEVAL_ABSOLUTE_DISTANCE_CEILING,
        absolute_floor: float = settings.RETRIEVAL_ABSOLUTE_DISTANCE_FLOOR,
        neighboring_delta_limit: float = settings.RETRIEVAL_NEIGHBOR_DELTA_LIMIT,
        top_anchor_delta_limit: float = settings.RETRIEVAL_TOP_ANCHOR_DELTA_LIMIT,
    ) -> list[str]:
        """Filters retrieved documents through the dual-anchor gating rules.

        Uses floor, ceiling, and neighbor delta limits to prevent irrelevant context creep.
        All inputs and logic operate on cosine_distance.
        """
        if not documents:
            return []

        # We treat base_threshold as the calibrated maximum admitted cosine distance
        maximum_admitted_distance = base_threshold

        matched_docs: list[str] = []
        matched_dists: list[float] = []
        matched_embs: list[list[float]] = []

        top_dist = distances[0]
        # Absolute ceiling exclusion check (dist > absolute_ceiling -> rejected)
        if top_dist > absolute_ceiling:
            return []

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

        return matched_docs

    async def evaluate_query_context(
        self,
        query_vector: list[float],
        collection: Any,
        session_id: str,
        base_threshold: float,
        entity_id: str,
        graphify_enabled: bool = True,
    ) -> str:
        """
        Executes Vector DB search and Graphify lookup in parallel using asyncio.gather.
        Fuses the retrieved context blocks into a single string payload.
        """
        import shutil

        from src.graphify_bridge import get_structural_context

        def do_vector_search() -> list[str]:
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

                    return self.filter_documents_via_gating(
                        query_vector=query_vector,
                        documents=docs,
                        distances=distances,
                        embeddings=embeddings,
                        base_threshold=base_threshold,
                    )
            except Exception as e:
                logging.getLogger("SC-EVM.Error").error(
                    f"Vector DB lookup failed: {e}", exc_info=True
                )
            return []

        def do_graph_lookup() -> str:
            if not graphify_enabled:
                return ""
            if not shutil.which("graphify"):
                logger = logging.getLogger("SC-EVM.Graphify")
                logger.info("Graphify CLI not found; skipping structural context retrieval.")
                return ""
            return get_structural_context(entity_id)

        # Run both DB queries concurrently in worker threads.
        vector_task = asyncio.to_thread(do_vector_search)
        graph_task = asyncio.to_thread(do_graph_lookup)

        vector_docs, graph_context = await asyncio.gather(vector_task, graph_task)

        # Context Fusion
        fused_context = []
        if graph_context:
            fused_context.append(f"<graphify_context>\n{graph_context}\n</graphify_context>")

        for doc in vector_docs:
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

        if action_type == "save_file" and action_payload:
            file_path = action_payload.get("file_path", "").lower()

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
        if action_type == "run_command" and action_payload:
            cmd = action_payload.get("command", "").lower()
            if ("npm" in cmd or "npx" in cmd or "react" in cmd) and current_phase < 3:
                logging.getLogger("SC-EVM.Gate").warning(
                    f"Phase-gate blocked UI command '{cmd}' in phase {current_phase}"
                )
                return False

        return True
