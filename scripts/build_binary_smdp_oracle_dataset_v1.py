#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from garc_eval.scan_confirm_controller.smdp_dataset import (  # noqa: E402
    BehaviorPolicy,
    collect_behavior_states,
    labeled_state_row,
)
from garc_eval.scan_confirm_controller.smdp_oracle import (  # noqa: E402
    ExternalCalibrationSafeTraceReplayEnvironment,
    conditioned_action_values,
)

OUT = ROOT / "outputs/binary_smdp_value_v1"
TASKS = ("V0_Q1", "V0_Q2", "V1_Q1", "V1_Q2")
BUDGETS = (30.0, 60.0, 120.0, 240.0)


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_parquet(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_parquet(temporary, index=False)
    os.replace(temporary, path)


def git_state() -> dict[str, object]:
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    status = subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True).splitlines()
    return {"commit": commit, "dirty": bool(status), "status": status}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--beam-widths", default="128,512,2048")
    parser.add_argument("--tasks", default=",".join(TASKS))
    parser.add_argument("--budgets", default=",".join(str(x) for x in BUDGETS))
    parser.add_argument("--max-states", type=int)
    parser.add_argument("--pilot", action="store_true", help="write pilot artifacts without replacing the formal dataset")
    args = parser.parse_args()
    widths = tuple(int(x) for x in args.beam_widths.split(",") if x)
    if not args.pilot and widths != (128, 512, 2048):
        raise SystemExit("formal dataset requires frozen beam widths 128,512,2048")
    tasks = tuple(x for x in args.tasks.split(",") if x)
    budgets = tuple(float(x) for x in args.budgets.split(",") if x)
    policies = [
        BehaviorPolicy("SCAN_FIRST"),
        BehaviorPolicy("VERIFY_FIRST"),
        BehaviorPolicy("RATIO_75_25"),
        BehaviorPolicy("RATIO_50_50"),
        BehaviorPolicy("R4_RATIO_25_75"),
        BehaviorPolicy("ALTERNATING"),
        BehaviorPolicy("FRONTIER_RULE"),
        *(BehaviorPolicy("RANDOM_LEGAL", seed) for seed in (0, 1, 2)),
        BehaviorPolicy("MYOPIC_VPS"),
    ]
    started = time.time()
    behavior_safety_failures = []
    states = collect_behavior_states(
        ExternalCalibrationSafeTraceReplayEnvironment,
        tasks=tasks,
        budgets=budgets,
        policies=policies,
        safety_failures=behavior_safety_failures,
    )
    ordered = sorted(states.values(), key=lambda row: (row.video_id, row.query_id, row.budget_sec, row.state_hash))
    if args.max_states is not None:
        ordered = ordered[: args.max_states]
    rows = []
    failures = []
    for index, state in enumerate(ordered):
        try:
            env = state.materialize()
            values = conditioned_action_values(env, beam_widths=widths)
            rows.append(labeled_state_row(state, env, values))
        except Exception as exc:  # retain failures; never silently delete a state
            failures.append({"state_hash": state.state_hash, "error_type": type(exc).__name__, "error": str(exc)})
        print(f"[{index + 1}/{len(ordered)}] rows={len(rows)} failures={len(failures)}", flush=True)
    frame = pd.DataFrame(rows)
    dataset_dir = OUT / ("dataset/pilot" if args.pilot else "dataset")
    atomic_parquet(dataset_dir / "state_action_values.parquet", frame)
    manifest = {
        "artifact_status": "PILOT" if args.pilot else "FORMAL",
        "command": " ".join(sys.argv),
        "tasks": tasks,
        "budgets_sec": budgets,
        "beam_widths": widths,
        "behavior_policies": [{"name": p.name, "seed": p.seed} for p in policies],
        "states_collected_total": len(states),
        "states_selected": len(ordered),
        "states_labeled": len(rows),
        "failures": failures,
        "behavior_safety_failures": behavior_safety_failures,
        "behavior_safety_failure_count": len(behavior_safety_failures),
        "label_counts": frame.label_class.value_counts(dropna=False).to_dict() if len(frame) else {},
        "stable_labels": int(frame.label_stable.sum()) if len(frame) else 0,
        "exact_labels": int(frame.oracle_exact.sum()) if len(frame) else 0,
        "imputed_cost_rows": int((frame.confirm_cost_imputed_fraction > 0).sum()) if len(frame) else 0,
        "runtime_sec": time.time() - started,
        "random_seeds": [0, 1, 2],
        "git": git_state(),
    }
    atomic_json(dataset_dir / "dataset_manifest.json", manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
