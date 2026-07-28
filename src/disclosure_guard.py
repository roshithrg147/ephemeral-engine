"""Disclosure guard inspecting outgoing responses for secrets, paths, stack traces, and internal prompts."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import StrEnum

from src.security_context import SecurityContext

logger = logging.getLogger("SC-EVM.DisclosureGuard")


class DisclosureAction(StrEnum):
    ALLOW = "ALLOW"
    REDACT = "REDACT"
    REGENERATE = "REGENERATE"
    BLOCK = "BLOCK"


@dataclass(frozen=True, slots=True)
class DisclosureResult:
    action: DisclosureAction
    cleaned_text: str
    reasons: list[str]


# Patterns identifying sensitive internal details
_PATH_PATTERNS = re.compile(
    r"(\bsrc/[a-zA-Z0-9_/-]+\.(py|json|md|sh)\b|\bengine-dashboard/[a-zA-Z0-9_/-]+\.(tsx|ts|js|json)\b|/\bhome/[a-zA-Z0-9_.-]+/\b|\bengine-dashboard/\b|\bsrc/\b)",
    re.IGNORECASE,
)
_BARE_FILENAME_PATTERNS = re.compile(
    r"\b[a-zA-Z0-9_-]+\.(py|ts|tsx|jsx|sh)\b",
    re.IGNORECASE,
)
_FUNCTION_NAME_PATTERNS = re.compile(
    r"\b(require_permission|verify_firebase_token_async|validate_context_for_workflow|sse_query_generator|reinitialize_session|SecurityContextResolver|ContextBroker|CapabilityBroker|DisclosureGuard|MemoryGateway|PromptManager|WorkflowPolicyEngine|CapabilityFilter|WorkflowContextFilter)\s*(\(\))?\b",
    re.IGNORECASE,
)
_ARCHITECTURE_PATTERNS = re.compile(
    r"(\bSC-EVM codebase\b|\bSC-EVM repository\b|\bSC-EVM internal\b|\bSC-EVM architecture\b|\bproject's codebase\b|\bproject codebase\b|\bnavigate the project\b|\binspect security modules\b|\blist_files\b|\bread_file\b|\bsave_file\b|\brun_command\b|\bburn_session\b|\bsearch_repository\b|\bPUBLIC_CHAT\b|\bMAINTENANCE\b|\bOPERATOR_READ\b|\bPRIVILEGED_ADMIN\b)",
    re.IGNORECASE,
)
_SECRET_PATTERNS = re.compile(
    r"(?i)(nvidia_api_key|firebase_api_key|secret[_-]?key|password\s*=|bearer\s+[a-z0-9._-]+|ey[a-z0-9_-]{20,}\.[a-z0-9_-]{20,})",
    re.IGNORECASE,
)
_STACK_TRACE_PATTERNS = re.compile(
    r"(Traceback \(most recent call last\)|File \".*?\.py\", line \d+|HTTPException|FastAPI Error)",
    re.IGNORECASE,
)
_PROMPT_PATTERNS = re.compile(
    r"(You are a cognitive query orchestration layer|CRITICAL RESPONSE RULE|CRITICAL PHASE GATING RULE|SYNTHESIS_SYSTEM_PROMPT)",
    re.IGNORECASE,
)
_INTERNAL_SCHEMA_PATTERNS = re.compile(
    r"(\btenant_memberships\b|\bsc_evm_sessions\b|\bpostgres_app_users\b)",
    re.IGNORECASE,
)


class DisclosureGuard:
    """Inspects generated response text against disclosure rules before frontend delivery."""

    SAFE_PUBLIC_BOUNDARY_RESPONSE = (
        "I can help answer questions and explain concepts, but I cannot provide private implementation details."
    )

    @classmethod
    def inspect(cls, sec_ctx: SecurityContext, text: str) -> DisclosureResult:
        if not text or not text.strip():
            return DisclosureResult(action=DisclosureAction.ALLOW, cleaned_text=text, reasons=[])

        # If internal disclosure is allowed under current workflow (e.g. MAINTENANCE), check only secrets
        if sec_ctx.allow_internal_disclosure():
            if _SECRET_PATTERNS.search(text):
                cleaned = _SECRET_PATTERNS.sub("[REDACTED_SECRET]", text)
                logger.warning("Redacted secret from maintenance output", extra={"user_id": sec_ctx.user_id})
                return DisclosureResult(
                    action=DisclosureAction.REDACT,
                    cleaned_text=cleaned,
                    reasons=["secret_redacted"],
                )
            return DisclosureResult(action=DisclosureAction.ALLOW, cleaned_text=text, reasons=[])

        # PUBLIC_CHAT / PUBLIC_RESEARCH / OPERATOR_READ: Enforce strict disclosure prevention
        reasons: list[str] = []

        if _SECRET_PATTERNS.search(text):
            reasons.append("secret_detected")

        if _STACK_TRACE_PATTERNS.search(text):
            reasons.append("stack_trace_detected")

        if _PROMPT_PATTERNS.search(text):
            reasons.append("system_prompt_detected")

        if _PATH_PATTERNS.search(text) or _BARE_FILENAME_PATTERNS.search(text):
            reasons.append("internal_path_detected")

        if _FUNCTION_NAME_PATTERNS.search(text) or _ARCHITECTURE_PATTERNS.search(text):
            reasons.append("architecture_disclosure_detected")

        if _INTERNAL_SCHEMA_PATTERNS.search(text):
            reasons.append("internal_schema_detected")

        if reasons:
            logger.warning(
                "DisclosureGuard triggered in public workflow",
                extra={
                    "workflow": sec_ctx.workflow.value,
                    "reasons": reasons,
                    "user_id": sec_ctx.user_id,
                },
            )
            # If critical issues (secrets, stack trace, system prompts, architecture leakage) are present, replace with safe response
            if (
                "secret_detected" in reasons
                or "stack_trace_detected" in reasons
                or "system_prompt_detected" in reasons
                or "architecture_disclosure_detected" in reasons
            ):
                return DisclosureResult(
                    action=DisclosureAction.BLOCK,
                    cleaned_text=cls.SAFE_PUBLIC_BOUNDARY_RESPONSE,
                    reasons=reasons,
                )

            # For path/schema disclosures, redact or substitute with safe boundary response
            cleaned_paths = _PATH_PATTERNS.sub("[internal_file]", text)
            cleaned_bare = _BARE_FILENAME_PATTERNS.sub("[internal_file]", cleaned_paths)
            cleaned_schema = _INTERNAL_SCHEMA_PATTERNS.sub("[internal_schema]", cleaned_bare)
            return DisclosureResult(
                action=DisclosureAction.REDACT,
                cleaned_text=cleaned_schema,
                reasons=reasons,
            )

        return DisclosureResult(action=DisclosureAction.ALLOW, cleaned_text=text, reasons=[])
