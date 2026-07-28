import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from src.exceptions.base import EngineError
from src.reliability.error_handler import GlobalErrorHandler

logger = logging.getLogger("SC-EVM.API")


class SafeErrorMapper:
    """Converts internal system exceptions into stable public error codes without disclosing stack traces."""

    _ERROR_CODE_MAP = {
        "AuthenticationError": ("ERR_UNAUTHENTICATED", 401, "Authentication is required or invalid."),
        "PermissionError": ("ERR_UNAUTHORIZED", 403, "The requested operation is forbidden."),
        "SandboxViolation": ("ERR_SANDBOX_VIOLATION", 400, "Requested path escapes session sandbox boundary."),
        "SessionNotInitialized": ("SESSION_NOT_INITIALIZED", 404, "Session state context is not initialized."),
        "KeyError": ("ERR_RESOURCE_NOT_FOUND", 404, "Requested resource could not be found."),
        "ValueError": ("ERR_INVALID_PAYLOAD", 400, "Invalid request payload or parameters."),
        "ValidationError": ("ERR_INVALID_PAYLOAD", 400, "Payload validation failed."),
    }

    @classmethod
    def map_exception(cls, exc: Exception) -> tuple[str, int, str]:
        if isinstance(exc, EngineError):
            status_code = GlobalErrorHandler._status_code_for_error(exc.error_code)
            return (exc.error_code, status_code, exc.safe_message)
        exc_type = type(exc).__name__
        if exc_type in cls._ERROR_CODE_MAP:
            return cls._ERROR_CODE_MAP[exc_type]
        return ("ERR_INTERNAL_SAFETY", 500, "An internal processing error occurred.")


class GlobalExceptionHandler:
    """Structured final boundary for unhandled FastAPI exceptions."""

    @staticmethod
    async def handle(request: Request, exc: Exception) -> JSONResponse:
        if isinstance(exc, EngineError):
            return await GlobalErrorHandler.handle_engine_error(request, exc)
        return await GlobalErrorHandler.handle_generic_exception(request, exc)
