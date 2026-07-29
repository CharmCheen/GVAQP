#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/binary_smdp_value_v1"


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def main() -> None:
    pilot_manifest = json.loads((OUT / "dataset/pilot/dataset_manifest.json").read_text())
    informative = json.loads((OUT / "oracle_headroom/informative_state_pilot.json").read_text())
    old_gate = json.loads((ROOT / "outputs/scan_confirm_decision_v1/metrics/gate_decision.json").read_text())
    physical_profile = pd.read_csv(ROOT / "outputs/psvr_stage0b_physical_profile/operator_latency_summary.csv")
    physical_verify_rows = physical_profile.query("operator == 'physical_verify'")
    if len(physical_verify_rows) != 1:
        raise ValueError(
            "expected exactly one physical_verify calibration row, "
            f"found {len(physical_verify_rows)}"
        )
    physical_verify = physical_verify_rows.iloc[0].to_dict()

    # Preserve the required dataset location without relabeling a bounded pilot
    # as a completed formal dataset.
    pilot_frame = pd.read_parquet(OUT / "dataset/pilot/state_action_values.parquet")
    formal_path = OUT / "dataset/state_action_values.parquet"
    formal_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = formal_path.with_suffix(".parquet.tmp")
    pilot_frame.to_parquet(temporary, index=False)
    os.replace(temporary, formal_path)

    git_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    safety_failure_count = int(pilot_manifest["behavior_safety_failure_count"])
    if safety_failure_count <= 0:
        raise ValueError("headroom-stop audit requires an observed safety failure")
    if bool(informative["oracle_exact"]):
        raise ValueError("headroom-stop audit expected the informative pilot to be approximate")
    dataset_manifest = {
        "artifact_status": "INCOMPLETE_HEADROOM_GATE_STOP",
        "source": "dataset/pilot/state_action_values.parquet",
        "rows": len(pilot_frame),
        "videos": sorted(pilot_frame.video_id.unique().tolist()),
        "queries": sorted(pilot_frame.query_id.unique().tolist()),
        "budgets_sec": sorted(float(x) for x in pilot_frame.budget_sec.unique()),
        "label_counts": pilot_frame.label_class.value_counts().to_dict(),
        "stable_labels": int(pilot_frame.label_stable.sum()),
        "exact_labels": int(pilot_frame.oracle_exact.sum()),
        "behavior_safety_failure_count": safety_failure_count,
        "missing_requirements": [
            "full four-group/four-budget conditioned labels",
            "complete non-imputed V0 per-unit costs",
            "causal cost bound with zero replay overrun",
            "both SCAN_BETTER and VERIFY_BETTER across multiple videos",
        ],
        "stop_reason": "preregistered headroom/safety gate failed before expensive full labeling",
        "git_commit": git_commit,
    }
    atomic_json(OUT / "dataset/dataset_manifest.json", dataset_manifest)

    gate = {
        "decision": "INSUFFICIENT_EVIDENCE",
        "learning_mainline_authorized": False,
        "gates": {
            "stable_oracle_headroom_over_r4": False,
            "both_actions_informative": False,
            "multiple_video_contribution": False,
            "leave_best_video_out_positive": False,
            "nonnegative_low_budget": False,
            "zero_deadline_overrun": False,
            "top_candidate_pathology_excluded": False,
        },
        "observed": {
            "conditioned_scan_better_states": 1,
            "conditioned_verify_better_states": 0,
            "conditioned_tied_states": int((pilot_frame.label_class == "EFFECTIVELY_TIED").sum()),
            "informative_state_delta_anytime": informative["delta_anytime"],
            "informative_state_exact": informative["oracle_exact"],
            "behavior_deadline_overruns": safety_failure_count,
            "v0_imputed_confirm_cost_units": {"V0_Q1": 345, "V0_Q2": 346},
            "independent_physical_verify_n": int(physical_verify["n"]),
            "independent_physical_verify_max_sec": float(physical_verify["max_seconds"]),
            "evaluated_v1_confirm_max_sec": 44.19692327167054,
        },
        "historical_context": {
            "strongest_fixed": old_gate.get("strongest_fixed", "R4_RATIO_25_75"),
            "r4_macro_auc": 187.5,
            "old_width16_multi_step_oracle_auc": 281.25,
            "old_oracle_comparable": False,
            "common_utility_static_gate": "FAIL",
        },
        "evidence_files": [
            "dataset/pilot/dataset_manifest.json",
            "oracle_headroom/informative_state_pilot.json",
            "outputs/scan_confirm_decision_v1/reports/FINAL_DECISION.md",
            "outputs/scan_confirm_common_utility_v1/reports/FINAL_DECISION.md",
            "outputs/psvr_stage0b_physical_profile/operator_latency_summary.csv",
        ],
    }
    atomic_json(OUT / "oracle_headroom/gate_decision.json", gate)
    report = """# Binary SMDP oracle headroom report

Decision: `INSUFFICIENT_EVIDENCE`
Learning mainline: `NOT_AUTHORIZED`

## Strongest supported conclusion

The conditioned SMDP implementation exposes a plausible long-horizon timing
effect, but the current evidence cannot establish safe oracle headroom over R4.
In one V1_Q2/120 state, SCAN-first and VERIFY-first both reached one event while
SCAN-first improved AnytimeAUC by 0.144552. The label agreed at beam widths
128/512/2048, but was approximate because admitted transitions overran.

The decisive counterevidence is deadline safety: 9 of 11 V1_Q1/60 behavior
rollouts admitted a VERIFY that completed after the deadline. Two-phase commit
correctly prevented post-deadline event/Frontier updates, so the gain is not
manufactured, but the public bound is unusable as a safety shield. The
independent same-model valid physical profile has 20 calls and maximum 16.063 s,
whereas the evaluated V1 trace contains a 44.197 s complete CONFIRM. Selecting a
larger factor after observing V1 would be post-hoc leakage, not frozen causal
calibration.

## Required questions

1. **Does the oracle stably exceed R4?** Not established. Historical width-16
   multi-step AUC (281.25 versus R4 187.5) used the old unsafe Q90 contract and
   is not the new conditioned oracle. The new informative state is stable but
   approximate and unsafe.
2. **Does it select both actions?** One SCAN-better and four tied states are
   observed; no VERIFY-better state is established.
3. **Is headroom multi-video?** No. V1 supplies the new value evidence; V0 is
   missing 345/347 and 346/347 per-unit costs for its two queries.
4. **Is leave-best-video-out positive?** Not evaluable.
5. **Is low-budget behavior nonnegative?** No safety claim is possible: nine
   60-second behavior runs overran, with zero post-deadline commits.
6. **Is top-candidate pathology excluded?** No. Only the frozen top candidate
   was evaluated and the safe multi-video comparison is unavailable.

## Competing explanation and uncertainty

The observed SCAN advantage may be genuine early-discovery option value, but it
may also depend on a single video/query state and evaluator rejection of unsafe
continuations. The decision-critical missing evidence is a frozen, independent
complete-action cost calibration that covers tail latency without reading the
evaluated video, plus complete V0 replay costs.

## Stop action

Per the frozen contract, full dataset labeling, PUBLIC model comparison, MLP/
LightGBM training, replay aggregation and learned-controller claims stop here.
The bounded dataset is retained with status
`INCOMPLETE_HEADROOM_GATE_STOP`; it is not renamed as a formal cross-video
dataset. Revision requires new independent cost calibration and non-imputed V0
cost evidence, after which the headroom gate must be rerun unchanged.
"""
    atomic_text(OUT / "reports/ORACLE_HEADROOM_REPORT.md", report)
    for directory in (
        "state_sufficiency", "models", "static_value_validation", "closed_loop_replay", "ablations"
    ):
        atomic_json(OUT / directory / "STATUS.json", {
            "status": "NOT_RUN_HEADROOM_GATE_FAILED",
            "decision": "INSUFFICIENT_EVIDENCE",
        })
    print(json.dumps(gate, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
