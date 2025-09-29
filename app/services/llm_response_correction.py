import json
import re

def extract_json_from_llm(raw):
    """
    Attempts to extract JSON from LLM output.
    - If raw is a dict, return it.
    - If wrapped in ```json ... ```, unwrap it.
    - If it doesn't look like JSON, return it as plain text.
    """
    # Already a dict?
    if isinstance(raw, dict):
        return raw

    if not isinstance(raw, str):
        raise TypeError("LLM response must be a string or dict.")

    raw = raw.strip()

    # Remove markdown ```json or ``` fences
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()

    # Try to parse JSON if it looks like JSON
    if cleaned.startswith("{") or cleaned.startswith("["):
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON from LLM output: {e}")

    # Otherwise, treat as plain string
    return cleaned