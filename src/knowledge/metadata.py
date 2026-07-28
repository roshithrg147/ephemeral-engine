"""Document metadata classification for retrieval security."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class Classification(StrEnum):
    """Security classification levels for indexed documents."""

    PUBLIC = "PUBLIC"
    USER_PROVIDED = "USER_PROVIDED"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    RESTRICTED = "RESTRICTED"
    REPOSITORY = "REPOSITORY"
    MAINTENANCE_MEMORY = "MAINTENANCE_MEMORY"
    WORKSPACE = "WORKSPACE"


class SourceType(StrEnum):
    """Origin type of an indexed document."""

    # Always INTERNAL — never downgrade
    REPOSITORY = "REPOSITORY"
    FILESYSTEM = "FILESYSTEM"
    GIT = "GIT"
    PACKAGE_JSON = "PACKAGE_JSON"
    PACKAGE_LOCK = "PACKAGE_LOCK"
    NODE_MODULES = "NODE_MODULES"
    DEPENDENCIES = "DEPENDENCIES"
    AST = "AST"
    GRAPHIFY_NODE = "GRAPHIFY_NODE"
    SOURCE_CODE = "SOURCE_CODE"
    CONFIGURATION = "CONFIGURATION"
    SEARCH_INDEX = "SEARCH_INDEX"
    FILE_TREE = "FILE_TREE"
    DEPENDENCY_GRAPH = "DEPENDENCY_GRAPH"

    # USER_PROVIDED
    USER_UPLOAD = "USER_UPLOAD"

    # PUBLIC
    PUBLIC_DOCUMENTATION = "PUBLIC_DOCUMENTATION"
    PUBLIC_WEB = "PUBLIC_WEB"
    ARXIV = "ARXIV"
    PUBMED = "PUBMED"

    # Operational
    OPERATIONAL_METRICS = "OPERATIONAL_METRICS"
    SYSTEM_HEALTH = "SYSTEM_HEALTH"
    SESSION_STATUS = "SESSION_STATUS"


# Deterministic source-to-classification mapping.
# INTERNAL sources can never be downgraded to PUBLIC.
_SOURCE_CLASSIFICATION: dict[SourceType, Classification] = {
    SourceType.REPOSITORY: Classification.REPOSITORY,
    SourceType.FILESYSTEM: Classification.INTERNAL,
    SourceType.GIT: Classification.INTERNAL,
    SourceType.PACKAGE_JSON: Classification.INTERNAL,
    SourceType.PACKAGE_LOCK: Classification.INTERNAL,
    SourceType.NODE_MODULES: Classification.INTERNAL,
    SourceType.DEPENDENCIES: Classification.INTERNAL,
    SourceType.AST: Classification.INTERNAL,
    SourceType.GRAPHIFY_NODE: Classification.INTERNAL,
    SourceType.SOURCE_CODE: Classification.INTERNAL,
    SourceType.CONFIGURATION: Classification.INTERNAL,
    SourceType.SEARCH_INDEX: Classification.INTERNAL,
    SourceType.FILE_TREE: Classification.INTERNAL,
    SourceType.DEPENDENCY_GRAPH: Classification.INTERNAL,
    SourceType.USER_UPLOAD: Classification.USER_PROVIDED,
    SourceType.PUBLIC_DOCUMENTATION: Classification.PUBLIC,
    SourceType.PUBLIC_WEB: Classification.PUBLIC,
    SourceType.ARXIV: Classification.PUBLIC,
    SourceType.PUBMED: Classification.PUBLIC,
    SourceType.OPERATIONAL_METRICS: Classification.CONFIDENTIAL,
    SourceType.SYSTEM_HEALTH: Classification.CONFIDENTIAL,
    SourceType.SESSION_STATUS: Classification.CONFIDENTIAL,
}

# Classifications that are INTERNAL-equivalent and can never be exposed to PUBLIC_CHAT.
INTERNAL_CLASSIFICATIONS: frozenset[Classification] = frozenset(
    {
        Classification.INTERNAL,
        Classification.CONFIDENTIAL,
        Classification.RESTRICTED,
        Classification.REPOSITORY,
        Classification.MAINTENANCE_MEMORY,
        Classification.WORKSPACE,
    }
)


def classify_source(source_type: SourceType) -> Classification:
    """Return the mandatory classification for a source type.

    Repository-derived sources are always INTERNAL regardless of any
    document-level metadata claim.
    """
    return _SOURCE_CLASSIFICATION.get(source_type, Classification.INTERNAL)


@dataclass(frozen=True, slots=True)
class DocumentMetadata:
    """Immutable metadata attached to every indexed document."""

    document_id: str
    tenant_id: str
    source_type: SourceType
    classification: Classification
    allowed_workflows: frozenset[str]
    namespace: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    owner: str = "system"

    def __post_init__(self) -> None:
        # Enforce: source classification always wins over claimed classification.
        # INTERNAL sources cannot be downgraded to PUBLIC.
        mandatory = classify_source(self.source_type)
        if mandatory in INTERNAL_CLASSIFICATIONS and self.classification not in INTERNAL_CLASSIFICATIONS:
            raise ValueError(
                f"Classification downgrade denied: source={self.source_type} "
                f"requires at least {mandatory}, got {self.classification}"
            )
