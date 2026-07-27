#!/usr/bin/env python3
"""Causal fixed-refinement baselines gated by the temporal audit."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
for directory in (ROOT / "src", ROOT / "scripts"):
    sys.path.insert(0, str(directory))

from garc_eval.scan_headroom.trusted_policies import (  # noqa: E402
    PublicObservation,
    PublicScanState,
    REFINEMENT_POLICY_IDS,
    make_refinement_policy,
)
from partial_scan_pilot_common import atomic_csv, atomic_json, atomic_text  # noqa: E402
from run_scan_optimization_headroom_audit import (  # noqa: E402
    CHECKPOINTS,
    DER,
    IMM,
    causal_order,
    frozen_cost,
    grid_auc,
    max_unobserved_gap,
    public_units,
    unit_event_map,
)


HEADROOM = ROOT / "outputs/scan_optimization_headroom_audit_v1"
TEMPORAL = HEADROOM / "temporal_correlation_audit"
OUT = HEADROOM / "fixed_refinement_baselines"


def run_policy(
    policy_id: str,
    units: pd.DataFrame,
    model: dict,
    budget: float,
    lateral_by_unit: dict[str, bool],
) -> list[dict]:
    policy = make_refinement_policy(policy_id)
    frozen_units = public_units(units)
    by_id = {str(row["unit_id"]): row for row in units.to_dict("records")}
    scanned: list[str] = []
    observations: list[PublicObservation] = []
    rows = []
    previous = None
    elapsed = 0.0
    while len(scanned) < len(units):
        state = PublicScanState(
            units=frozen_units,
            scanned_unit_ids=tuple(scanned),
            current_unit_id=None if previous is None else str(previous["unit_id"]),
            remaining_budget_sec=max(0.0, budget - elapsed),
            past_action_costs_sec=tuple(row["estimated_action_cost_sec"] for row in rows),
            revealed_candidate_ids=(),
            revealed_observations=tuple(observations),
        )
        selected_id = policy.choose_next_unit(state)
        if selected_id in scanned or selected_id not in by_id:
            raise RuntimeError(f"invalid refinement action {policy_id}: {selected_id}")
        selected = by_id[selected_id]
        cost, tr = frozen_cost(previous, selected, model)
        elapsed += cost
        scanned.append(selected_id)
        observations.append(
            PublicObservation(selected_id, lateral_by_unit.get(selected_id, False))
        )
        rows.append(
            {
                "action_index": len(scanned), "unit_id": selected_id,
                "estimated_action_cost_sec": cost,
                "cumulative_estimated_cost_sec": elapsed,
                "visible_lateral_motion_signal": lateral_by_unit.get(selected_id, False),
                **tr,
            }
        )
        previous = selected
    return rows


def main() -> None:
    temporal_decision = json.loads(
        (TEMPORAL / "temporal_refinement_decision.json").read_text()
    )
    if temporal_decision["FIXED_REFINEMENT_GATE"] != "PASS":
        raise RuntimeError("fixed refinement is prohibited by temporal gate")
    if temporal_decision["passing_predeclared_triggers"] != ["lateral_motion_signal"]:
        raise RuntimeError("unexpected trigger set; do not select post-hoc trigger")

    timeline = pd.read_csv(IMM / "timeline_units.csv")
    mapping = pd.read_parquet(DER / "candidate_event_map.parquet")
    mapping = mapping[mapping.partition_offset_sec.eq(0)]
    events_by_unit = unit_event_map(mapping)
    model = json.loads((DER / "cost_calibration/conservative_cost_model.json").read_text())
    features = pd.read_csv(TEMPORAL / "unit_visible_features.csv")
    lateral_by_unit = dict(
        zip(features.unit_id.astype(str), features.lateral_motion_signal.astype(bool))
    )
    action_rows = []
    checkpoint_rows = []
    summary_rows = []

    for video_id, units in timeline.groupby("video_id"):
        units = units.sort_values("unit_index").reset_index(drop=True)
        ceiling = set(mapping[mapping.video_id.eq(video_id)].reference_event_id.astype(str))
        sequential = causal_order("SEQUENTIAL", 0, units, model, float("inf"))
        common_bmax = float(sequential[-1]["cumulative_estimated_cost_sec"])
        for policy_id in REFINEMENT_POLICY_IDS:
            order = run_policy(policy_id, units, model, common_bmax, lateral_by_unit)
            exposed: set[str] = set()
            counts = []
            for row in order:
                exposed |= events_by_unit.get(str(row["unit_id"]), set())
                counts.append(len(exposed))
                action_rows.append(
                    {"video_id": video_id, "policy_id": policy_id, **row,
                     "distinct_events_exposed": len(exposed)}
                )
            local_checkpoints = []
            for fraction in CHECKPOINTS:
                deadline = fraction * common_bmax
                indices = [
                    index for index, row in enumerate(order)
                    if float(row["cumulative_estimated_cost_sec"]) <= deadline + 1e-9
                ]
                count = counts[indices[-1]] if indices else 0
                scanned = [str(order[index]["unit_id"]) for index in indices]
                gap, gap_sec = max_unobserved_gap(scanned, units)
                payload = {
                    "video_id": video_id, "policy_id": policy_id,
                    "budget_fraction": fraction, "deadline_sec": deadline,
                    "action_count": len(indices), "distinct_events_exposed": count,
                    "exposure_recall_offset0_ceiling": count / max(1, len(ceiling)),
                    "maximum_unobserved_gap_units": gap,
                    "maximum_unobserved_gap_sec": gap_sec,
                }
                checkpoint_rows.append(payload)
                local_checkpoints.append(payload)
            local = pd.DataFrame(local_checkpoints)
            summary_rows.append(
                {
                    "video_id": video_id, "policy_id": policy_id,
                    "exposure_grid_auc": grid_auc(local, "exposure_recall_offset0_ceiling"),
                    "recall_at_10pct": float(local.loc[local.budget_fraction.eq(.1), "exposure_recall_offset0_ceiling"].iloc[0]),
                    "recall_at_20pct": float(local.loc[local.budget_fraction.eq(.2), "exposure_recall_offset0_ceiling"].iloc[0]),
                    "recall_at_40pct": float(local.loc[local.budget_fraction.eq(.4), "exposure_recall_offset0_ceiling"].iloc[0]),
                    "recall_at_60pct": float(local.loc[local.budget_fraction.eq(.6), "exposure_recall_offset0_ceiling"].iloc[0]),
                }
            )

    actions = pd.DataFrame(action_rows)
    checkpoints = pd.DataFrame(checkpoint_rows)
    summary = pd.DataFrame(summary_rows)
    coverage = pd.read_csv(HEADROOM / "replay_run_summary.csv")
    coverage = coverage[coverage.method_class.eq("CAUSAL")].groupby(
        ["video_id", "policy_id"], as_index=False
    ).exposure_grid_auc.mean()
    strongest = coverage.loc[
        coverage.groupby("video_id").exposure_grid_auc.idxmax()
    ].rename(columns={"policy_id": "strongest_coverage_policy", "exposure_grid_auc": "strongest_coverage_auc"})
    comparison = summary.merge(
        strongest[["video_id", "strongest_coverage_policy", "strongest_coverage_auc"]],
        on="video_id",
    )
    comparison["delta_vs_strongest_coverage_auc"] = (
        comparison.exposure_grid_auc - comparison.strongest_coverage_auc
    )
    pivot = comparison.pivot(
        index="policy_id", columns="video_id",
        values="delta_vs_strongest_coverage_auc",
    )
    stable_winners = [
        policy_id for policy_id, row in pivot.iterrows() if bool((row > 0).all())
    ]
    guarded_gate = bool(stable_winners)
    decision = {
        "status": "PASS",
        "trigger": "lateral_motion_signal",
        "strongest_coverage_by_video": strongest.to_dict("records"),
        "stable_refinement_winners": stable_winners,
        "GUARDED_MARGINAL_SCAN_GATE": "PASS" if guarded_gate else "STOP",
        "reason": (
            "AT_LEAST_ONE_FIXED_REFINEMENT_POLICY_IMPROVES_BOTH_VIDEOS"
            if guarded_gate else
            "NO_FIXED_REFINEMENT_POLICY_IMPROVES_STRONGEST_COVERAGE_ON_BOTH_VIDEOS"
        ),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    atomic_csv(OUT / "refinement_action_orders.csv", actions)
    atomic_csv(OUT / "refinement_budget_checkpoints.csv", checkpoints)
    atomic_csv(OUT / "refinement_summary.csv", summary)
    atomic_csv(OUT / "refinement_vs_coverage.csv", comparison)
    atomic_json(OUT / "refinement_decision.json", decision)
    lines = "\n".join(
        f"- `{row.policy_id}` / `{row.video_id}`: AUC={row.exposure_grid_auc:.4f}, "
        f"delta vs `{row.strongest_coverage_policy}`={row.delta_vs_strongest_coverage_auc:+.4f}."
        for row in comparison.itertuples(index=False)
    )
    report = f"""# Fixed Lateral-Refinement Baselines

Only the preregistered `lateral_motion_signal` trigger passed the temporal gate. All policies are causal and use completed-unit observations only.

{lines}

```text
GUARDED_MARGINAL_SCAN_GATE = {'PASS' if guarded_gate else 'STOP'}
STABLE_REFINEMENT_WINNERS = {', '.join(stable_winners) if stable_winners else 'NONE'}
```

The comparator is the strongest simple causal coverage policy separately on each video, not merely Sequential or Largest-Gap.
"""
    atomic_text(OUT / "FIXED_REFINEMENT_REPORT.md", report)
    print(json.dumps(decision, indent=2))


if __name__ == "__main__":
    main()
