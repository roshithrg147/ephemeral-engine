def strip_code_fences(text: str) -> str:
    """Remove fenced markdown wrappers from model JSON responses."""
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()
