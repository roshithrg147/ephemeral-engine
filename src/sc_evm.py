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
        gateway: Any = None,
        tenant_id: str = "default",
        principal_id: str = "system",
        sec_ctx: Any = None,
    ) -> tuple[str, Any]:
        """
        Executes Vector DB search and Graphify lookup via RetrievalGateway.
        Fuses the retrieved context blocks into a single string payload.
        Returns a tuple of (fused_context_string, ContextTrace).
        """
        import shutil
        import asyncio
        import logging
        from src.retrieval.gateway import RetrievalRequest
        from src.workflow_policy import WorkflowClass
        from src.retrieval.trace import ContextTrace

        logger = logging.getLogger("SC-EVM.Retrieval")

        if not gateway:
            logger.warning("No RetrievalGateway provided, returning empty context.")
            return "", ContextTrace(
                correlation_id="fallback",
                workflow=WorkflowClass.PUBLIC_CHAT.value,
                principal_id=principal_id,
                query_intent="fallback"
            )

        def do_gateway_search() -> tuple[str, ContextTrace]:
            try:
                request = RetrievalRequest(
                    query=entity_id,
                    top_k=settings.RETRIEVAL_RESULT_LIMIT,
                    requested_namespace="default",
                    requested_graph_namespace="default" if graphify_enabled else None,
                    sec_ctx=sec_ctx,
                )
                result = gateway.retrieve(
                    request=request,
                    workflow=WorkflowClass.PUBLIC_CHAT,
                    tenant_id=tenant_id,
                    principal_id=principal_id,
                )

                if result.retrieval_blocked:
                    logger.warning(f"Retrieval blocked: {result.blocked_reason}")
                    return "", result.trace or ContextTrace(
                        correlation_id="blocked",
                        workflow=WorkflowClass.PUBLIC_CHAT.value,
                        principal_id=principal_id,
                        query_intent="blocked"
                    )

                # Context Fusion
                fused_context = []
                for item in result.items:
                    if item.metadata.get("source_type") == "GRAPHIFY_NODE":
                        fused_context.append(item.content)
                    else:
                        fused_context.append(f"<retrieved_memory>\n{item.content}\n</retrieved_memory>")

                return "\n\n".join(fused_context), result.trace
            except Exception as e:
                logger.error(f"Gateway search failed: {e}", exc_info=True)
                return "", ContextTrace(
                    correlation_id="error",
                    workflow=WorkflowClass.PUBLIC_CHAT.value,
                    principal_id=principal_id,
                    query_intent="error"
                )

        # Run gateway search in worker thread
        fused_context, trace = await asyncio.to_thread(do_gateway_search)
        return fused_context, trace

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
