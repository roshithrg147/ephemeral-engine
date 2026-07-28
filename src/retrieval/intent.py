"""Query intent classifier — detects retrieval-sensitive queries before retrieval executes."""

from __future__ import annotations

import re
from enum import StrEnum


class QueryIntent(StrEnum):
    """Classified intent of a user query with respect to retrieval security."""

    NORMAL_INFORMATION_REQUEST = "NORMAL_INFORMATION_REQUEST"
    INTERNAL_CAPABILITY_DISCOVERY = "INTERNAL_CAPABILITY_DISCOVERY"
    INTERNAL_ARCHITECTURE_DISCOVERY = "INTERNAL_ARCHITECTURE_DISCOVERY"
    SECURITY_PROBING = "SECURITY_PROBING"


# Patterns that indicate attempts to discover internal capabilities or architecture.
# Compiled once at module load.
_CAPABILITY_DISCOVERY_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bwhat\s+tools?\s+(exist|do\s+you\s+have|are\s+(available|installed|there))\b", re.I),
    re.compile(r"\bshow\s+(me\s+)?(your\s+)?(internal\s+)?tools?\b", re.I),
    re.compile(r"\blist\s+(your\s+)?(tools?|capabilities|functions?|commands?)\b", re.I),
    re.compile(r"\bwhat\s+capabilities\s+(do\s+you\s+have|exist|are\s+available)\b", re.I),
    re.compile(r"\bshow\s+(your\s+)?permissions?\b", re.I),
    re.compile(r"\bwhat\s+(can\s+you\s+do|are\s+your\s+capabilities)\b", re.I),
    re.compile(r"\blist\s+(all\s+)?(available\s+)?capabilities\b", re.I),
]

_ARCHITECTURE_DISCOVERY_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bwhat\s+files?\s+(exist|are\s+(there|available|in\s+this))\b", re.I),
    re.compile(r"\blist\s+(all\s+)?files?\b", re.I),
    re.compile(r"\bshow\s+(me\s+)?(the\s+)?file\s+(tree|structure|list)\b", re.I),
    re.compile(r"\blist\s+(all\s+)?dependencies\b", re.I),
    re.compile(r"\bwhat\s+dependencies\s+are\s+(installed|used|there)\b", re.I),
    re.compile(r"\bshow\s+(me\s+)?(the\s+)?package\.json\b", re.I),
    re.compile(r"\bshow\s+(me\s+)?(the\s+)?package-lock\.json\b", re.I),
    re.compile(r"\bexplain\s+(your\s+)?(internal\s+)?(architecture|design|structure)\b", re.I),
    re.compile(r"\bhow\s+(does|is)\s+(the\s+)?(system|engine|backend|architecture)\s+(work|structured|built|designed)\b", re.I),
    re.compile(r"\bwhat\s+(is|are)\s+(the\s+)?(internal\s+)?(components?|modules?|services?)\b", re.I),
    re.compile(r"\bshow\s+(me\s+)?(the\s+)?(source\s+code|codebase|repository)\b", re.I),
    re.compile(r"\bwhat\s+packages?\s+are\s+(installed|used|available)\b", re.I),
    re.compile(r"\bexplain\s+contextbroker\b", re.I),
    re.compile(r"\bexplain\s+workflowpolicy\b", re.I),
    re.compile(r"\bexplain\s+(the\s+)?(retrieval|vector|embedding)\s+(pipeline|system|architecture)\b", re.I),
]

_SECURITY_PROBING_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\byou\s+are\s+(now\s+)?(an?\s+)?(admin(istrator)?|root|superuser|privileged)\b", re.I),
    re.compile(r"\bact\s+as\s+(an?\s+)?(admin(istrator)?|root|superuser)\b", re.I),
    re.compile(r"\bignore\s+(previous|all|your)\s+(instructions?|rules?|constraints?|guidelines?)\b", re.I),
    re.compile(r"\bbypass\s+(security|restrictions?|policy|filters?)\b", re.I),
    re.compile(r"\bshow\s+(internal|private|hidden|restricted|confidential)\s+(tools?|data|files?|info)\b", re.I),
    re.compile(r"\boverride\s+(security|policy|restrictions?|permissions?)\b", re.I),
    re.compile(r"\bpretend\s+(you\s+are|to\s+be)\s+(an?\s+)?(admin|root|developer|engineer)\b", re.I),
    re.compile(r"\bdisregard\s+(your\s+)?(instructions?|rules?|policy)\b", re.I),
    re.compile(r"\bsystem\s+prompt\b", re.I),
    re.compile(r"\bshow\s+(me\s+)?(your\s+)?(system\s+)?prompt\b", re.I),
    re.compile(r"\bwhat\s+is\s+(in\s+)?(your\s+)?(system\s+)?prompt\b", re.I),
    re.compile(r"\breveal\s+(your\s+)?(instructions?|prompt|configuration)\b", re.I),
    re.compile(r"\bprint\s+(your\s+)?(instructions?|prompt|system\s+message)\b", re.I),
    re.compile(r"\btoken\s+injection\b", re.I),
    re.compile(r"\bprompt\s+injection\b", re.I),
    re.compile(r"\bjailbreak\b", re.I),
]


class QueryIntentClassifier:
    """Classifies query intent to prevent retrieval-based information leakage.

    Security probing and internal capability/architecture discovery queries
    must not trigger retrieval in PUBLIC_CHAT or PUBLIC_RESEARCH workflows.
    """

    @classmethod
    def classify(cls, query: str) -> QueryIntent:
        """Return the most restrictive intent classification for the query."""
        if not query or not query.strip():
            return QueryIntent.NORMAL_INFORMATION_REQUEST

        # Security probing takes highest priority
        for pattern in _SECURITY_PROBING_PATTERNS:
            if pattern.search(query):
                return QueryIntent.SECURITY_PROBING

        # Internal capability discovery
        for pattern in _CAPABILITY_DISCOVERY_PATTERNS:
            if pattern.search(query):
                return QueryIntent.INTERNAL_CAPABILITY_DISCOVERY

        # Internal architecture discovery
        for pattern in _ARCHITECTURE_DISCOVERY_PATTERNS:
            if pattern.search(query):
                return QueryIntent.INTERNAL_ARCHITECTURE_DISCOVERY

        return QueryIntent.NORMAL_INFORMATION_REQUEST

    @classmethod
    def retrieval_blocked_for_public(cls, intent: QueryIntent) -> bool:
        """Return True if retrieval must be disabled for PUBLIC_CHAT/PUBLIC_RESEARCH."""
        return intent in (
            QueryIntent.SECURITY_PROBING,
            QueryIntent.INTERNAL_CAPABILITY_DISCOVERY,
            QueryIntent.INTERNAL_ARCHITECTURE_DISCOVERY,
        )
