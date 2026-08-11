from __future__ import annotations

import json
from pathlib import Path


def load_replay(path: Path) -> dict:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict) or "units" not in value or "confirm_outcomes" not in value:
        raise ValueError("replay manifest requires units and confirm_outcomes")
    return value
