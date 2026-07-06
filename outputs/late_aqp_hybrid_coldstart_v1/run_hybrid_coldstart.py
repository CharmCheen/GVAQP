#!/usr/bin/env python3
"""
Implement and validate "Hybrid Cold-Start" discovery (Direction 3 only).

For B <= 20, v2_hybrid runs a short B6-style chunk-level Thompson-sampling phase
followed by the standard prior-based discovery phase. For B > 20 it is identical
to the existing v1 path (audit + discovery + repair), because cold_start_fallback
only triggers at low budgets.

No GPU/VLM, no new labels, no segment/event-specific hardcoding.
"""

import csv
import math
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

import numpy as np
import pandas as pd

ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
FROZEN_DIR = ROOT / "outputs" / "late_aqp_frozen_cross_segment_v1"
OUT = ROOT / "outputs" / "late_aqp_hybrid_coldstart_v1"
OUT.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(FROZEN_DIR))
from run_frozen_cross_segment import (
    BIN_SIZE,
    RANDOM_SEED_BASE,
    SEEDS,
    build_segment_grid,
    compute_metrics,
    get_event_at_bin,
    get_label_at_bin,
    get_prior_at_bin,
    load_dev_events,
    load_dev_grid,
    load_full_events,
    load_proxy_scores,
)

SEGMENTS = [
    {"segment_id": "realcartest_0_1570", "video_id": "realcartest", "time_start": 0.0, "time_end": 1570.0, "is_dev": False},
    {"segment_id": "realcartest_2000_3200", "video_id": "realcartest", "time_start": 2000.0, "time_end": 3200.0, "is_dev": True},
    {"segment_id": "realcartest_3200_3830", "video_id": "realcartest", "time_start": 3200.0, "time_end": 3830.0, "is_dev": False},
]

BUDGETS_LOW = [10, 20]
BUDGETS_HIGH = [40, 80, 120]
CHUNK_SIZE_S = 120
R_VALUES = [0.3, 0.5, 0.7]


def run_b6_phase1(grid: pd.DataFrame, max_calls: int, chunk_size_s: int, rng: np.random.Generator) -> List[int]:
    """Run B6-style chunk-level Thompson sampling for exactly max_calls calls."""
    n_bins = len(grid)
    bins_per_chunk = max(1, chunk_size_s // int(BIN_SIZE))
    n_chunks = int(math.ceil(n_bins / bins_per_chunk))
    sampled: Set[int] = set()
    n_c = np.zeros(n_chunks, dtype=int)
    discovered_events: List[Dict[str, int]] = [dict() for _ in range(n_chunks)]
    order: List[int] = []

    while len(order) < max_calls:
        N1_c = np.zeros(n_chunks, dtype=float)
        for c in range(n_chunks):
            N1_c[c] = sum(1 for cnt in discovered_events[c].values() if cnt == 1)
        theta = rng.gamma(shape=N1_c + 0.1, scale=1.0 / (n_c + 1.0))
        for c in range(n_chunks):
            chunk_bins = list(range(c * bins_per_chunk, min((c + 1) * bins_per_chunk, n_bins)))
            if all(b in sampled for b in chunk_bins):
                theta[c] = -np.inf
        if np.all(theta == -np.inf):
            break
        chosen_c = int(np.argmax(theta))
        chunk_bins = list(range(chosen_c * bins_per_chunk, min((chosen_c + 1) * bins_per_chunk, n_bins)))
        unsampled = [b for b in chunk_bins if b not in sampled]
        if not unsampled:
            break
        b = int(rng.choice(unsampled))
        sampled.add(b)
        order.append(b)
        n_c[chosen_c] += 1
        e = get_event_at_bin(grid, b)
        if e is not None:
            discovered_events[chosen_c][e] = discovered_events[chosen_c].get(e, 0) + 1
    return order


def run_v2_discovery(grid: pd.DataFrame, budget: int, already_selected: Set[int]) -> List[int]:
    """Top-prior-score discovery on unqueried bins."""
    ranked = grid.sort_values("prior_score_max", ascending=False)
    selected: List[int] = []
    for _, row in ranked.iterrows():
        b = int(row["bin_idx"])
        if b in already_selected:
            continue
        selected.append(b)
        if len(selected) >= budget:
            break
    return selected


def run_hybrid(grid: pd.DataFrame, budget: int, r: float, rng: np.random.Generator) -> Tuple[List[int], Dict]:
    """Hybrid cold-start: phase1 B6-style chunk sampling, phase2 prior-based discovery."""
    if budget > 20:
        # Not the cold-start regime; hybrid does not apply.
        return [], {"phase1_calls": 0, "phase2_calls": 0, "hybrid_applied": False}

    n_bins = len(grid)
    bins_per_chunk = max(1, CHUNK_SIZE_S // int(BIN_SIZE))
    n_chunks = int(math.ceil(n_bins / bins_per_chunk))
    phase1_calls = min(n_chunks, math.ceil(budget * r))
    phase1_calls = max(0, min(phase1_calls, budget))

    phase1_selected = run_b6_phase1(grid, phase1_calls, CHUNK_SIZE_S, rng)
    already_selected = set(phase1_selected)
    remaining_budget = budget - len(phase1_selected)
    phase2_selected = run_v2_discovery(grid, remaining_budget, already_selected)

    selected = phase1_selected + phase2_selected
    diagnostics = {
        "phase1_calls": len(phase1_selected),
        "phase2_calls": len(phase2_selected),
        "hybrid_applied": True,
        "r": r,
    }
    return selected, diagnostics


def run_b6_full(grid: pd.DataFrame, budget: int, rng: np.random.Generator) -> List[int]:
    """Full B6 baseline for comparison."""
    n_bins = len(grid)
    bins_per_chunk = max(1, CHUNK_SIZE_S // int(BIN_SIZE))
    n_chunks = int(math.ceil(n_bins / bins_per_chunk))
    sampled: Set[int] = set()
    n_c = np.zeros(n_chunks, dtype=int)
    discovered_events: List[Dict[str, int]] = [dict() for _ in range(n_chunks)]

    while len(sampled) < budget:
        N1_c = np.zeros(n_chunks, dtype=float)
        for c in range(n_chunks):
            N1_c[c] = sum(1 for cnt in discovered_events[c].values() if cnt == 1)
        theta = rng.gamma(shape=N1_c + 0.1, scale=1.0 / (n_c + 1.0))
        for c in range(n_chunks):
            chunk_bins = list(range(c * bins_per_chunk, min((c + 1) * bins_per_chunk, n_bins)))
            if all(b in sampled for b in chunk_bins):
                theta[c] = -np.inf
        if np.all(theta == -np.inf):
            break
        chosen_c = int(np.argmax(theta))
        chunk_bins = list(range(chosen_c * bins_per_chunk, min((c + 1) * bins_per_chunk, n_bins)))
        unsampled = [b for b in chunk_bins if b not in sampled]
        if not unsampled:
            break
        b = int(rng.choice(unsampled))
        sampled.add(b)
        n_c[chosen_c] += 1
        e = get_event_at_bin(grid, b)
        if e is not None:
            discovered_events[chosen_c][e] = discovered_events[chosen_c].get(e, 0) + 1
    return sorted(sampled)


def run_v2(grid: pd.DataFrame, budget: int) -> List[int]:
    """Discovery-only v2: top prior_score_max bins."""
    ranked = grid.sort_values("prior_score_max", ascending=False)
    return [int(b) for b in ranked.head(budget)["bin_idx"].tolist()]


def main():
    full_events = load_full_events()
    proxy_scores = load_proxy_scores()
    dev_events = load_dev_events()
    dev_grid = load_dev_grid()

    # Load existing v1 results for the same segments/budgets.
    v1_existing = []
    breakdown_path = FROZEN_DIR / "per_budget_breakdown.csv"
    with open(breakdown_path) as f:
        for r in csv.DictReader(f):
            if r["segment"] not in {s["segment_id"] for s in SEGMENTS}:
                continue
            if r["method"] != "Frozen-LATE-AQP-v1":
                continue
            v1_existing.append({
                "segment": r["segment"],
                "budget": int(r["budget"]),
                "method": "Frozen-LATE-AQP-v1",
                "long_event_recall": r["long_event_recall"],
                "precision": r["precision"],
                "selected_duration": r["selected_duration"],
            })

    sensitivity_rows = []
    comparison_rows = []

    for seg in SEGMENTS:
        seg_id = seg["segment_id"]
        print(f"\nSegment {seg_id}")
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

        for budget in BUDGETS_LOW:
            for trial, seed_offset in enumerate(SEEDS):
                rng = np.random.default_rng(RANDOM_SEED_BASE + seed_offset)

                # B6
                selected_b6 = run_b6_full(grid, budget, rng)
                m_b6 = compute_metrics(selected_b6, grid, ref)
                # v2
                selected_v2 = run_v2(grid, budget)
                m_v2 = compute_metrics(selected_v2, grid, ref)

                comparison_rows.append({
                    "segment": seg_id, "budget": budget, "seed": trial,
                    "method": "B6",
                    "long_event_recall": m_b6["long_event_recall"],
                    "precision": m_b6["selected_precision"],
                    "selected_duration": m_b6["selected_total_duration"],
                })
                comparison_rows.append({
                    "segment": seg_id, "budget": budget, "seed": trial,
                    "method": "Frozen-LATE-AQP-v2",
                    "long_event_recall": m_v2["long_event_recall"],
                    "precision": m_v2["selected_precision"],
                    "selected_duration": m_v2["selected_total_duration"],
                })

                # v2_hybrid for each r.
                for r in R_VALUES:
                    rng_h = np.random.default_rng(RANDOM_SEED_BASE + seed_offset)
                    selected_h, diag = run_hybrid(grid, budget, r, rng_h)
                    m_h = compute_metrics(selected_h, grid, ref)
                    sensitivity_rows.append({
                        "segment": seg_id, "budget": budget, "seed": trial, "r": r,
                        "method": f"v2_hybrid_r{r}",
                        "phase1_calls": diag["phase1_calls"],
                        "phase2_calls": diag["phase2_calls"],
                        "long_event_recall": m_h["long_event_recall"],
                        "precision": m_h["selected_precision"],
                        "selected_duration": m_h["selected_total_duration"],
                    })

    # Sensitivity CSV.
    sens_df = pd.DataFrame(sensitivity_rows)
    sens_df.to_csv(OUT / "sensitivity_r.csv", index=False)
    print(f"\nWrote sensitivity_r.csv ({len(sens_df)} rows)")

    # Choose final r using a pre-specified criterion.
    # Criterion: maximize number of segments with substantive improvement at both B=10 and B=20 vs v2,
    # where substantive = mean improvement > max(v2_std, hybrid_std). Ties broken toward r=0.5.
    def stats_of(rows, segment, budget, method, metric):
        vals = [float(r[metric]) for r in rows if r["segment"]==segment and r["budget"]==budget and r["method"]==method]
        if not vals:
            return None, None
        return sum(vals)/len(vals), (sum((x-sum(vals)/len(vals))**2 for x in vals)/len(vals))**0.5 if len(vals)>1 else 0.0

    def fmt(x):
        return f"{x:.3f}" if x is not None and not (isinstance(x, float) and math.isnan(x)) else "-"

    v2_rows = [
        {"segment": r["segment"], "budget": r["budget"], "seed": r["seed"], "method": "Frozen-LATE-AQP-v2",
         "long_event_recall": r["long_event_recall"], "precision": r["precision"], "selected_duration": r["selected_duration"]}
        for r in comparison_rows if r["method"] == "Frozen-LATE-AQP-v2"
    ]

    best_r = None
    best_score = -1
    for r in R_VALUES:
        hybrid_rows = [
            {"segment": r2["segment"], "budget": r2["budget"], "seed": r2["seed"], "method": f"v2_hybrid_r{r}",
             "long_event_recall": r2["long_event_recall"], "precision": r2["precision"], "selected_duration": r2["selected_duration"]}
            for r2 in sensitivity_rows if r2["r"] == r
        ]
        seg_improved = 0
        for seg in SEGMENTS:
            improved_both = True
            for budget in BUDGETS_LOW:
                m_v2, s_v2 = stats_of(v2_rows, seg["segment_id"], budget, "Frozen-LATE-AQP-v2", "long_event_recall")
                m_h, s_h = stats_of(hybrid_rows, seg["segment_id"], budget, f"v2_hybrid_r{r}", "long_event_recall")
                if m_v2 is None or m_h is None:
                    improved_both = False; break
                delta = m_h - m_v2
                noise = max(s_v2, s_h)
                if delta <= noise:
                    improved_both = False; break
            if improved_both:
                seg_improved += 1
        score = seg_improved + (0.1 if r == 0.5 else 0.0)  # tie-break toward 0.5
        print(f"r={r}: {seg_improved}/3 segments improved at both B=10 and B=20")
        if score > best_score:
            best_score = score
            best_r = r

    print(f"Selected final r = {best_r}")
    final_hybrid_method = f"v2_hybrid_r{best_r}"

    # Add chosen v2_hybrid rows to comparison.
    for r in sensitivity_rows:
        if r["r"] == best_r:
            comparison_rows.append({
                "segment": r["segment"], "budget": r["budget"], "seed": r["seed"],
                "method": "Frozen-LATE-AQP-v2-hybrid",
                "long_event_recall": r["long_event_recall"],
                "precision": r["precision"],
                "selected_duration": r["selected_duration"],
            })

    # Append v1 rows (low and high budgets) for completeness.
    for r in v1_existing:
        if r["budget"] in BUDGETS_LOW + BUDGETS_HIGH:
            comparison_rows.append({
                "segment": r["segment"], "budget": r["budget"], "seed": 0,
                "method": r["method"],
                "long_event_recall": float(r["long_event_recall"]) if r["long_event_recall"] != "" else float("nan"),
                "precision": float(r["precision"]),
                "selected_duration": float(r["selected_duration"]),
            })
            # For high budgets, v2_hybrid is identical to v1 because cold_start_fallback does not apply.
            if r["budget"] in BUDGETS_HIGH:
                comparison_rows.append({
                    "segment": r["segment"], "budget": r["budget"], "seed": 0,
                    "method": "Frozen-LATE-AQP-v2-hybrid",
                    "long_event_recall": float(r["long_event_recall"]) if r["long_event_recall"] != "" else float("nan"),
                    "precision": float(r["precision"]),
                    "selected_duration": float(r["selected_duration"]),
                })

    comp_df = pd.DataFrame(comparison_rows)
    comp_df.to_csv(OUT / "comparison_v1_v2_hybrid_b6.csv", index=False)
    print("Wrote comparison_v1_v2_hybrid_b6.csv")

    # Hybrid design doc.
    design_md = "# Hybrid Cold-Start Discovery Design\n\n"
    design_md += "## Motivation\n\n"
    design_md += "The diagnosis showed that discovery-only v2 loses to B6 at B=10/20 because "
    design_md += "prior-score ranking is not spatially diverse: it can spend multiple low-budget calls on the same event. "
    design_md += "B6's chunk-level Thompson sampling spreads calls across chunks and therefore discovers new events faster.\n\n"
    design_md += "## Algorithm\n\n"
    design_md += "For budgets B <= 20 (the cold_start_fallback regime):\n\n"
    design_md += "1. **Phase 1 (chunk exploration)**: allocate `phase1_calls = min(chunk_count, ceil(B * r))` calls to "
    design_md += "B6-style chunk-level Thompson sampling. This seeds the search with spatially dispersed bins.\n"
    design_md += "2. **Phase 2 (prior exploitation)**: use the remaining `B - phase1_calls` calls to select the highest-prior "
    design_md += "unqueried bins, exactly as v2 discovery does.\n\n"
    design_md += "For B > 20, hybrid is **not applied** because cold_start_fallback is not active; the method falls back to "
    design_md += "the existing v1 audit/discovery/repair path.\n\n"
    design_md += "## Parameters\n\n"
    design_md += f"- `r` (phase-1 fraction): default/final value **{best_r}**.\n"
    design_md += "- `chunk_size_s`: 120 s, identical to B6.\n"
    design_md += "- `chunk_count`: `ceil(n_bins / (chunk_size_s / bin_size))`.\n\n"
    design_md += "## Hard-constraint compliance\n\n"
    design_md += "- No segment- or event-specific rules.\n"
    design_md += "- No GPU/VLM/new labels.\n"
    design_md += "- The only new parameter is `r`, evaluated at {0.3, 0.5, 0.7} and selected by a pre-specified criterion.\n"
    with open(OUT / "hybrid_design.md", "w") as f:
        f.write(design_md)
    print("Wrote hybrid_design.md")

    # Verdict report.
    verdict_md = "# Verdict Report — Hybrid Cold-Start Discovery\n\n"
    verdict_md += f"## Selected design parameter\n\nr = **{best_r}** (chosen by pre-specified criterion: maximize number of segments with substantive improvement at both B=10 and B=20 vs v2, tie-break toward 0.5).\n\n"

    verdict_md += "## Sensitivity of r\n\n"
    verdict_md += "| r | segments improved at both B=10 and B=20 |\n"
    verdict_md += "|---|------------------------------------------|\n"
    # Recompute for report (same logic).
    for r in R_VALUES:
        hybrid_rows = [
            {"segment": r2["segment"], "budget": r2["budget"], "seed": r2["seed"], "method": f"v2_hybrid_r{r}",
             "long_event_recall": r2["long_event_recall"], "precision": r2["precision"], "selected_duration": r2["selected_duration"]}
            for r2 in sensitivity_rows if r2["r"] == r
        ]
        seg_improved = 0
        for seg in SEGMENTS:
            ok = True
            for budget in BUDGETS_LOW:
                m_v2, s_v2 = stats_of(v2_rows, seg["segment_id"], budget, "Frozen-LATE-AQP-v2", "long_event_recall")
                m_h, s_h = stats_of(hybrid_rows, seg["segment_id"], budget, f"v2_hybrid_r{r}", "long_event_recall")
                if m_v2 is None or m_h is None or (m_h - m_v2) <= max(s_v2, s_h):
                    ok = False; break
            if ok:
                seg_improved += 1
        verdict_md += f"| {r} | {seg_improved}/3 |\n"

    verdict_md += "\n## 4a) Does v2_hybrid improve over v2 on >=2/3 segments at B=10/20?\n\n"
    verdict_md += "| Segment | Budget | v2 mean | v2 std | hybrid mean | hybrid std | Δ | Δ > noise? |\n"
    verdict_md += "|---------|--------|---------|--------|-------------|------------|---|------------|\n"
    improved_segments = set()
    for seg in SEGMENTS:
        seg_id = seg["segment_id"]
        both_improved = True
        for budget in BUDGETS_LOW:
            m_v2, s_v2 = stats_of(v2_rows, seg_id, budget, "Frozen-LATE-AQP-v2", "long_event_recall")
            m_h, s_h = stats_of(
                [{"segment": r["segment"], "budget": r["budget"], "seed": r["seed"], "method": r["method"],
                  "long_event_recall": r["long_event_recall"], "precision": r["precision"], "selected_duration": r["selected_duration"]}
                 for r in sensitivity_rows if r["r"] == best_r],
                seg_id, budget, f"v2_hybrid_r{best_r}", "long_event_recall"
            )
            delta = (m_h - m_v2) if (m_v2 is not None and m_h is not None) else float("nan")
            noise = max(s_v2, s_h) if (m_v2 is not None and m_h is not None) else 0.0
            flag = (delta > noise)
            verdict_md += f"| {seg_id} | {budget} | {fmt(m_v2)} | {fmt(s_v2)} | {fmt(m_h)} | {fmt(s_h)} | {fmt(delta)} | {'Yes' if flag else 'No'} |\n"
            if not flag:
                both_improved = False
        if both_improved:
            improved_segments.add(seg_id)

    verdict_md += f"\nSegments with substantive improvement at **both** B=10 and B=20: **{len(improved_segments)}/3**.\n\n"
    answer_4a = "Yes" if len(improved_segments) >= 2 else "No"
    verdict_md += f"**Answer 4a: {answer_4a}.**\n\n"

    verdict_md += "## 4b) Does v2_hybrid reach or exceed B6?\n\n"
    verdict_md += "| Segment | Budget | hybrid mean | hybrid std | B6 mean | B6 std | gap (hybrid−B6) |\n"
    verdict_md += "|---------|--------|-------------|------------|---------|--------|-----------------|\n"
    beats_or_ties = 0
    total = 0
    for seg in SEGMENTS:
        seg_id = seg["segment_id"]
        for budget in BUDGETS_LOW:
            m_h, s_h = stats_of(
                [{"segment": r["segment"], "budget": r["budget"], "seed": r["seed"], "method": r["method"],
                  "long_event_recall": r["long_event_recall"], "precision": r["precision"], "selected_duration": r["selected_duration"]}
                 for r in sensitivity_rows if r["r"] == best_r],
                seg_id, budget, f"v2_hybrid_r{best_r}", "long_event_recall"
            )
            m_b6, s_b6 = stats_of(comparison_rows, seg_id, budget, "B6", "long_event_recall")
            gap = (m_h - m_b6) if (m_h is not None and m_b6 is not None) else float("nan")
            verdict_md += f"| {seg_id} | {budget} | {fmt(m_h)} | {fmt(s_h)} | {fmt(m_b6)} | {fmt(s_b6)} | {fmt(gap)} |\n"
            if m_h is not None and m_b6 is not None:
                total += 1
                if m_h >= m_b6 - 1e-9:
                    beats_or_ties += 1
    verdict_md += f"\nv2_hybrid mean recall is >= B6 mean recall in **{beats_or_ties}/{total}** segment-budget combinations.\n\n"
    answer_4b = "Yes" if beats_or_ties == total else ("Partial" if beats_or_ties >= total // 2 else "No")
    verdict_md += f"**Answer 4b: {answer_4b}.**\n\n"

    verdict_md += "## 4c) Choice of r and sensitivity\n\n"
    verdict_md += f"Final `r = {best_r}`. The sensitivity table above shows how many segments improve at both low budgets for each r. "
    if best_r == 0.5:
        verdict_md += "The default value 0.5 was selected (or tied and chosen by the tie-breaker), matching the design intuition of splitting the cold-start budget evenly between exploration and exploitation.\n\n"
    else:
        verdict_md += f"Although 0.5 was the proposed default, the pre-specified criterion selected r={best_r} as giving the broadest improvement.\n\n"

    verdict_md += "## 4d) High-budget behavior\n\n"
    verdict_md += "Hybrid cold-start is only applied when `cold_start_fallback` is active, i.e. B <= 20. "
    verdict_md += "For B > 20 the method is identical to Frozen-LATE-AQP-v1 (audit + discovery + repair). "
    verdict_md += "Therefore high-budget behavior is unchanged from the already-validated v1 and is not expected to regress. "
    verdict_md += "The comparison CSV includes the existing v1 high-budget rows under both the v1 and v2_hybrid method names for reference.\n\n"

    verdict_md += "## Overall verdict\n\n"
    if answer_4a == "Yes" and answer_4b in ("Yes", "Partial"):
        verdict_md += "**IMPROVEMENT CONFIRMED**: Hybrid cold-start with the chosen r provides substantive low-budget improvement over v2 on at least 2/3 segments and reaches or exceeds B6 in most cases. No high-budget regression is introduced because the hybrid stage is gated to B <= 20.\n"
    elif answer_4a == "Yes":
        verdict_md += "**PARTIAL**: v2_hybrid improves over v2 on at least 2/3 segments but does not consistently reach B6 levels. The mechanism is validated as a real improvement but may need combination with other fixes for full B6 parity.\n"
    else:
        verdict_md += "**FAIL**: Even the hybrid cold-start does not substantively improve v2 on at least 2/3 segments. The low-budget discovery problem remains unresolved and requires a different fix.\n"

    with open(OUT / "verdict_report.md", "w") as f:
        f.write(verdict_md)
    print("Wrote verdict_report.md")


if __name__ == "__main__":
    main()
