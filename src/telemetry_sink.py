import json
import logging
import os
import threading
from datetime import UTC, datetime

from src.config import settings

logger = logging.getLogger("TelemetrySink")
AUDIT_LOG_PATH = settings.AUDIT_LOG_PATH
_audit_lock = threading.Lock()


def _append_audit_entry(entry: dict) -> None:
    if not settings.TELEMETRY_ENABLED:
        return
    directory = os.path.dirname(AUDIT_LOG_PATH)
    with _audit_lock:
        if directory:
            os.makedirs(directory, mode=0o700, exist_ok=True)
        if (
            os.path.exists(AUDIT_LOG_PATH)
            and os.path.getsize(AUDIT_LOG_PATH) >= settings.TELEMETRY_MAX_FILE_SIZE_BYTES
        ):
            old_path = AUDIT_LOG_PATH + ".old"
            if os.path.exists(old_path):
                os.remove(old_path)
            os.replace(AUDIT_LOG_PATH, old_path)
        descriptor = os.open(AUDIT_LOG_PATH, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "a", encoding="utf-8") as audit_file:
            audit_file.write(json.dumps(entry, ensure_ascii=False) + "\n")


def log_interaction(session_id: str, role: str, content: str) -> None:
    """Appends interaction events to a secure, immutable audit datastore.
    This runs in parallel to the volatile session storage and ensures that
    even if a session is burned, compliance logs are retained.
    """
    if not settings.TELEMETRY_ENABLED:
        return
    if settings.TELEMETRY_REDACT_CONTENT:
        import hashlib

        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        logged_content = f"[REDACTED; length={len(content)}; sha256={content_hash}]"
    else:
        logged_content = content
    try:
        _append_audit_entry(
            {
                "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "session_id": session_id,
                "role": role,
                "content": logged_content,
            }
        )
    except Exception as e:
        logger.error(f"Failed to append to telemetry sink for session {session_id}: {e}")


def log_error(context: str, error_msg: str) -> None:
    """Logs system failures to the secure telemetry sink."""
    if not settings.TELEMETRY_ENABLED:
        return
    try:
        _append_audit_entry(
            {
                "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "type": "error",
                "context": context,
                "error": error_msg,
            }
        )
    except Exception as e:
        logger.error(f"Failed to append error to telemetry sink: {e}")
