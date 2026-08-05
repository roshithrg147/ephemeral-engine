"""Retrieval Fusion Engine for SC-EVM.

Combines Semantic (Vector), Lexical (BM25), and Structural (AST) rankings into a
unified, deduplicated result list using Reciprocal Rank Fusion (RRF) with
runtime-configurable pipeline weights.
"""
from __future__ import annotations

import time
from typing import Any, NamedTuple

from src.config import settings


class FusedCandidate(NamedTuple):
    doc_id: str
    text: str
    fusion_score: float
    pipeline_sources: list[str]
    metadata: dict[str, Any]


class RetrievalFusionEngine:
    def __init__(
        self,
        semantic_weight: float | None = None,
        lexical_weight: float | None = None,
        structural_weight: float | None = None,
        rrf_k: int = 60,
    ):
        self.semantic_weight = (
            semantic_weight if semantic_weight is not None else settings.FUSION_SEMANTIC_WEIGHT
        )
        self.lexical_weight = (
            lexical_weight if lexical_weight is not None else settings.FUSION_LEXICAL_WEIGHT
        )
        self.structural_weight = (
            structural_weight if structural_weight is not None else settings.FUSION_STRUCTURAL_WEIGHT
        )
        self.rrf_k = rrf_k

    def fuse(
        self,
        semantic_results: list[dict[str, Any]],
        lexical_results: list[dict[str, Any]],
        structural_results: list[dict[str, Any]],
        limit: int = 5,
    ) -> tuple[list[FusedCandidate], float]:
        """Fuse candidate results from all three pipelines using Reciprocal Rank Fusion (RRF).

        Returns (fused_candidates, fusion_latency_ms).
        """
        start_time = time.perf_counter()

        rrf_scores: dict[str, float] = {}
        doc_texts: dict[str, str] = {}
        doc_sources: dict[str, list[str]] = {}
        doc_metadata: dict[str, dict[str, Any]] = {}

        # Helper to process a pipeline candidate list
        def process_pipeline(pipeline_name: str, candidates: list[dict[str, Any]], weight: float):
            if weight <= 0 or not candidates:
                return

            for rank, cand in enumerate(candidates, 1):
                # Unique candidate key
                doc_id = cand.get("doc_id") or cand.get("file_path") or str(hash(cand.get("text", "")))
                text = cand.get("text") or cand.get("signature") or ""

                if not text:
                    continue

                rrf_score = weight * (1.0 / (self.rrf_k + rank))

                rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + rrf_score
                doc_texts[doc_id] = text

                sources = doc_sources.setdefault(doc_id, [])
                if pipeline_name not in sources:
                    sources.append(pipeline_name)

                meta = doc_metadata.setdefault(doc_id, {})
                meta.update(cand.get("metadata") or {})

        # Process all three pipelines
        process_pipeline("semantic", semantic_results, self.semantic_weight)
        process_pipeline("lexical", lexical_results, self.lexical_weight)
        process_pipeline("structural", structural_results, self.structural_weight)

        # Rank candidates by combined RRF score
        sorted_candidates = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:limit]

        fused = [
            FusedCandidate(
                doc_id=doc_id,
                text=doc_texts[doc_id],
                fusion_score=score,
                pipeline_sources=doc_sources[doc_id],
                metadata=doc_metadata[doc_id],
            )
            for doc_id, score in sorted_candidates
        ]

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        return fused, latency_ms
