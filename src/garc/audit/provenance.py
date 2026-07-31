from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


REQUIRED_SOURCE_FIELDS = (
    "source_kind", "capture_session_id", "registration_utc", "known_parent_video",
    "known_derivation_operation", "target_event_information_used_for_selection",
    "video_sha256", "is_event_centered", "is_original_continuous_video",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_sidecar(video: Path) -> dict[str, Any]:
    sidecar = Path(str(video) + ".source.json")
    if not sidecar.exists():
        return {}
    value = json.loads(sidecar.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def audit_source(video: Path, source: dict[str, Any], session_ids: list[str]) -> dict[str, Any]:
    reasons = [f"MISSING_FIELD:{key}" for key in REQUIRED_SOURCE_FIELDS if key not in source]
    digest = sha256(video)
    if source.get("video_sha256") != digest:
        reasons.append("HASH_BINDING_MISMATCH")
    if source.get("source_kind") != "original_continuous_capture" or source.get("is_original_continuous_video") is not True:
        reasons.append("NOT_DECLARED_ORIGINAL_CONTINUOUS_CAPTURE")
    if source.get("known_parent_video") is not None or source.get("known_derivation_operation") is not None:
        reasons.append("DECLARED_DERIVATIVE")
    if source.get("is_event_centered") is not False:
        reasons.append("EVENT_CENTERED_NOT_FALSE")
    if source.get("target_event_information_used_for_selection") is not False:
        reasons.append("TARGET_SELECTION_NOT_FALSE")
    session = source.get("capture_session_id")
    if not isinstance(session, str) or not session.strip():
        reasons.append("INVALID_CAPTURE_SESSION_ID")
    elif session_ids.count(session) > 1:
        reasons.append("DUPLICATE_CAPTURE_SESSION_ID")
    try:
        parsed = datetime.fromisoformat(str(source.get("registration_utc", "")).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
    except ValueError:
        reasons.append("INVALID_REGISTRATION_UTC")
    return {"path": str(video), "sha256": digest, "failure_reasons": sorted(set(reasons)), "pass": not reasons}
