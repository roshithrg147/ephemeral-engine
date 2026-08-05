import json
import re


def strip_code_fences(text: str) -> str:
    """Remove fenced markdown wrappers from model JSON responses."""
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()


def clean_structured_response(text: str) -> str:
    """Clean non-standard characters and convert markdown pipe tables into structured chat text."""
    if not text or not isinstance(text, str):
        return text if text is not None else ""

    cleaned = text.strip()

    # Unwrap JSON code blocks or raw JSON string dumps
    if cleaned.startswith("```"):
        cleaned = strip_code_fences(cleaned)

    if cleaned.startswith("{") and cleaned.endswith("}"):
        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                extracted = data.get("text") or data.get("message") or data.get("content")
                if extracted and isinstance(extracted, str):
                    cleaned = extracted.strip()
        except Exception:
            pass

    # Normalize unicode hyphens/dashes to standard hyphen, and smart quotes to standard quotes
    cleaned = re.sub(r"[\u2010\u2011\u2012\u2013\u2014\u2015]", "-", cleaned)
    cleaned = re.sub(r"[\u2018\u2019]", "'", cleaned)
    cleaned = re.sub(r"[\u201c\u201d]", '"', cleaned)

    lines = cleaned.splitlines()
    new_lines = []
    in_table = False
    headers = []

    for line in lines:
        stripped = line.strip()

        # Table divider check (e.g. |---|---|)
        if re.match(r"^\|?(\s*:?-+:?\s*\|)+\s*:?-+:?\s*\|?$", stripped):
            in_table = True
            continue

        # Table row check
        if "|" in stripped and (stripped.startswith("|") or stripped.endswith("|") or stripped.count("|") >= 2):
            parts = [p.strip() for p in stripped.strip("|").split("|")]

            # If headers not set or starting new table section
            if not headers or not in_table:
                headers = parts
                in_table = True
                continue

            first_col = parts[0] if parts else ""
            if len(parts) > 1 and first_col:
                new_lines.append("")
                new_lines.append(f"### {first_col}")
                for idx in range(1, len(parts)):
                    col_val = parts[idx]
                    if not col_val or col_val == "-":
                        continue
                    col_header = headers[idx] if idx < len(headers) else f"Field {idx+1}"
                    new_lines.append(f"* **{col_header}:** {col_val}")
            else:
                for idx, col_val in enumerate(parts):
                    if not col_val or col_val == "-":
                        continue
                    col_header = headers[idx] if idx < len(headers) else f"Field {idx+1}"
                    new_lines.append(f"* **{col_header}:** {col_val}")
        else:
            in_table = False
            headers = []
            new_lines.append(line)

    result = "\n".join(new_lines).strip()
    return re.sub(r"\n{3,}", "\n\n", result)

