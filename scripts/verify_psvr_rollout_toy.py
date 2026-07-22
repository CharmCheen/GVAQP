#!/usr/bin/env python3
"""Verify the amended protocol state without executing any policy."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/psvr_rollout_preimplementation"


def load(name: str) -> dict:
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def main() -> None:
    amendment = load("PROTOCOL_AMENDMENT_D2_SPLIT.json")
    binding = load("D2_TOY_NUMERIC_BINDING.json")
    prereg = load("UPDATED_H_ROLLOUT1A_PREREGISTRATION.json")
    assert amendment["results_visible_at_amendment"] is False
    assert amendment["heldout_toy_results_visible"] is False
    assert amendment["d2_physical_numeric_binding"] == "BLOCKED_CALIBRATION_REQUIRED"
    assert binding["support_bounds"]["scan_complete_seconds_supremum"] == 56.5
    assert binding["support_bounds"]["confirm_complete_seconds_supremum"] == 13.75
    assert binding["physical_safety_claim"] is False
    assert prereg["execution_authorized"] is False
    assert prereg["status"] == "REBOUND_BUT_BLOCKED_INTERNAL_INCONSISTENCY"
    heldout_dir = OUT / "h_rollout1a_heldout"
    assert not heldout_dir.exists() or not any(heldout_dir.iterdir())
    print("PASS_AMENDMENT_BLOCKED_INTERNAL_INCONSISTENCY")


if __name__ == "__main__":
    main()

