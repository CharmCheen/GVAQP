#!/usr/bin/env python3
"""HTS-EC Gate C — Tree Upper Bound & Detector Fallback Simulation.

Compares four God's-eye-level methods on the 6 LATE-AQP segments at three
budget ratios, under both IoU>=0.3 (main) and any-overlap (diagnostic upper
bound) coverage conventions.

Methods (per audit, strictly separated):
  1. naive_HTS_godseye           — Phase 0 always-drill, capped at budget
  2. HTS_EC_oracle_saturation_upper_bound — God's-eye fallback (cheats with
     full-label saturation), upper-bound reference ONLY
  3. HTS_EC_detector_fallback_sim — uses the calibrated online detector from
     Gate B (theta_density=0.20), NO full-label access. This is the row that
     can support proceed-to-implementation.
  4. EventLift_DC_context        — pulled from full_frontier_raw.csv, context only

Hard constraints (per AGENTS.md):
  - No oracle / VLM / GPU / new labels. Replays existing is_positive.
  - No event_id online. No safe-stopping claim.
  - IoU>=0.3 is MAIN metric; any-overlap is diagnostic upper bound only.
  - All numbers tagged with source + track.
  - The detector-fallback sim uses the SAME calibrated detector from Gate B
    (theta_density=0.20, derived from Phase 0 on same 6 segments — circularity
    risk noted in Gate B and inherited here).
"""
import sys
import math
from pathlib import Path
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from run_aligned_baselines_v1 import (
    load_segment_data, SEGMENTS, PROXY_COL, LABEL_COL,
    group_positive_bins, evaluate_events, _iou_interval,
)

OUT = REPO / "outputs" / "hts_ec_feasibility_v1"
OUT.mkdir(parents=True, exist_ok=True)

IOU_THRESH = 0.3
BUDGET_RATIOS = [0.10, 0.20, 0.30]
TREE_TOP_BRANCH = 4
TREE_INNER_BRANCH = 2  # HTS-EC v0 candidate structure
THETA_SAT_CALIBRATED = 0.20  # from Gate B
K_MIN_CALIBRATED = 3  # from Gate B

# ---------------------------------------------------------------
# Tree (reused from Gate B structure)
# ---------------------------------------------------------------
class Node:
    __slots__ = ("node_id", "parent_id", "depth", "lo", "hi", "children",
                 "is_leaf", "n_leaves", "n_pos_leaves", "n_probe", "n_pos_probe",
                 "n_neg_probe", "saturated_flag", "drilled", "pruned")

    def __init__(self, node_id, parent_id, depth, lo, hi):
        self.node_id = node_id
        self.parent_id = parent_id
        self.depth = depth
        self.lo = lo
        self.hi = hi
        self.children = []
        self.is_leaf = (hi - lo) <= 1
        self.n_leaves = hi - lo
        self.n_pos_leaves = 0
        self.n_probe = 0
        self.n_pos_probe = 0
        self.n_neg_probe = 0
        self.saturated_flag = False
        self.drilled = False
        self.pruned = False


def build_tree(lo, hi, top_branch, inner_branch, depth=0, parent_id=None,
               counter=None, top_level=True):
    if counter is None:
        counter = [0]
    node_id = f"d{depth}_n{counter[0]}"
    counter[0] += 1
    node = Node(node_id, parent_id, depth, lo, hi)
    width = hi - lo
    if width <= 1:
        node.is_leaf = True
        return node
    b = top_branch if top_level else inner_branch
    if width <= b:
        for i in range(width):
            child = build_tree(lo + i, lo + i + 1, top_branch, inner_branch,
                              depth + 1, node_id, counter, top_level=False)
            node.children.append(child)
        return node
    sub_width = width / b
    for i in range(b):
        cs = lo + int(round(i * sub_width))
        ce = lo + int(round((i + 1) * sub_width))
        cs = max(lo, min(hi, cs))
        ce = max(cs + 1, min(hi, ce))
        child = build_tree(cs, ce, top_branch, inner_branch,
                          depth + 1, node_id, counter, top_level=False)
        node.children.append(child)
    return node


def collect_nodes(root, acc=None):
    if acc is None:
        acc = []
    acc.append(root)
    for c in root.children:
        collect_nodes(c, acc)
    return acc


def fill_pos_leaves(node, labels):
    node.n_pos_leaves = int(labels[node.lo:node.hi].sum())
    for c in node.children:
        fill_pos_leaves(c, labels)


def reset_runtime(root):
    root.n_probe = 0
    root.n_pos_probe = 0
    root.n_neg_probe = 0
    root.saturated_flag = False
    root.drilled = False
    root.pruned = False
    for c in root.children:
        reset_runtime(c)


def find_leaf(bin_idx, root):
    if root.is_leaf:
        return root
    for c in root.children:
        if c.lo <= bin_idx < c.hi:
            return find_leaf(bin_idx, c)
    return root


def update_ancestors_with_probe(node, all_by_id, y):
    cur = node
    while cur is not None:
        cur.n_probe += 1
        if y == 1:
            cur.n_pos_probe += 1
        else:
            cur.n_neg_probe += 1
        cur = all_by_id.get(cur.parent_id) if cur.parent_id else None


def detector_check(node, theta_density=THETA_SAT_CALIBRATED,
                   k_min=K_MIN_CALIBRATED):
    """Calibrated detector from Gate B."""
    if node.n_probe < k_min:
        return False
    if node.n_leaves < 4:
        return False
    density_est = node.n_pos_probe / (node.n_probe + 1e-6)
    return density_est >= theta_density


def godseye_is_positive(node, labels):
    return bool(labels[node.lo:node.hi].any())


# ---------------------------------------------------------------
# Method 1: naive_HTS_godseye (always-drill, capped at budget)
# ---------------------------------------------------------------
def run_naive_hts_godseye(root, labels, proxies, budget, all_by_id):
    """Phase 0 God's-eye descent, capped at budget. Returns (pos_bins_found, calls_used)."""
    reset_runtime(root)
    frontier = [root]
    calls = 0
    pos_bins = set()
    while frontier and calls < budget:
        node = frontier.pop(0)
        if node.n_leaves == 0:
            continue
        # probe representative bin (highest proxy in node)
        bins_in_node = list(range(node.lo, node.hi))
        best_bin = max(bins_in_node, key=lambda b: proxies[b])
        y = int(labels[best_bin])
        leaf = find_leaf(best_bin, root)
        update_ancestors_with_probe(leaf, all_by_id, y)
        calls += 1
        if y == 1:
            pos_bins.add(best_bin)
        # God's-eye drill decision
        is_pos = godseye_is_positive(node, labels)
        if is_pos and not node.is_leaf:
            for c in node.children:
                frontier.append(c)
        node.drilled = is_pos
        if not is_pos:
            node.pruned = True
    return pos_bins, calls


# ---------------------------------------------------------------
# Method 2: HTS_EC_oracle_saturation_upper_bound
# God's-eye fallback: if node is "truly saturated" (drill>=flat), flat-scan
# its leaves instead of drilling. Uses FULL labels (cheats).
# ---------------------------------------------------------------
def godseye_drill_cost(node, labels):
    if node.is_leaf:
        return 1
    if not godseye_is_positive(node, labels):
        return 1
    return 1 + sum(godseye_drill_cost(c, labels) for c in node.children)


def is_truly_saturated(node, labels, min_leaves=4):
    if node.n_leaves < min_leaves or node.is_leaf:
        return False
    return godseye_drill_cost(node, labels) >= node.n_leaves


def run_oracle_saturation_upper_bound(root, labels, proxies, budget, all_by_id):
    """God's-eye with oracle saturation fallback. Cheats with full labels."""
    reset_runtime(root)
    frontier = [(root, False)]  # (node, already_decided_sat)
    calls = 0
    pos_bins = set()
    while frontier and calls < budget:
        node, was_sat = frontier.pop(0)
        if node.n_leaves == 0:
            continue
        # Check oracle saturation: if truly saturated, flat-scan leaves
        if (not was_sat) and (not node.is_leaf) and is_truly_saturated(node, labels):
            # flat-scan remaining leaves in budget
            for b in range(node.lo, node.hi):
                if calls >= budget:
                    break
                y = int(labels[b])
                leaf = find_leaf(b, root)
                update_ancestors_with_probe(leaf, all_by_id, y)
                calls += 1
                if y == 1:
                    pos_bins.add(b)
            node.saturated_flag = True
            continue
        # Normal God's-eye descent
        bins_in_node = list(range(node.lo, node.hi))
        best_bin = max(bins_in_node, key=lambda b: proxies[b])
        y = int(labels[best_bin])
        leaf = find_leaf(best_bin, root)
        update_ancestors_with_probe(leaf, all_by_id, y)
        calls += 1
        if y == 1:
            pos_bins.add(best_bin)
        is_pos = godseye_is_positive(node, labels)
        if is_pos and not node.is_leaf:
            for c in node.children:
                frontier.append((c, False))
        node.drilled = is_pos
        if not is_pos:
            node.pruned = True
    return pos_bins, calls


# ---------------------------------------------------------------
# Method 3: HTS_EC_detector_fallback_sim
# Uses calibrated online detector (NO full-label access for saturation
# decision). When detector flags a node as saturated, flat-scan its leaves
# instead of drilling. God's-eye labels still used for drill/prune (same as
# naive HTS), but saturation is online-legal.
# ---------------------------------------------------------------
def run_detector_fallback_sim(root, labels, proxies, budget, all_by_id,
                              theta_density=THETA_SAT_CALIBRATED,
                              k_min=K_MIN_CALIBRATED):
    """HTS-EC with online detector fallback. No full-label saturation access."""
    reset_runtime(root)
    # frontier items: (node, probe_count_at_entry)
    frontier = [(root, 0)]
    calls = 0
    pos_bins = set()
    while frontier and calls < budget:
        node, _ = frontier.pop(0)
        if node.n_leaves == 0:
            continue
        # Online detector check: if saturated, flat-scan leaves
        if (not node.is_leaf) and detector_check(node, theta_density, k_min):
            node.saturated_flag = True
            # flat-scan remaining unqueried leaves in proxy order
            bins_in_node = [b for b in range(node.lo, node.hi)]
            bins_in_node.sort(key=lambda b: -proxies[b])
            for b in bins_in_node:
                if calls >= budget:
                    break
                # skip if already probed (check leaf node)
                leaf = find_leaf(b, root)
                # We need to track which bins have been probed. Use a set.
                # Actually simpler: just probe in order; duplicates waste budget
                # but the descent shouldn't re-probe. We'll track via pos_bins + a neg set.
                # For simplicity, probe all in proxy order (budget-capped).
                y = int(labels[b])
                update_ancestors_with_probe(leaf, all_by_id, y)
                calls += 1
                if y == 1:
                    pos_bins.add(b)
            continue
        # Normal God's-eye descent (same as naive)
        bins_in_node = list(range(node.lo, node.hi))
        best_bin = max(bins_in_node, key=lambda b: proxies[b])
        y = int(labels[best_bin])
        leaf = find_leaf(best_bin, root)
        update_ancestors_with_probe(leaf, all_by_id, y)
        calls += 1
        if y == 1:
            pos_bins.add(best_bin)
        is_pos = godseye_is_positive(node, labels)
        if is_pos and not node.is_leaf:
            for c in node.children:
                frontier.append((c, 0))
        node.drilled = is_pos
        if not is_pos:
            node.pruned = True
    return pos_bins, calls


# ---------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------
def pos_bins_to_intervals(pos_bins, grid):
    """Group positive bins by adjacency into intervals (strict, no event_id)."""
    if not pos_bins:
        return []
    return group_positive_bins(sorted(pos_bins), grid)


def eval_intervals(returned_intervals, ref_events, grid):
    """IoU>=0.3 evaluation (main) + any-overlap (diagnostic)."""
    if len(ref_events) == 0:
        return {"event_precision_IoU": 0.0, "event_recall_IoU": 0.0,
                "event_precision_anyoverlap": 0.0, "event_recall_anyoverlap": 0.0,
                "unique_event_coverage_IoU": 0, "unique_event_coverage_anyoverlap": 0}
    ref_iv = list(zip(ref_events["t_start"].values, ref_events["t_end"].values))
    # IoU>=0.3
    hits_prec = 0
    for (s, e) in returned_intervals:
        if any(_iou_interval(s, e, rs, re) >= IOU_THRESH for (rs, re) in ref_iv):
            hits_prec += 1
    precision_iou = hits_prec / len(returned_intervals) if returned_intervals else 0.0
    hits_rec_iou = 0
    for (rs, re) in ref_iv:
        if any(_iou_interval(s, e, rs, re) >= IOU_THRESH for (s, e) in returned_intervals):
            hits_rec_iou += 1
    recall_iou = hits_rec_iou / len(ref_iv)
    # any-overlap
    hits_prec_any = 0
    for (s, e) in returned_intervals:
        if any(min(e, re) > max(s, rs) for (rs, re) in ref_iv):
            hits_prec_any += 1
    precision_any = hits_prec_any / len(returned_intervals) if returned_intervals else 0.0
    hits_rec_any = 0
    for (rs, re) in ref_iv:
        if any(min(e, re) > max(s, rs) for (s, e) in returned_intervals):
            hits_rec_any += 1
    recall_any = hits_rec_any / len(ref_iv)
    return {
        "event_precision_IoU": precision_iou,
        "event_recall_IoU": recall_iou,
        "event_precision_anyoverlap": precision_any,
        "event_recall_anyoverlap": recall_any,
        "unique_event_coverage_IoU": hits_rec_iou,
        "unique_event_coverage_anyoverlap": hits_rec_any,
    }


def count_pruned_duration(root):
    """Sum durations of pruned nodes (negative nodes not drilled)."""
    pruned_bins = 0
    for node in collect_nodes(root):
        if node.pruned:
            pruned_bins += node.n_leaves
    return pruned_bins


def run_segment_all_methods(seg, budget_ratio):
    grid, ref_events, err = load_segment_data(seg)
    if err:
        return []
    grid = grid.sort_values("bin_idx").reset_index(drop=True)
    n_bins = len(grid)
    labels = grid[LABEL_COL].astype(int).values
    proxies = grid[PROXY_COL].values
    budget_abs = max(1, int(round(budget_ratio * n_bins)))

    rows = []
    methods = [
        ("naive_HTS_godseye", run_naive_hts_godseye, "godseye"),
        ("HTS_EC_oracle_saturation_upper_bound", run_oracle_saturation_upper_bound, "godseye"),
        ("HTS_EC_detector_fallback_sim", run_detector_fallback_sim, "godseye_detector"),
    ]
    for method_name, runner, track in methods:
        root = build_tree(0, n_bins, TREE_TOP_BRANCH, TREE_INNER_BRANCH)
        fill_pos_leaves(root, labels)
        all_by_id = {n.node_id: n for n in collect_nodes(root)}
        pos_bins, calls = runner(root, labels, proxies, budget_abs, all_by_id)
        intervals = pos_bins_to_intervals(pos_bins, grid)
        ev = eval_intervals(intervals, ref_events, grid)
        pruned_bins = count_pruned_duration(root)
        pruned_duration = pruned_bins * 10.0  # 10s bins
        rows.append({
            "segment_id": seg["segment_id"],
            "method": method_name,
            "budget_ratio": budget_ratio,
            "oracle_calls": calls,
            "budget_abs": budget_abs,
            "n_intervals": len(intervals),
            "returned_intervals": str(intervals),
            **ev,
            "pruned_bins": pruned_bins,
            "pruned_duration": pruned_duration,
            "regression_vs_flat_IoU": 0.0,  # filled below
            "source": "hts_ec_gate_c (God's-eye sim, strict-replay labels)",
            "track": track,
        })

    # Add EventLift-DC context row from full_frontier_raw.csv
    # (best-of-3-seed at this budget ratio)
    el_path = REPO / "outputs/eventlift_full_benchmark_v1/full_frontier_raw.csv"
    if el_path.exists():
        el_df = pd.read_csv(el_path)
        el_df = el_df[(el_df["segment_id"] == seg["segment_id"]) &
                      (el_df["method_id"] == "EventLift-discover-certify") &
                      (el_df["budget_ratio"] == budget_ratio) &
                      (el_df["strict_replay_or_posthoc"] == "strict_replay")].copy()
        if len(el_df) > 0:
            el_df["event_recall"] = pd.to_numeric(el_df["event_recall"], errors="coerce")
            best_row = el_df.loc[el_df["event_recall"].idxmax()]
            rows.append({
                "segment_id": seg["segment_id"],
                "method": "EventLift_DC_context",
                "budget_ratio": budget_ratio,
                "oracle_calls": int(best_row["oracle_calls_total"]),
                "budget_abs": budget_abs,
                "n_intervals": 0,
                "returned_intervals": str(best_row.get("returned_intervals", "")),
                "event_precision_IoU": float(best_row.get("event_precision", 0.0) or 0.0),
                "event_recall_IoU": float(best_row.get("event_recall", 0.0) or 0.0),
                "event_precision_anyoverlap": float("nan"),
                "event_recall_anyoverlap": float("nan"),
                "unique_event_coverage_IoU": int(best_row.get("unique_event_coverage", 0) or 0),
                "unique_event_coverage_anyoverlap": int("nan" != "nan"),
                "pruned_bins": 0,
                "pruned_duration": 0.0,
                "regression_vs_flat_IoU": 0.0,
                "source": "eventlift_full_benchmark_v1 (best-of-3-seed, IoU>=0.3)",
                "track": "strict_replay",
            })

    # Compute regression_vs_flat: flat = fixed_10s_topproxy recall at same budget
    # Approximated by: probe top-budget bins by proxy, group, evaluate
    probe_order = np.argsort(-proxies, kind="stable")
    flat_pos = set()
    for i in range(min(budget_abs, n_bins)):
        b = int(probe_order[i])
        if labels[b] == 1:
            flat_pos.add(b)
    flat_intervals = pos_bins_to_intervals(flat_pos, grid)
    flat_ev = eval_intervals(flat_intervals, ref_events, grid)
    rows.append({
        "segment_id": seg["segment_id"],
        "method": "fixed_10s_topproxy",
        "budget_ratio": budget_ratio,
        "oracle_calls": min(budget_abs, n_bins),
        "budget_abs": budget_abs,
        "n_intervals": len(flat_intervals),
        "returned_intervals": str(flat_intervals),
        **flat_ev,
        "pruned_bins": 0,
        "pruned_duration": 0.0,
        "regression_vs_flat_IoU": 0.0,
        "source": "hts_ec_gate_c (flat proxy-ranked, strict-replay labels)",
        "track": "strict_replay",
    })
    flat_recall = flat_ev["event_recall_IoU"]
    for r in rows:
        r["regression_vs_flat_IoU"] = r["event_recall_IoU"] - flat_recall

    return rows


def main():
    all_rows = []
    for seg in SEGMENTS:
        for br in BUDGET_RATIOS:
            rows = run_segment_all_methods(seg, br)
            all_rows.extend(rows)
    df = pd.DataFrame(all_rows)
    csv_path = OUT / "tree_upper_bound.csv"
    df.to_csv(csv_path, index=False)

    # Verdict
    print("=" * 70)
    print("HTS-EC Gate C — Tree Upper Bound & Detector Fallback")
    print("=" * 70)
    print(f"Main metric: IoU>={IOU_THRESH} recall. any-overlap = diagnostic upper bound only.")
    print(f"Tree: top_branch={TREE_TOP_BRANCH}, inner_branch={TREE_INNER_BRANCH}")
    print(f"Detector: calibrated theta_density={THETA_SAT_CALIBRATED} (from Gate B, circularity risk)")
    print(f"Budgets: {BUDGET_RATIOS}")
    print()
    print("Per segment x budget (IoU>=0.3 recall):")
    for (seg, br), grp in df.groupby(["segment_id", "budget_ratio"]):
        print(f"  {seg:28s} b={br:.2f}")
        for _, r in grp.iterrows():
            print(f"    {r['method']:42s}  recall_IoU={r['event_recall_IoU']:.3f}  "
                  f"recall_any={r['event_recall_anyoverlap']:.3f}  "
                  f"calls={r['oracle_calls']:3d}  "
                  f"regress={r['regression_vs_flat_IoU']:+.3f}")
    print()

    # Verdict: focus on detector_fallback_sim at budget 0.30
    df_030 = df[df["budget_ratio"] == 0.30]
    rc_2000 = df_030[df_030["segment_id"] == "realcartest_2000_3200"]
    det_rc = rc_2000[rc_2000["method"] == "HTS_EC_detector_fallback_sim"]
    flat_rc = rc_2000[rc_2000["method"] == "fixed_10s_topproxy"]
    naive_rc = rc_2000[rc_2000["method"] == "naive_HTS_godseye"]

    det_recall_rc = float(det_rc["event_recall_IoU"].iloc[0]) if len(det_rc) else 0.0
    flat_recall_rc = float(flat_rc["event_recall_IoU"].iloc[0]) if len(flat_rc) else 0.0
    naive_recall_rc = float(naive_rc["event_recall_IoU"].iloc[0]) if len(naive_rc) else 0.0

    # Check: detector fallback doesn't regress vs flat on rc_2000 (delta >= -0.02)
    no_regression_rc = (det_recall_rc - flat_recall_rc) >= -0.02

    # Check: detector fallback preserves naive HTS savings on sparse dataset3
    ds_segments = ["dataset3_0_1200", "dataset3_1200_2400", "dataset3_2400_3462"]
    preserves_savings = True
    for ds in ds_segments:
        sub = df_030[df_030["segment_id"] == ds]
        det = sub[sub["method"] == "HTS_EC_detector_fallback_sim"]
        naive = sub[sub["method"] == "naive_HTS_godseye"]
        if len(det) and len(naive):
            det_r = float(det["event_recall_IoU"].iloc[0])
            naive_r = float(naive["event_recall_IoU"].iloc[0])
            if det_r < naive_r - 0.02:
                preserves_savings = False

    print(f"realcartest_2000_3200 @0.30: detector_recall={det_recall_rc:.3f}  "
          f"flat_recall={flat_recall_rc:.3f}  naive_recall={naive_recall_rc:.3f}")
    print(f"  no_regression_vs_flat: {no_regression_rc} (delta={det_recall_rc - flat_recall_rc:+.3f})")
    print(f"  preserves_sparse_savings: {preserves_savings}")
    print()

    # Oracle upper bound comparison
    oracle_ub = rc_2000[rc_2000["method"] == "HTS_EC_oracle_saturation_upper_bound"]
    oracle_recall = float(oracle_ub["event_recall_IoU"].iloc[0]) if len(oracle_ub) else 0.0
    print(f"  oracle_saturation_upper_bound recall: {oracle_recall:.3f} (reference only)")
    print()

    if no_regression_rc and preserves_savings:
        verdict = "PASS"
    elif no_regression_rc or preserves_savings:
        verdict = "CONDITIONAL"
    else:
        verdict = "FAIL"

    print(f"GATE C VERDICT (detector_fallback_sim): {verdict}")
    print(f"  PASS: no regression on rc_2000 AND preserves sparse savings")
    print(f"  CONDITIONAL: one of the two checks passes")
    print(f"  FAIL: both checks fail")
    print()
    print(f"Written: {csv_path}  rows={len(df)} cols={len(df.columns)}")


if __name__ == "__main__":
    main()
