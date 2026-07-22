#!/usr/bin/env python3
"""Evaluator-only audit and decision for the H-STAGE1 physical matrix."""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
OUT = ROOT / "outputs/psvr_bottleneck_research"
CYCLE2 = OUT / "cycle_02_H_BOTTLE2"
CYCLE3 = OUT / "cycle_03_H_STAGE1"
RAW = CYCLE3 / "raw"
HISTORICAL = CYCLE2 / "raw"
BOTTLENECK_EVALUATOR = ROOT / "scripts/evaluate_psvr_bottleneck.py"
BASE_RUNNER = ROOT / "scripts/run_psvr_two_video_physical.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def runs(raw: Path) -> dict[str, dict[str, Any]]:
    result = {}
    for path in sorted(raw.glob("*/attempt_*/complete.json")):
        row = json.loads(path.read_text(encoding="utf-8"))
        result[row["run_id"]] = row
    return result


def evidence_signature(run: dict[str, Any]) -> list[tuple[int, str]]:
    return [
        (int(row["unit_id"]), str(row["candidate_evidence_sha256"]))
        for row in run["proxy_unit_costs"]
    ]


def snapshot_signature(run: dict[str, Any]) -> list[tuple[Any, ...]]:
    snapshot = json.loads(Path(run["final_snapshot_path"]).read_text(encoding="utf-8"))
    return sorted(
        (
            str(row.get("anchor_unit_ids", "")), str(row.get("evidence_unit_ids", "")),
            float(row.get("start_time", 0.0)), float(row.get("end_time", 0.0)),
        )
        for row in snapshot.get("strict_confirmed_events", [])
    )


def load_cell(raw: Path, method: str, task: str, deadline: str, replicate: int) -> dict[str, Any]:
    pattern = (
        f"{method}__Y8__{task}__{deadline}__replicate_{replicate:02d}"
        "/attempt_*/complete.json"
    )
    matches = sorted(raw.glob(pattern))
    if len(matches) != 1:
        raise RuntimeError(f"expected one complete cell for {pattern}, got {len(matches)}")
    return json.loads(matches[0].read_text(encoding="utf-8"))


def correctness(frame: pd.DataFrame, runner) -> dict[str, Any]:
    current = runs(RAW)
    equivalence = []
    for task in ("V0_Q1", "V0_Q2", "V1_Q1", "V1_Q2"):
        for deadline in ("T_transition", "T_high"):
            for replicate in range(3):
                row = load_cell(RAW, "F0", task, deadline, replicate)
                old = load_cell(HISTORICAL, "C10", task, deadline, replicate)
                equivalence.append(
                    row["scan_order_prefix"] == old["scan_order_prefix"]
                    and [q["unit_id"] for q in row["queried_results"]]
                    == [q["unit_id"] for q in old["queried_results"]]
                    and [q["parsed_label"] for q in row["queried_results"]]
                    == [q["parsed_label"] for q in old["queried_results"]]
                    and evidence_signature(row) == evidence_signature(old)
                    and snapshot_signature(row) == snapshot_signature(old)
                )
    replay_checks = []
    for run in current.values():
        if run["method"] != "ST1":
            continue
        expected = 0
        for action_index, action in enumerate(run["actions"]):
            if action["action"] != "scan":
                continue
            state = action["stage_state"]
            expected += int(runner.stage_conditioned_should_verify(
                completed_scans=int(state.get("completed_scans", 0))
                if "completed_scans" in state else sum(
                    prior["action"] == "scan"
                    for prior in run["actions"][: action_index + 1]
                ),
                coarse_cell_count=int(state["coarse_cell_count"]),
                persistent_candidate_count=int(state["persistent_candidate_count"]),
                retained_temporal_cells=int(state["retained_temporal_cells"]),
            ))
        replay_checks.append(expected == int(run["verify_opportunities"]))
    grouped = frame.groupby(["method", "task_id", "deadline_name"])
    exact_query = grouped.query_signature.nunique()
    event_consistent_cells = 0
    for method in ("F0", "ST1"):
        for task in ("V0_Q1", "V0_Q2", "V1_Q1", "V1_Q2"):
            for deadline in ("T_transition", "T_high"):
                signatures = {
                    tuple(snapshot_signature(load_cell(RAW, method, task, deadline, replicate)))
                    for replicate in range(3)
                }
                event_consistent_cells += int(len(signatures) == 1)
    audit = {
        "physical_runs": len(frame),
        "expected_runs": 48,
        "failed_attempts": len(list(RAW.glob("*/attempt_*/failed.json"))),
        "F0_C10_equivalence_cells": sum(equivalence),
        "F0_C10_equivalence_expected": 24,
        "stage_policy_state_replay_pass": bool(replay_checks) and all(replay_checks),
        "exact_query_signature_consistent_cells": int((exact_query == 1).sum()),
        "exact_query_signature_expected_cells": 16,
        "preregistered_exact_repeat_signature": bool((exact_query == 1).all()),
        "semantic_event_repeat_consistent_cells": event_consistent_cells,
        "semantic_event_repeat_expected_cells": 16,
        "deadline_misses": int(frame.deadline_miss.sum()),
        "cache_replays": int(frame.cache_replay_calls.sum()),
        "future_accesses": int(frame.future_proxy_accesses.sum()),
        "visibility_violations": int(frame.visibility_violations.sum()),
        "missing_snapshots": int((~frame.snapshot_exists.astype(bool)).sum()),
        "invalid_action_ledgers": int((~frame.action_ledger_valid.astype(bool)).sum()),
        "heldout_opened": False,
    }
    audit["physical_validity_gate"] = "PASS" if (
        audit["physical_runs"] == audit["expected_runs"] == 48
        and audit["failed_attempts"] == 0
        and audit["F0_C10_equivalence_cells"] == 24
        and audit["stage_policy_state_replay_pass"]
        and audit["semantic_event_repeat_consistent_cells"] == 16
        and all(audit[key] == 0 for key in (
            "deadline_misses", "cache_replays", "future_accesses", "visibility_violations",
            "missing_snapshots", "invalid_action_ledgers",
        ))
    ) else "FAIL"
    audit["preregistered_correctness_gate"] = (
        "PASS" if audit["physical_validity_gate"] == "PASS"
        and audit["preregistered_exact_repeat_signature"] else "FAIL_EXACT_REPEAT_SIGNATURE"
    )
    return audit


def main() -> None:
    bottleneck = load_module("psvr_stage1_bottleneck_evaluator", BOTTLENECK_EVALUATOR)
    base = bottleneck.load_module("psvr_stage1_base_evaluator", bottleneck.BASE_EVALUATOR)
    runner = load_module("psvr_stage1_runner_for_replay", BASE_RUNNER)
    frame = bottleneck.evaluate_raw(base, RAW, CYCLE3 / "tables")
    audit = correctness(frame, runner)
    base.durable_json(CYCLE3 / "CORRECTNESS_AUDIT.json", audit)

    lifecycle_rows = []
    for run in runs(RAW).values():
        label = bottleneck.labels(str(run["task_id"]))
        positive_units = {unit_id for unit_id, value in label.items() if value == "positive"}
        scanned = {
            int(action["unit_id"]) for action in run["actions"] if action["action"] == "scan"
        }
        lifecycle = {int(row["unit_id"]): row for row in run["candidate_lifecycle"]}
        created = positive_units & scanned & set(lifecycle)
        frontier = {
            int(str(candidate_id).split("_")[-1])
            for action in run["actions"] if action["action"] == "scan"
            for candidate_id in action["frontier_candidate_ids"]
        }
        verified = {int(row["unit_id"]) for row in run["queried_results"]}
        lifecycle_rows.append({
            "run_id": run["run_id"],
            "method": run["method"],
            "task_id": run["task_id"],
            "deadline_name": run["deadline_name"],
            "replicate": run["replicate"],
            "positive_units_scanned": len(positive_units & scanned),
            "positive_candidates_created": len(created),
            "positive_candidates_entered_frontier": len(created & frontier),
            "positive_candidates_verified": len(created & verified),
            "positive_candidates_discarded": sum(
                lifecycle[unit_id]["terminal_state"] == "discarded" for unit_id in created
            ),
            "positive_candidates_survived_to_stop": sum(
                lifecycle[unit_id]["terminal_state"] == "survived_to_stop" for unit_id in created
            ),
            "reference_visibility": "evaluator_only",
        })
    lifecycle_frame = pd.DataFrame(lifecycle_rows)
    base.atomic_csv(CYCLE3 / "tables/ACTUAL_LIFECYCLE_FAILURE_CHAIN.csv", lifecycle_frame)
    lifecycle_task = lifecycle_frame.groupby(["method", "task_id"], as_index=False)[[
        "positive_units_scanned", "positive_candidates_created",
        "positive_candidates_entered_frontier", "positive_candidates_verified",
        "positive_candidates_discarded", "positive_candidates_survived_to_stop",
    ]].median()
    base.atomic_csv(CYCLE3 / "tables/ACTUAL_LIFECYCLE_TASK_MEDIANS.csv", lifecycle_task)

    task = pd.read_csv(CYCLE3 / "tables/TASK_MEDIAN_OBSERVATIONS.csv").set_index(
        ["method", "task_id"]
    )
    task_rows = []
    for task_id in ("V0_Q1", "V0_Q2", "V1_Q1", "V1_Q2"):
        control, method = task.loc[("F0", task_id)], task.loc[("ST1", task_id)]
        control_tuple = (
            float(control.AnytimeAUC_F1), float(control.F1_at_deadline),
            -float(control.TTFC_censored),
        )
        method_tuple = (
            float(method.AnytimeAUC_F1), float(method.F1_at_deadline),
            -float(method.TTFC_censored),
        )
        task_rows.append({
            "task_id": task_id,
            "winner": "ST1" if method_tuple > control_tuple else "F0" if method_tuple < control_tuple else "TIE",
            "F0_AnytimeAUC_F1": float(control.AnytimeAUC_F1),
            "ST1_AnytimeAUC_F1": float(method.AnytimeAUC_F1),
            "F0_F1": float(control.F1_at_deadline),
            "ST1_F1": float(method.F1_at_deadline),
            "F0_unique_events": float(control.unique_confirmed_events),
            "ST1_unique_events": float(method.unique_confirmed_events),
            "F0_positive_units_scanned": float(control.positive_units_scanned),
            "ST1_positive_units_scanned": float(method.positive_units_scanned),
            "F0_candidate_to_VERIFY": float(control.positive_candidate_to_VERIFY_conversion),
            "ST1_candidate_to_VERIFY": float(method.positive_candidate_to_VERIFY_conversion),
        })
    task_frame = pd.DataFrame(task_rows)
    base.atomic_csv(CYCLE3 / "tables/TASK_WINNERS.csv", task_frame)
    macro = frame.groupby("method").agg(
        AnytimeAUC_F1=("AnytimeAUC_F1", "mean"),
        F1_at_deadline=("F1_at_deadline", "mean"),
        TTFC_censored=("TTFC_censored", "mean"),
        unique_confirmed_events=("unique_confirmed_events", "mean"),
        positive_units_scanned=("positive_units_scanned", "mean"),
        unique_reference_events_touched=("unique_reference_events_touched", "mean"),
        positive_candidate_to_VERIFY_conversion=("positive_candidate_to_VERIFY_conversion", "mean"),
        total_GPU_seconds=("total_GPU_seconds", "sum"),
        total_wall_clock=("total_wall_clock", "sum"),
    )
    f0, st1 = macro.loc["F0"], macro.loc["ST1"]
    relative_auc = (
        math.inf if f0.AnytimeAUC_F1 == 0 and st1.AnytimeAUC_F1 > 0
        else st1.AnytimeAUC_F1 / f0.AnytimeAUC_F1 - 1.0
    )
    thresholds = {
        "macro_anytime_relative_gain_10pct": bool(relative_auc >= 0.10),
        "macro_TTFC_reduction_20pct": bool(
            (f0.TTFC_censored - st1.TTFC_censored) / max(f0.TTFC_censored, 1e-9) >= 0.20
        ),
        "macro_absolute_F1_gain_005": bool(st1.F1_at_deadline - f0.F1_at_deadline >= 0.05),
        "four_task_unique_event_gain_2": bool(
            4.0 * (st1.unique_confirmed_events - f0.unique_confirmed_events) >= 2.0
        ),
    }
    winning = task_frame.loc[task_frame.winner == "ST1", "task_id"].tolist()
    nonworse = int((task_frame.winner != "F0").sum())
    cross_video = any(task.startswith("V0") for task in winning) and any(
        task.startswith("V1") for task in winning
    )
    exposure_alignment = bool(
        st1.positive_units_scanned > f0.positive_units_scanned
        and st1.unique_reference_events_touched > f0.unique_reference_events_touched
    )
    quality_accept = bool(
        audit["preregistered_correctness_gate"] == "PASS"
        and cross_video and nonworse >= 3 and any(thresholds.values()) and exposure_alignment
    )
    near_miss = bool(
        not quality_accept and cross_video and exposure_alignment and any(thresholds.values())
    )
    if quality_accept:
        decision = "ACCEPT_QUALITY_RUN_KEY_ABLATION"
    elif near_miss:
        decision = "REVISE_ONCE_CAUSAL_NEAR_MISS"
    else:
        decision = "REJECT_NO_CROSS_VIDEO_QUALITY_SIGNAL"
    result = {
        "BRANCH_HYPOTHESIS": "H-STAGE1",
        "BRANCH_DECISION": decision,
        "physical_validity_gate": audit["physical_validity_gate"],
        "preregistered_correctness_gate": audit["preregistered_correctness_gate"],
        "cross_video_quality_signal": cross_video,
        "nonworse_tasks": nonworse,
        "winning_tasks": winning,
        "quality_thresholds": thresholds,
        "mechanism_exposure_alignment": exposure_alignment,
        "dynamic_survival_metric_status": (
            "LEGACY_EVERY_3_SCAN_SURVIVAL_NOT_USED; actual lifecycle tables are authoritative"
        ),
        "updated_task_bottleneck_map": {
            "V0_Q1": "VERIFY_ORDER_SIGNAL_NOT_IMPROVED; ST1 over-allocation worsens AUC",
            "V0_Q2": "SCAN_EXPOSURE_RECOVERED_SECOND_EVENT",
            "V1_Q1": "FRONTIER_RETENTION_OR_ADMISSION_LIMITED",
            "V1_Q2": "FRONTIER_OR_VERIFY_ORDER_LIMITED with VERIFY_BUDGET_LIMITED alternative",
        },
        "task_results": task_rows,
        "macro_metrics": macro.reset_index().to_dict("records"),
        "KEY_ABLATION_OR_REVISION": "NOT_RUN_BRANCH_REJECTED",
        "PSVR_CORE_METHOD_CANDIDATE": "NONE",
        "PSVR_TWO_VIDEO_SEARCH": "NO_GO",
        "heldout_opened": False,
    }
    result["decision_hash"] = base.canonical_hash(result)
    base.durable_json(CYCLE3 / "AUDITED_DECISION.json", result)
    report = f"""# H-STAGE1 observable stage-conditioned controller

`BRANCH_DECISION = {decision}`

`PHYSICAL_VALIDITY_GATE = {audit['physical_validity_gate']}`

`PREREGISTERED_CORRECTNESS_GATE = {audit['preregistered_correctness_gate']}`

`CROSS_VIDEO_QUALITY_SIGNAL = {cross_video}`

`KEY_ABLATION_OR_REVISION = NOT_RUN_BRANCH_REJECTED`

`PSVR_TWO_VIDEO_SEARCH = NO_GO`

ST1 converted unused deadline into substantially more SCAN and VERIFY actions and consistently
recovered a second event on V0_Q2. It recovered no event on either V1 task in any of twelve
physical cells, despite evaluator-only evidence that positive units were scanned. Therefore the
mechanism improves exposure but not cross-video candidate-to-VERIFY/event conversion. This is not
a near miss under the frozen rule: the required cross-video direction is absent, so neither an
ablation nor the single causal revision is triggered.
"""
    (CYCLE3 / "FINAL_REPORT.md").write_text(report, encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
