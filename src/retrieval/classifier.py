"""Document classifier — assigns classification to documents at index time."""

from __future__ import annotations

import logging
import re

from src.knowledge.metadata import Classification, SourceType, classify_source

logger = logging.getLogger("SC-EVM.DocumentClassifier")

# Filename patterns that indicate INTERNAL source type
_PACKAGE_JSON_RE = re.compile(r"(^|/)package(-lock)?\.json$", re.I)
_NODE_MODULES_RE = re.compile(r"(^|/)node_modules/", re.I)
_GIT_RE = re.compile(r"(^|/)\.git(/|$)", re.I)
_CONFIG_EXTENSIONS = frozenset({".env", ".ini", ".cfg", ".toml", ".yaml", ".yml", ".conf"})
_SOURCE_EXTENSIONS = frozenset({".py", ".ts", ".js", ".tsx", ".jsx", ".java", ".go", ".rs", ".c", ".cpp", ".h"})


class DocumentClassifier:
    """Classifies documents by source type and path heuristics.

    Classification is deterministic and cannot be overridden by document metadata claims.
    """

    @classmethod
    def classify_by_source_type(cls, source_type: SourceType) -> Classification:
        """Return mandatory classification for a known source type."""
        return classify_source(source_type)

    @classmethod
    def classify_by_path(cls, path: str) -> tuple[SourceType, Classification]:
        """Infer source type and classification from a file path.

        Returns (source_type, classification). Always fails toward INTERNAL.
        """
        if not path:
            return SourceType.FILESYSTEM, Classification.INTERNAL

        if _PACKAGE_JSON_RE.search(path):
            if "lock" in path.lower():
                return SourceType.PACKAGE_LOCK, Classification.INTERNAL
            return SourceType.PACKAGE_JSON, Classification.INTERNAL

        if _NODE_MODULES_RE.search(path):
            return SourceType.NODE_MODULES, Classification.INTERNAL

        if _GIT_RE.search(path):
            return SourceType.GIT, Classification.INTERNAL

        ext = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
        if ext in _SOURCE_EXTENSIONS:
            return SourceType.SOURCE_CODE, Classification.INTERNAL

        if ext in _CONFIG_EXTENSIONS:
            return SourceType.CONFIGURATION, Classification.INTERNAL

        # Default: filesystem = INTERNAL
        return SourceType.FILESYSTEM, Classification.INTERNAL

    @classmethod
    def classify_graphify_node(cls) -> tuple[SourceType, Classification]:
        """All graphify/AST nodes are INTERNAL."""
        return SourceType.GRAPHIFY_NODE, Classification.INTERNAL

    @classmethod
    def classify_user_upload(cls) -> tuple[SourceType, Classification]:
        """User-uploaded documents are USER_PROVIDED."""
        return SourceType.USER_UPLOAD, Classification.USER_PROVIDED

    @classmethod
    def classify_public_doc(cls) -> tuple[SourceType, Classification]:
        """Explicitly public documentation."""
        return SourceType.PUBLIC_DOCUMENTATION, Classification.PUBLIC

    @classmethod
    def validate_claimed_classification(
        cls,
        source_type: SourceType,
        claimed_classification: Classification,
    ) -> Classification:
        """Override claimed classification if source mandates a stricter one.

        INTERNAL sources can never be downgraded to PUBLIC.
        """
        mandatory = classify_source(source_type)
        from src.knowledge.metadata import INTERNAL_CLASSIFICATIONS

        if mandatory in INTERNAL_CLASSIFICATIONS and claimed_classification not in INTERNAL_CLASSIFICATIONS:
            logger.warning(
                "Classification downgrade blocked: source=%s claimed=%s -> enforced=%s",
                source_type,
                claimed_classification,
                mandatory,
            )
            return mandatory
        return claimed_classification
