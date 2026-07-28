"""Global application exception handlers and middleware for FastAPI."""

from __future__ import annotations

import json
import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from src.exceptions.base import EngineError
from src.reliability.failure_policy import FailurePolicy
from src.telemetry_sink import log_error

logger = logging.getLogger("SC-EVM.RELIABILITY.ERROR_HANDLER")


class GlobalErrorHandler:
    """Centralized exception handler producing sanitized JSON responses for all unhandled HTTP failures."""

    @staticmethod
    async def handle_engine_error(request: Request, exc: EngineError) -> JSONResponse:
        """Handle typed EngineError exceptions."""
        logger.error(
            "EngineError occurred [%s]: %s",
            exc.error_code,
            exc,
            extra={
                "correlation_id": exc.correlation_id,
                "error_code": exc.error_code,
                "severity": exc.severity,
                "path": request.url.path,
                "internal_details": exc.internal_details,
            },
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        log_error(
            "api.engine_error",
            json.dumps(
                {
                    "error_code": exc.error_code,
                    "correlation_id": exc.correlation_id,
                    "path": request.url.path,
                }
            ),
        )
        status_code = GlobalErrorHandler._status_code_for_error(exc.error_code)
        return JSONResponse(
            status_code=status_code,
            content=exc.to_safe_dict(),
        )

    @staticmethod
    async def handle_generic_exception(request: Request, exc: Exception) -> JSONResponse:
        """Handle unhandled Python exceptions, TimeoutErrors, and ValidationErrors."""
        classified = FailurePolicy.classify_exception(exc)

        logger.error(
            "Unhandled exception occurred [%s]: %s",
            classified["code"],
            exc,
            extra={
                "correlation_id": classified["correlation_id"],
                "path": request.url.path,
                "error_type": type(exc).__name__,
            },
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        log_error(
            "api.generic_exception",
            json.dumps(
                {
                    "error_type": type(exc).__name__,
                    "path": request.url.path,
                    "error_code": classified["code"],
                }
            ),
        )
        status_code = GlobalErrorHandler._status_code_for_error(classified["code"])
        return JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "code": classified["code"],
                    "message": classified["message"],
                    "correlation_id": classified["correlation_id"],
                }
            },
        )

    @staticmethod
    def _status_code_for_error(error_code: str) -> int:
        status_map = {
            "SESSION_NOT_INITIALIZED": 404,
            "SESSION_EXPIRED": 410,
            "AUTHORIZATION_FAILURE": 403,
            "CONTEXT_VALIDATION_FAILURE": 400,
            "SANDBOX_VIOLATION": 400,
            "DISCLOSURE_BLOCKED": 400,
            "MODEL_PROVIDER_FAILURE": 503,
            "MODEL_TIMEOUT": 504,
            "TOOL_EXECUTION_FAILURE": 500,
            "WORKFLOW_EXECUTION_FAILURE": 500,
            "RATE_LIMIT_EXCEEDED": 429,
        }
        return status_map.get(error_code, 500)
