import json
import re

class ConfirmResponseError(ValueError):
    pass

def _json_object(text):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    return json.loads(match.group(0))

def parse_confirm_response(text, clip_duration=None):
    """Frozen PSVR parser: preserve the source's permissive response policy."""
    try:
        value = _json_object(text)
        if value is None:
            return {}, "no_json"
        if str(value.get("label", "")).lower() not in {"positive", "negative", "abstain"}:
            return value, "invalid_label"
        if str(value.get("confidence", "")).lower() not in {"high", "medium", "low"}:
            return value, "invalid_confidence"
        return value, "ok"
    except Exception as exc:
        return {}, f"parse_error:{type(exc).__name__}"
