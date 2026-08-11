from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_config(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if value.get("benchmark_id") != "SCAN_CONFIRM_DECISION_BENCHMARK_V1":
        raise ValueError("wrong benchmark config")
    return value

