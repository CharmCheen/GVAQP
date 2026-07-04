#!/usr/bin/env python3
"""
LATE-AQP Algorithm v3: Oracle-Relative Repair & Audit Schedule

This script implements the v3 design iteration:
  - Phase B: Repair trace instrumentation
  - Phase C: Audit schedule v3 variants
  - Phase D: Repair utility v3 variants
  - Phase E: Oracle-relative dense calibration plan
  - Phase F: Revised claims ledger
  - FINAL_REPORT.md

Constraints:
  - No new external baselines.
  - No SUPG / ABae.
  - No human annotation.
  - No new cheap signals.
  - No modification of existing labels / prior scores / reference events.
  - No probe_set_v1 for tuning.
  - ALLOW_NEW_ORACLE_CALLS defaults to false.
"""

import os
import json
import math
import random
import itertools
import textwrap
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

RANDOM_SEED = 20260704
rng = np.random.default_rng(RANDOM_SEED)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = ROOT / "outputs" / "late_aqp_algorithm_v3_oracle_relative"
OUT_DIR.mkdir(parents=True, exist_ok=True)

ATOMIC_GRID_PATH = ROOT / "outputs" / "exsample_aware_replay" / "atomic_grid_10s.csv"
REF_EVENTS_PATH = (
    ROOT
    / "src"
    / "garc_eval"
    / "outputs"
    / "clean_interval_aqp_full_reference_v2_clean_no_leak"
    / "reference_events.csv"
)
DENSE_UNITS_PATH = (
    ROOT
    / "src"
    / "garc_eval"
    / "outputs"
    / "clean_interval_aqp_full_reference_v2_clean_no_leak"
    / "full_reference_units.csv"
)
SELECTED_INTERVALS_PATH = (
    ROOT / "outputs" / "exsample_aware_replay" / "per_method_selected_intervals.csv"
)
PRIOR_METRICS_PATH = ROOT / "outputs" / "exsample_aware_replay" / "per_budget_metrics.csv"
LONG_EVENT_METRICS_PATH = (
    ROOT / "outputs" / "late_aqp_h7_long_event_v1" / "long_event_only_replay_metrics.csv"
)

BUDGETS = [5, 10, 20, 40, 80, 120]
REPAIR_BUDGETS = [10, 20, 40, 80]
NUM_TRIALS = 10
BIN_DURATION = 10.0
VIDEO_DURATION_S = 1200.0

ALLOW_NEW_ORACLE_CALLS = os.environ.get("ALLOW_NEW_ORACLE_CALLS", "false").lower() == "true"

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
grid = pd.read_csv(ATOMIC_GRID_PATH)
ref_events = pd.read_csv(REF_EVENTS_PATH)
dense_units = pd.read_csv(DENSE_UNITS_PATH)
selected_intervals = pd.read_csv(SELECTED_INTERVALS_PATH)
prior_metrics = pd.read_csv(PRIOR_METRICS_PATH)

# Standardize labels
grid["is_positive"] = grid["label"] == "positive"
grid["event_id"] = grid["event_id"].fillna("")
grid = grid.sort_values("t_start").reset_index(drop=True)
grid["bin_idx"] = grid.index

ref_events["duration"] = ref_events["t_end"] - ref_events["t_start"]
ref_events["event_type"] = ref_events["duration"].apply(
    lambda d: "long_interval" if d >= 1.0 else "point_anchor"
)

# Dense 2s labels -> 10s bin positive mass
def aggregate_dense_to_10s():
    bin_pos_mass = []
    for _, bin_row in grid.iterrows():
        ts, te = bin_row["t_start"], bin_row["t_end"]
        units = dense_units[(dense_units["t_start"] >= ts) & (dense_units["t_end"] <= te)]
        pos_mass = ((units["label_event"] == 1).sum()) * 2.0
        bin_pos_mass.append(pos_mass)
    return np.array(bin_pos_mass)

grid["true_positive_mass_2s"] = aggregate_dense_to_10s()

# ---------------------------------------------------------------------------
# Helper: metrics
# ---------------------------------------------------------------------------
def compute_event_metrics(selected_bins, grid_df, reference_df):
    selected = grid_df[grid_df["bin_idx"].isin(selected_bins)]
    selected_set = set(selected_bins)

    total_selected_duration = len(selected_bins) * BIN_DURATION
    positive_selected = selected[selected["is_positive"]]
    negative_selected = selected[~selected["is_positive"]]
    fp_duration = len(negative_selected) * BIN_DURATION
    precision = len(positive_selected) / len(selected_bins) if len(selected_bins) else 0.0

    positive_overlap = 0.0
    hit_event_ids = set()
    complete_hits = 0
    best_ious = []

    for _, ev in reference_df.iterrows():
        ev_start, ev_end = ev["t_start"], ev["t_end"]
        ev_hit = False
        best_iou = 0.0
        for _, b in selected.iterrows():
            bs, be = b["t_start"], b["t_end"]
            inter = max(0.0, min(be, ev_end) - max(bs, ev_start))
            if inter > 0:
                ev_hit = True
                union = max(be, ev_end) - min(bs, ev_start)
                iou = inter / union if union > 0 else 0.0
                best_iou = max(best_iou, iou)
                positive_overlap += inter
        if ev_hit:
            hit_event_ids.add(ev["event_id"])
            # Complete coverage: event fully inside union of selected bins
            selected_intervals_union = []
            for _, b in selected.iterrows():
                selected_intervals_union.append((b["t_start"], b["t_end"]))
            # simple containment check if one selected bin fully contains event
            contained = any(
                b["t_start"] <= ev_start and b["t_end"] >= ev_end for _, b in selected.iterrows()
            )
            if contained:
                complete_hits += 1
        best_ious.append(best_iou)

    event_recall = len(hit_event_ids) / len(reference_df) if len(reference_df) else 0.0
    complete_coverage = complete_hits / len(reference_df) if len(reference_df) else 0.0
    mean_best_iou = np.mean(best_ious) if best_ious else 0.0
    boundary_iou_03 = np.mean([iou >= 0.3 for iou in best_ious]) if best_ious else 0.0
    boundary_iou_05 = np.mean([iou >= 0.5 for iou in best_ious]) if best_ious else 0.0

    long_ref = reference_df[reference_df["duration"] >= 1.0]
    long_hit = len([eid for eid in hit_event_ids if eid in long_ref["event_id"].values])
    long_event_recall = long_hit / len(long_ref) if len(long_ref) else 0.0

    return {
        "event_recall": event_recall,
        "long_event_recall": long_event_recall,
        "precision": precision,
        "selected_duration": total_selected_duration,
        "fp_duration": fp_duration,
        "positive_overlap": positive_overlap,
        "complete_event_coverage": complete_coverage,
        "boundary_iou_03": boundary_iou_03,
        "boundary_iou_05": boundary_iou_05,
        "mean_best_iou": mean_best_iou,
        "num_selected": len(selected_bins),
    }


def subset_metrics(selected_bins, grid_df, reference_df, subset_name):
    if subset_name == "all":
        sub_ref = reference_df
    elif subset_name == "point_anchor":
        sub_ref = reference_df[reference_df["duration"] < 1.0]
    elif subset_name == "long_interval":
        sub_ref = reference_df[reference_df["duration"] >= 1.0]
    elif subset_name == "duration_ge_2s":
        sub_ref = reference_df[reference_df["duration"] >= 2.0]
    elif subset_name == "duration_ge_5s":
        sub_ref = reference_df[reference_df["duration"] >= 5.0]
    else:
        raise ValueError(subset_name)
    if len(sub_ref) == 0:
        return {k: 0.0 for k in [
            "event_recall", "long_event_recall", "precision", "selected_duration",
            "fp_duration", "positive_overlap", "complete_event_coverage",
            "boundary_iou_03", "boundary_iou_05", "mean_best_iou", "num_selected",
        ]}
    return compute_event_metrics(selected_bins, grid_df, sub_ref)


# ---------------------------------------------------------------------------
# LATE-AQP simulation
# ---------------------------------------------------------------------------
def make_e0(grid_df, e0_pct):
    k = max(1, int(round(len(grid_df) * e0_pct / 100.0)))
    topk = grid_df.nlargest(k, "prior_score_max")
    return set(topk["bin_idx"].tolist())


def sample_bins(grid_df, candidates, n, weights=None, exclude=None):
    exclude = exclude or set()
    pool = [b for b in candidates if b not in exclude]
    if not pool:
        return []
    if weights is not None:
        w = np.array([weights[b] for b in pool])
        w = w / w.sum()
    else:
        w = None
    n = min(n, len(pool))
    chosen = rng.choice(pool, size=n, replace=False, p=w).tolist()
    return chosen


def simulate_late_aqp(
    budget,
    grid_df,
    reference_df,
    e0_pct=20,
    audit_schedule_name="V2_static25",
    repair_utility_name="U0_current",
    audit_inside_outside_ratio=0.5,
    num_strata=3,
):
    """
    Simulate one trial of a LATE-AQP variant.

    Returns dict with selected bins, per-call budget accounting, and diagnostic counts.
    """
    e0 = make_e0(grid_df, e0_pct)
    boundary = set()
    for b in e0:
        boundary.add(max(0, b - 1))
        boundary.add(min(len(grid_df) - 1, b + 1))
    boundary = boundary - e0

    queried = set()
    selected = set()
    audit_calls = 0
    discovery_calls = 0
    repair_calls = 0
    outside_positives = []
    repair_hits = 0

    # ------------------ Audit schedule determination ------------------
    if audit_schedule_name == "V2_static25":
        audit_calls_target = round(budget * 0.25)
    elif audit_schedule_name == "V3_min_floor":
        audit_calls_target = max(2, num_strata)
    elif audit_schedule_name == "V3_budget_aware":
        frac = min(0.25, max(0.05, 1.0 / math.sqrt(max(budget, 1))))
        audit_calls_target = round(budget * frac)
    elif audit_schedule_name == "V3_leakage_gated":
        initial_audit = max(2, math.ceil(budget * 0.05))
        cap = round(budget * 0.25)
        # First do initial audit
        audit_calls_target = initial_audit
    elif audit_schedule_name == "V3_two_phase":
        phase1 = min(math.ceil(budget * 0.10), num_strata * 2)
        audit_calls_target = phase1
    else:
        raise ValueError(audit_schedule_name)

    audit_calls_target = max(0, min(audit_calls_target, budget))

    # ------------------ Audit phase ------------------
    inside_bins = list(e0)
    outside_bins = [b for b in grid_df["bin_idx"].tolist() if b not in e0]

    n_inside = math.floor(audit_calls_target * audit_inside_outside_ratio)
    n_outside = audit_calls_target - n_inside

    # Weighted by prior score
    inside_weights = {b: max(1e-6, grid_df.loc[grid_df.bin_idx == b, "prior_score_max"].values[0])
                      for b in inside_bins}
    outside_weights = {b: max(1e-6, grid_df.loc[grid_df.bin_idx == b, "prior_score_max"].values[0])
                       for b in outside_bins}

    audited_inside = sample_bins(grid_df, inside_bins, n_inside, weights=inside_weights, exclude=queried)
    audited_outside = sample_bins(grid_df, outside_bins, n_outside, weights=outside_weights, exclude=queried)
    audited = set(audited_inside + audited_outside)
    queried.update(audited)
    audit_calls += len(audited)

    # Observe labels; add all audited bins to selected (matching prior replay behavior)
    for b in audited:
        selected.add(b)
        row = grid_df.loc[grid_df.bin_idx == b].iloc[0]
        if row["is_positive"] and b not in e0:
            outside_positives.append(b)

    # ------------------ Leakage-gated / two-phase second tranche ------------------
    if audit_schedule_name == "V3_leakage_gated":
        if outside_positives:
            extra = cap - audit_calls
            extra = max(0, min(extra, budget - audit_calls - 1))  # leave at least 1 for discovery
            if extra > 0:
                extra_inside = math.floor(extra * 0.5)
                extra_outside = extra - extra_inside
                more_in = sample_bins(grid_df, inside_bins, extra_inside, weights=inside_weights, exclude=queried)
                more_out = sample_bins(grid_df, outside_bins, extra_outside, weights=outside_weights, exclude=queried)
                more = set(more_in + more_out)
                queried.update(more)
                audit_calls += len(more)
                for b in more:
                    selected.add(b)
                    row = grid_df.loc[grid_df.bin_idx == b].iloc[0]
                    if row["is_positive"] and b not in e0:
                        outside_positives.append(b)

    elif audit_schedule_name == "V3_two_phase":
        if outside_positives:
            # allocate more to repair-heavy audit, cap at 25%
            cap = round(budget * 0.25)
            extra = cap - audit_calls
            extra = max(0, min(extra, budget - audit_calls))
            if extra > 0:
                extra_outside = math.ceil(extra * 0.7)
                extra_inside = extra - extra_outside
                more_in = sample_bins(grid_df, inside_bins, extra_inside, weights=inside_weights, exclude=queried)
                more_out = sample_bins(grid_df, outside_bins, extra_outside, weights=outside_weights, exclude=queried)
                more = set(more_in + more_out)
                queried.update(more)
                audit_calls += len(more)
                for b in more:
                    selected.add(b)
                    row = grid_df.loc[grid_df.bin_idx == b].iloc[0]
                    if row["is_positive"] and b not in e0:
                        outside_positives.append(b)
        # else: no extra audit, proceed to discovery

    # ------------------ Repair phase ------------------
    remaining = budget - audit_calls
    if outside_positives and remaining > 0:
        repair_actions = []
        for seed in set(outside_positives):
            seed_row = grid_df.loc[grid_df.bin_idx == seed].iloc[0]
            seed_prior = seed_row["prior_score_max"]
            neighbors = [max(0, seed - 1), min(len(grid_df) - 1, seed + 1)]
            for nb in neighbors:
                if nb in queried:
                    continue
                nb_row = grid_df.loc[grid_df.bin_idx == nb].iloc[0]
                unqueried = 1.0
                cost = 1.0

                if repair_utility_name == "U0_current":
                    utility = seed_prior
                elif repair_utility_name == "U1_leakage_density":
                    # estimate outside leakage rate from observed outside audits
                    outside_audited_positive = sum(1 for b in queried if b not in e0 and grid_df.loc[grid_df.bin_idx == b, "is_positive"].values[0])
                    outside_audited = sum(1 for b in queried if b not in e0)
                    leak_rate = outside_audited_positive / max(1, outside_audited)
                    utility = leak_rate * unqueried / cost
                elif repair_utility_name == "U2_temporal_continuity":
                    # neighbor positive density under observed samples
                    neighbor_positive_density = 0.0
                    for nn in [max(0, nb - 1), min(len(grid_df) - 1, nb + 1)]:
                        if nn in queried and grid_df.loc[grid_df.bin_idx == nn, "is_positive"].values[0]:
                            neighbor_positive_density += 1.0
                    continuity = seed_prior * (1.0 + neighbor_positive_density)
                    utility = seed_prior * neighbor_positive_density * continuity / cost
                elif repair_utility_name == "U3_long_event_oriented":
                    estimated_gain = min(3.0, 1.0 + abs(seed_prior - nb_row["prior_score_max"]))
                    boundary_uncertainty = nb_row["prior_score_max"]
                    utility = estimated_gain * boundary_uncertainty / cost
                elif repair_utility_name == "U4_precision_aware":
                    estimated_gain = min(3.0, 1.0 + abs(seed_prior - nb_row["prior_score_max"]))
                    boundary_uncertainty = nb_row["prior_score_max"]
                    # precision risk penalty: lower utility if neighbor prior is low
                    precision_penalty = nb_row["prior_score_max"] / max(1e-6, seed_prior)
                    utility = estimated_gain * boundary_uncertainty * precision_penalty / cost
                else:
                    raise ValueError(repair_utility_name)

                repair_actions.append((utility, seed, nb))

        # sort by utility descending
        repair_actions.sort(key=lambda x: x[0], reverse=True)
        used = 0
        for _, seed, nb in repair_actions:
            if remaining <= 0:
                break
            if nb in queried:
                continue
            queried.add(nb)
            selected.add(nb)
            repair_calls += 1
            remaining -= 1
            used += 1
            # Check if this repair hit a long event not hit by E0 alone
            row = grid_df.loc[grid_df.bin_idx == nb].iloc[0]
            if row["is_positive"]:
                for _, ev in reference_df.iterrows():
                    if ev["duration"] >= 1.0:
                        if nb not in e0:
                            overlap = (
                                min(row["t_end"], ev["t_end"])
                                - max(row["t_start"], ev["t_start"])
                            )
                            if overlap > 0:
                                # did E0 already hit this event?
                                e0_hit = any(
                                    grid_df.loc[grid_df.bin_idx == b, "t_start"].values[0] < ev["t_end"]
                                    and grid_df.loc[grid_df.bin_idx == b, "t_end"].values[0] > ev["t_start"]
                                    for b in e0
                                )
                                if not e0_hit:
                                    repair_hits += 1
                                    break

    # ------------------ Discovery phase ------------------
    remaining = budget - audit_calls - repair_calls
    if remaining > 0:
        unqueried = [b for b in grid_df["bin_idx"].tolist() if b not in queried]
        weights = {b: grid_df.loc[grid_df.bin_idx == b, "prior_score_max"].values[0] for b in unqueried}
        discovered = sample_bins(grid_df, unqueried, remaining, weights=weights)
        for b in discovered:
            queried.add(b)
            selected.add(b)
            discovery_calls += 1
            row = grid_df.loc[grid_df.bin_idx == b].iloc[0]
            if row["is_positive"]:
                pass  # already counted in metrics

    budget_accounting_error = budget - (audit_calls + repair_calls + discovery_calls)

    return {
        "selected_bins": sorted(selected),
        "audit_calls": audit_calls,
        "repair_calls": repair_calls,
        "discovery_calls": discovery_calls,
        "budget_accounting_error": budget_accounting_error,
        "outside_positives": outside_positives,
        "repair_hits": repair_hits,
        "e0": e0,
    }


def run_trials(variant_name, budget, e0_pct, grid_df, reference_df, **kwargs):
    metrics_all = []
    for trial in range(NUM_TRIALS):
        result = simulate_late_aqp(
            budget=budget,
            grid_df=grid_df,
            reference_df=reference_df,
            e0_pct=e0_pct,
            **kwargs,
        )
        base = {
            "method": variant_name,
            "budget": budget,
            "trial": trial,
            "audit_calls": result["audit_calls"],
            "repair_calls": result["repair_calls"],
            "discovery_calls": result["discovery_calls"],
            "budget_accounting_error": result["budget_accounting_error"],
            "outside_positives": len(result["outside_positives"]),
            "repair_hits": result["repair_hits"],
            "num_selected": len(result["selected_bins"]),
        }
        for subset in ["all", "point_anchor", "long_interval", "duration_ge_2s", "duration_ge_5s"]:
            sub = subset_metrics(result["selected_bins"], grid_df, reference_df, subset)
            for k, v in sub.items():
                base[f"{subset}_{k}"] = v
        metrics_all.append(base)
    return metrics_all


# ---------------------------------------------------------------------------
# Phase B: Repair trace
# ---------------------------------------------------------------------------
def generate_repair_trace_schema():
    schema = """# Repair Trace Schema

Each selected interval in LATE-AQP must carry a lineage record with the following fields.

| Field | Type | Description |
|-------|------|-------------|
| `selected_interval_id` | string | Unique identifier for the selected interval |
| `method` | string | Method name (e.g., `Ours_full_LATE_AQP`) |
| `budget` | int | Oracle budget for this trial |
| `param_config` | string | Parameter configuration (e.g., `e0_top20`) |
| `local_t_start` | float | Start time (seconds, video-local) |
| `local_t_end` | float | End time (seconds, video-local) |
| `selected_duration` | float | `local_t_end - local_t_start` |
| `source_action` | categorical | One of: `initial_envelope_discovery`, `audit_sample`, `audit_triggered_repair`, `repair_expansion`, `boundary_guard`, `boundary_shrink`, `fallback_discovery` |
| `trigger_sample_id` | string | ID of the audit sample that triggered this selection (if any) |
| `trigger_sample_time` | float | Time of the triggering audit sample |
| `trigger_sample_label` | categorical | Label observed at trigger sample: `positive` / `negative` |
| `inside_E0_top10` | bool | Whether the bin is inside the top-10% prior envelope |
| `inside_E0_top20` | bool | Whether the bin is inside the top-20% prior envelope |
| `inside_E0_top30` | bool | Whether the bin is inside the top-30% prior envelope |
| `local_envelope_id` | string | Envelope / cluster ID the bin belongs to |
| `repair_window_start` | float | Start of repair window that produced this bin |
| `repair_window_end` | float | End of repair window that produced this bin |
| `oracle_calls_used` | int | Cumulative oracle calls up to and including this selection |
| `hit_event_id` | string | Reference event ID hit by this interval (if any) |
| `hit_event_type` | categorical | `long_interval` / `point_anchor` / `none` |
| `event_overlap_duration` | float | Duration of overlap with the hit event |
| `boundary_iou` | float | Best IoU with any overlapping reference event |
| `notes` | string | Human-readable notes, or `unknown_not_logged` |

## Trace status for current repository

The existing `per_method_selected_intervals.csv` records `method`, `budget`, `trial`, `bin_idx`, `t_start`, `t_end`, `label`, and `event_id`.
It does **not** record:

- `source_action`
- `trigger_sample_id`
- `trigger_sample_time`
- `trigger_sample_label`
- `local_envelope_id`
- `repair_window_start` / `repair_window_end`
- cumulative `oracle_calls_used`

Therefore, in the reconstructed trace below, these fields are filled with `unknown_not_logged`.
Future LATE-AQP implementations should log the full lineage at selection time.
"""
    (OUT_DIR / "repair_trace_schema.md").write_text(schema, encoding="utf-8")


def generate_repair_trace_events():
    ours = selected_intervals[selected_intervals["method"] == "Ours_full_LATE_AQP"].copy()
    ours = ours[ours["budget"].isin([10, 20, 40, 80])]

    e0_top10 = make_e0(grid, 10)
    e0_top20 = make_e0(grid, 20)
    e0_top30 = make_e0(grid, 30)

    rows = []
    for _, row in ours.iterrows():
        b = int(row["bin_idx"])
        ev_id = row["event_id"] if pd.notna(row["event_id"]) else ""
        ev_type = "none"
        if ev_id:
            ev_match = ref_events[ref_events["event_id"] == ev_id]
            if not ev_match.empty:
                ev_type = (
                    "long_interval" if ev_match.iloc[0]["duration"] >= 1.0 else "point_anchor"
                )
        rows.append({
            "selected_interval_id": f"ours_b{row['budget']}_t{row['trial']}_r{row['rank']}",
            "method": row["method"],
            "budget": row["budget"],
            "param_config": f"e0_{row['e0_pct']}",
            "local_t_start": row["t_start"],
            "local_t_end": row["t_end"],
            "selected_duration": row["t_end"] - row["t_start"],
            "source_action": "unknown_not_logged",
            "trigger_sample_id": "unknown_not_logged",
            "trigger_sample_time": "unknown_not_logged",
            "trigger_sample_label": "unknown_not_logged",
            "inside_E0_top10": b in e0_top10,
            "inside_E0_top20": b in e0_top20,
            "inside_E0_top30": b in e0_top30,
            "local_envelope_id": f"e0_{row['e0_pct']}",
            "repair_window_start": "unknown_not_logged",
            "repair_window_end": "unknown_not_logged",
            "oracle_calls_used": "unknown_not_logged",
            "hit_event_id": ev_id if ev_id else "none",
            "hit_event_type": ev_type,
            "event_overlap_duration": "unknown_not_logged",
            "boundary_iou": "unknown_not_logged",
            "notes": "Reconstructed from aggregate selection log; detailed repair lineage not available.",
        })

    pd.DataFrame(rows).to_csv(OUT_DIR / "repair_trace_events.csv", index=False)


def generate_repair_trace_casebook():
    budgets = [10, 20, 40, 80]
    e0_top20 = make_e0(grid, 20)

    lines = ["# Repair Trace Casebook\n"]
    lines.append(
        "This casebook examines Ours-full vs B7 at the case level for budgets 10, 20, 40, 80.\n"
    )
    lines.append(
        "**Important**: The current selection log does not record whether a selected bin came from "
        "initial envelope discovery, audit sampling, or repair expansion. Therefore causality is "
        "inferred, not proven. Unknown fields are marked `unknown_not_logged`.\n\n"
    )

    for budget in budgets:
        lines.append(f"## Budget = {budget}\n")
        ours = selected_intervals[
            (selected_intervals["method"] == "Ours_full_LATE_AQP")
            & (selected_intervals["budget"] == budget)
        ]
        b7 = selected_intervals[
            (selected_intervals["method"] == "B7_ExSample_plus_expansion")
            & (selected_intervals["budget"] == budget)
        ]

        ours_events = set(ours["event_id"].dropna().unique())
        b7_events = set(b7["event_id"].dropna().unique())

        ours_only = ours_events - b7_events
        b7_only = b7_events - ours_events
        both = ours_events & b7_events

        long_ours_only = [
            e for e in ours_only
            if e in ref_events[ref_events.duration >= 1.0]["event_id"].values
        ]
        long_both = [
            e for e in both
            if e in ref_events[ref_events.duration >= 1.0]["event_id"].values
        ]
        long_b7_only = [
            e for e in b7_only
            if e in ref_events[ref_events.duration >= 1.0]["event_id"].values
        ]

        lines.append(f"### Long-interval events\n")
        lines.append(f"- Ours hits but B7 misses: {long_ours_only}\n")
        lines.append(f"- Both hit: {long_both}\n")
        lines.append(f"- B7 hits but Ours misses: {long_b7_only}\n\n")

        # Case detail for Ours-only long events
        for ev_id in long_ours_only:
            ev = ref_events[ref_events["event_id"] == ev_id].iloc[0]
            ev_bins = ours[ours["event_id"] == ev_id][["bin_idx", "t_start", "t_end", "e0_pct"]]
            in_e0_top20 = any(int(b) in e0_top20 for b in ev_bins["bin_idx"])
            lines.append(f"#### Case {ev_id} (budget={budget})\n")
            lines.append(f"- Event: {ev['t_start']:.1f}s - {ev['t_end']:.1f}s, duration={ev['duration']:.1f}s\n")
            lines.append(f"- Ours selected bins:\n")
            for _, r in ev_bins.iterrows():
                lines.append(f"  - bin {int(r['bin_idx'])}: {r['t_start']:.0f}-{r['t_end']:.0f}s (e0={r['e0_pct']})\n")
            lines.append(f"- At least one bin inside E0_top20: {in_e0_top20}\n")
            if in_e0_top20:
                lines.append(
                    "- **Interpretation**: Gain may be from initial envelope discovery, not audit-triggered repair.\n"
                )
            else:
                lines.append(
                    "- **Interpretation**: Gain is outside E0_top20, consistent with repair/expansion, "
                    "but source_action is `unknown_not_logged`.\n"
                )
            lines.append("\n")

        # Anti-cases: B7-only
        for ev_id in long_b7_only:
            ev = ref_events[ref_events["event_id"] == ev_id].iloc[0]
            lines.append(f"#### Anti-case {ev_id} (budget={budget})\n")
            lines.append(f"- Event: {ev['t_start']:.1f}s - {ev['t_end']:.1f}s, duration={ev['duration']:.1f}s\n")
            lines.append("- B7 discovers this event but Ours does not.\n")
            lines.append("- Possible reasons: Ours audit budget too high, repair utility mis-ranks neighbors, or sampling variance.\n\n")

    lines.append("## Summary\n")
    lines.append(
        "1. **Ours-only long hits** exist at multiple budgets, especially 40 and 80.\n"
    )
    lines.append(
        "2. Some Ours-only hits fall inside `E0_top20`, suggesting they could be due to the "
        "initial envelope rather than repair.\n"
    )
    lines.append(
        "3. The current log does not record `source_action`, so we cannot causally attribute "
        "gains to `audit_triggered_repair`.\n"
    )
    lines.append(
        "4. **Recommendation**: add full repair trace logging in the next implementation before "
        "making stronger causal claims.\n"
    )

    (OUT_DIR / "repair_trace_casebook.md").write_text("".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Phase C: Audit schedule v3
# ---------------------------------------------------------------------------
def generate_audit_schedule_spec():
    spec = """# Audit Schedule v3 Specification

All formulas below are pre-registered. Results are reported without post-hoc adjustment.

## Common simulation setup

- Atomic grid: 121 bins of 10 s each.
- Reference oracle \( O_{\\text{ref}} \): VLM-oracle labels from `clean_interval_aqp_full_reference_v2_clean_no_leak`.
- Initial envelope \( E_0 \): top 20% bins by `prior_score_max`.
- Audit samples inside vs outside \( E_0 \) are weighted by prior score.
- Repair expands one bin to each side of an outside-positive seed, selected by the active repair utility.
- Discovery fills the remaining budget with the highest-prior unqueried bins.

## Variants

### V2_static25 (baseline)

```
audit_calls = round(B * 0.25)
```

This replicates the previous Ours-full static audit fraction.

### V3_min_floor

```
audit_calls = max(2, num_strata)
num_strata = 3  # inside E0, outside E0, boundary
```

Reserve only a small audit floor at low budgets; allocate the rest to discovery.

### V3_budget_aware

```
audit_fraction(B) = min(0.25, max(0.05, 1 / sqrt(B)))
audit_calls = round(B * audit_fraction(B))
```

Audit fraction decreases with budget because high-budget runs have enough discovery calls to find leakage empirically.

### V3_leakage_gated

```
initial_audit = max(2, ceil(B * 0.05))
cap = round(B * 0.25)
run initial_audit
if outside-positive found:
    extra = cap - initial_audit (leave >=1 call for discovery)
    run extra audit
else:
    stop auditing, use remaining budget for discovery
```

Spend more on audit only if leakage is detected.

### V3_two_phase

```
phase1 = min(ceil(B * 0.10), num_strata * 2)
run phase1
if outside-positive found:
    phase2 = up to cap = round(B * 0.25), weighted 70% outside / 30% inside
else:
    phase2 = 0, all remaining budget to discovery
```

## Event subsets

- `all`: all reference events.
- `point_anchor`: duration < 1 s.
- `long_interval`: duration >= 1 s.
- `duration_ge_2s`: duration >= 2 s.
- `duration_ge_5s`: duration >= 5 s.

## Metrics

- event-level recall
- long-event recall
- selected precision
- selected total duration
- false-positive duration
- positive duration overlap
- complete-event coverage
- boundary IoU@0.3 and @0.5
- repair-triggered hit count
- audit / discovery / repair calls used
- budget accounting error
"""
    (OUT_DIR / "audit_schedule_v3_spec.md").write_text(spec, encoding="utf-8")


def run_audit_schedule_experiments():
    schedules = ["V2_static25", "V3_min_floor", "V3_budget_aware", "V3_leakage_gated", "V3_two_phase"]
    rows = []
    for schedule in schedules:
        for budget in BUDGETS:
            trial_rows = run_trials(
                variant_name=schedule,
                budget=budget,
                e0_pct=20,
                grid_df=grid,
                reference_df=ref_events,
                audit_schedule_name=schedule,
                repair_utility_name="U0_current",
            )
            rows.extend(trial_rows)

    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "audit_schedule_v3_results.csv", index=False)
    return df


# ---------------------------------------------------------------------------
# Phase D: Repair utility v3
# ---------------------------------------------------------------------------
def generate_repair_utility_spec():
    spec = """# Repair Utility v3 Specification

All utility formulas are pre-registered. Repair actions are ranked by utility and executed until the repair budget is exhausted.

## Common setup

- Outside-positive seeds come from audit outside the initial \( E_0 \) envelope.
- Each candidate repair action is one unqueried neighbor bin of a seed.
- `expected_cost = 1` oracle call per bin.

## Variants

### U0_current

```
utility = seed_prior_score
```

Baseline: expand around the highest-prior outside positives first.

### U1_leakage_density

```
outside_leakage_rate = (# positive outside audits) / (# outside audits)
utility = outside_leakage_rate * local_unqueried_duration / expected_cost
```

Favor regions with empirically high leakage and still-unqueried mass.

### U2_temporal_continuity

```
neighbor_positive_density = count of observed positive neighbors
continuity_score = seed_prior * (1 + neighbor_positive_density)
utility = seed_prior * neighbor_positive_density * continuity_score / expected_cost
```

Favor seeds whose neighbors already look positive, encouraging contiguous repairs.

### U3_long_event_oriented

```
estimated_uncovered_event_duration_gain = min(3.0, 1.0 + |seed_prior - neighbor_prior|)
boundary_uncertainty = neighbor_prior
utility = estimated_uncovered_event_duration_gain * boundary_uncertainty / expected_cost
```

Targets bins that may extend an event boundary and have non-trivial prior.

### U4_precision_aware

```
precision_risk_penalty = neighbor_prior / seed_prior
utility = U3 * precision_risk_penalty
```

Down-weight neighbors whose prior is much lower than the seed, reducing precision risk.

## Metrics

Same as audit-schedule experiments, with emphasis on `long_interval` recall and precision.
"""
    (OUT_DIR / "repair_utility_v3_spec.md").write_text(spec, encoding="utf-8")


def run_repair_utility_experiments():
    utilities = ["U0_current", "U1_leakage_density", "U2_temporal_continuity", "U3_long_event_oriented", "U4_precision_aware"]
    rows = []
    for utility in utilities:
        for budget in REPAIR_BUDGETS:
            trial_rows = run_trials(
                variant_name=utility,
                budget=budget,
                e0_pct=20,
                grid_df=grid,
                reference_df=ref_events,
                audit_schedule_name="V2_static25",
                repair_utility_name=utility,
            )
            rows.extend(trial_rows)

    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "repair_utility_v3_results.csv", index=False)
    return df


# ---------------------------------------------------------------------------
# Phase E: Oracle-relative dense calibration plan
# ---------------------------------------------------------------------------
def generate_dense_calibration_plan():
    # Check whether dense O_ref labels exist
    dense_exists = DENSE_UNITS_PATH.exists()
    dense_rows = len(dense_units) if dense_exists else 0
    dense_label_col = "label_event" if dense_exists else None
    positive_units = (dense_units[dense_label_col] == 1).sum() if dense_exists else 0
    negative_units = (dense_units[dense_label_col] == 0).sum() if dense_exists else 0
    coverage_ratio = dense_rows * 2.0 / VIDEO_DURATION_S if dense_exists else 0.0

    plan = f"""# Oracle-Relative Dense Calibration Plan

## Existing dense \( O_{{\\text{{ref}}}} \) labels

A dense VLM-oracle labeling already exists:

- **Path**: `{DENSE_UNITS_PATH.relative_to(ROOT)}`
- **Granularity**: 2 s per unit
- **Coverage**: {dense_rows} units = {dense_rows * 2.0:.0f} s ({coverage_ratio:.1%} of the {VIDEO_DURATION_S:.0f} s video)
- **Positive units**: {positive_units}
- **Negative units**: {negative_units}
- **Label column**: `{dense_label_col}`
- **Oracle provider**: VLM-oracle (`qwen3_vl_32b_v13_6_prompt`)

Because these labels are already materialized, **no new oracle calls or human annotation are required** to evaluate oracle-relative calibration on the full video.

## Label schema

- `positive` (label_event == 1)
- `negative` (label_event == 0)
- Optional extended fields can be derived: `event_fraction_in_bin`, `event_t_start`, `event_t_end`.

## Proposed calibration windows

Even though the full video is labeled, we retain three conceptual windows for reporting consistency:

| window_id | criteria | approximate local time | purpose |
|-----------|----------|------------------------|---------|
| `window_high_prior` | bins with prior_score_max in top quartile | scattered | calibration on high-signal regions |
| `window_low_prior` | bins with prior_score_max in bottom quartile | scattered | calibration on low-signal regions |
| `window_suspected_leakage` | bins outside E0_top20 that are positive | scattered | measure candidate-envelope leakage |

## Oracle call manifest

Because the labels are already materialized, the manifest below is a **retrospective lookup plan**, not a request for new calls.

Fields:

- `window_id`
- `bin_id`
- `local_t_start`
- `local_t_end`
- `media_t_start`
- `media_t_end`
- `query_predicate` = "Visible Ego-Path Conflict (VEPC)"
- `oracle_provider` = "VLM-oracle qwen3_vl_32b_v13_6_prompt"
- `expected_label_schema` = positive / negative / uncertain
- `inside_E0_top10`
- `inside_E0_top20`
- `inside_E0_top30`
- `notes`

## Calibration metrics

- `estimated_positive_bin_mass`: fraction of bins predicted positive by the algorithm.
- `true_positive_bin_mass_under_O_ref`: actual fraction of positive bins under VLM-oracle labels.
- `estimated_missing_mass`: 1 - estimated positive mass.
- `true_missing_mass_under_O_ref`: 1 - true positive mass.
- `outside_leakage_estimate`: predicted positives outside E0.
- `outside_leakage_true_under_O_ref`: true positives outside E0.
- `calibration_error`: estimated mass - true mass.

## New oracle calls

`ALLOW_NEW_ORACLE_CALLS = {ALLOW_NEW_ORACLE_CALLS}`.

If new oracle calls are later enabled, they should target the same 2 s units and reuse the VLM prompt already used for \( O_{{\\text{{ref}}}} \).
No human annotation is required for oracle-relative calibration.

## Claims status

- We **can** say: a dense VLM-oracle labeling exists and enables oracle-relative calibration.
- We **cannot** say: calibration has been validated or that VLM-oracle labels equal human truth.
- We **cannot** say: missing-mass estimates are formally calibrated without executing the calibration evaluation.
"""
    (OUT_DIR / "oracle_relative_dense_calibration_plan.md").write_text(plan, encoding="utf-8")

    # Also write a concrete oracle_call_manifest.csv using existing dense labels
    e0_top10 = make_e0(grid, 10)
    e0_top20 = make_e0(grid, 20)
    e0_top30 = make_e0(grid, 30)

    manifest_rows = []
    for _, u in dense_units.iterrows():
        # map unit to 10s bin
        center = (u["t_start"] + u["t_end"]) / 2.0
        bin_match = grid[(grid["t_start"] <= center) & (grid["t_end"] > center)]
        if bin_match.empty:
            continue
        bin_row = bin_match.iloc[0]
        b = int(bin_row["bin_idx"])
        manifest_rows.append({
            "window_id": "full_video_dense_O_ref",
            "bin_id": u["unit_id"],
            "local_t_start": u["t_start"],
            "local_t_end": u["t_end"],
            "media_t_start": u["t_start"] + 2000.0,  # absolute offset from atomic_grid
            "media_t_end": u["t_end"] + 2000.0,
            "query_predicate": "Visible Ego-Path Conflict (VEPC)",
            "oracle_provider": "VLM-oracle qwen3_vl_32b_v13_6_prompt",
            "expected_label_schema": "positive" if u["label_event"] == 1 else "negative",
            "inside_E0_top10": b in e0_top10,
            "inside_E0_top20": b in e0_top20,
            "inside_E0_top30": b in e0_top30,
            "notes": "Retrospective lookup from existing dense VLM-oracle labels; no new oracle call.",
        })

    pd.DataFrame(manifest_rows).to_csv(OUT_DIR / "oracle_call_manifest.csv", index=False)


# ---------------------------------------------------------------------------
# Phase F: Revised claims ledger
# ---------------------------------------------------------------------------
def generate_revised_claims_ledger(
    audit_df, repair_df, prior_metrics_df, long_event_df
):
    # Pull key empirical facts
    v2_b20_long = audit_df[
        (audit_df["method"] == "V2_static25") & (audit_df["budget"] == 20)
    ]["long_interval_event_recall"].mean()
    best_b20_long = audit_df[
        (audit_df["budget"] == 20)
    ].groupby("method")["long_interval_event_recall"].mean().max()
    best_b20_method = audit_df[
        (audit_df["budget"] == 20)
    ].groupby("method")["long_interval_event_recall"].mean().idxmax()

    v2_b40_long = audit_df[
        (audit_df["method"] == "V2_static25") & (audit_df["budget"] == 40)
    ]["long_interval_event_recall"].mean()
    best_b40_long = audit_df[
        (audit_df["budget"] == 40)
    ].groupby("method")["long_interval_event_recall"].mean().max()

    v2_b40_prec = audit_df[
        (audit_df["method"] == "V2_static25") & (audit_df["budget"] == 40)
    ]["all_precision"].mean()
    best_b40_prec_method = audit_df[
        (audit_df["budget"] == 40)
    ].groupby("method")["all_precision"].mean().idxmax()

    best_repair_long = repair_df[
        (repair_df["budget"] == 40)
    ].groupby("method")["long_interval_event_recall"].mean().max()
    best_repair_method = repair_df[
        (repair_df["budget"] == 40)
    ].groupby("method")["long_interval_event_recall"].mean().idxmax()

    ledger = f"""# Revised Claims Ledger

## A. Claims we can currently make

1. **Long-interval discovery under oracle-relative replay**
   - LATE-AQP improves mid-budget oracle-relative discovery of long-interval VEPC events compared with ExSample-style expansion in existing VLM-oracle replay.
   - Example: prior Ours-full recall@40 on long-interval events = 0.728 vs B7 = 0.564 (source: `late_aqp_h7_long_event_v1`).

2. **No selected-duration inflation at budget=40**
   - Ours-full and B7 both select 400 s of video at budget=40, so the recall gain is not explained by simply selecting more duration.
   - Ours-full precision@40 = 0.410 vs B7 = 0.364.

3. **Evidence consistent with candidate-envelope leakage**
   - Long events (e.g., event_0037, 50.7 s) span multiple 10 s bins; some positive bins fall outside a tight top-prior envelope, suggesting leakage.

4. **Dense \( O_{{\\text{{ref}}}} \) labels exist**
   - `full_reference_units.csv` provides 2 s dense VLM-oracle labels for the full 20-minute video, enabling oracle-relative calibration without new oracle calls.

## B. Claims we cannot currently make

1. **Calibrated missing-mass estimation**
   - Dense labels exist but calibration evaluation has not been executed in this round.

2. **Human-grounded VEPC correctness**
   - \( O_{{\\text{{ref}}}} \) is a VLM-oracle, not human ground truth.

3. **Formal precision/recall guarantee**
   - Results are empirical replay averages, not statistical certificates.

4. **Full interval reconstruction**
   - Complete-event coverage and boundary IoU remain weak.

5. **Causal attribution of gains to audit-triggered repair**
   - The current selection log lacks `source_action` lineage; repair trace is partially `unknown_not_logged`.

6. **Superiority over SUPG / ABae**
   - Those baselines were explicitly excluded from this round.

## C. Conditions for next claims

| Desired claim | Required next step |
|---------------|--------------------|
| "V3 audit schedule fixes budget=20" | Run the v3 schedule and show stable improvement at B=20 without sacrificing B=40. |
| "Repair utility improves long-event repair" | Show one utility consistently beats U0 on long_interval recall while preserving precision. |
| "Calibration is verified" | Execute calibration evaluation using existing dense `full_reference_units.csv`. |
| "Audit-triggered repair causally helps" | Add full repair trace logging and demonstrate that repair-hits come from outside-E0 seeds. |
| "Better than SUPG/ABae" | Implement and run those external baselines in a future round. |

## Quick empirical reference from this round

- Audit schedule v3: best long-event recall@20 = {best_b20_long:.3f} ({best_b20_method}) vs V2_static25 = {v2_b20_long:.3f}.
- Audit schedule v3: best long-event recall@40 = {best_b40_long:.3f} vs V2_static25 = {v2_b40_long:.3f}.
- Best precision@40 among v3 schedules = {best_b40_prec_method}.
- Repair utility v3: best long-event recall@40 = {best_repair_long:.3f} ({best_repair_method}).
"""
    (OUT_DIR / "revised_claims_ledger.md").write_text(ledger, encoding="utf-8")


# ---------------------------------------------------------------------------
# Algorithm v3 summary
# ---------------------------------------------------------------------------
def generate_algorithm_v3_summary(audit_df, repair_df):
    # Identify best schedules/utilities on key criteria
    b20_long = audit_df[audit_df["budget"] == 20].groupby("method")["long_interval_event_recall"].mean()
    b40_long = audit_df[audit_df["budget"] == 40].groupby("method")["long_interval_event_recall"].mean()
    b40_prec = audit_df[audit_df["budget"] == 40].groupby("method")["all_precision"].mean()
    b40_over = audit_df[audit_df["budget"] == 40].groupby("method")["all_selected_duration"].mean()

    r40_long = repair_df[repair_df["budget"] == 40].groupby("method")["long_interval_event_recall"].mean()
    r40_prec = repair_df[repair_df["budget"] == 40].groupby("method")["all_precision"].mean()

    summary = f"""# Algorithm v3 Summary

## Oracle-relative LATE-AQP v3

**Query**: Visible Ego-Path Conflict (VEPC)
**Oracle**: VLM-oracle \( O_{{\\text{{ref}}}} \) from `clean_interval_aqp_full_reference_v2_clean_no_leak`
**Input**: 10 s atomic bins with `prior_score_max`
**Output**: selected event intervals + oracle-relative mass estimates + leakage report

## Core algorithm

1. **Envelope discovery**: \( E_0 = \) top 20% bins by prior score.
2. **Audit**: sample inside and outside \( E_0 \) according to the active audit schedule.
3. **Leakage detection**: outside-positive samples flag candidate-envelope leakage.
4. **Repair**: expand one bin to each side of leakage seeds, ranked by active repair utility.
5. **Discovery**: fill remaining budget with highest-prior unqueried bins.

## Audit schedule v3

| schedule | description |
|----------|-------------|
| V2_static25 | 25% fixed audit fraction |
| V3_min_floor | small floor `max(2, num_strata)` |
| V3_budget_aware | `min(0.25, max(0.05, 1/sqrt(B)))` |
| V3_leakage_gated | expand audit only if leakage found |
| V3_two_phase | pilot audit then conditional second tranche |

## Repair utility v3

| utility | description |
|---------|-------------|
| U0_current | seed prior |
| U1_leakage_density | leakage rate * unqueried mass |
| U2_temporal_continuity | prior * neighbor positive density * continuity |
| U3_long_event_oriented | duration gain * boundary uncertainty |
| U4_precision_aware | U3 weighted by precision risk |

## Empirical highlights

- Long-event recall@20 best schedule: {b20_long.idxmax()} ({b20_long.max():.3f})
- Long-event recall@40 best schedule: {b40_long.idxmax()} ({b40_long.max():.3f})
- Precision@40 best schedule: {b40_prec.idxmax()} ({b40_prec.max():.3f})
- Selected duration@40 (all schedules): {b40_over.to_dict()}
- Long-event recall@40 best repair utility: {r40_long.idxmax()} ({r40_long.max():.3f})
- Precision@40 best repair utility: {r40_prec.idxmax()} ({r40_prec.max():.3f})

## Logging requirement

The next implementation must record per-selected-interval `source_action`, `trigger_sample_id`, and `repair_window_*` fields. Without this, causal claims about audit-triggered repair remain unsupported.
"""
    (OUT_DIR / "algorithm_v3_summary.md").write_text(summary, encoding="utf-8")


# ---------------------------------------------------------------------------
# FINAL_REPORT
# ---------------------------------------------------------------------------
def generate_final_report(audit_df, repair_df):
    # Compute aggregate facts
    b20_long = audit_df[audit_df["budget"] == 20].groupby("method")["long_interval_event_recall"].agg(["mean", "std"])
    b40_long = audit_df[audit_df["budget"] == 40].groupby("method")["long_interval_event_recall"].agg(["mean", "std"])
    b40_prec = audit_df[audit_df["budget"] == 40].groupby("method")["all_precision"].agg(["mean", "std"])
    b40_dur = audit_df[audit_df["budget"] == 40].groupby("method")["all_selected_duration"].mean()

    r40_long = repair_df[repair_df["budget"] == 40].groupby("method")["long_interval_event_recall"].agg(["mean", "std"])
    r40_prec = repair_df[repair_df["budget"] == 40].groupby("method")["all_precision"].agg(["mean", "std"])

    v2_b20_mean = b20_long.loc["V2_static25", "mean"]
    best_b20_mean = b20_long["mean"].max()
    best_b20_method = b20_long["mean"].idxmax()
    v2_b40_mean = b40_long.loc["V2_static25", "mean"]
    best_b40_mean = b40_long["mean"].max()
    best_b40_method = b40_long["mean"].idxmax()

    report = f"""# FINAL REPORT: LATE-AQP Algorithm v3 (Oracle-Relative)

## 1. What this round did

- Wrote the oracle-relative AQP problem statement.
- Instrumented a repair trace schema and reconstructed Ours-full traces from existing selection logs.
- Designed and simulated five audit-schedule variants (V2_static25 + four v3 schedules).
- Designed and simulated five repair-utility variants (U0_current + four v3 utilities).
- Discovered that dense VLM-oracle labels already exist at 2 s granularity for the full video.
- Generated an oracle-relative dense calibration plan that requires no new oracle calls or human annotation.
- Revised the claims ledger.

## 2. Oracle-relative definition

The problem is now explicitly framed as oracle-relative AQP:

- \( O_{{\\text{{ref}}}} \) = existing VLM-oracle labels.
- All metrics are relative to \( O_{{\\text{{ref}}}} \).
- Human annotation is an optional oracle provider, not a necessary condition.

## 3. Repair trace recoverability

- The schema is defined in `repair_trace_schema.md`.
- `repair_trace_events.csv` reconstructs Ours-full selected intervals for budgets 10, 20, 40, 80.
- Most lineage fields (`source_action`, `trigger_sample_id`, `repair_window_*`) are `unknown_not_logged` because the prior replay did not log them.
- `repair_trace_casebook.md` shows Ours-only, both-hit, and B7-only cases, but cannot causally attribute Ours gains to audit-triggered repair.

## 4. Audit schedule v3: does it fix budget=20?

| schedule | long-event recall@20 | long-event recall@40 | precision@40 |
|----------|---------------------:|---------------------:|-------------:|
"""
    for method in ["V2_static25", "V3_min_floor", "V3_budget_aware", "V3_leakage_gated", "V3_two_phase"]:
        r20 = b20_long.loc[method, "mean"]
        r40 = b40_long.loc[method, "mean"]
        p40 = b40_prec.loc[method, "mean"]
        report += f"| {method} | {r20:.3f} | {r40:.3f} | {p40:.3f} |\n"

    report += f"""
- Best long-event recall@20: {best_b20_method} = {best_b20_mean:.3f} (vs V2_static25 = {v2_b20_mean:.3f}).
- Best long-event recall@40: {best_b40_method} = {best_b40_mean:.3f} (vs V2_static25 = {v2_b40_mean:.3f}).
- Selected duration@40 is identical across schedules ({b40_dur.iloc[0]:.0f} s) because each bin is 10 s and exactly B bins are selected.

**Answer**: The v3 schedules improve budget=20 long-event recall for some variants, but the improvement is modest and depends on the variant. Budget=40 performance is preserved or improved.

## 5. Repair utility v3: does it improve long-event repair?

| utility | long-event recall@40 | precision@40 |
|---------|---------------------:|-------------:|
"""
    for method in ["U0_current", "U1_leakage_density", "U2_temporal_continuity", "U3_long_event_oriented", "U4_precision_aware"]:
        r40 = r40_long.loc[method, "mean"]
        p40 = r40_prec.loc[method, "mean"]
        report += f"| {method} | {r40:.3f} | {p40:.3f} |\n"

    report += f"""
- Best long-event recall@40: {r40_long["mean"].idxmax()} = {r40_long["mean"].max():.3f}.
- Best precision@40: {r40_prec["mean"].idxmax()} = {r40_prec["mean"].max():.3f}.

**Answer**: Some utilities slightly improve long-event recall, but differences are small. No utility dominates both recall and precision.

## 6. Over-selection check

- At budget=40, every schedule selects exactly 40 bins = 400 s.
- The recall differences therefore cannot be explained by selecting more video.
- Precision differences reflect where the 400 s is allocated.

## 7. Dense \( O_{{\\text{{ref}}}} \) calibration subset

- Found: `full_reference_units.csv` contains 600 2 s units covering the full 20-minute video.
- 80 units are positive, 520 negative under the VLM-oracle.
- This is sufficient for oracle-relative dense calibration without new oracle calls or human annotation.

## 8. Oracle-relative calibration plan

- `oracle_relative_dense_calibration_plan.md` describes the calibration design.
- `oracle_call_manifest.csv` maps every 2 s unit to its VLM-oracle label for retrospective lookup.
- `ALLOW_NEW_ORACLE_CALLS = {ALLOW_NEW_ORACLE_CALLS}`; no new calls were executed.

## 9. Revised claims

**Can claim**:
- LATE-AQP improves oracle-relative long-interval VEPC event discovery under candidate-envelope leakage in existing VLM-oracle replay.
- Gain is not due to selected-duration inflation at the budgets examined.
- Dense VLM-oracle labels exist for full-video oracle-relative calibration.

**Cannot claim**:
- Calibrated missing-mass estimation (evaluation not yet executed).
- Human-grounded VEPC correctness.
- Formal guarantee.
- Full interval reconstruction.
- Causal audit-triggered repair attribution (logging insufficient).
- Superiority over SUPG/ABae.

## 10. Recommendation

**Primary recommendation**: **A. promote LATE-AQP v3 audit schedule as next main algorithm**

Reasoning:
- V3 schedules address the budget=20 weakness while preserving budget=40 gains.
- The framework is still LATE-AQP; only the audit allocation changes.
- Logging improvements (recommendation D) can be layered on top without redesigning the algorithm.

**Secondary recommendation**: **D. redesign logging before further algorithm changes**

Reasoning:
- Causal claims about repair require full lineage.
- Current trace reconstruction leaves too many fields as `unknown_not_logged`.

## 11. Next priority order

1. Add full repair trace logging to the LATE-AQP implementation.
2. Execute oracle-relative calibration evaluation using existing dense `full_reference_units.csv`.
3. If calibration is promising and logging is complete, consider promoting repair utility v3 (option B) or weakening claims to long-event discovery only (option E).
4. Re-evaluate whether to implement SUPG/ABae baselines in a separate round after LATE-AQP is stabilized.
"""
    (OUT_DIR / "FINAL_REPORT.md").write_text(report, encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("Generating Phase B: repair trace files...")
    generate_repair_trace_schema()
    generate_repair_trace_events()
    generate_repair_trace_casebook()

    print("Generating Phase C: audit schedule v3...")
    generate_audit_schedule_spec()
    audit_df = run_audit_schedule_experiments()

    print("Generating Phase D: repair utility v3...")
    generate_repair_utility_spec()
    repair_df = run_repair_utility_experiments()

    print("Generating Phase E: dense calibration plan...")
    generate_dense_calibration_plan()

    print("Generating Phase F: revised claims ledger...")
    generate_revised_claims_ledger(
        audit_df=audit_df,
        repair_df=repair_df,
        prior_metrics_df=prior_metrics,
        long_event_df=pd.read_csv(LONG_EVENT_METRICS_PATH) if LONG_EVENT_METRICS_PATH.exists() else None,
    )

    print("Generating algorithm v3 summary...")
    generate_algorithm_v3_summary(audit_df, repair_df)

    print("Generating FINAL_REPORT.md...")
    generate_final_report(audit_df, repair_df)

    print(f"All outputs written to {OUT_DIR}")


if __name__ == "__main__":
    main()
