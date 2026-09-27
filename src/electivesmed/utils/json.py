"""Lenient JSON extraction from LLM responses."""

import json
import re

from ..errors import LlmError

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def extract_json(raw: str) -> dict:
    """Parse a JSON object (or wrap a top-level array as {"items": [...]})."""
    cleaned = _FENCE_RE.sub("", raw).strip()
    try:
        parsed = json.loads(cleaned)
        return {"items": parsed} if isinstance(parsed, list) else parsed
    except json.JSONDecodeError:
        pass
    for opener, closer in (("{", "}"), ("[", "]")):
        start = cleaned.find(opener)
        end = cleaned.rfind(closer)
        if start != -1 and end > start:
            try:
                parsed = json.loads(cleaned[start : end + 1])
                if isinstance(parsed, list):
                    return {"items": parsed}
                return parsed
            except json.JSONDecodeError:
                continue
    raise LlmError(f"LLM did not return valid JSON: {cleaned[:200]!r}")
