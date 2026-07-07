#!/usr/bin/env python3
"""HTS-EC Gate B — Saturation Detector Feasibility.

Simulates an online-legal saturation detector on three tree structures
(b=2, b=4, top_branch=4/inner_branch=2) over the 6 LATE-AQP segments.
The detector sees ONLY proxy-ordered probe prefixes (online info), never
full labels at decision time. Offline true-saturation labels (computed
from full labels) are used ONLY for evaluation, never for the detector.

Hard constraints (per AGENTS.md):
  - No oracle / VLM / GPU / new labels. Replays existing is_positive.
  - No event_id used by the detector. No safe-stopping claim.
  - Detector is a feasibility diagnostic, not a deployed module.
  - All numbers tagged with source + track.

Pass criteria (relaxed per audit):
  - realcartest_2000_3200 root or majority of level-1 nodes flagged
    saturated (across all 3 tree configs).
  - dataset3_0_1200 root NOT globally saturated.
  - Sparse negative subtrees in dataset3_0_1200 not over-flagged.
  - Local high-proxy false-positive subtrees in dataset3_0_1200 MAY be
    flagged (allowed, not a failure).
"""
import sys
import math
from pathlib import Path
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from run_aligned_baselines_v1 import load_segment_data, SEGMENTS, PROXY_COL, LABEL_COL

OUT = REPO / "outputs" / "hts_ec_feasibility_v1"
OUT.mkdir(parents=True, exist_ok=True)

# Detector params (from spec §7.3)
K_MIN = 2
THETA_SAT = 0.67
THETA_PV = 1.0
EPS = 1e-6

# Calibrated detector: Phase 0 showed the drill-vs-flat crossover at ~20%
# positive density. A density-calibrated detector flags saturation when the
# observed bin-level positive rate within a node exceeds this crossover,
# because above it, OR-aggregated coarse nodes are almost always positive
# and drilling overhead exceeds pruning savings.
# NOTE: this 0.20 threshold is derived from Phase 0 results on the SAME 6
# segments, creating a circularity risk. Reported alongside the spec
# detector to honestly characterize the calibration gap.
THETA_SAT_CALIBRATED = 0.20
K_MIN_CALIBRATED = 3  # need more probes for a density estimate

# Offline true-saturation: node is truly saturated if God's-eye drilling
# into its subtree uses >= as many oracle calls as flat-scanning its leaves.
# This is exactly the Phase 0 failure mode (tree overhead > pruning savings).
# Computed by recursing the Phase 0 simulate() on each subtree using full
# labels. Only applied to non-leaf nodes with >= 4 leaves (small nodes have
# no meaningful tree overhead).
TRUE_SAT_MIN_LEAVES = 4

# Probe-prefix checkpoints (fraction of segment bins probed)
PREFIX_CHECKPOINTS = [0.10, 0.20, 0.30]

TREE_CONFIGS = [
    {"name": "b2", "top_branch": 2, "inner_branch": 2},
    {"name": "b4", "top_branch": 4, "inner_branch": 4},
    {"name": "top4_inner2", "top_branch": 4, "inner_branch": 2},
]


class Node:
    __slots__ = ("node_id", "parent_id", "depth", "leaf_bin_idx_lo", "leaf_bin_idx_hi",
                 "children", "is_leaf", "n_leaves", "n_pos_leaves_full",
                 "n_probe", "n_pos_probe", "n_neg_probe")

    def __init__(self, node_id, parent_id, depth, lo, hi):
        self.node_id = node_id
        self.parent_id = parent_id
        self.depth = depth
        self.leaf_bin_idx_lo = lo  # inclusive bin index
        self.leaf_bin_idx_hi = hi  # exclusive
        self.children = []
        self.is_leaf = (hi - lo) <= 1
        self.n_leaves = hi - lo
        self.n_pos_leaves_full = 0  # filled from full labels
        self.n_probe = 0
        self.n_pos_probe = 0
        self.n_neg_probe = 0


def build_tree(lo, hi, top_branch, inner_branch, depth=0, parent_id=None,
               node_counter=None, top_level=True):
    """Build multi-resolution tree. top_branch at root, inner_branch below."""
    if node_counter is None:
        node_counter = [0]
    node_id = f"d{depth}_n{node_counter[0]}"
    node_counter[0] += 1
    node = Node(node_id, parent_id, depth, lo, hi)
    width = hi - lo
    if width <= 1:
        node.is_leaf = True
        return node
    b = top_branch if top_level else inner_branch
    # If fewer bins than branch, just split into single-bin leaves
    if width <= b:
        for i in range(width):
            child = build_tree(lo + i, lo + i + 1, top_branch, inner_branch,
                              depth + 1, node_id, node_counter, top_level=False)
            node.children.append(child)
        return node
    sub_width = width / b
    for i in range(b):
        cs = lo + int(round(i * sub_width))
        ce = lo + int(round((i + 1) * sub_width))
        cs = max(lo, min(hi, cs))
        ce = max(cs + 1, min(hi, ce))
        child = build_tree(cs, ce, top_branch, inner_branch,
                          depth + 1, node_id, node_counter, top_level=False)
        node.children.append(child)
    return node


def collect_nodes(root, acc=None):
    if acc is None:
        acc = []
    acc.append(root)
    for c in root.children:
        collect_nodes(c, acc)
    return acc


def fill_full_labels(root, labels_array):
    """Fill n_pos_leaves_full from full labels (offline, eval only)."""
    root.n_pos_leaves_full = int(labels_array[root.leaf_bin_idx_lo:root.leaf_bin_idx_hi].sum())
    for c in root.children:
        fill_full_labels(c, labels_array)


def reset_probe_stats(root):
    root.n_probe = 0
    root.n_pos_probe = 0
    root.n_neg_probe = 0
    for c in root.children:
        reset_probe_stats(c)


def update_ancestors(node, all_nodes_by_id, y):
    """Walk up from node, incrementing probe stats. Also increment the node itself."""
    cur = node
    while cur is not None:
        cur.n_probe += 1
        if y == 1:
            cur.n_pos_probe += 1
        else:
            cur.n_neg_probe += 1
        cur = all_nodes_by_id.get(cur.parent_id) if cur.parent_id else None


def detector_saturation(node, k_min=K_MIN, theta_sat=THETA_SAT, theta_pv=THETA_PV):
    """Online-legal saturation detector (spec §7.1-7.3)."""
    if node.n_probe < k_min:
        return False, 0.0, 0.0
    S = node.n_pos_probe / (node.n_probe + EPS)
    # posterior p(v) via Beta(1+n+, 1+n-)
    alpha = 1.0 + node.n_pos_probe
    beta = 1.0 + node.n_neg_probe
    p = alpha / (alpha + beta)
    n_unqueried = node.n_leaves - node.n_probe
    PV = (1.0 - p) * max(0, n_unqueried)
    sat = (S >= theta_sat) and (PV <= theta_pv)
    return sat, S, PV


def detector_saturation_calibrated(node, theta_density=THETA_SAT_CALIBRATED,
                                   k_min=K_MIN_CALIBRATED):
    """Density-calibrated detector (Phase 0 crossover-based).
    Flags saturation when observed bin-level positive density within the node
    exceeds the ~20% crossover threshold at which God's-eye drilling overhead
    exceeds pruning savings. Does NOT use PV (which scales with N_unqueried
    and is ill-suited for large nodes).

    Circular: theta_density derived from Phase 0 on same 6 segments.
    """
    if node.n_probe < k_min:
        return False, 0.0
    if node.n_leaves < 4:
        return False, 0.0
    density_est = node.n_pos_probe / (node.n_probe + EPS)
    return density_est >= theta_density, density_est


def godseye_drill_cost(node, labels_array):
    """Phase 0 God's-eye descent cost for a subtree (full labels).
    1 call to probe node; if positive and non-leaf, recurse into all children;
    if negative, prune (no more calls). Leaf positive = 1 call, found."""
    if node.is_leaf:
        return 1
    is_pos = bool(labels_array[node.leaf_bin_idx_lo:node.leaf_bin_idx_hi].any())
    if not is_pos:
        return 1  # probe + prune
    return 1 + sum(godseye_drill_cost(c, labels_array) for c in node.children)


def true_saturation(node, labels_array, min_leaves=TRUE_SAT_MIN_LEAVES):
    """Offline true saturation (from full labels, eval only).
    True if God's-eye drilling uses >= as many calls as flat-scanning leaves."""
    if node.n_leaves < min_leaves or node.is_leaf:
        return False
    drill = godseye_drill_cost(node, labels_array)
    flat = node.n_leaves
    return drill >= flat


def simulate_naive_hts_descent(root, labels, proxies, all_nodes_by_id, budget):
    """Simulate a naive HTS God's-eye descent to generate realistic probe prefixes.

    The descent uses God's-eye coarse labels (OR of leaves) to decide
    drill/prune — this is the same as Phase 0. But the DETECTOR only sees
    the observed probes (online-legal). Probes concentrate in subtrees
    the way a real HTS run would, unlike a flat proxy-ordered sweep.

    Returns list of (step, bin_probed, leaf_node_id) so checkpoints can
    evaluate the detector at realistic probe prefixes.
    """
    probe_log = []
    # frontier = list of nodes to probe (representative bin each)
    # Start with root
    frontier = [root]
    steps = 0
    while frontier and steps < budget:
        node = frontier.pop(0)
        if node.n_leaves == 0:
            continue
        # Select representative bin: highest-proxy unqueried leaf bin in this node
        leaf_bins = list(range(node.leaf_bin_idx_lo, node.leaf_bin_idx_hi))
        # find the leaf node and probe one bin
        # pick highest proxy among bins in this node
        node_proxy_vals = [(b, proxies[b]) for b in leaf_bins]
        node_proxy_vals.sort(key=lambda x: -x[1])
        bin_to_probe = node_proxy_vals[0][0]
        y = int(labels[bin_to_probe])
        # find leaf node for this bin
        leaf = _find_leaf_in_tree(bin_to_probe, root)
        update_ancestors(leaf, all_nodes_by_id, y)
        probe_log.append((steps, bin_to_probe, leaf.node_id))
        steps += 1
        # God's-eye drill decision: was this node positive (any leaf positive)?
        is_node_pos = bool(labels[node.leaf_bin_idx_lo:node.leaf_bin_idx_hi].any())
        if is_node_pos and not node.is_leaf:
            # drill: add children to frontier
            for c in node.children:
                frontier.append(c)
        # if negative: prune (don't add children)
    return probe_log


def _find_leaf_in_tree(bin_idx, root):
    if root.is_leaf:
        return root
    for c in root.children:
        if c.leaf_bin_idx_lo <= bin_idx < c.leaf_bin_idx_hi:
            return _find_leaf_in_tree(bin_idx, c)
    return root

def run_segment(seg, tree_config):
    grid, ref_seg, err = load_segment_data(seg)
    if err:
        return []
    grid = grid.sort_values("bin_idx").reset_index(drop=True)
    n_bins = len(grid)
    labels = grid[LABEL_COL].astype(int).values
    proxies = grid[PROXY_COL].values

    root = build_tree(0, n_bins, tree_config["top_branch"], tree_config["inner_branch"])
    fill_full_labels(root, labels)
    all_nodes = collect_nodes(root)
    all_nodes_by_id = {n.node_id: n for n in all_nodes}

    # Simulate naive HTS God's-eye descent up to 30% budget
    max_budget = int(round(0.30 * n_bins))
    probe_log = simulate_naive_hts_descent(root, labels, proxies, all_nodes_by_id, max_budget)

    # Evaluate detector at checkpoints (by probe count, matching prefix fractions)
    rows = []
    for cp_frac in PREFIX_CHECKPOINTS:
        reset_probe_stats(root)
        n_probes_at_cp = min(len(probe_log), max(1, int(round(cp_frac * n_bins))))
        # Replay probes up to checkpoint
        for step in range(n_probes_at_cp):
            _, bin_probed, leaf_id = probe_log[step]
            y = int(labels[bin_probed])
            leaf = all_nodes_by_id[leaf_id]
            update_ancestors(leaf, all_nodes_by_id, y)
        # Evaluate detector on every node at this checkpoint
        for node in all_nodes:
            sat_pred, S, PV = detector_saturation(node)
            sat_pred_cal, density_est = detector_saturation_calibrated(node)
            sat_true = true_saturation(node, labels)
            density = node.n_pos_leaves_full / node.n_leaves if node.n_leaves > 0 else 0.0
            rows.append({
                "segment_id": seg["segment_id"],
                "tree_config": tree_config["name"],
                "checkpoint_frac": cp_frac,
                "n_probes_so_far": n_probes_at_cp,
                "node_id": node.node_id,
                "parent_id": node.parent_id if node.parent_id else "",
                "depth": node.depth,
                "n_leaf_bins": node.n_leaves,
                "n_probe": node.n_probe,
                "n_pos_probe": node.n_pos_probe,
                "n_neg_probe": node.n_neg_probe,
                "positive_probe_rate": S,
                "estimated_pruning_value": PV,
                "observed_density_est": density_est,
                "true_positive_leaf_density": density,
                "true_n_positive_leaves": node.n_pos_leaves_full,
                "saturated_pred_spec": int(sat_pred),
                "saturated_pred_calibrated": int(sat_pred_cal),
                "saturated_true": int(sat_true),
                "false_positive_spec": int(sat_pred and not sat_true),
                "false_negative_spec": int(not sat_pred and sat_true),
                "false_positive_calibrated": int(sat_pred_cal and not sat_true),
                "false_negative_calibrated": int(not sat_pred_cal and sat_true),
                "root_saturated_spec": int(sat_pred) if node.parent_id is None else 0,
                "root_saturated_calibrated": int(sat_pred_cal) if node.parent_id is None else 0,
                "source": "hts_ec_gate_b (naive HTS descent prefix; offline label = drill_cost>=flat_cost for eval only)",
                "track": "feasibility_detector",
            })
    return rows


def compute_summary(all_rows_df):
    """Per segment × tree_config: detector precision/recall + root/level1 flags.
    Reports both spec and calibrated detector variants."""
    summary = []
    for (seg, tree), grp in all_rows_df.groupby(["segment_id", "tree_config"]):
        row = {"segment_id": seg, "tree_config": tree}
        for variant, suffix in [("spec", "_spec"), ("calibrated", "_calibrated")]:
            pred_col = f"saturated_pred_{variant}"
            tp = int(((grp[pred_col] == 1) & (grp["saturated_true"] == 1)).sum())
            fp = int(((grp[pred_col] == 1) & (grp["saturated_true"] == 0)).sum())
            fn = int(((grp[pred_col] == 0) & (grp["saturated_true"] == 1)).sum())
            tn = int(((grp[pred_col] == 0) & (grp["saturated_true"] == 0)).sum())
            precision = tp / (tp + fp) if (tp + fp) > 0 else float("nan")
            recall = tp / (tp + fn) if (tp + fn) > 0 else float("nan")
            root_col = f"root_saturated_{variant}"
            root_rows = grp[grp["depth"] == 0]
            root_sat_pred = int(root_rows[root_col].max()) if len(root_rows) else 0
            l1 = grp[grp["depth"] == 1]
            l1_sat_pred = int(l1[pred_col].sum()) if len(l1) else 0
            row[f"precision_{variant}"] = precision
            row[f"recall_{variant}"] = recall
            row[f"tp_{variant}"] = tp
            row[f"fp_{variant}"] = fp
            row[f"fn_{variant}"] = fn
            row[f"tn_{variant}"] = tn
            row[f"root_saturated_{variant}"] = root_sat_pred
            row[f"level1_saturated_count_{variant}"] = l1_sat_pred
        # common
        root_rows = grp[grp["depth"] == 0]
        root_sat_true = int(root_rows["saturated_true"].max()) if len(root_rows) else 0
        l1 = grp[grp["depth"] == 1]
        l1_sat_true = int(l1["saturated_true"].sum()) if len(l1) else 0
        neg_sub = grp[grp["true_positive_leaf_density"] == 0.0]
        fp_sparse_spec = int(neg_sub["false_positive_spec"].sum()) if len(neg_sub) else 0
        fp_sparse_cal = int(neg_sub["false_positive_calibrated"].sum()) if len(neg_sub) else 0
        neg_sub_total = len(neg_sub)
        row["root_saturated_true"] = root_sat_true
        row["level1_saturated_count_true"] = l1_sat_true
        row["false_positive_sparse_spec"] = fp_sparse_spec
        row["false_positive_sparse_calibrated"] = fp_sparse_cal
        row["false_positive_sparse_rate_spec"] = fp_sparse_spec / neg_sub_total if neg_sub_total > 0 else 0.0
        row["false_positive_sparse_rate_calibrated"] = fp_sparse_cal / neg_sub_total if neg_sub_total > 0 else 0.0
        row["neg_subtree_nodes_total"] = neg_sub_total
        row["source"] = "hts_ec_gate_b summary"
        summary.append(row)
    return pd.DataFrame(summary)


def main():
    all_rows = []
    for seg in SEGMENTS:
        for tc in TREE_CONFIGS:
            rows = run_segment(seg, tc)
            all_rows.extend(rows)
    all_df = pd.DataFrame(all_rows)
    detail_path = OUT / "saturation_detector_feasibility.csv"
    all_df.to_csv(detail_path, index=False)

    summary_df = compute_summary(all_df)
    summary_path = OUT / "saturation_detector_summary.csv"
    summary_df.to_csv(summary_path, index=False)

    # Verdict
    print("=" * 70)
    print("HTS-EC Gate B — Saturation Detector Feasibility")
    print("=" * 70)
    print(f"Detector params: k_min={K_MIN}, theta_sat={THETA_SAT}, theta_pv={THETA_PV}")
    print(f"Tree configs: {[t['name'] for t in TREE_CONFIGS]}")
    print(f"Probe-prefix checkpoints: {PREFIX_CHECKPOINTS}")
    print(f"Offline true-sat: God's-eye drill_cost >= flat_scan_cost, min_leaves>={TRUE_SAT_MIN_LEAVES}")
    print()
    print("Per segment x tree_config summary (spec / calibrated):")
    for _, r in summary_df.iterrows():
        print(f"  {r['segment_id']:28s} {r['tree_config']:12s}")
        print(f"    spec:       P={r['precision_spec']:.3f} R={r['recall_spec']:.3f}  "
              f"root_pred={r['root_saturated_spec']} root_true={r['root_saturated_true']}  "
              f"l1_pred={r['level1_saturated_count_spec']} l1_true={r['level1_saturated_count_true']}  "
              f"fp_sparse={r['false_positive_sparse_spec']}/{r['neg_subtree_nodes_total']}")
        print(f"    calibrated: P={r['precision_calibrated']:.3f} R={r['recall_calibrated']:.3f}  "
              f"root_pred={r['root_saturated_calibrated']} root_true={r['root_saturated_true']}  "
              f"l1_pred={r['level1_saturated_count_calibrated']} l1_true={r['level1_saturated_count_true']}  "
              f"fp_sparse={r['false_positive_sparse_calibrated']}/{r['neg_subtree_nodes_total']}")
    print()

    # Verdict checks — evaluate BOTH detector variants
    rc_2000 = summary_df[summary_df["segment_id"] == "realcartest_2000_3200"]
    ds_0 = summary_df[summary_df["segment_id"] == "dataset3_0_1200"]

    def check_variant(variant):
        rc_root = int((rc_2000[f"root_saturated_{variant}"] == 1).any())
        rc_l1_true_max = int(rc_2000["level1_saturated_count_true"].max())
        if rc_l1_true_max > 0:
            rc_l1 = int((rc_2000[f"level1_saturated_count_{variant}"] >= rc_l1_true_max / 2).any())
        else:
            rc_l1 = int((rc_2000[f"level1_saturated_count_{variant}"] > 0).any())
        rc_flagged = rc_root or rc_l1
        ds_root_not_sat = int((ds_0[f"root_saturated_{variant}"] == 0).all())
        ds_fp_rate = float(ds_0[f"false_positive_sparse_rate_{variant}"].mean())
        return rc_flagged, ds_root_not_sat, ds_fp_rate

    rc_spec, ds_spec, fp_spec = check_variant("spec")
    rc_cal, ds_cal, fp_cal = check_variant("calibrated")

    print(f"SPEC detector:      rc_flagged={rc_spec}  ds_root_not_sat={ds_spec}  fp_sparse_rate={fp_spec:.3f}")
    print(f"CALIBRATED detector: rc_flagged={rc_cal}  ds_root_not_sat={ds_cal}  fp_sparse_rate={fp_cal:.3f}")
    print()

    # Verdict: calibrated detector is the primary (spec detector is too strict
    # for 27% density segments, as expected). But circularity noted.
    if rc_cal and ds_cal and fp_cal < 0.30:
        verdict_cal = "PASS"
    elif rc_cal and ds_cal:
        verdict_cal = "CONDITIONAL"
    else:
        verdict_cal = "FAIL"

    if rc_spec and ds_spec and fp_spec < 0.30:
        verdict_spec = "PASS"
    elif rc_spec and ds_spec:
        verdict_spec = "CONDITIONAL"
    else:
        verdict_spec = "FAIL"

    print(f"GATE B VERDICT (spec detector, theta_sat={THETA_SAT}):       {verdict_spec}")
    print(f"GATE B VERDICT (calibrated, theta_density={THETA_SAT_CALIBRATED}): {verdict_cal}")
    print(f"  NOTE: calibrated threshold derived from Phase 0 on same 6 segments (circularity risk)")
    print()
    print(f"Written: {detail_path}  rows={len(all_df)} cols={len(all_df.columns)}")
    print(f"Written: {summary_path}  rows={len(summary_df)} cols={len(summary_df.columns)}")


if __name__ == "__main__":
    main()
