import logging
import subprocess

logger = logging.getLogger("GraphifyBridge")


def get_structural_context(entity_id: str) -> str:
    """
    Executes a strict structural lookup via the graphify CLI to replace fuzzy
    vector similarity with deterministic Abstract Syntax Tree (AST) context.
    """
    if not entity_id:
        return ""

    try:
        # Run `graphify query` to fetch structural data for the given entity
        result = subprocess.run(
            ["graphify", "query", f"What are the dependencies and usages of {entity_id}?"],
            capture_output=True,
            text=True,
            timeout=15,
        )

        if result.returncode == 0 and result.stdout:
            return result.stdout.strip()
        else:
            logger.warning(
                f"Graphify query failed or returned empty for {entity_id}. Code: {result.returncode}, Error: {result.stderr}"
            )
            return ""

    except subprocess.TimeoutExpired:
        logger.error(f"Graphify query timed out for {entity_id}.")
        return ""
    except FileNotFoundError:
        logger.error("Graphify CLI is not installed or not found on system PATH.")
        return ""
    except Exception as e:
        logger.error(f"Unexpected error executing graphify bridge: {e}", exc_info=True)
        return ""
