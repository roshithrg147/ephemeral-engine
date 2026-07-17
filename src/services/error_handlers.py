import json
import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from src.telemetry_sink import log_error

logger = logging.getLogger("SC-EVM.API")


class GlobalExceptionHandler:
    """Structured final boundary for unhandled FastAPI exceptions."""

    @staticmethod
    async def handle(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "Unhandled request failure",
            extra={
                "path": request.url.path,
                "method": request.method,
                "client": request.client.host if request.client else None,
            },
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        log_error(
            "api.unhandled_exception",
            json.dumps(
                {
                    "path": request.url.path,
                    "method": request.method,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            ),
        )
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Internal server error"},
        )
