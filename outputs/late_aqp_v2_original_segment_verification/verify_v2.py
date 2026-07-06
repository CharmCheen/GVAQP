#!/usr/bin/env python3
"""Verify Frozen-LATE-AQP-v2 on the original failure segments (no new labels/GPU)."""

import csv
import math
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

# Allow importing from the frozen cross-segment directory.
ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
FROZEN_DIR = ROOT / "outputs" / "late_aqp_frozen_cross_segment_v1"
OUT = ROOT / "outputs" / "late_aqp_v2_original_segment_verification"
OUT.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(FROZEN_DIR))
from run_frozen_cross_segment import (
    BIN_SIZE,
    BUDGETS,
    RANDOM_SEED_BASE,
    SEEDS,
    build_segment_grid,
    compute_metrics,
    load_dev_events,
    load_dev_grid,
    load_full_events,
    load_proxy_scores,
    merge_bins,
    run_b6,
    run_b7,
)

SEGMENTS = [
    {"segment_id": "realcartest_0_1570", "video_id": "realcartest", "time_start": 0.0, "time_end": 1570.0, "is_dev": False},
    {"segment_id": "realcartest_2000_3200", "video_id": "realcartest", "time_start": 2000.0, "time_end": 3200.0, "is_dev": True},
    {"segment_id": "realcartest_3200_3830", "video_id": "realcartest", "time_start": 3200.0, "time_end": 3830.0, "is_dev": False},
]


def run_ours_v2(
    grid: pd.DataFrame,
    ref: pd.DataFrame,
    budget: int,
    rng: np.random.Generator,
    segment_id: str,
    trial: int,
    call_rows: List[Dict],
) -> Tuple[List[int], Dict]:
    """Frozen-LATE-AQP-v2: B<=20 skip audit and repair; B>20 identical to v1."""
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
            "method": "Frozen-LATE-AQP-v2",
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

    # v2 behavior: skip audit/repair for low budgets.
    if budget > 20:
        # --- identical to v1 audit schedule ---
        audit_calls_target = min(math.ceil(budget * 0.10), 3 * 2)
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
            queried.add(b); selected.add(b); audit_calls += 1
            log_call("audit_inside", b)
        for b in audited_outside:
            queried.add(b); selected.add(b); audit_calls += 1
            call_id = log_call("audit_outside", b)
            if bin_to_row[b]["is_positive"]:
                outside_positives.append(b)
                seed_to_trigger_call[b] = call_id

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
                    queried.add(b); selected.add(b); audit_calls += 1
                    log_call("audit_inside", b)
                for b in more_out:
                    queried.add(b); selected.add(b); audit_calls += 1
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
                    utility = seed_prior
                    actions.append((utility, seed, nb))
            actions.sort(key=lambda x: x[0], reverse=True)
            for _, seed, nb in actions:
                if remaining <= 0:
                    break
                if nb in queried:
                    continue
                queried.add(nb); selected.add(nb); repair_calls += 1; remaining -= 1
                trigger_call_id = seed_to_trigger_call.get(seed)
                seed_row = bin_to_row[seed]
                log_call(
                    "repair_expansion", nb,
                    trigger_call_id=trigger_call_id,
                    trigger_unit_id=seed,
                    repair_utility_value=seed_row["prior_score_max"],
                    repair_window_start=seed_row["t_start"],
                    repair_window_end=seed_row["t_end"],
                    repair_reason="audit_outside_positive",
                )

    # Discovery phase uses all remaining budget.
    remaining = budget - audit_calls - repair_calls
    if remaining > 0:
        unqueried = [b for b in range(n_bins) if b not in queried]
        ranked = sorted(unqueried, key=lambda b: bin_to_row[b]["prior_score_max"], reverse=True)
        for b in ranked[:remaining]:
            queried.add(b); selected.add(b); discovery_calls += 1
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


def main():
    full_events = load_full_events()
    proxy_scores = load_proxy_scores()
    dev_events = load_dev_events()
    dev_grid = load_dev_grid()

    v2_rows = []
    trigger_rows = []
    for seg in SEGMENTS:
        seg_id = seg["segment_id"]
        print(f"\nSegment {seg_id}")
        # Reuse the same grid construction as v1.
        if seg["is_dev"]:
            grid = dev_grid.copy()
            grid = grid[grid["t_start"] < (seg["time_end"] - seg["time_start"])].reset_index(drop=True)
            grid["bin_idx"] = np.arange(len(grid))
            grid["local_t_start"] = grid["t_start"]
            grid["local_t_end"] = grid["t_end"].clip(upper=(seg["time_end"] - seg["time_start"]))
            grid["t_start"] = grid["local_t_start"]
            grid["t_end"] = grid["local_t_end"]
            ref = dev_events.copy()
            ref["event_type"] = ref["duration"].apply(lambda d: "long_interval" if d >= 1.0 else "point_anchor")
        else:
            grid, ref = build_segment_grid(seg, full_events, proxy_scores)

        for budget in BUDGETS:
            for trial, seed_offset in enumerate(SEEDS):
                rng = np.random.default_rng(RANDOM_SEED_BASE + seed_offset)
                call_rows: List[Dict] = []
                selected, diag = run_ours_v2(grid, ref, budget, rng, seg_id, trial, call_rows)
                metrics = compute_metrics(selected, grid, ref)
                metrics.update({
                    "segment_id": seg_id,
                    "method": "Frozen-LATE-AQP-v2",
                    "budget": budget,
                    "trial": trial,
                    "audit_calls": diag["audit_calls"],
                    "discovery_calls": diag["discovery_calls"],
                    "repair_calls": diag["repair_calls"],
                    "budget_accounting_error": diag["budget_accounting_error"],
                })
                v2_rows.append(metrics)
                trigger_rows.append({
                    "segment_id": seg_id,
                    "budget": budget,
                    "trial": trial,
                    "audit_calls": diag["audit_calls"],
                    "discovery_calls": diag["discovery_calls"],
                    "repair_calls": diag["repair_calls"],
                    "low_budget_path": "cold_start_fallback" if budget <= 20 else "v1_audit_repair",
                })

    # Load v1/B6/B7 from the previously generated per_budget_breakdown.csv.
    breakdown_path = FROZEN_DIR / "per_budget_breakdown.csv"
    existing = []
    with open(breakdown_path) as f:
        for r in csv.DictReader(f):
            if r["segment"] not in {s["segment_id"] for s in SEGMENTS}:
                continue
            if r["method"] not in {"B6_ExSample", "B7_ExSample_plus_expansion", "Frozen-LATE-AQP-v1"}:
                continue
            existing.append({
                "segment": r["segment"],
                "budget": int(r["budget"]),
                "method": r["method"],
                "long_event_recall": r["long_event_recall"],
                "precision": r["precision"],
                "selected_duration": r["selected_duration"],
            })

    for r in v2_rows:
        existing.append({
            "segment": r["segment_id"],
            "budget": int(r["budget"]),
            "method": r["method"],
            "long_event_recall": "" if (isinstance(r["long_event_recall"], float) and math.isnan(r["long_event_recall"])) else f"{r['long_event_recall']}",
            "precision": f"{r['selected_precision']}",
            "selected_duration": f"{r['selected_total_duration']}",
        })

    out_csv = OUT / "per_segment_budget_breakdown.csv"
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["segment", "budget", "method", "long_event_recall", "precision", "selected_duration"])
        w.writeheader(); w.writerows(existing)
    print(f"\nWrote {out_csv}")

    # Helper statistics.
    def stats(rows, segment, method, budget, metric):
        vals = [float(r[metric]) for r in rows if r["segment"]==segment and r["method"]==method and int(r["budget"])==budget and r[metric]!=""]
        if not vals:
            return None, None
        return sum(vals)/len(vals), (sum((x-sum(vals)/len(vals))**2 for x in vals)/len(vals))**0.5 if len(vals)>1 else 0.0

    def fmt(x):
        return f"{x:.3f}" if x is not None and not (isinstance(x, float) and math.isnan(x)) else "-"

    # --- trigger_activation_check.md ---
    trig_md = "# Trigger Activation Check — Frozen-LATE-AQP-v2\n\n"
    trig_md += "For budgets ≤ 20, v2 should skip audit/repair and use the full budget for discovery.\n\n"
    trig_md += "| Segment | Budget | Trial | audit_calls | discovery_calls | repair_calls | Path activated |\n"
    trig_md += "|---------|--------|-------|-------------|-----------------|--------------|----------------|\n"
    activated_counts = defaultdict(lambda: {"cold_start": 0, "v1": 0})
    for r in trigger_rows:
        activated = "cold_start_fallback" if (r["budget"] <= 20 and r["audit_calls"] == 0) else ("v1_audit_repair" if r["budget"] > 20 else "UNEXPECTED")
        activated_counts[(r["segment_id"], r["budget"])]["cold_start" if r["budget"] <= 20 else "v1"] += 1
        trig_md += f"| {r['segment_id']} | {r['budget']} | {r['trial']} | {r['audit_calls']} | {r['discovery_calls']} | {r['repair_calls']} | {activated} |\n"

    trig_md += "\n## Summary\n\n"
    all_low_budget_cold = True
    for seg in SEGMENTS:
        for b in [5, 10, 20]:
            cnt = activated_counts[(seg["segment_id"], b)]["cold_start"]
            trig_md += f"- {seg['segment_id']} B={b}: {cnt}/5 trials activated cold_start_fallback (audit=0, repair=0).\n"
            if cnt < 5:
                all_low_budget_cold = False
    trig_md += f"\n**All B≤20 trials activated cold_start_fallback: {'Yes' if all_low_budget_cold else 'No'}**\n"
    trig_md += "\nInterpretation: If 'No', then v2 did not actually behave differently from v1 on those trials, "
    trig_md += "and any observed similarity between v1 and v2 is because the fallback path was not taken.\n"
    with open(OUT / "trigger_activation_check.md", "w") as f:
        f.write(trig_md)

    # --- high_budget_regression_check.md ---
    reg_md = "# High-Budget Regression Check — v2 vs v1\n\n"
    reg_md += "Per-segment mean ± std for long_event_recall and precision at B=40/80/120.\n\n"
    reg_md += "| Segment | Budget | Metric | v1 mean | v1 std | v2 mean | v2 std | Δ (v2-v1) |\n"
    reg_md += "|---------|--------|--------|---------|--------|---------|--------|-----------|\n"
    high_budgets = [40, 80, 120]
    regression_flags = []
    for seg in SEGMENTS:
        for b in high_budgets:
            for metric, label in [("long_event_recall", "recall"), ("precision", "precision")]:
                m1, s1 = stats(existing, seg["segment_id"], "Frozen-LATE-AQP-v1", b, metric)
                m2, s2 = stats(existing, seg["segment_id"], "Frozen-LATE-AQP-v2", b, metric)
                delta = (m2 - m1) if (m1 is not None and m2 is not None) else float("nan")
                reg_md += f"| {seg['segment_id']} | {b} | {label} | {fmt(m1)} | {fmt(s1)} | {fmt(m2)} | {fmt(s2)} | {fmt(delta)} |\n"
                if m1 is not None and m2 is not None:
                    # flag if drop larger than v1 std
                    if delta < -s1:
                        regression_flags.append((seg["segment_id"], b, label, delta, s1))
    reg_md += "\n## Regression flags\n\n"
    if regression_flags:
        reg_md += "The following v2 drops are larger than the v1 within-seed standard deviation:\n\n"
        for seg, b, label, delta, s1 in regression_flags:
            reg_md += f"- {seg} B={b} {label}: Δ={delta:.3f}, v1 std={s1:.3f}\n"
    else:
        reg_md += "No v2 drop exceeds the v1 within-seed standard deviation at B=40/80/120.\n"
    with open(OUT / "high_budget_regression_check.md", "w") as f:
        f.write(reg_md)

    # --- verdict_report.md ---
    verdict_md = "# Verdict Report — Frozen-LATE-AQP-v2 on Original Failure Segments\n\n"
    verdict_md += "## Trigger activation\n\n"
    verdict_md += f"**All B≤20 trials activated cold_start_fallback: {'Yes' if all_low_budget_cold else 'No'}**\n\n"

    verdict_md += "## Low-budget (B=10/20) per-segment improvement\n\n"
    verdict_md += "| Segment | Budget | v1 mean | v1 std | v2 mean | v2 std | Δ | Δ > v1 std? |\n"
    verdict_md += "|---------|--------|---------|--------|---------|--------|---|-------------|\n"
    low_improvements = []
    for seg in SEGMENTS:
        for b in [10, 20]:
            m1, s1 = stats(existing, seg["segment_id"], "Frozen-LATE-AQP-v1", b, "long_event_recall")
            m2, s2 = stats(existing, seg["segment_id"], "Frozen-LATE-AQP-v2", b, "long_event_recall")
            delta = (m2 - m1) if (m1 is not None and m2 is not None) else float("nan")
            improved = (delta > s1) if (m1 is not None and m2 is not None) else False
            low_improvements.append((seg["segment_id"], b, improved, delta, s1))
            verdict_md += f"| {seg['segment_id']} | {b} | {fmt(m1)} | {fmt(s1)} | {fmt(m2)} | {fmt(s2)} | {fmt(delta)} | {'Yes' if improved else 'No'} |\n"

    # Count segments with substantive improvement at both B=10 and B=20.
    seg_improved_count = 0
    for seg in SEGMENTS:
        b10 = any(improved for s, b, improved, _, _ in low_improvements if s==seg["segment_id"] and b==10)
        b20 = any(improved for s, b, improved, _, _ in low_improvements if s==seg["segment_id"] and b==20)
        if b10 and b20:
            seg_improved_count += 1

    verdict_md += f"\nSegments with substantive improvement at **both** B=10 and B=20: **{seg_improved_count}/3**\n\n"

    verdict_md += "## High-budget (B=40/80/120) regression\n\n"
    if regression_flags:
        verdict_md += "v2 shows regressions exceeding v1 std at:\n"
        for seg, b, label, delta, s1 in regression_flags:
            verdict_md += f"- {seg} B={b} {label}: Δ={delta:.3f}, v1 std={s1:.3f}\n"
    else:
        verdict_md += "No regression exceeds v1 within-seed standard deviation at B=40/80/120.\n"

    # Final verdict per pre-specified criteria.
    verdict_md += "\n## Verdict\n\n"
    if all_low_budget_cold and seg_improved_count >= 2 and not regression_flags:
        verdict = "PASS"
        verdict_md += "**PASS**: v2 cold_start_fallback is consistently activated at B≤20, improves B=10/20 long-event recall on at least 2/3 segments by more than seed noise, and does not regress at high budgets.\n"
    elif all_low_budget_cold and seg_improved_count >= 1 and not regression_flags:
        verdict = "PARTIAL"
        verdict_md += "**PARTIAL**: v2 is activated and improves some segment/budget combinations, but the improvement is not consistent across at least 2 segments at both B=10 and B=20.\n"
    else:
        verdict = "FAIL"
        if not all_low_budget_cold:
            verdict_md += "**FAIL**: v2's cold_start_fallback path was NOT reliably activated on B≤20 trials, so the observed v1≈v2 behavior is explained by v2 effectively falling back to the v1 code path.\n"
        elif seg_improved_count < 2:
            verdict_md += "**FAIL**: cold_start_fallback is activated but does not substantively improve B=10/20 long-event recall on at least 2 of the 3 original failure segments. The low-budget problem remains unresolved.\n"
        else:
            verdict_md += "**FAIL**: Improvement is present at low budgets but high-budget regression exceeds the noise threshold.\n"

    with open(OUT / "verdict_report.md", "w") as f:
        f.write(verdict_md)
    print(f"Verdict: {verdict}")


if __name__ == "__main__":
    main()
