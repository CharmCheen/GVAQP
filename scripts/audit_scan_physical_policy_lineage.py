#!/usr/bin/env python3
"""Verify existing physical traces reproduce under the frozen trusted policies."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
for directory in (ROOT / "src", ROOT / "scripts"):
    sys.path.insert(0, str(directory))

from garc_eval.scan_headroom.trusted_policies import (  # noqa: E402
    PublicScanState,
    make_policy,
)
from partial_scan_pilot_common import SEED, atomic_json  # noqa: E402
from run_scan_optimization_headroom_audit import (  # noqa: E402
    IMM,
    PHYSICAL,
    public_units,
)


POLICY_IDS = (
    "SEQUENTIAL", "RANDOM_WITHOUT_REPLACEMENT",
    "UNIFORM_PREFIX", "ANYTIME_LARGEST_GAP",
)
OUT = ROOT / "outputs/scan_optimization_headroom_audit_v1"


def main() -> None:
    timeline = pd.read_csv(IMM / "timeline_units.csv")
    details = []
    for trace_path in sorted(PHYSICAL.glob("*/action_trace.jsonl")):
        rows = [json.loads(line) for line in trace_path.read_text().splitlines() if line.strip()]
        completed = [row for row in rows if row.get("action_completed")]
        first = rows[0]
        video_id = str(first["video_id"])
        policy_id = str(first["policy_id"])
        block_id = int(first["block_id"])
        units = timeline[timeline.video_id.eq(video_id)].sort_values("unit_index")
        policy = make_policy(
            policy_id, SEED + block_id * 100 + POLICY_IDS.index(policy_id)
        )
        scanned = []
        costs = []
        mismatches = []
        for row in completed:
            state = PublicScanState(
                units=public_units(units),
                scanned_unit_ids=tuple(scanned),
                current_unit_id=scanned[-1] if scanned else None,
                remaining_budget_sec=60.0 - sum(costs),
                past_action_costs_sec=tuple(costs),
            )
            predicted = policy.choose_next_unit(state)
            observed = str(row["selected_unit_id"])
            if predicted != observed:
                mismatches.append(
                    {"action_index": row["action_index"], "predicted": predicted, "observed": observed}
                )
            scanned.append(observed)
            costs.append(float(row["actual_action_cost_sec"]))
        details.append(
            {
                "run_id": first["run_id"], "completed_actions": len(completed),
                "mismatch_count": len(mismatches), "mismatches": mismatches,
            }
        )
    mismatch_count = sum(row["mismatch_count"] for row in details)
    payload = {
        "status": "PASS" if len(details) == 32 and mismatch_count == 0 else "FAIL",
        "run_count": len(details), "action_mismatch_count": mismatch_count,
        "comparison": "EXISTING_PHYSICAL_SELECTED_UNITS_VS_FROZEN_TRUSTED_POLICY_REPLAY",
        "public_inputs_only": True, "details": details,
    }
    atomic_json(OUT / "physical_policy_lineage_audit.json", payload)
    print(json.dumps({key: payload[key] for key in ["status", "run_count", "action_mismatch_count"]}, indent=2))


if __name__ == "__main__":
    main()
