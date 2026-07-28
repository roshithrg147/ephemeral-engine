"""Adapters bridging underlying storage to the RetrievalGateway."""

from __future__ import annotations

import logging
from typing import Any

from src.graphify_bridge import get_structural_context

logger = logging.getLogger("SC-EVM.RetrievalAdapters")


class ChromaVectorStoreAdapter:
    """Adapts ChromaDB collection to the RetrievalGateway interface."""

    def __init__(self, collection: Any, embed_fn: Any, session_id: str) -> None:
        self.collection = collection
        self.embed_fn = embed_fn
        self.session_id = session_id

    def query(
        self,
        query_text: str,
        n_results: int,
        where: dict[str, Any],
        namespace: str,
    ) -> list[dict[str, Any]]:
        """Execute a synchronous query against ChromaDB."""
        try:
            # Generate embedding
            query_vector = self.embed_fn([query_text])[0]

            # Inject session_id into the where filter
            # ChromaDB requires $and if we have multiple conditions
            if "$and" in where:
                where["$and"].append({"session_id": self.session_id})
            else:
                where = {"$and": [where, {"session_id": self.session_id}]}

            results = self.collection.query(
                query_embeddings=[query_vector],
                n_results=n_results,
                where=where,
                include=["documents", "metadatas", "distances"],
            )

            if not results or not results.get("documents") or not results["documents"][0]:
                return []

            docs = results["documents"][0]
            metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)

            formatted_results = []
            for doc, meta in zip(docs, metas, strict=False):
                formatted_results.append({
                    "content": doc,
                    "metadata": meta,
                })
            return formatted_results

        except Exception as e:
            logger.error("ChromaDB query failed: %s", e, exc_info=True)
            return []


class GraphifyStoreAdapter:
    """Adapts Graphify CLI to the RetrievalGateway interface."""

    def query(
        self,
        query_text: str,
        n_results: int,
        where: dict[str, Any],
        namespace: str,
    ) -> list[dict[str, Any]]:
        """Execute a synchronous query against Graphify."""
        try:
            # Graphify currently ignores where/namespace, but we enforce it at the gateway
            context = get_structural_context(query_text)
            if not context:
                return []

            return [
                {
                    "content": f"<graphify_context>\n{context}\n</graphify_context>",
                    "metadata": {
                        "source_type": "GRAPHIFY_NODE",
                        "classification": "INTERNAL",
                        "namespace": namespace,
                        # We trust the gateway to have validated the namespace
                    },
                }
            ]
        except Exception as e:
            logger.error("Graphify query failed: %s", e, exc_info=True)
            return []
