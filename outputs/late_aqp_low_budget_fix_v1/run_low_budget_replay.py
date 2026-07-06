#!/usr/bin/env python3
"""
Low-budget audit-schedule tuning and final validation (offline replay only).

Stages:
1. Tuning on realcartest 3830–3920.7 (existing center10 labels, not used before).
2. Compare Frozen-LATE-AQP-v1 against V4 candidates on B=10/20 (and B=40 sanity).
3. Select one candidate as Frozen-LATE-AQP-v2.
4. Final validation on realcartest_5k 0–208.3 s (newly generated labels).
"""

import csv
import math
import os
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
OUT = ROOT / "outputs" / "late_aqp_low_budget_fix_v1"
OUT.mkdir(parents=True, exist_ok=True)

BIN_SIZE = 10.0
BUDGETS = [5, 10, 20, 40, 80, 120]
SEEDS = [0, 1, 2, 3, 4]
RANDOM_SEED_BASE = 20260705

# Data sources.
CENTER10_EVENTS = ROOT / "experiments" / "v13" / "v13_8_full_oracle" / "tables" / "center10_vlm_oracle_events.csv"
NEW_EVENTS = OUT / "new_labels" / "center10_vlm_oracle_events_realcartest_5k.csv"
PROXY_SCORES = ROOT / "experiments" / "roadclip_budget_v2" / "roadclip_budget_v2" / "proxy_scores.csv"

# Data scarcity note: the original realcartest.mp4 is no longer present, so we
# cannot label additional realcartest footage. We therefore:
#   - tune on the full newly-labeled realcartest_5k video (21 bins, 2 long + 1 point);
#   - validate on the unused existing interval realcartest 3830–3920.7 (1 long + 1 point).
SEGMENTS = [
    {
        "segment_id": "realcartest_5k_tuning",
        "video_id": "realcartest_5k",
        "time_start": 0.0,
        "time_end": 208.333333,
        "events_path": NEW_EVENTS,
        "label_source": "newly_generated_this_task",
        "role": "tuning",
    },
    {
        "segment_id": "realcartest_3830_3920_final",
        "video_id": "realcartest",
        "time_start": 3830.0,
        "time_end": 3920.7,
        "events_path": CENTER10_EVENTS,
        "label_source": "existing_vlm_oracle",
        "role": "final_validation",
    },
]


def load_events(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    # Normalize column names for both existing and newly generated events.
    rename = {}
    if "event_start" in df.columns:
        rename["event_start"] = "t_start"
    if "event_end" in df.columns:
        rename["event_end"] = "t_end"
    if "event_duration" in df.columns:
        rename["event_duration"] = "duration"
    df = df.rename(columns=rename)
    df["duration"] = df["t_end"] - df["t_start"]
    df["event_type"] = df["duration"].apply(lambda d: "long_interval" if d >= 1.0 else "point_anchor")
    return df


def load_proxy_scores() -> pd.DataFrame:
    df = pd.read_csv(PROXY_SCORES)
    df = df.rename(columns={"start_time": "t_start", "end_time": "t_end", "score_count": "score"})
    df["score"] = pd.to_numeric(df["score"], errors="coerce").fillna(0.0)
    return df


def build_segment_grid(seg: dict, events_df: pd.DataFrame, proxy_scores: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    t0, t1 = seg["time_start"], seg["time_end"]
    duration = t1 - t0
    n_bins = int(math.ceil(duration / BIN_SIZE))
    bins = []
    for i in range(n_bins):
        bs = i * BIN_SIZE
        be = min(bs + BIN_SIZE, duration)
        bins.append({"bin_idx": i, "local_t_start": bs, "local_t_end": be})
    grid = pd.DataFrame(bins)

    # Events overlapping segment -> local time.
    ev_overlap = events_df[(events_df["t_end"] > t0) & (events_df["t_start"] < t1)].copy()
    ev_overlap["t_start"] = ev_overlap["t_start"].clip(lower=t0) - t0
    ev_overlap["t_end"] = ev_overlap["t_end"].clip(upper=t1) - t0
    ev_overlap["duration"] = ev_overlap["t_end"] - ev_overlap["t_start"]
    ref = ev_overlap.reset_index(drop=True)

    # Labels per bin.
    labels = []
    event_ids = []
    for _, b in grid.iterrows():
        bs, be = b["local_t_start"], b["local_t_end"]
        best_eid = ""
        best_ov = 0.0
        is_pos = False
        for _, ev in ref.iterrows():
            inter = max(0.0, min(be, ev["t_end"]) - max(bs, ev["t_start"]))
            if inter > 0:
                is_pos = True
                if inter > best_ov:
                    best_ov = inter
                    best_eid = ev["event_id"]
        labels.append("positive" if is_pos else "negative")
        event_ids.append(best_eid)
    grid["label"] = labels
    grid["is_positive"] = grid["label"] == "positive"
    grid["event_id"] = event_ids

    # Prior scores from proxy_scores.
    scores_max = []
    scores_mean = []
    for _, b in grid.iterrows():
        bs_abs = t0 + b["local_t_start"]
        be_abs = t0 + b["local_t_end"]
        over = proxy_scores[(proxy_scores["t_start"] < be_abs) & (proxy_scores["t_end"] > bs_abs)]
        if len(over) > 0:
            scores_max.append(float(over["score"].max()))
            scores_mean.append(float(over["score"].mean()))
        else:
            scores_max.append(0.0)
            scores_mean.append(0.0)
    grid["prior_score_max"] = scores_max
    grid["prior_score_mean"] = scores_mean

    grid["t_start"] = grid["local_t_start"]
    grid["t_end"] = grid["local_t_end"]
    return grid, ref


def merge_bins(grid: pd.DataFrame, bin_indices: List[int]) -> pd.DataFrame:
    if not bin_indices:
        return pd.DataFrame(columns=["t_start", "t_end", "duration", "bin_indices"])
    sorted_bins = sorted(set(bin_indices))
    intervals = []
    cur_bins = [sorted_bins[0]]
    cur_start = float(grid.loc[grid["bin_idx"] == sorted_bins[0], "t_start"].iloc[0])
    cur_end = float(grid.loc[grid["bin_idx"] == sorted_bins[0], "t_end"].iloc[0])
    for b in sorted_bins[1:]:
        b_start = float(grid.loc[grid["bin_idx"] == b, "t_start"].iloc[0])
        b_end = float(grid.loc[grid["bin_idx"] == b, "t_end"].iloc[0])
        if abs(b_start - cur_end) < 1e-6:
            cur_bins.append(b)
            cur_end = b_end
        else:
            intervals.append({"t_start": cur_start, "t_end": cur_end, "duration": cur_end - cur_start, "bin_indices": cur_bins.copy()})
            cur_bins = [b]
            cur_start, cur_end = b_start, b_end
    intervals.append({"t_start": cur_start, "t_end": cur_end, "duration": cur_end - cur_start, "bin_indices": cur_bins.copy()})
    return pd.DataFrame(intervals)


def compute_metrics(selected_bins: List[int], grid: pd.DataFrame, ref: pd.DataFrame) -> Dict:
    selected_bins = sorted(set(selected_bins))
    selected_grid = grid[grid["bin_idx"].isin(selected_bins)]

    total_selected_duration = selected_grid["t_end"].sum() - selected_grid["t_start"].sum()
    positive_overlap = 0.0
    for _, b in selected_grid.iterrows():
        bs, be = b["t_start"], b["t_end"]
        for _, ev in ref.iterrows():
            inter = max(0.0, min(be, ev["t_end"]) - max(bs, ev["t_start"]))
            positive_overlap += inter
    fp_duration = total_selected_duration - positive_overlap
    selected_precision = positive_overlap / total_selected_duration if total_selected_duration > 0 else 0.0

    pos_sel = selected_grid[selected_grid["is_positive"]]
    n_pos_bins = len(pos_sel)
    pos_events_hit = set()
    for _, b in pos_sel.iterrows():
        if b["event_id"]:
            pos_events_hit.add(b["event_id"])
    all_events = set(ref["event_id"].tolist())
    event_recall = len(pos_events_hit) / len(all_events) if all_events else 0.0

    long_events = ref[ref["event_type"] == "long_interval"]
    point_events = ref[ref["event_type"] == "point_anchor"]
    long_hit = {eid for eid in pos_events_hit if eid in set(long_events["event_id"])}
    point_hit = {eid for eid in pos_events_hit if eid in set(point_events["event_id"])}
    long_event_recall = len(long_hit) / len(long_events) if len(long_events) > 0 else None
    point_anchor_recall = len(point_hit) / len(point_events) if len(point_events) > 0 else None

    intervals = merge_bins(grid, selected_bins)
    complete_coverage = 0
    boundary_iou_03 = 0.0
    boundary_iou_05 = 0.0
    if not intervals.empty and len(all_events) > 0:
        matched_events = set()
        ious = []
        for _, iv in intervals.iterrows():
            best_iou = 0.0
            best_eid = None
            for _, ev in ref.iterrows():
                inter = max(0.0, min(iv["t_end"], ev["t_end"]) - max(iv["t_start"], ev["t_start"]))
                union = max(iv["t_end"], ev["t_end"]) - min(iv["t_start"], ev["t_start"])
                iou = inter / union if union > 0 else 0.0
                if iou > best_iou:
                    best_iou = iou
                    best_eid = ev["event_id"]
            if best_iou >= 0.3:
                ious.append(best_iou)
            if best_iou >= 0.5:
                ious.append(best_iou)
            if best_eid is not None and best_iou >= 0.5:
                matched_events.add(best_eid)
        complete_coverage = len(matched_events) / len(all_events)
        boundary_iou_03 = sum(1 for x in ious if x >= 0.3) / len(intervals) if intervals is not None else 0.0
        boundary_iou_05 = sum(1 for x in ious if x >= 0.5) / len(intervals) if intervals is not None else 0.0

    duplicate_rate = 0.0
    fragmentation_rate = 0.0
    if not intervals.empty:
        duplicate_rate = (len(intervals) - len(pos_events_hit)) / len(intervals) if len(intervals) > 0 else 0.0
        if len(pos_events_hit) > 0:
            fragmentation_rate = (len(intervals) / len(pos_events_hit)) - 1.0

    return {
        "event_recall": event_recall,
        "long_event_recall": long_event_recall if long_event_recall is not None else float("nan"),
        "point_anchor_recall": point_anchor_recall if point_anchor_recall is not None else float("nan"),
        "selected_total_duration": total_selected_duration,
        "positive_duration_overlap": positive_overlap,
        "false_positive_duration": fp_duration,
        "selected_precision": selected_precision,
        "complete_event_coverage": complete_coverage,
        "boundary_iou_03": boundary_iou_03,
        "boundary_iou_05": boundary_iou_05,
        "duplicate_rate": duplicate_rate,
        "fragmentation_rate": fragmentation_rate,
        "num_selected_bins": len(selected_bins),
        "num_selected_intervals": len(intervals),
        "num_events": len(all_events),
        "num_long_events": len(long_events),
        "num_point_anchor_events": len(point_events),
    }


def run_b6(grid: pd.DataFrame, budget: int, chunk_size_s: float, rng: np.random.Generator) -> List[int]:
    n_bins = len(grid)
    chunk_bins = max(1, int(round(chunk_size_s / BIN_SIZE)))
    n_chunks = max(1, math.ceil(n_bins / chunk_bins))
    samples_per_chunk = max(1, int(round(budget / n_chunks)))
    selected = []
    for c in range(n_chunks):
        start = c * chunk_bins
        end = min(start + chunk_bins, n_bins)
        pool = list(range(start, end))
        n = min(samples_per_chunk, len(pool))
        chosen = rng.choice(pool, size=n, replace=False).tolist()
        selected.extend(chosen)
    return selected


def run_b7(grid: pd.DataFrame, budget: int, chunk_size_s: float, k: int, rng: np.random.Generator) -> List[int]:
    selected = set(run_b6(grid, budget, chunk_size_s, rng))
    n_bins = len(grid)
    expanded = set(selected)
    for b in list(selected):
        for o in range(1, k + 1):
            if b - o >= 0:
                expanded.add(b - o)
            if b + o < n_bins:
                expanded.add(b + o)
    return sorted(expanded)


def run_ours(
    grid: pd.DataFrame,
    ref: pd.DataFrame,
    budget: int,
    rng: np.random.Generator,
    segment_id: str,
    trial: int,
    call_rows: List[Dict],
    variant: str = "v1",
) -> Tuple[List[int], Dict]:
    n_bins = len(grid)
    e0_pct = 20
    k = max(1, int(round(n_bins * e0_pct / 100.0)))
    top = grid.nlargest(k, "prior_score_max")
    e0 = set(int(x) for x in top["bin_idx"].tolist())

    queried: Set[int] = set()
    selected: Set[int] = set()
    audit_calls = 0
    discovery_calls = 0
    repair_calls = 0
    outside_positives: List[int] = []
    seed_to_trigger_call: Dict[int, str] = {}

    bin_to_row = {int(r["bin_idx"]): r for _, r in grid.iterrows()}

    def log_call(
        action_type: str,
        b: int,
        trigger_call_id: Optional[str] = None,
        trigger_unit_id: Optional[int] = None,
        repair_utility_value: Optional[float] = None,
        repair_window_start: Optional[float] = None,
        repair_window_end: Optional[float] = None,
        repair_reason: Optional[str] = None,
    ) -> str:
        call_id = f"{segment_id}_ours_b{budget}_t{trial}_{len(call_rows)}"
        row = bin_to_row[b]
        label = "positive" if row["is_positive"] else "negative"
        hit_event_id = row["event_id"] if row["is_positive"] else "none"
        hit_event_type = ""
        event_overlap = 0.0
        if row["is_positive"] and hit_event_id:
            ev = ref[ref["event_id"] == hit_event_id]
            if not ev.empty:
                ev = ev.iloc[0]
                event_overlap = max(0.0, min(row["t_end"], ev["t_end"]) - max(row["t_start"], ev["t_start"]))
                hit_event_type = ev["event_type"]
        call_rows.append({
            "call_id": call_id,
            "segment_id": segment_id,
            "round_id": trial,
            "budget": budget,
            "method": f"Frozen-LATE-AQP-{variant}",
            "action_type": action_type,
            "selected_unit_id": f"b{b}",
            "local_t_start": row["t_start"],
            "local_t_end": row["t_end"],
            "prior_score": row["prior_score_max"],
            "inside_E0_top20": b in e0,
            "oracle_label": label,
            "source_of_action": "V3_two_phase",
            "trigger_call_id": trigger_call_id if trigger_call_id else "",
            "trigger_unit_id": f"b{trigger_unit_id}" if trigger_unit_id is not None else "",
            "trigger_label": "positive" if trigger_unit_id is not None else "",
            "local_envelope_id": "e0_top20",
            "repair_window_start": repair_window_start if repair_window_start is not None else "",
            "repair_window_end": repair_window_end if repair_window_end is not None else "",
            "repair_reason": repair_reason if repair_reason else "",
            "repair_utility_value": repair_utility_value if repair_utility_value is not None else "",
            "audit_probability": "unknown_not_logged",
            "inclusion_probability": "unknown_not_logged",
            "is_used_for_estimator": action_type in ("audit_inside", "audit_outside"),
            "is_used_for_discovery": action_type.startswith("discovery") or action_type == "fallback_discovery",
            "is_used_for_repair": action_type == "repair_expansion",
            "hit_event_id": hit_event_id,
            "hit_event_type": hit_event_type,
            "event_overlap_duration": event_overlap,
            "selected_interval_id": "",
            "notes": "",
        })
        return call_id

    # --- Audit target per variant ---
    if variant == "v1":
        audit_calls_target = min(math.ceil(budget * 0.10), 3 * 2)
    elif variant == "floor_a":
        base = min(math.ceil(budget * 0.10), 3 * 2)
        floor = math.ceil(budget * 0.20) if budget <= 20 else 0
        audit_calls_target = max(base, floor)
    elif variant == "floor_b":
        base = min(math.ceil(budget * 0.10), 3 * 2)
        floor = math.ceil(budget * 0.30) if budget <= 20 else 0
        audit_calls_target = max(base, floor)
    elif variant == "cold_start_fallback":
        audit_calls_target = 0 if budget <= 20 else min(math.ceil(budget * 0.10), 3 * 2)
    else:
        raise ValueError(variant)
    audit_calls_target = max(0, min(audit_calls_target, budget))

    inside_bins = [b for b in range(n_bins) if b in e0]
    outside_bins = [b for b in range(n_bins) if b not in e0]
    n_inside = math.floor(audit_calls_target * 0.5)
    n_outside = audit_calls_target - n_inside

    inside_weights = {b: max(1e-6, bin_to_row[b]["prior_score_max"]) for b in inside_bins}
    outside_weights = {b: max(1e-6, bin_to_row[b]["prior_score_max"]) for b in outside_bins}

    def sample_weighted(pool: List[int], n: int, weights: Dict[int, float]) -> List[int]:
        if n <= 0 or not pool:
            return []
        pool = [b for b in pool if b not in queried]
        if not pool:
            return []
        n = min(n, len(pool))
        w = np.array([weights.get(b, 1e-6) for b in pool])
        w = w / w.sum()
        chosen = rng.choice(pool, size=n, replace=False, p=w).tolist()
        return [int(x) for x in chosen]

    audited_inside = sample_weighted(inside_bins, n_inside, inside_weights)
    audited_outside = sample_weighted(outside_bins, n_outside, outside_weights)
    for b in audited_inside:
        queried.add(b)
        selected.add(b)
        audit_calls += 1
        log_call("audit_inside", b)
    for b in audited_outside:
        queried.add(b)
        selected.add(b)
        audit_calls += 1
        call_id = log_call("audit_outside", b)
        if bin_to_row[b]["is_positive"]:
            outside_positives.append(b)
            seed_to_trigger_call[b] = call_id

    # Second tranche if leakage detected.
    if outside_positives:
        cap = round(budget * 0.25)
        extra = cap - audit_calls
        extra = max(0, min(extra, budget - audit_calls))
        if extra > 0:
            extra_outside = math.ceil(extra * 0.7)
            extra_inside = extra - extra_outside
            more_in = sample_weighted(inside_bins, extra_inside, inside_weights)
            more_out = sample_weighted(outside_bins, extra_outside, outside_weights)
            for b in more_in:
                queried.add(b)
                selected.add(b)
                audit_calls += 1
                log_call("audit_inside", b)
            for b in more_out:
                queried.add(b)
                selected.add(b)
                audit_calls += 1
                call_id = log_call("audit_outside", b)
                if bin_to_row[b]["is_positive"]:
                    outside_positives.append(b)
                    seed_to_trigger_call[b] = call_id

    # Repair phase.
    remaining = budget - audit_calls
    repair_seeds = list(set(outside_positives))
    if repair_seeds and remaining > 0:
        actions = []
        for seed in repair_seeds:
            seed_prior = bin_to_row[seed]["prior_score_max"]
            for nb in [max(0, seed - 1), min(n_bins - 1, seed + 1)]:
                if nb in queried:
                    continue
                utility = seed_prior  # U0_current
                actions.append((utility, seed, nb))
        actions.sort(key=lambda x: x[0], reverse=True)
        for _, seed, nb in actions:
            if remaining <= 0:
                break
            if nb in queried:
                continue
            queried.add(nb)
            selected.add(nb)
            repair_calls += 1
            remaining -= 1
            trigger_call_id = seed_to_trigger_call.get(seed)
            seed_row = bin_to_row[seed]
            log_call(
                "repair_expansion",
                nb,
                trigger_call_id=trigger_call_id,
                trigger_unit_id=seed,
                repair_utility_value=seed_row["prior_score_max"],
                repair_window_start=seed_row["t_start"],
                repair_window_end=seed_row["t_end"],
                repair_reason="audit_outside_positive",
            )

    # Discovery phase.
    remaining = budget - audit_calls - repair_calls
    if remaining > 0:
        unqueried = [b for b in range(n_bins) if b not in queried]
        ranked = sorted(unqueried, key=lambda b: bin_to_row[b]["prior_score_max"], reverse=True)
        for b in ranked[:remaining]:
            queried.add(b)
            selected.add(b)
            discovery_calls += 1
            action = "discovery_initial_envelope" if b in e0 else "fallback_discovery"
            log_call(action, b)

    budget_accounting_error = budget - (audit_calls + repair_calls + discovery_calls)
    diagnostics = {
        "audit_calls": audit_calls,
        "repair_calls": repair_calls,
        "discovery_calls": discovery_calls,
        "budget_accounting_error": budget_accounting_error,
        "outside_positives": len(outside_positives),
    }
    return sorted(selected), diagnostics


def run_variant_on_segment(
    grid: pd.DataFrame,
    ref: pd.DataFrame,
    segment_id: str,
    variant: str,
) -> List[Dict]:
    rows = []
    for budget in BUDGETS:
        for trial, seed_offset in enumerate(SEEDS):
            rng = np.random.default_rng(RANDOM_SEED_BASE + seed_offset)
            ours_calls: List[Dict] = []
            selected, diag = run_ours(grid, ref, budget, rng, segment_id, trial, ours_calls, variant=variant)
            metrics = compute_metrics(selected, grid, ref)
            metrics.update({
                "segment_id": segment_id,
                "method": f"Frozen-LATE-AQP-{variant}",
                "budget": budget,
                "trial": trial,
                "audit_calls": diag["audit_calls"],
                "discovery_calls": diag["discovery_calls"],
                "repair_calls": diag["repair_calls"],
                "budget_accounting_error": diag["budget_accounting_error"],
                "outside_positives": diag["outside_positives"],
            })
            rows.append(metrics)

            rng = np.random.default_rng(RANDOM_SEED_BASE + seed_offset)
            selected_b6 = run_b6(grid, budget, chunk_size_s=120, rng=rng)
            metrics_b6 = compute_metrics(selected_b6, grid, ref)
            metrics_b6.update({
                "segment_id": segment_id, "method": "B6_ExSample", "budget": budget, "trial": trial,
                "audit_calls": len(selected_b6), "discovery_calls": 0, "repair_calls": 0,
                "budget_accounting_error": budget - len(selected_b6), "outside_positives": 0,
            })
            rows.append(metrics_b6)

            rng = np.random.default_rng(RANDOM_SEED_BASE + seed_offset)
            selected_b7 = run_b7(grid, budget, chunk_size_s=120, k=3, rng=rng)
            metrics_b7 = compute_metrics(selected_b7, grid, ref)
            metrics_b7.update({
                "segment_id": segment_id, "method": "B7_ExSample_plus_expansion", "budget": budget, "trial": trial,
                "audit_calls": len(selected_b7), "discovery_calls": 0, "repair_calls": 0,
                "budget_accounting_error": budget - len(selected_b7), "outside_positives": 0,
            })
            rows.append(metrics_b7)
    return rows


def aggregate(rows: List[Dict], method: str) -> Dict[Tuple[int, str], float]:
    """Return mean per budget/metric for a method across trials."""
    groups = defaultdict(list)
    for r in rows:
        if r["method"] != method:
            continue
        b = int(r["budget"])
        for k in ["long_event_recall", "event_recall", "selected_precision", "selected_total_duration"]:
            if k in r and not (isinstance(r[k], float) and math.isnan(r[k])):
                groups[(b, k)].append(float(r[k]))
    out = {}
    for key, vals in groups.items():
        out[key] = sum(vals) / len(vals)
    return out


def main():
    proxy_scores = load_proxy_scores()

    # Build grids and refs.
    grids = {}
    refs = {}
    for seg in SEGMENTS:
        events_df = load_events(seg["events_path"])
        grid, ref = build_segment_grid(seg, events_df, proxy_scores)
        grids[seg["segment_id"]] = grid
        refs[seg["segment_id"]] = ref
        print(f"{seg['segment_id']}: {len(grid)} bins, {len(ref)} events, "
              f"long={sum(ref['event_type']=='long_interval')}, point={sum(ref['event_type']=='point_anchor')}, "
              f"label_source={seg['label_source']}")

    tuning_seg = "realcartest_5k_tuning"
    final_seg = "realcartest_3830_3920_final"

    # ---------- Tuning ----------
    variants = ["v1", "floor_a", "floor_b", "cold_start_fallback"]
    tuning_rows = []
    for variant in variants:
        print(f"\nTuning variant {variant} on {tuning_seg}")
        tuning_rows.extend(run_variant_on_segment(grids[tuning_seg], refs[tuning_seg], tuning_seg, variant))

    tuning_path = OUT / "tuning_results.csv"
    with open(tuning_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=tuning_rows[0].keys())
        w.writeheader(); w.writerows(tuning_rows)
    print(f"Wrote {tuning_path}")

    # Selection criterion: maximize average long-event recall at B=5, B=10 and B=20.
    # Only consider variants that do not destroy B=40 recall relative to v1.
    def avg_low_budget_recall(rows, variant, budgets=(5, 10, 20)):
        agg = aggregate(rows, f"Frozen-LATE-AQP-{variant}")
        vals = [agg.get((b, "long_event_recall"), 0.0) for b in budgets]
        return sum(vals) / len(vals)

    v1_b40 = aggregate(tuning_rows, "Frozen-LATE-AQP-v1").get((40, "long_event_recall"), 0.0)
    candidates = {}
    for v in variants:
        b40 = aggregate(tuning_rows, f"Frozen-LATE-AQP-{v}").get((40, "long_event_recall"), 0.0)
        if b40 >= v1_b40 - 0.05:  # allow at most 0.05 drop at B=40
            candidates[v] = avg_low_budget_recall(tuning_rows, v)
    if not candidates:
        # Fallback: just pick best low-budget recall even if B=40 drops.
        candidates = {v: avg_low_budget_recall(tuning_rows, v) for v in variants}

    best_variant = max(candidates, key=candidates.get)
    print(f"\nSelected variant: {best_variant} (avg B=10/20 long recall = {candidates[best_variant]:.3f})")

    # ---------- Final validation ----------
    final_rows = []
    # Run v1 and selected v2 for direct comparison, plus B6/B7.
    for variant in ["v1", best_variant]:
        print(f"\nFinal validation variant {variant} on {final_seg}")
        final_rows.extend(run_variant_on_segment(grids[final_seg], refs[final_seg], final_seg, variant))

    final_path = OUT / "final_validation_results.csv"
    with open(final_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=final_rows[0].keys())
        w.writeheader(); w.writerows(final_rows)
    print(f"Wrote {final_path}")

    # ---------- frozen_v2_config.md ----------
    config_md = "# Frozen-LATE-AQP-v2 Configuration\n\n"
    config_md += "This is the refrozen configuration selected after low-budget diagnosis and tuning.\n\n"
    config_md += "## Differences from v1\n\n"
    config_md += "Only the low-budget audit schedule changed; all other components (E0 top20 envelope, repair utility U0_current, discovery ranking, B6/B7 baselines) remain identical to v1.\n\n"
    config_md += f"- **Selected variant**: `{best_variant}`\n"
    if best_variant == "floor_a":
        config_md += "- **Audit schedule**: for budgets ≤ 20, enforce a minimum audit share of 20% (audit_calls_target = max(base, ceil(budget*0.20))). Budgets > 20 keep v1 schedule.\n"
    elif best_variant == "floor_b":
        config_md += "- **Audit schedule**: for budgets ≤ 20, enforce a minimum audit share of 30% (audit_calls_target = max(base, ceil(budget*0.30))). Budgets > 20 keep v1 schedule.\n"
    elif best_variant == "cold_start_fallback":
        config_md += "- **Audit schedule**: for budgets ≤ 20, skip audit entirely and use the full budget for discovery (repair trigger is disabled). Budgets > 20 keep v1 schedule.\n"
    else:
        config_md += "- **Audit schedule**: unchanged from v1.\n"
    tuning_spec = next(s for s in SEGMENTS if s["role"] == "tuning")
    final_spec = next(s for s in SEGMENTS if s["role"] == "final_validation")
    config_md += "\n## Tuning segment\n\n"
    config_md += f"- `{tuning_spec['segment_id']}` (label_source={tuning_spec['label_source']})\n"
    config_md += "\n## Final validation segment\n\n"
    config_md += f"- `{final_spec['segment_id']}` (label_source={final_spec['label_source']})\n"
    with open(OUT / "frozen_v2_config.md", "w") as f:
        f.write(config_md)

    # ---------- final_validation_report.md ----------
    def fmt(x):
        return f"{x:.3f}" if isinstance(x, (int, float)) else str(x)

    report_md = "# Final Validation Report — Frozen-LATE-AQP-v2\n\n"
    report_md += f"**Selected v2 variant**: `{best_variant}` (tuned on `{tuning_seg}`; validated on `{final_seg}`).\n\n"
    report_md += "## Tuning-stage long-event recall (source: tuning segment labels)\n\n"
    report_md += "| Budget | B6 | B7 | v1 | floor_a | floor_b | cold_start_fallback |\n"
    report_md += "|--------|----|----|----|---------|---------|---------------------|\n"
    for b in BUDGETS:
        vals = []
        for method in ["B6_ExSample", "B7_ExSample_plus_expansion", "Frozen-LATE-AQP-v1", "Frozen-LATE-AQP-floor_a", "Frozen-LATE-AQP-floor_b", "Frozen-LATE-AQP-cold_start_fallback"]:
            agg = aggregate(tuning_rows, method)
            v = agg.get((b, "long_event_recall"), float("nan"))
            vals.append(fmt(v))
        report_md += f"| {b} | " + " | ".join(vals) + " |\n"

    report_md += "\n## Final validation long-event recall (source: final validation segment labels)\n\n"
    report_md += "| Budget | B6 | B7 | v1 | v2 |\n"
    report_md += "|--------|----|----|----|----|\n"
    for b in BUDGETS:
        vals = []
        for method in ["B6_ExSample", "B7_ExSample_plus_expansion", "Frozen-LATE-AQP-v1", f"Frozen-LATE-AQP-{best_variant}"]:
            agg = aggregate(final_rows, method)
            v = agg.get((b, "long_event_recall"), float("nan"))
            vals.append(fmt(v))
        report_md += f"| {b} | " + " | ".join(vals) + " |\n"

    report_md += "\n## Final validation precision (source: final validation segment labels)\n\n"
    report_md += "| Budget | B6 | B7 | v1 | v2 |\n"
    report_md += "|--------|----|----|----|----|\n"
    for b in BUDGETS:
        vals = []
        for method in ["B6_ExSample", "B7_ExSample_plus_expansion", "Frozen-LATE-AQP-v1", f"Frozen-LATE-AQP-{best_variant}"]:
            agg = aggregate(final_rows, method)
            v = agg.get((b, "selected_precision"), float("nan"))
            vals.append(fmt(v))
        report_md += f"| {b} | " + " | ".join(vals) + " |\n"

    report_md += "\n## Final validation selected duration (source: final validation segment labels)\n\n"
    report_md += "| Budget | B6 | B7 | v1 | v2 |\n"
    report_md += "|--------|----|----|----|----|\n"
    for b in BUDGETS:
        vals = []
        for method in ["B6_ExSample", "B7_ExSample_plus_expansion", "Frozen-LATE-AQP-v1", f"Frozen-LATE-AQP-{best_variant}"]:
            agg = aggregate(final_rows, method)
            v = agg.get((b, "selected_total_duration"), float("nan"))
            vals.append(fmt(v))
        report_md += f"| {b} | " + " | ".join(vals) + " |\n"

    # Compute some summary comparisons.
    def get_recall(rows, method, budget):
        return aggregate(rows, method).get((budget, "long_event_recall"), 0.0)
    def get_prec(rows, method, budget):
        return aggregate(rows, method).get((budget, "selected_precision"), 0.0)

    report_md += "\n## Key comparisons\n\n"
    for b in [10, 20, 40, 80]:
        v1_r = get_recall(final_rows, "Frozen-LATE-AQP-v1", b)
        v2_r = get_recall(final_rows, f"Frozen-LATE-AQP-{best_variant}", b)
        v1_p = get_prec(final_rows, "Frozen-LATE-AQP-v1", b)
        v2_p = get_prec(final_rows, f"Frozen-LATE-AQP-{best_variant}", b)
        report_md += f"- B={b}: v2 long recall {fmt(v2_r)} vs v1 {fmt(v1_r)} (Δ {fmt(v2_r-v1_r)}); precision {fmt(v2_p)} vs v1 {fmt(v1_p)} (Δ {fmt(v2_p-v1_p)}).\n"

    report_md += "\n## Conclusion\n\n"
    low_improved = (get_recall(final_rows, f"Frozen-LATE-AQP-{best_variant}", 10) > get_recall(final_rows, "Frozen-LATE-AQP-v1", 10)) and \
                   (get_recall(final_rows, f"Frozen-LATE-AQP-{best_variant}", 20) > get_recall(final_rows, "Frozen-LATE-AQP-v1", 20))
    high_kept = (get_recall(final_rows, f"Frozen-LATE-AQP-{best_variant}", 40) >= get_recall(final_rows, "Frozen-LATE-AQP-v1", 40) - 0.05) and \
                (get_recall(final_rows, f"Frozen-LATE-AQP-{best_variant}", 80) >= get_recall(final_rows, "Frozen-LATE-AQP-v1", 80) - 0.05)
    if low_improved and high_kept:
        report_md += "Frozen-LATE-AQP-v2 improves low-budget long-event recall while keeping the B=40/80 recall advantage within the 0.05 tolerance.\n"
    elif low_improved:
        report_md += "Frozen-LATE-AQP-v2 improves low-budget long-event recall, but the B=40/80 advantage is partially eroded; see tables above for the trade-off.\n"
    else:
        report_md += "Frozen-LATE-AQP-v2 does **not** consistently improve low-budget long-event recall on the final validation segment. The low-budget failure remains unresolved.\n"

    report_md += "\n## Data provenance note\n\n"
    report_md += f"- Tuning data: `{tuning_spec['segment_id']}` uses `{tuning_spec['label_source']}` labels.\n"
    report_md += f"- Final validation data: `{final_spec['segment_id']}` uses `{final_spec['label_source']}` labels.\n"
    report_md += "- `test` video could not be read by OpenCV, so no labels were generated for it.\n"
    report_md += "- `realcartest.mp4` was no longer present in the workspace, so no additional realcartest footage beyond existing center10 labels could be labeled.\n"

    with open(OUT / "final_validation_report.md", "w") as f:
        f.write(report_md)
    print(f"Wrote {OUT / 'final_validation_report.md'}")


if __name__ == "__main__":
    main()
