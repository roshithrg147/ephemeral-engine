import math
from typing import List, Dict, Tuple

class SCEVMEngine:
    """Pure logic calculation engine for query reformulation and confidence gating calculations."""

    @staticmethod
    def reformulate_query(current_input: str, history: List[Dict[str, str]]) -> str:
        """Cleanly compiles a sliding historical turn window to fix potential conversational blindness."""
        # Retrieve a sliding window of the last 6 messages (3 full turns)
        history_window = history[-6:]
        formatted_turns = []
        for turn in history_window:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            role_label = "User" if role == "user" else "Assistant"
            formatted_turns.append(f"{role_label}: {content}")
        
        history_str = "\n".join(formatted_turns)
        return f"Conversation History:\n{history_str}\n\nCurrent User Prompt: {current_input}"

    @staticmethod
    def calculate_dual_anchor_gating(
        query_vector: List[float],
        anchor_a: List[float],
        anchor_b: List[float],
        base_threshold: float = 0.72
    ) -> Tuple[float, bool]:
        """Compute the mathematical cosine similarity against dual tracking anchor targets to establish structural confidence gating.
        
        Includes standard safe vector-magnitude verification boundaries to isolate against divide-by-zero errors.
        """
        # Calculate Euclidean norms (magnitudes)
        mag_q = math.sqrt(sum(x * x for x in query_vector))
        mag_a = math.sqrt(sum(x * x for x in anchor_a))
        mag_b = math.sqrt(sum(x * x for x in anchor_b))

        # Safe vector-magnitude verification boundaries to isolate against divide-by-zero errors
        if mag_q < 1e-9 or mag_a < 1e-9 or mag_b < 1e-9:
            return 0.0, False

        # Calculate dot products
        dot_a = sum(q * a for q, a in zip(query_vector, anchor_a))
        dot_b = sum(q * b for q, b in zip(query_vector, anchor_b))

        # Calculate cosine similarities
        sim_a = dot_a / (mag_q * mag_a)
        sim_b = dot_b / (mag_q * mag_b)

        # Establish structural confidence gating:
        # Determine the maximum similarity against dual anchors
        max_similarity = max(sim_a, sim_b)
        passes_gate = max_similarity >= base_threshold

        return max_similarity, passes_gate

    @staticmethod
    def filter_documents_via_gating(
        query_vector: List[float],
        documents: List[str],
        distances: List[float],
        embeddings: List[List[float]],
        *,
        base_threshold: float = 0.52,
        absolute_ceiling: float = 0.48,
        absolute_floor: float = 0.40,
        neighboring_delta_limit: float = 0.12,
        top_anchor_delta_limit: float = 0.18
    ) -> List[str]:
        """Filters retrieved documents through the dual-anchor gating rules.
        
        Uses floor, ceiling, and neighbor delta limits to prevent irrelevant context creep.
        """
        if not documents:
            return []

        matched_docs: List[str] = []
        matched_dists: List[float] = []
        matched_embs: List[List[float]] = []

        top_dist = distances[0]
        # Absolute ceiling exclusion check (dist > absolute_ceiling -> rejected)
        if top_dist > absolute_ceiling:
            return []

        for doc, dist, emb in zip(documents, distances, embeddings):
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

                    # Run core gated validation logic
                    _, passes_gate = SCEVMEngine.calculate_dual_anchor_gating(
                        query_vector,
                        matched_embs[0],  # Anchor A
                        matched_embs[-1], # Anchor B
                        base_threshold=base_threshold
                    )
                    if passes_gate and neighboring_delta <= neighboring_delta_limit and top_anchor_delta <= top_anchor_delta_limit:
                        matched_docs.append(doc)
                        matched_dists.append(dist)
                        matched_embs.append(emb)
                else:
                    # Accept top match if it is within absolute ceiling
                    matched_docs.append(doc)
                    matched_dists.append(dist)
                    matched_embs.append(emb)

        return matched_docs
