"""Capability broker enforcing tool authorization, schema validation, sandboxing, and result sanitization."""

from __future__ import annotations

import logging
import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from src.security_context import SecurityContext
from src.tools import sandbox_fs

logger = logging.getLogger("SC-EVM.CapabilityBroker")

_SECRET_PATTERN = re.compile(
    r"(?i)(api[_-]?key|secret|password|bearer\s+[a-z0-9._-]+|ey[a-z0-9_-]{20,}\.[a-z0-9_-]{20,}\.[a-z0-9_-]{20,})",
    re.IGNORECASE,
)


class ToolExecutionRefusal(Exception):
    """Raised when a tool call violates security policy or workflow capability boundaries."""

    def __init__(self, reason: str, code: str = "TOOL_NOT_AUTHORIZED"):
        super().__init__(reason)
        self.reason = reason
        self.code = code


# --- Tool Argument Validation Schemas ---


class ListFilesSchema(BaseModel):
    glob: str | None = Field(default="*", max_length=256)
    max_results: int | None = Field(default=100, ge=1, le=1000)


class ReadFileSchema(BaseModel):
    file_path: str = Field(..., min_length=1, max_length=1024)


class SaveFileSchema(BaseModel):
    file_path: str = Field(..., min_length=1, max_length=1024)
    file_content: str = Field(..., max_length=1_000_000)


class RunCommandSchema(BaseModel):
    command: str = Field(..., min_length=1, max_length=1024)
    approval_granted: bool = Field(default=False)


class BurnSessionSchema(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128)
    approval_granted: bool = Field(default=False)


class CapabilityBroker:
    """Shared capability broker that validates, authorizes, executes, and sanitizes tool calls."""

    @staticmethod
    def filter_manifest_tools(sec_ctx: SecurityContext) -> list[str]:
        """Return the list of tool names authorized for the model's manifest under current workflow."""
        from src.capabilities.workflow_filter import CapabilityFilter

        manifest = CapabilityFilter.filter_manifest(sec_ctx)
        return manifest.allowed_tools

    @classmethod
    def execute_tool(
        cls,
        sec_ctx: SecurityContext,
        session_id: str,
        tool_name: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Authorize, validate, execute, and sanitize a proposed tool call."""
        payload = payload or {}

        # 1. Authorization check: Tool must be explicitly allowed by the WorkflowPolicy
        if not sec_ctx.is_tool_allowed(tool_name):
            logger.warning(
                "Tool call denied by CapabilityBroker",
                extra={
                    "tool": tool_name,
                    "workflow": sec_ctx.workflow.value,
                    "user_id": sec_ctx.user_id,
                },
            )
            return {
                "status": "denied",
                "code": "TOOL_NOT_AUTHORIZED",
                "message": f"Tool '{tool_name}' is not authorized under workflow {sec_ctx.workflow.value}",
            }

        # 2. Schema validation and execution per tool type
        try:
            if tool_name == "none":
                return {"status": "success", "message": "No action executed"}

            elif tool_name == "list_files":
                args = ListFilesSchema(**payload)
                dir_path = args.glob if args.glob and args.glob != "*" else "."
                entries = sandbox_fs.list_dir(
                    session_id,
                    dir_path,
                    tenant_id=sec_ctx.tenant_id,
                    owner_subject=sec_ctx.user_id,
                )
                if args.max_results and len(entries) > args.max_results:
                    entries = entries[: args.max_results]
                return {
                    "status": "success",
                    "files": entries,
                    "count": len(entries),
                }

            elif tool_name == "read_file":
                args = ReadFileSchema(**payload)
                content = sandbox_fs.read_text(
                    session_id,
                    args.file_path,
                    tenant_id=sec_ctx.tenant_id,
                    owner_subject=sec_ctx.user_id,
                )
                sanitized_content = cls._sanitize_tool_output(sec_ctx, content)
                return {
                    "status": "success",
                    "file_path": args.file_path,
                    "content": sanitized_content,
                }

            elif tool_name == "save_file":
                args = SaveFileSchema(**payload)
                sandbox_fs.write_text(
                    session_id,
                    args.file_path,
                    args.file_content,
                    tenant_id=sec_ctx.tenant_id,
                    owner_subject=sec_ctx.user_id,
                )
                return {
                    "status": "success",
                    "file_path": args.file_path,
                    "bytes_written": len(args.file_content.encode()),
                }

            elif tool_name == "run_command":
                args = RunCommandSchema(**payload)
                if sec_ctx.workflow_policy.approval_required and not args.approval_granted:
                    return {
                        "status": "approval_required",
                        "code": "EXPLICIT_APPROVAL_REQUIRED",
                        "message": f"Execution of shell command '{args.command}' requires explicit approval.",
                    }
                # Command execution is restricted to authorized privileged workflow
                return {
                    "status": "denied",
                    "code": "COMMAND_EXECUTION_RESTRICTED",
                    "message": "Arbitrary shell command execution is restricted.",
                }

            elif tool_name == "burn_session":
                args = BurnSessionSchema(**payload)
                if sec_ctx.workflow_policy.approval_required and not args.approval_granted:
                    return {
                        "status": "approval_required",
                        "code": "EXPLICIT_APPROVAL_REQUIRED",
                        "message": f"Burning session '{args.session_id}' requires explicit approval.",
                    }
                res = sandbox_fs.burn_session(
                    args.session_id,
                    tenant_id=sec_ctx.tenant_id,
                    owner_subject=sec_ctx.user_id,
                )
                return {
                    "status": "success",
                    "existed": res.existed,
                    "removed": res.removed,
                }

            else:
                return {
                    "status": "denied",
                    "code": "UNKNOWN_TOOL",
                    "message": f"Tool '{tool_name}' is unrecognised.",
                }

        except ValidationError as val_err:
            logger.warning("Tool payload schema validation failed", extra={"tool": tool_name, "error": str(val_err)})
            return {
                "status": "error",
                "code": "INVALID_TOOL_ARGUMENTS",
                "message": f"Tool '{tool_name}' arguments failed schema validation.",
            }
        except sandbox_fs.SandboxViolation as sb_exc:
            logger.warning("Sandbox violation in tool execution", extra={"tool": tool_name, "error": str(sb_exc)})
            return {
                "status": "denied",
                "code": "SANDBOX_VIOLATION",
                "message": "Requested operation escapes session sandbox boundary.",
            }
        except Exception:
            logger.exception("Unexpected error in tool execution", extra={"tool": tool_name})
            return {
                "status": "error",
                "code": "TOOL_EXECUTION_FAILED",
                "message": "Tool execution encountered an internal error.",
            }

    @classmethod
    def _sanitize_tool_output(cls, sec_ctx: SecurityContext, content: str) -> str:
        """Redact secrets and sensitive system info from tool results before returning to model."""
        if not content:
            return content

        # Replace any detected API key or JWT token patterns
        sanitized = _SECRET_PATTERN.sub("[REDACTED_SECRET]", content)

        # In non-internal disclosure workflows, strip absolute Linux paths
        if not sec_ctx.allow_internal_disclosure():
            sanitized = re.sub(r"/home/[a-zA-Z0-9_.-]+/", "/user_home/", sanitized)

        return sanitized
