"""CapabilityFilter building workflow-specific capability manifests prior to model invocation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.capabilities.registry import ALL_CAPABILITIES
from src.workflow_policy import WorkflowClass

if TYPE_CHECKING:
    from src.security_context import SecurityContext


@dataclass(frozen=True, slots=True)
class AllowedCapabilityManifest:
    workflow: str
    allowed_capabilities: list[str]
    forbidden_capabilities: list[str]
    allowed_tools: list[str]


class CapabilityFilter:
    """Filters capability manifests and tool availability strictly per security context workflow."""

    FORBIDDEN_PUBLIC_CAPABILITIES: frozenset[str] = frozenset({
        "list_files",
        "read_file",
        "save_file",
        "search_repository",
        "execute_command",
        "inspect_logs",
        "read_memory",
        "code_analysis",
        "run_command",
        "burn_session",
        "run_tests",
    })

    @classmethod
    def filter_manifest(cls, sec_ctx: SecurityContext) -> AllowedCapabilityManifest:
        workflow = sec_ctx.workflow

        allowed_caps: list[str] = []
        forbidden_caps: list[str] = []

        for cap_name, cap_def in ALL_CAPABILITIES.items():
            if workflow in cap_def.allowed_workflows:
                allowed_caps.append(cap_name)
            else:
                forbidden_caps.append(cap_name)

        if workflow in (WorkflowClass.PUBLIC_CHAT, WorkflowClass.PUBLIC_RESEARCH):
            for forbidden in cls.FORBIDDEN_PUBLIC_CAPABILITIES:
                if forbidden not in forbidden_caps:
                    forbidden_caps.append(forbidden)
                if forbidden in allowed_caps:
                    allowed_caps.remove(forbidden)

        # Tools allowed by workflow policy
        policy_tools = sorted(list(sec_ctx.workflow_policy.allowed_tools))
        # Include 'none' if present in policy tools or filter against capability manifest
        filtered_tools = [t for t in policy_tools if t in allowed_caps or t == "none"]

        return AllowedCapabilityManifest(
            workflow=workflow.value,
            allowed_capabilities=sorted(allowed_caps),
            forbidden_capabilities=sorted(forbidden_caps),
            allowed_tools=filtered_tools,
        )
