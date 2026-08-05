"""BM25 Lexical Indexer for SC-EVM Hybrid Retrieval.

Implements standard BM25Okapi scoring over code tokens, docstrings, filenames,
routes, configurations, and workspace content with incremental update capability.
"""
from __future__ import annotations

import math
import re
from typing import Any, NamedTuple


class BM25SearchResult(NamedTuple):
    doc_id: str
    text: str
    score: float
    metadata: dict[str, Any]


class BM25Indexer:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._documents: dict[str, str] = {}  # doc_id -> text
        self._metadata: dict[str, dict[str, Any]] = {}  # doc_id -> metadata
        self._doc_tokens: dict[str, list[str]] = {}  # doc_id -> token list
        self._doc_lens: dict[str, int] = {}  # doc_id -> doc length
        self._doc_freqs: dict[str, dict[str, int]] = {}  # doc_id -> token freq map
        self._df: dict[str, int] = {}  # term -> document frequency (count of docs containing term)
        self._avgdl: float = 0.0
        self._dirty: bool = False

    @staticmethod
    def tokenize(text: str) -> list[str]:
        """Tokenize code and text into lowercase word tokens."""
        if not text:
            return []
        # Split on non-word characters and camelCase/snake_case boundaries
        words = re.findall(r"[A-Za-z0-9_]+", text)
        tokens = []
        for word in words:
            # Handle camelCase splitting
            sub_words = re.findall(r"[A-Z]?[a-z0-9]+|[A-Z]+(?=[A-Z][a-z0-9]|\b)", word)
            if sub_words:
                tokens.extend(w.lower() for w in sub_words)
            else:
                tokens.append(word.lower())
        return tokens

    def add_document(self, doc_id: str, text: str, metadata: dict[str, Any] | None = None) -> None:
        """Add or update a document in the index."""
        if not doc_id or not text:
            return

        if doc_id in self._documents:
            self.remove_document(doc_id)

        tokens = self.tokenize(text)
        if not tokens:
            return

        self._documents[doc_id] = text
        self._metadata[doc_id] = metadata or {}
        self._doc_tokens[doc_id] = tokens
        self._doc_lens[doc_id] = len(tokens)

        tf: dict[str, int] = {}
        for token in tokens:
            tf[token] = tf.get(token, 0) + 1
        self._doc_freqs[doc_id] = tf

        for term in tf:
            self._df[term] = self._df.get(term, 0) + 1

        self._dirty = True

    def remove_document(self, doc_id: str) -> None:
        """Remove a document from the index."""
        if doc_id not in self._documents:
            return

        tf = self._doc_freqs.pop(doc_id, {})
        for term in tf:
            if term in self._df:
                self._df[term] -= 1
                if self._df[term] <= 0:
                    del self._df[term]

        self._documents.pop(doc_id, None)
        self._metadata.pop(doc_id, None)
        self._doc_tokens.pop(doc_id, None)
        self._doc_lens.pop(doc_id, None)
        self._dirty = True

    def _recalculate_stats(self) -> None:
        """Recalculate global collection statistics if index changed."""
        if not self._dirty:
            return
        num_docs = len(self._doc_lens)
        if num_docs > 0:
            self._avgdl = sum(self._doc_lens.values()) / num_docs
        else:
            self._avgdl = 0.0
        self._dirty = False

    def search(self, query: str, top_k: int = 5) -> list[BM25SearchResult]:
        """Search the BM25 index and return top_k candidates ranked by score."""
        self._recalculate_stats()
        query_tokens = self.tokenize(query)
        if not query_tokens or not self._documents:
            return []

        num_docs = len(self._documents)
        scores: dict[str, float] = {}

        for token in query_tokens:
            if token not in self._df:
                continue

            df = self._df[token]
            # Standard BM25 IDF formula
            idf = math.log((num_docs - df + 0.5) / (df + 0.5) + 1.0)

            for doc_id, tf_map in self._doc_freqs.items():
                freq = tf_map.get(token, 0)
                if freq == 0:
                    continue

                doc_len = self._doc_lens[doc_id]
                denom = freq + self.k1 * (1.0 - self.b + self.b * (doc_len / self._avgdl))
                num = freq * (self.k1 + 1.0)
                score = idf * (num / denom)
                scores[doc_id] = scores.get(doc_id, 0.0) + score

        sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [
            BM25SearchResult(
                doc_id=doc_id,
                text=self._documents[doc_id],
                score=score,
                metadata=self._metadata.get(doc_id, {}),
            )
            for doc_id, score in sorted_docs
        ]

    def clear(self) -> None:
        """Clear all indexed documents."""
        self._documents.clear()
        self._metadata.clear()
        self._doc_tokens.clear()
        self._doc_lens.clear()
        self._doc_freqs.clear()
        self._df.clear()
        self._avgdl = 0.0
        self._dirty = False
