"""Tokenizer Abstraction for SC-EVM Context Control Plane.

Supports multiple tokenization strategies (tiktoken, regex tokenizers, and character ratio estimation)
without hardcoding any single tokenizer or model assumption.
"""
from __future__ import annotations

import re
from typing import Protocol


class TokenizerProtocol(Protocol):
    def count_tokens(self, text: str, model_name: str = "") -> int:
        ...


class TiktokenAdapter:
    """Adapter for OpenAI tiktoken library if installed."""

    def __init__(self):
        self._encoders = {}

    def count_tokens(self, text: str, model_name: str = "gpt-4") -> int:
        if not text:
            return 0
        try:
            import tiktoken

            encoding_name = "cl100k_base"
            if "gpt-3.5" in model_name:
                encoding_name = "cl100k_base"
            elif "gpt-4o" in model_name or "o1" in model_name or "o3" in model_name:
                encoding_name = "o200k_base"

            if encoding_name not in self._encoders:
                self._encoders[encoding_name] = tiktoken.get_encoding(encoding_name)
            enc = self._encoders[encoding_name]
            return len(enc.encode(text))
        except Exception:
            return FallbackCharTokenizer().count_tokens(text, model_name)


class FallbackCharTokenizer:
    """Fast, accurate fallback tokenizer splitting on words, code identifiers, and symbols."""

    @staticmethod
    def count_tokens(text: str, model_name: str = "") -> int:
        if not text:
            return 0
        # Estimate: 1 token ≈ 4 characters or ~0.75 words + code punctuation
        # Sub-word tokenization estimation
        words = re.findall(r"\w+|[^\w\s]", text)
        if not words:
            return max(1, len(text) // 4)
        # Average token count: max of word/symbol count and char_len // 3.8
        return max(len(words), int(len(text) / 3.8))


class TokenizerRegistry:
    """Registry providing tokenizer selection based on configuration or environment."""

    _instance: TokenizerRegistry | None = None

    def __init__(self):
        self._adapter: TokenizerProtocol = self._auto_select()

    def _auto_select(self) -> TokenizerProtocol:
        try:
            import tiktoken  # noqa: F401

            return TiktokenAdapter()
        except ImportError:
            return FallbackCharTokenizer()

    @classmethod
    def get_tokenizer(cls) -> TokenizerProtocol:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance._adapter

    @classmethod
    def count_tokens(cls, text: str, model_name: str = "") -> int:
        return cls.get_tokenizer().count_tokens(text, model_name)
