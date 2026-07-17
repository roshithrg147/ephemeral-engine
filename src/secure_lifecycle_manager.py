import argparse
import json
import logging
import os
import sys
import tempfile

import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("SecureLifecycleManager")

REGISTRY_PATH = os.path.expanduser("~/.config/anthropic-agent/temp_previews.json")
PREVIEW_DIR = os.getenv(
    "SC_EVM_PREVIEW_DIR",
    os.path.join(tempfile.gettempdir(), f"sc-evm-previews-{os.getuid()}"),
)


def _is_managed_preview(path: str) -> bool:
    preview_root = os.path.realpath(PREVIEW_DIR)
    candidate = os.path.realpath(path)
    try:
        return os.path.commonpath([preview_root, candidate]) == preview_root
    except ValueError:
        return False


def _reset_registry_file() -> None:
    try:
        os.remove(REGISTRY_PATH)
        logger.info("Cleared temp previews registry file.")
    except Exception as e:
        logger.error(f"Failed to remove registry file {REGISTRY_PATH}: {e}")
        try:
            with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
                f.write("[]")
        except Exception as fallback_error:
            logger.error(f"Failed to truncate registry file {REGISTRY_PATH}: {fallback_error}")


def trigger_session_burn(api_url: str, session_id: str) -> bool:
    """
    Triggers the /api/session/burn/{session_id} DELETE request.
    Verifies that the response is 200 OK.
    """
    url = f"{api_url}/api/session/burn/{session_id}"
    try:
        logger.info(f"Sending DELETE request to burn session: {url}")
        response = httpx.delete(url, timeout=10.0)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                logger.info(f"FastAPI session burn reported SUCCESS for: {session_id}")
                return True
        logger.error(
            f"FastAPI session burn failed. Status code: {response.status_code}, Response: {response.text}"
        )
        return False
    except Exception as e:
        logger.error(f"HTTP request failed to burn session {session_id}: {e}")
        return False


def purge_local_temp_previews() -> int:
    """
    Reads the temp_previews.json registry and deletes all files registered.
    Wipes/truncates the registry file.
    """
    if not os.path.exists(REGISTRY_PATH):
        logger.info("No temporary preview files registry found. Nothing to purge.")
        return 0

    try:
        with open(REGISTRY_PATH, encoding="utf-8") as f:
            data = f.read().strip()
            if not data:
                return 0
            paths = json.loads(data)
    except Exception as e:
        logger.error(f"Failed to read temp previews registry file: {e}")
        return 0

    purged_count = 0
    for path in paths:
        if not isinstance(path, str) or not _is_managed_preview(path):
            logger.warning("Skipped unmanaged preview path from registry: %r", path)
            continue
        if os.path.exists(path):
            try:
                os.remove(path)
                logger.info(f"Purged preview file: {path}")
                purged_count += 1
            except Exception as e:
                logger.error(f"Failed to remove preview file {path}: {e}")
        else:
            logger.debug(f"Preview file already removed: {path}")

    _reset_registry_file()

    return purged_count


def main():
    parser = argparse.ArgumentParser(description="SC-EVM Secure Lifecycle Manager")
    parser.add_argument("--session-id", type=str, required=True, help="Session ID to destroy/burn")
    parser.add_argument(
        "--api-url", type=str, default="http://127.0.0.1:8000", help="FastAPI microservice base URL"
    )

    args = parser.parse_args()

    # 1. Trigger session heap burn
    burn_success = trigger_session_burn(args.api_url, args.session_id)

    # 2. Trigger local file cleanup regardless of FastAPI server status
    # (Clean desk policy requires local file destruction even if backend server is already down)
    purged_files = purge_local_temp_previews()

    if burn_success:
        print(
            json.dumps(
                {
                    "status": "success",
                    "message": "Session destroyed and local temp files purged successfully.",
                    "session_id": args.session_id,
                    "purged_files_count": purged_files,
                }
            )
        )
        sys.exit(0)
    else:
        print(
            json.dumps(
                {
                    "status": "partial_success",
                    "message": "Local files cleaned, but backend session heap burn failed.",
                    "session_id": args.session_id,
                    "purged_files_count": purged_files,
                }
            ),
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
