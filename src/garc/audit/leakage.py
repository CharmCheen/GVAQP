from __future__ import annotations

from garc.controller.state import PUBLIC_FIELDS


FORBIDDEN_STATE_TOKENS = frozenset({"video_id", "future_confirm_outcomes", "oracle_label", "reference_event"})


def audit_public_state(value: dict) -> dict:
    keys = set(value)
    forbidden = sorted(keys & FORBIDDEN_STATE_TOKENS)
    missing = sorted(PUBLIC_FIELDS - keys)
    extra = sorted(keys - PUBLIC_FIELDS)
    return {"pass": not forbidden and not missing and not extra,
            "forbidden": forbidden, "missing": missing, "extra": extra}
