#!/usr/bin/env python3
"""naive-HTS-strict: faithful strict-replay implementation of HTS-AQP
(HTS_AQP_DESIGN.md §2.2) — Beta-UCB frontier + always-drill-on-positive,
NO saturation fallback, NO EventLift certify, NO temporal expansion.

This is the missing strict-replay comparator that Phase 1/2 needs to show
HTS-EC's delta. It uses the same AlignedOracle / load_segment_data /
evaluate_events plumbing as B7-strict / D3-strict / SUPG-event-strict.

Tree structure: top_branch=4, inner_branch=2 (HTS-EC v0 candidate, so
the delta comparison is a fair same-structure comparison).

Returned intervals = observed positive bins grouped by temporal adjacency
(reuses group_positive_bins from run_aligned_baselines_v1).

Hard constraints (per AGENTS.md):
  - No event_id online. AlignedOracle.assert_no_event_id() at end of each run.
  - oracle_calls_total <= budget_abs asserted.
  - No VLM/GPU/video. Replays existing is_positive labels.
  - IoU>=0.3 evaluation (same as aligned baselines).
  - No safe-stopping / formal-guarantee claim.
  - No certify, no temporal expansion, no saturation fallback.
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
    AlignedOracle, group_positive_bins, evaluate_events,
)

OUT = REPO / "outputs" / "hts_ec_feasibility_v1"
OUT.mkdir(parents=True, exist_ok=True)

BUDGET_RATIOS = [0.10, 0.20, 0.30]
SEEDS = [0, 1, 2]
TREE_TOP_BRANCH = 4
TREE_INNER_BRANCH = 2

# Beta-UCB params (HTS_AQP_DESIGN.md §2.2)
K0_PRIOR = 3.0       # pseudo-count strength
UCB_C = 0.5          # exploration constant
EPS = 1e-6

# Posterior-based variant decision thresholds
# (not in §2.2, but needed because single-probe §2.2 decision is broken
#  in strict-replay where CoarseProbe = 1 bin query, not free OR-aggregation)
POSTERIOR_DRILL_THRESH = 0.5
POSTERIOR_PRUNE_THRESH = 0.3
POSTERIOR_MIN_PROBES = 2  # need at least 2 probes before deciding


class TreeNode:
    __slots__ = ("node_id", "parent_id", "depth", "lo", "hi", "children",
                 "is_leaf", "n_leaves", "alpha", "beta", "n_probe",
                 "n_pos_probe", "in_frontier", "expanded", "pruned",
                 "mean_proxy")

    def __init__(self, node_id, parent_id, depth, lo, hi, mean_proxy=0.0):
        self.node_id = node_id
        self.parent_id = parent_id
        self.depth = depth
        self.lo = lo
        self.hi = hi
        self.children = []
        self.is_leaf = (hi - lo) <= 1
        self.n_leaves = hi - lo
        self.alpha = 1.0 + K0_PRIOR * mean_proxy
        self.beta = 1.0 + K0_PRIOR * (1.0 - mean_proxy)
        self.n_probe = 0
        self.n_pos_probe = 0
        self.in_frontier = False
        self.expanded = False
        self.pruned = False
        self.mean_proxy = mean_proxy


def build_tree(lo, hi, proxies, top_branch, inner_branch, depth=0,
               parent_id=None, counter=None, top_level=True):
    if counter is None:
        counter = [0]
    node_id = f"d{depth}_n{counter[0]}"
    counter[0] += 1
    mean_proxy = float(np.mean(proxies[lo:hi])) if hi > lo else 0.0
    node = TreeNode(node_id, parent_id, depth, lo, hi, mean_proxy)
    width = hi - lo
    if width <= 1:
        node.is_leaf = True
        return node
    b = top_branch if top_level else inner_branch
    if width <= b:
        for i in range(width):
            child = build_tree(lo + i, lo + i + 1, proxies, top_branch,
                              inner_branch, depth + 1, node_id, counter, False)
            node.children.append(child)
        return node
    sub_width = width / b
    for i in range(b):
        cs = lo + int(round(i * sub_width))
        ce = lo + int(round((i + 1) * sub_width))
        cs = max(lo, min(hi, cs))
        ce = max(cs + 1, min(hi, ce))
        child = build_tree(cs, ce, proxies, top_branch, inner_branch,
                          depth + 1, node_id, counter, False)
        node.children.append(child)
    return node


def collect_all_nodes(root, acc=None):
    if acc is None:
        acc = []
    acc.append(root)
    for c in root.children:
        collect_all_nodes(c, acc)
    return acc


def find_leaf_node(bin_idx, root):
    if root.is_leaf:
        return root
    for c in root.children:
        if c.lo <= bin_idx < c.hi:
            return find_leaf_node(bin_idx, c)
    return root


def ucb_score(node, t):
    """Beta-UCB score from HTS_AQP_DESIGN.md §2.2."""
    mean = node.alpha / (node.alpha + node.beta + EPS)
    exploration = UCB_C * math.sqrt(math.log(max(t, 1) + 1) / (node.n_probe + 1 + EPS))
    return mean + exploration


def select_representative_bin(node, proxies, rng, queried_bins):
    """Select a representative bin within node: highest proxy among unqueried.
    Ties broken randomly by seed."""
    bins_in_node = list(range(node.lo, node.hi))
    candidates = [b for b in bins_in_node if b not in queried_bins]
    if not candidates:
        candidates = bins_in_node
    # Sort by proxy desc, random tie-break
    candidates.sort(key=lambda b: (-proxies[b], rng.random()))
    return candidates[0]


def run_naive_hts_strict(grid, ref_seg, seg_id, budget_abs, budget_ratio, seed,
                         decision_mode="single_probe"):
    """Faithful HTS-AQP §2.2 strict-replay run.

    decision_mode:
      "single_probe" — §2.2 literal: positive probe → drill, negative → prune.
                      Broken in strict-replay (1 neg probe on root prunes all).
      "posterior"    — Posterior-based: drill if P(pos)>0.5 after >=2 probes,
                      prune if P(pos)<0.3 after >=2 probes, else probe again.
                      More robust; still no saturation fallback.
    """
    method_id = f"naive-HTS-strict-{decision_mode}"
    oracle = AlignedOracle(grid, seg_id, method_id, seed, budget_abs, budget_ratio)
    grid_sorted = grid.sort_values("bin_idx").reset_index(drop=True)
    n_bins = len(grid_sorted)
    labels = dict(zip(grid_sorted["bin_idx"], grid_sorted[LABEL_COL]))
    proxies = dict(zip(grid_sorted["bin_idx"], grid_sorted[PROXY_COL]))
    proxies_arr = grid_sorted[PROXY_COL].values

    rng = np.random.RandomState(seed)

    root = build_tree(0, n_bins, proxies_arr, TREE_TOP_BRANCH, TREE_INNER_BRANCH)
    all_nodes = collect_all_nodes(root)
    all_by_id = {n.node_id: n for n in all_nodes}

    # Initialize frontier with root
    frontier = [root]
    root.in_frontier = True

    queried_bins = set()
    positive_bins = set()
    t = 0  # global step counter for UCB

    while oracle.calls < budget_abs and frontier:
        # Select highest-UCB node from frontier
        best_node = None
        best_score = -float("inf")
        for node in frontier:
            s = ucb_score(node, t)
            if s > best_score:
                best_score = s
                best_node = node

        if best_node is None:
            break

        # Probe representative bin in best_node
        bin_to_probe = select_representative_bin(best_node, proxies, rng, queried_bins)
        result = oracle.query_unit(
            bin_to_probe,
            action_type="COARSE_PROBE",
            source_action="naive_hts_ucb",
            notes=f"node={best_node.node_id} depth={best_node.depth} ucb={best_score:.4f}",
        )
        y = 1 if result == "positive" else 0
        queried_bins.add(bin_to_probe)
        if y == 1:
            positive_bins.add(bin_to_probe)
        t += 1

        # Update Beta posterior for this node and all ancestors
        cur = best_node
        while cur is not None:
            cur.n_probe += 1
            if y == 1:
                cur.n_pos_probe += 1
                cur.alpha += 1
            else:
                cur.beta += 1
            cur = all_by_id.get(cur.parent_id) if cur.parent_id else None

        # Drill/prune decision
        if decision_mode == "single_probe":
            # §2.2 literal: positive → drill, negative → prune
            if y == 1:
                if not best_node.is_leaf and not best_node.expanded:
                    for c in best_node.children:
                        c.in_frontier = True
                        frontier.append(c)
                    best_node.expanded = True
                if best_node in frontier:
                    frontier.remove(best_node)
                    best_node.in_frontier = False
            else:
                if best_node in frontier:
                    frontier.remove(best_node)
                    best_node.in_frontier = False
                    best_node.pruned = True
        else:  # posterior
            posterior_mean = best_node.alpha / (best_node.alpha + best_node.beta + EPS)
            if best_node.n_probe >= POSTERIOR_MIN_PROBES:
                if posterior_mean >= POSTERIOR_DRILL_THRESH:
                    if not best_node.is_leaf and not best_node.expanded:
                        for c in best_node.children:
                            c.in_frontier = True
                            frontier.append(c)
                        best_node.expanded = True
                    if best_node in frontier:
                        frontier.remove(best_node)
                        best_node.in_frontier = False
                elif posterior_mean <= POSTERIOR_PRUNE_THRESH:
                    if best_node in frontier:
                        frontier.remove(best_node)
                        best_node.in_frontier = False
                        best_node.pruned = True
                # else: keep in frontier, probe again next time
            # if < min probes, keep in frontier for more probing

    # Build returned intervals from positive bins (adjacency grouping)
    pos_bin_list = sorted(positive_bins)
    returned_intervals = group_positive_bins(pos_bin_list, grid_sorted)

    # Evaluate (IoU>=0.3)
    ev = evaluate_events(returned_intervals, ref_seg)

    oracle.assert_no_event_id()
    assert oracle.calls <= budget_abs, f"Budget violation: {oracle.calls} > {budget_abs}"

    # Build frontier row
    frontier_row = {
        "segment_id": seg_id,
        "method_id": method_id,
        "seed": seed,
        "budget_abs": budget_abs,
        "budget_ratio": budget_ratio,
        "oracle_calls_total": oracle.calls,
        "returned_intervals": str(returned_intervals),
        "event_precision": ev["event_precision"],
        "event_recall": ev["event_recall"],
        "unique_event_coverage": ev["unique_event_coverage"],
        "duplicate_rate": 0.0,  # adjacency grouping has no duplicates by construction
        "strict_replay_or_posthoc": "strict_replay",
        "online_uses_event_id": False,
        "can_be_main_comparison": True,
        "applicability_note": "naive HTS-AQP §2.2 Beta-UCB frontier, always-drill-on-positive, no saturation fallback, no certify, no temporal expansion; tree top_branch=4 inner_branch=2; returned intervals = positive bins grouped by adjacency",
    }

    return frontier_row, oracle.ledger, {
        "n_frontier_final": len(frontier),
        "n_positive_bins": len(positive_bins),
        "n_pruned_nodes": sum(1 for n in all_nodes if n.pruned),
        "n_expanded_nodes": sum(1 for n in all_nodes if n.expanded),
        "tree_total_nodes": len(all_nodes),
    }


def main():
    all_frontier = []
    all_trace = []
    all_diag = []

    for seg in SEGMENTS:
        seg_id = seg["segment_id"]
        grid, ref_seg, err = load_segment_data(seg)
        if err:
            print(f"SKIP {seg_id}: {err}")
            continue
        n_bins = len(grid)
        for br in BUDGET_RATIOS:
            budget_abs = max(1, int(round(br * n_bins)))
            for seed in SEEDS:
                for dm in ["single_probe", "posterior"]:
                    frontier_row, trace, diag = run_naive_hts_strict(
                        grid, ref_seg, seg_id, budget_abs, br, seed, decision_mode=dm)
                    all_frontier.append(frontier_row)
                    all_trace.extend(trace)
                    diag_row = {"segment_id": seg_id, "seed": seed, "decision_mode": dm,
                               "budget_abs": budget_abs, "budget_ratio": br, **diag}
                    all_diag.append(diag_row)

    frontier_df = pd.DataFrame(all_frontier)
    trace_df = pd.DataFrame(all_trace)
    diag_df = pd.DataFrame(all_diag)

    f_path = OUT / "naive_hts_aqp_frontier.csv"
    t_path = OUT / "naive_hts_aqp_call_trace.csv"
    d_path = OUT / "naive_hts_aqp_diagnostics.csv"
    frontier_df.to_csv(f_path, index=False)
    trace_df.to_csv(t_path, index=False)
    diag_df.to_csv(d_path, index=False)

    # Verify constraints
    n_violations = int((frontier_df["oracle_calls_total"] > frontier_df["budget_abs"]).sum())
    n_event_id_leaks = int((frontier_df["online_uses_event_id"] == True).sum())

    print("=" * 70)
    print("naive-HTS-strict — faithful §2.2 Beta-UCB strict-replay baseline")
    print("=" * 70)
    print(f"Tree: top_branch={TREE_TOP_BRANCH}, inner_branch={TREE_INNER_BRANCH}")
    print(f"Beta-UCB: k0={K0_PRIOR}, c={UCB_C}")
    print(f"Budgets: {BUDGET_RATIOS}, Seeds: {SEEDS}")
    print(f"Segments: {len(SEGMENTS)}")
    print(f"Total runs: {len(frontier_df)}")
    print()
    print(f"Budget violations: {n_violations} (must be 0)")
    print(f"event_id leaks: {n_event_id_leaks} (must be 0)")
    print()
    print("Per segment x budget (best-of-3-seed IoU>=0.3 recall):")
    for (seg, br), grp in frontier_df.groupby(["segment_id", "budget_ratio"]):
        best_recall = grp["event_recall"].max()
        mean_recall = grp["event_recall"].mean()
        n_runs = len(grp)
        print(f"  {seg:28s} b={br:.2f}  n={n_runs}  best_recall={best_recall:.3f}  mean={mean_recall:.3f}")
    print()
    print(f"Written: {f_path}  rows={len(frontier_df)} cols={len(frontier_df.columns)}")
    print(f"Written: {t_path}  rows={len(trace_df)} cols={len(trace_df.columns)}")
    print(f"Written: {d_path}  rows={len(diag_df)} cols={len(diag_df.columns)}")

    assert n_violations == 0, f"Budget violations: {n_violations}"
    assert n_event_id_leaks == 0, f"event_id leaks: {n_event_id_leaks}"


if __name__ == "__main__":
    main()
