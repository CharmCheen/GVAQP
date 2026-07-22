#!/usr/bin/env python3
"""H-TIE1 continuation guard: refuse physical registration until inputs exist."""

from __future__ import annotations

import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
AUDIT = REPO / "outputs/psvr_autonomous_research/cycle_06_H_TIE1/INPUT_AUDIT.json"


def main() -> None:
    audit = json.loads(AUDIT.read_text())
    available = audit["available"]
    if available["independent_sources_with_stable_complete_reference"] < 3 or available["fully_supported_queries_per_source"] < 2:
        missing = "; ".join(audit["missing"])
        raise RuntimeError(f"H-TIE1 remains blocked: {missing}. Update INPUT_AUDIT.json only from verified new assets.")
    raise RuntimeError("Inputs are marked available; implement and freeze DEV_TASK_SELECTION_PROTOCOL before physical execution.")


if __name__ == "__main__":
    main()
