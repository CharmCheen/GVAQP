#!/usr/bin/env python3
"""HTS-AQP Phase 0 — Offline Coarse-to-Fine Feasibility Diagnostic (rewrite).

Per task spec §2 (Context Assembly),
§3 (Deterministic simulation, b ∈ {2, 4}),
§4 (Baseline comparison with explicit alignment notes),
§5 (CSV schema exactly as specified),
§6 (report answering all 5 questions with quantified ratio threshold),
§7 (both b regimes reported; no adverse segment hidden).

Hard constraints honored:
  - No Beta posterior / UCB / frontier management (this is a deterministic
    God's-eye simulation, not a real algorithm).
  - No oracle / VLM / GPU / new labels.
  - No modification of existing code / benchmark output.
  - No large artifacts (output < 100 KB total).
  - All event-level numbers are VLM-oracle-relative.
  - No safe-stopping / formal-guarantee / statistical-bound claim.
  - Coverage convention explicitly flagged (`any-overlap` for HTS Phase 0
    discovery bins vs. `IoU >= 0.3` for baseline returned-intervals).
"""
import sys, math, os, json
from pathlib import Path
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

# Reuse the canonical grid loader used by the EventLift full benchmark
from eventlift_stage2_multiseg_smoke import load_segment_data, SEGMENTS

OUT = REPO / "outputs" / "hts_aqp_phase0_feasibility"
OUT.mkdir(parents=True, exist_ok=True)

BRANCHING_FACTORS = [2, 4]
IOU_THRESHOLD = 0.3  # used only for baseline coverage, per run_eventlift_full_benchmark_v1.py:38

# Ratio threshold for "A — strong feasibility" per task spec §6 Q5
RATIO_STRONG_FEASIBILITY = 0.5   # HTS uses <= 50% of best baseline calls
RATIO_FEASIBILITY_NEUTRAL = 1.0  # > 1.0 means HTS uses more calls than the comparator

# ============================================================
# Tree
# ============================================================

class TreeNode:
    __slots__ = ("start", "end", "children", "is_leaf", "label")
    def __init__(self, start, end):
        self.start = start    # bin index (inclusive)
        self.end   = end      # bin index (exclusive)
        self.children = []
        self.is_leaf = (end - start) <= 1
        self.label = None


def build_tree(start, end, b):
    """Recursively build a b-ary tree over [start, end)."""
    node = TreeNode(start, end)
    width = end - start
    if width <= 1:
        node.is_leaf = True
        return node
    sub_width = width / b
    for i in range(b):
        cs = start + int(round(i * sub_width))
        ce = start + int(round((i + 1) * sub_width))
        cs = max(start, min(end, cs))
        ce = max(cs, min(end, ce))
        if ce > cs:
            node.children.append(build_tree(cs, ce, b))
    return node


def label_tree(node, labels):
    """Assign OR-coarse label to every node."""
    node.label = bool(labels[node.start:node.end].any())
    for c in node.children:
        label_tree(c, labels)


def simulate(node, counter):
    """God's-eye deterministic coarse-to-fine descent.

    Visit cost: 1 oracle call per node visited, REGARDLESS of interval size
    (per task spec §3: count aligned to existing baseline budget convention
    where 1 query = 1 call).

    Negative node  -> prune (no descendant calls).
    Positive leaf  -> discovered positive leaf.
    Positive non-leaf -> drill into all b children.
    """
    counter["calls"] += 1
    if not node.label:
        return  # prune
    if node.is_leaf:
        counter["positive_leaves"] += 1
        return
    for c in node.children:
        simulate(c, counter)


def tree_depth(node):
    if node.is_leaf:
        return 0
    return 1 + max(tree_depth(c) for c in node.children) if node.children else 0


def tree_size(node):
    return 1 + sum(tree_size(c) for c in node.children)


# ============================================================
# Coverage computation for any-overlap convention
# ============================================================

def events_touched_by_positive_bins(grid, ref_seg):
    """HTS Phase 0 coverage: any-overlap between a discovered positive bin
    and a reference event counts as that event being discovered.
    (Distinct from IoU>=0.3 used by baseline returned-intervals; see §2.4
    of context_manifest.md.)
    Returns (n_events_touchable_total, n_events_actually_touched).
    """
    if len(ref_seg) == 0:
        return 0, 0
    bs = grid["local_t_start"].to_numpy()
    be = grid["local_t_end"].to_numpy()
    y = grid["is_positive"].to_numpy()
    pos_idx = np.where(y)[0]
    pos_bins = pos_idx
    touched = set()
    es = ref_seg["t_start"].to_numpy()
    ee = ref_seg["t_end"].to_numpy()
    eids = list(ref_seg["event_id"])
    for b in pos_bins:
        for k in range(len(ref_seg)):
            if be[b] > es[k] and bs[b] < ee[k]:
                touched.add(eids[k])
    return len(ref_seg), len(touched)


# ============================================================
# Baseline comparison
# ============================================================

def baseline_seed_mean_frontier(full_df, segment_id, method_id):
    """Per-segment per-method: average oracle_calls and unique_event_coverage
    over the 3 seeds at each budget. Returns a sorted list of (calls, cov)."""
    sub = full_df[(full_df.segment_id == segment_id) &
                  (full_df.method_id == method_id)].copy()
    sub["calls"] = pd.to_numeric(sub["oracle_calls_total"], errors="coerce")
    sub["cov"]   = pd.to_numeric(sub["unique_event_coverage"], errors="coerce")
    df = sub.dropna(subset=["calls", "cov"]).groupby("budget_ratio", as_index=False)[["calls", "cov"]].mean()
    df = df.sort_values("calls").reset_index(drop=True)
    return df


def baseline_best_seed_frontier(full_df, segment_id, method_id):
    """Per-segment per-method: take the BEST seed per budget (i.e., the
    seed that achieved the highest coverage at that budget). Reported as
    an upper envelope (matches posthoc best-of-N convention used in
    b90_90_comparison.csv)."""
    sub = full_df[(full_df.segment_id == segment_id) &
                  (full_df.method_id == method_id)].copy()
    sub["calls"] = pd.to_numeric(sub["oracle_calls_total"], errors="coerce")
    sub["cov"]   = pd.to_numeric(sub["unique_event_coverage"], errors="coerce")
    df = sub.dropna(subset=["calls", "cov"])
    if len(df) == 0:
        return None
    df = df.sort_values(["budget_ratio", "cov"], ascending=[True, False])
    # take the seed with highest coverage per budget
    df = df.groupby("budget_ratio", as_index=False).first()[["budget_ratio", "calls", "cov"]]
    df = df.sort_values("calls").reset_index(drop=True)
    return df


def find_calls_for_coverage(frontier_df, target_cov):
    """Linear interpolation of seed-mean frontier to find the minimum call
    count at which coverage first reaches target_cov. Returns (calls,
    note). If max coverage < target_cov, returns (max_calls,
    'existing_method_never_reaches_target_coverage')."""
    if frontier_df is None or len(frontier_df) == 0:
        return -1, "no_baseline_data_available"
    # Find first budget at which cov >= target_cov (mean across seeds)
    reached = frontier_df[frontier_df["cov"] >= target_cov]
    if len(reached) > 0:
        # linear interpolation between the first reached budget and the
        # previous budget
        idx = reached.index[0]
        if idx == 0 or frontier_df.iloc[idx - 1]["cov"] >= target_cov:
            # even the smallest budget reaches coverage
            return float(frontier_df.iloc[idx]["calls"]), \
                "directly_reached_at_smallest_available_budget"
        prev = frontier_df.iloc[idx - 1]
        cur  = frontier_df.iloc[idx]
        slope_cov = (cur["cov"] - prev["cov"])
        slope_calls = (cur["calls"] - prev["calls"])
        if slope_cov == 0:
            return float(cur["calls"]), "directly_reached_at_budget"
        # interpolate calls
        # cov_prev + slope_cov * x = target_cov
        x = (target_cov - prev["cov"]) / slope_cov
        calls_interp = prev["calls"] + x * slope_calls
        return float(calls_interp), "linear_interpolated_frontier"
    # Coverage never reached
    max_row = frontier_df.iloc[-1]
    return float(max_row["calls"]), "existing_method_never_reaches_target_coverage"


def load_b90_90():
    """Posthoc_eval B_90/90 frontier; context-only per CLAIMS_LEDGER.md."""
    p = REPO / "outputs/late_aqp_event_diverse_discovery_v1/b90_90_comparison.csv"
    if not p.exists():
        return None
    return pd.read_csv(p)


# Comparison rows produced *per method* (not just per best method).
def baseline_coverage_at_calls(frontier_df, target_calls):
    """For "edge-of-frontier" reporting: report the maximum coverage achieved
    by the method at the LARGEST available call count <= target_calls."""
    if frontier_df is None or len(frontier_df) == 0:
        return -1, -1
    below = frontier_df[frontier_df["calls"] <= target_calls]
    if len(below) == 0:
        return float(frontier_df.iloc[0]["calls"]), float(frontier_df.iloc[0]["cov"])
    best = below.loc[below["cov"].idxmax()]
    return float(best["calls"]), float(best["cov"])


def build_comparison_row(seg_id, branching_factor, hts_calls, hts_full_coverage,
                         hts_full_coverage_any_overlap,
                         full_df, b90_df):
    rows = []

    # --- strict_replay track: per-method best-of-seeds ---
    strict_methods = [
        "B7-strict-replay", "D3-norepair-core-strict",
        "SUPG-event-rt-strict",
        "EventLift-discover-only", "EventLift-discover-audit",
        "EventLift-discover-certify", "EventLift-discover-audit-certify",
        "EventLift-full-stage2",
    ]

    per_method_rows = []
    for mid in strict_methods:
        f = baseline_best_seed_frontier(full_df, seg_id, mid)
        if f is None or len(f) == 0:
            continue
        calls_reach, note = find_calls_for_coverage(f, hts_full_coverage_any_overlap)
        # boundary coverage (coverage this method achieved with calls <= hts_calls)
        calls_at_or_below, cov_at_or_below = baseline_coverage_at_calls(f, hts_calls)
        # ratio: HTS calls / (existing method's calls for its best-at-or-below-budget coverage)
        if calls_at_or_below > 0:
            ratio = hts_calls / calls_at_or_below
        else:
            ratio = float("nan")
        row = {
            "segment_id": seg_id,
            "branching_factor": branching_factor,
            "hts_calls_to_full_coverage": hts_calls,
            "hts_full_coverage_event_count": hts_full_coverage_any_overlap,
            "best_existing_baseline_calls_to_same_coverage": calls_reach,
            "existing_best_seed_coverage_at_or_below_hts_calls": int(cov_at_or_below),
            "existing_calls_at_which_above_coverage_reached": int(calls_at_or_below),
            "existing_baseline_name": mid,
            "ratio": round(float(ratio), 4),
            "track": "strict_replay",
            "comparison_alignment_note": note,
            "coverage_convention_mismatch": (
                "HTS_phase0_any_overlap_discovery vs "
                "baseline_IoU>=0.3_returned_intervals"
            ),
        }
        rows.append(row)
        per_method_rows.append(row)

    # --- "best existing baseline" summary row ---
    # When NO strict-replay baseline reaches target coverage (common case
    # here at budgets {0.1, 0.2, 0.3}), pick the method / configuration with
    # the HIGHEST coverage at-or-below the HTS call count — that's the
    # closest comparator and gives an honest "what coverage could we get with
    # X calls" answer.
    if per_method_rows:
        best_at_budget = max(
            per_method_rows,
            key=lambda r: (r["existing_best_seed_coverage_at_or_below_hts_calls"],
                          -r["existing_calls_at_which_above_coverage_reached"]))
        best_summary_row = {
            "segment_id": seg_id,
            "branching_factor": branching_factor,
            "hts_calls_to_full_coverage": hts_calls,
            "hts_full_coverage_event_count": hts_full_coverage_any_overlap,
            "best_existing_baseline_calls_to_same_coverage":
                best_at_budget["best_existing_baseline_calls_to_same_coverage"],
            "existing_best_seed_coverage_at_or_below_hts_calls":
                best_at_budget["existing_best_seed_coverage_at_or_below_hts_calls"],
            "existing_calls_at_which_above_coverage_reached":
                best_at_budget["existing_calls_at_which_above_coverage_reached"],
            "existing_baseline_name":
                best_at_budget["existing_baseline_name"],
            "ratio": best_at_budget["ratio"],
            "track": "strict_replay_only_comparison_row_per_method_best",
            "comparison_alignment_note":
                f"no_strict_replay_baseline_reaches_target_coverage({hts_full_coverage_any_overlap}_events)_at_"
                f"any_available_budget_in_full_frontier_raw.csv; "
                f"row_reports_{best_at_budget['existing_baseline_name']}'s_"
                f"best_seed_coverage_(={best_at_budget['existing_best_seed_coverage_at_or_below_hts_calls']}_"
                f"events)_obtained_at_or_below_hts_call_count_(<= {hts_calls}_calls); "
                f"baseline_actual_calls_for_that_coverage="
                f"{best_at_budget['existing_calls_at_which_above_coverage_reached']}; "
                f"ratio_is_hts_calls_to_full_coverage_over_baseline_calls_to_reach_"
                f"its_own_best_coverage_at_or_below_that_call_count.",
            "coverage_convention_mismatch":
                "HTS_phase0_any_overlap_discovery vs "
                "baseline_IoU>=0.3_returned_intervals",
        }
        rows.insert(0, best_summary_row)
    else:
        summary_row = {
            "segment_id": seg_id,
            "branching_factor": branching_factor,
            "hts_calls_to_full_coverage": hts_calls,
            "hts_full_coverage_event_count": hts_full_coverage_any_overlap,
            "best_existing_baseline_calls_to_same_coverage": -1,
            "existing_best_seed_coverage_at_or_below_hts_calls": -1,
            "existing_calls_at_which_above_coverage_reached": -1,
            "existing_baseline_name": "NONE",
            "ratio": "",
            "track": "strict_replay_only_comparison_row_per_method_best",
            "comparison_alignment_note": "no_strict_replay_data_available",
            "coverage_convention_mismatch": "n/a",
        }
        rows.insert(0, summary_row)
    return rows


# ============================================================
# Main
# ============================================================

def main():
    full_df = pd.read_csv(
        REPO / "outputs/eventlift_full_benchmark_v1/full_frontier_raw.csv")
    b90_df = load_b90_90()

    call_rows = []
    comparison_rows = []

    for seg in SEGMENTS:
        seg_id = seg["segment_id"]
        grid, ref_seg, err = load_segment_data(seg)
        if grid is None or err:
            print(f"  SKIP {seg_id}: {err}")
            continue

        labels = grid["is_positive"].astype(int).to_numpy()
        n_bins = len(labels)
        n_pos_bins = int(labels.sum())
        ref_total, ref_touched = events_touched_by_positive_bins(grid, ref_seg)

        print(f"\n=== {seg_id} === bins={n_bins} pos_bins={n_pos_bins} "
              f"ref_events={ref_total} ref_events_touchable_by_pos_bins={ref_touched}")

        for b in BRANCHING_FACTORS:
            root = build_tree(0, n_bins, b)
            label_tree(root, labels)
            depth = tree_depth(root)
            total_nodes = tree_size(root)
            counter = {"calls": 0, "positive_leaves": 0}
            simulate(root, counter)
            calls = counter["calls"]
            pos_leaves = counter["positive_leaves"]
            saved = n_bins - calls
            saved_pct = 100.0 * saved / max(1, n_bins)

            print(f"  b={b}: depth={depth} total_nodes={total_nodes} "
                  f"hts_calls={calls} pos_leaves={pos_leaves}/{n_pos_bins} "
                  f"saved_vs_flat={saved} ({saved_pct:.1f}%)")

            call_rows.append({
                "segment_id": seg_id,
                "branching_factor": b,
                "total_oracle_calls_used": calls,
                "total_positive_leaves_found": pos_leaves,
                "total_atomic_bins_in_segment": n_bins,
                "calls_saved_vs_exhaustive_leaf_scan": saved,
                "calls_saved_pct": round(saved_pct, 2),
                "num_positive_bins": n_pos_bins,
                "positive_density": round(n_pos_bins / n_bins, 4),
                "tree_depth": depth,
                "total_tree_nodes": total_nodes,
                "ref_events_total": ref_total,
                "ref_events_touchable_by_pos_bins": ref_touched,
                "coverage_convention": "any-overlap_positive_bin vs ref_event",
                "offline_only_event_mapping": True,
            })

            rows = build_comparison_row(
                seg_id, b, calls, ref_touched, ref_touched,
                full_df, b90_df)
            comparison_rows.extend(rows)

    call_df = pd.DataFrame(call_rows)
    comp_df = pd.DataFrame(comparison_rows)

    call_df.to_csv(OUT / "coarse_to_fine_call_count_by_segment.csv", index=False)
    comp_df.to_csv(OUT / "comparison_vs_existing_baselines.csv", index=False)

    print(f"\nWrote {len(call_df)} call-count rows, {len(comp_df)} comparison rows.")
    print((OUT / "coarse_to_fine_call_count_by_segment.csv").as_posix())
    print((OUT / "comparison_vs_existing_baselines.csv").as_posix())


if __name__ == "__main__":
    main()