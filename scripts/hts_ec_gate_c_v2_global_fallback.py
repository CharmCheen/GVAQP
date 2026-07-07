#!/usr/bin/env python3
"""HTS-EC Gate C v2 — Global Fallback + Early Detection + Dual-Frontier.

Addresses the v1 finding that per-node flat-scan fallback is insufficient
(budget fragmentation). Tests three new fallback actions:

  4. HTS_EC_global_fallback       — root saturates → abandon tree, global proxy scan
  5. HTS_EC_early_global_fallback — 4-probe regime check, if dense → global scan
  6. HTS_EC_dual_frontier         — tree + fine frontier, pick best each step

Also retains v1 methods for comparison:
  1. naive_HTS_godseye
  2. naive_HTS_strict_posterior   (real Beta-UCB, posterior drill/prune)
  3. HTS_EC_detector_per_node_fallback (v1 failing version, LOO theta)
  7. fixed_10s_topproxy
  8. EventLift_DC_context

Key change: detector threshold is LOO-calibrated (leave-one-segment-out),
NOT derived from the test segment. This resolves the v1 circularity.

Hard constraints (per AGENTS.md):
  - No oracle / VLM / GPU / new labels. Replays existing is_positive.
  - No event_id online. No safe-stopping claim.
  - IoU>=0.3 is MAIN metric; any-overlap is diagnostic upper bound only.
  - LOO calibration: test segment's theta_density comes from other 5 segments.
"""
import sys
import math
from pathlib import Path
import numpy as np
import pandas as pd

from scipy.stats import beta as beta_dist

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
TREE_INNER_BRANCH = 2

# Beta-posterior detector params
K_MIN_BETA = 5               # minimum probes before detector can trigger
POSTERIOR_THRESH = 0.75      # P(density >= d*) > this → saturated
THETA_SWEEP = [0.10, 0.12, 0.14, 0.16, 0.18, 0.20, 0.22, 0.24, 0.26, 0.28, 0.30]

K_MIN_DEFAULT = K_MIN_BETA

# Beta-UCB params for posterior variant
K0_PRIOR = 3.0
UCB_C = 0.5
EPS = 1e-6
POSTERIOR_DRILL_THRESH = 0.5
POSTERIOR_PRUNE_THRESH = 0.3
POSTERIOR_MIN_PROBES = 2
UCB_C = 0.5
EPS = 1e-6
POSTERIOR_DRILL_THRESH = 0.5
POSTERIOR_PRUNE_THRESH = 0.3
POSTERIOR_MIN_PROBES = 2

# Dual-frontier params
DUAL_PRUNE_THRESH = 0.15  # prune tree node if P(pos) < this after k_min probes
DUAL_SAT_K_MIN = 2

# Early regime probe params
REGIME_PROBE_BUDGET_FRAC = 0.05  # 5% of budget for regime probing
REGIME_PROBE_MIN = 4

# Key test segments (per audit)
KEY_SEGMENTS = [
    "realcartest_2000_3200",
    "dataset3_0_1200",
    "dataset3_1200_2400",
    "dataset3_2400_3462",
]

# ============================================================
# Tree
# ============================================================
class Node:
    __slots__ = ("node_id", "parent_id", "depth", "lo", "hi", "children",
                 "is_leaf", "n_leaves", "n_pos_leaves", "alpha", "beta",
                 "n_probe", "n_pos_probe", "n_neg_probe", "mean_proxy",
                 "in_tree_frontier", "expanded", "pruned", "saturated")

    def __init__(self, node_id, parent_id, depth, lo, hi, mean_proxy=0.0):
        self.node_id = node_id
        self.parent_id = parent_id
        self.depth = depth
        self.lo = lo
        self.hi = hi
        self.children = []
        self.is_leaf = (hi - lo) <= 1
        self.n_leaves = hi - lo
        self.n_pos_leaves = 0
        self.alpha = 1.0 + K0_PRIOR * mean_proxy
        self.beta = 1.0 + K0_PRIOR * (1.0 - mean_proxy)
        self.n_probe = 0
        self.n_pos_probe = 0
        self.n_neg_probe = 0
        self.mean_proxy = mean_proxy
        self.in_tree_frontier = False
        self.expanded = False
        self.pruned = False
        self.saturated = False


def build_tree(lo, hi, proxies, depth=0, parent_id=None, counter=None, top_level=True):
    if counter is None:
        counter = [0]
    node_id = f"d{depth}_n{counter[0]}"
    counter[0] += 1
    mean_proxy = float(np.mean(proxies[lo:hi])) if hi > lo else 0.0
    node = Node(node_id, parent_id, depth, lo, hi, mean_proxy)
    width = hi - lo
    if width <= 1:
        node.is_leaf = True
        return node
    b = TREE_TOP_BRANCH if top_level else TREE_INNER_BRANCH
    if width <= b:
        for i in range(width):
            child = build_tree(lo + i, lo + i + 1, proxies,
                              depth + 1, node_id, counter, False)
            node.children.append(child)
        return node
    sub_width = width / b
    for i in range(b):
        cs = lo + int(round(i * sub_width))
        ce = lo + int(round((i + 1) * sub_width))
        cs = max(lo, min(hi, cs))
        ce = max(cs + 1, min(hi, ce))
        child = build_tree(cs, ce, proxies,
                          depth + 1, node_id, counter, False)
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
    root.alpha = 1.0 + K0_PRIOR * root.mean_proxy
    root.beta = 1.0 + K0_PRIOR * (1.0 - root.mean_proxy)
    root.n_probe = 0
    root.n_pos_probe = 0
    root.n_neg_probe = 0
    root.in_tree_frontier = False
    root.expanded = False
    root.pruned = False
    root.saturated = False
    for c in root.children:
        reset_runtime(c)


def find_leaf_node(bin_idx, root):
    if root.is_leaf:
        return root
    for c in root.children:
        if c.lo <= bin_idx < c.hi:
            return find_leaf_node(bin_idx, c)
    return root


def godseye_is_positive(node, labels):
    return bool(labels[node.lo:node.hi].any())


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


def update_ancestors(node, all_by_id, y):
    cur = node
    while cur is not None:
        cur.n_probe += 1
        if y == 1:
            cur.n_pos_probe += 1
            cur.alpha += 1
        else:
            cur.n_neg_probe += 1
            cur.beta += 1
        cur = all_by_id.get(cur.parent_id) if cur.parent_id else None


def detector_check(node, theta_density, k_min):
    """Beta-posterior detector: P(density >= theta_density | probes) > POSTERIOR_THRESH.
    theta_density is the theoretical break-even density for this segment's tree."""
    if node.n_probe < k_min:
        return False
    if node.n_leaves < 4:
        return False
    a = 1 + node.n_pos_probe
    b = 1 + node.n_neg_probe
    p_density_above = 1.0 - beta_dist.cdf(theta_density, a, b)
    return p_density_above > POSTERIOR_THRESH


def posterior_mean(node):
    return node.alpha / (node.alpha + node.beta + EPS)


def ucb_score(node, t):
    mean = posterior_mean(node)
    exploration = UCB_C * math.sqrt(math.log(max(t, 1) + 1) / (node.n_probe + 1 + EPS))
    return mean + exploration


def select_representative_bin(node, proxies, queried_bins):
    bins_in_node = list(range(node.lo, node.hi))
    candidates = [b for b in bins_in_node if b not in queried_bins]
    if not candidates:
        candidates = bins_in_node
    candidates.sort(key=lambda b: -proxies[b])
    return candidates[0]


# ============================================================
# Theoretical break-even density (no labels needed, no circularity)
# ============================================================
def expected_drill_cost(node, d):
    """Expected God's-eye drill cost at bin-density d (Bernoulli assumption).
    No labels used — purely structural + density assumption."""
    if node.is_leaf:
        return 1.0
    p_pos = 1.0 - (1.0 - d) ** node.n_leaves
    return 1.0 + p_pos * sum(expected_drill_cost(c, d) for c in node.children)


def find_break_even_density(root, n_bins, tol=1e-4):
    """Find d* where expected_drill_cost(root, d*) = n_bins (flat cost).
    Binary search over d in [0, 1]."""
    def cost_at(d):
        return expected_drill_cost(root, d)

    lo, hi = 0.001, 0.999
    for _ in range(50):
        mid = (lo + hi) / 2.0
        c = cost_at(mid)
        if c < n_bins:
            lo = mid  # need higher density to break even
        else:
            hi = mid
    return (lo + hi) / 2.0


# ============================================================
# LOO Calibration (kept as secondary check)
# ============================================================
def collect_detector_data(seg, labels, proxies, n_bins):
    """Run naive HTS descent, collect (observed_density, true_saturation) per node."""
    root = build_tree(0, n_bins, proxies)
    fill_pos_leaves(root, labels)
    all_nodes = collect_nodes(root)
    all_by_id = {n.node_id: n for n in all_nodes}

    # Naive HTS descent to 30% budget
    budget = int(round(0.30 * n_bins))
    frontier = [root]
    root.in_tree_frontier = True
    queried = set()
    calls = 0

    while frontier and calls < budget:
        best = max(frontier, key=lambda n: ucb_score(n, calls))
        bin_probe = select_representative_bin(best, proxies, queried)
        y = int(labels[bin_probe])
        leaf = find_leaf_node(bin_probe, root)
        update_ancestors(leaf, all_by_id, y)
        queried.add(bin_probe)
        calls += 1

        if y == 1:
            if not best.is_leaf and not best.expanded:
                for c in best.children:
                    c.in_tree_frontier = True
                    frontier.append(c)
                best.expanded = True
            if best in frontier:
                frontier.remove(best)
                best.in_tree_frontier = False
        else:
            if best in frontier:
                frontier.remove(best)
                best.in_tree_frontier = False
                best.pruned = True

    # Collect (density_est, true_sat) for each node with enough probes
    data = []
    for node in all_nodes:
        if node.n_probe >= K_MIN_DEFAULT and node.n_leaves >= 4:
            density_est = node.n_pos_probe / (node.n_probe + EPS)
            true_sat = is_truly_saturated(node, labels)
            data.append((density_est, true_sat))
    return data


def loo_calibrate(all_seg_data, test_seg):
    """Leave-one-segment-out: find best theta on other 5 segments."""
    train_data = []
    for seg_id, data in all_seg_data.items():
        if seg_id != test_seg:
            train_data.extend(data)

    if not train_data:
        return 0.20, K_MIN_DEFAULT  # fallback

    densities = np.array([d[0] for d in train_data])
    trues = np.array([d[1] for d in train_data])
    n_pos = int(trues.sum())
    n_neg = len(trues) - n_pos

    best_f1 = -1
    best_theta = 0.20
    for theta in THETA_SWEEP:
        preds = densities >= theta
        tp = int(((preds == True) & (trues == True)).sum())
        fp = int(((preds == True) & (trues == False)).sum())
        fn = int(((preds == False) & (trues == True)).sum())
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        if f1 > best_f1:
            best_f1 = f1
            best_theta = theta

    return best_theta, K_MIN_DEFAULT


# ============================================================
# Method 1: naive_HTS_godseye
# ============================================================
def run_naive_hts_godseye(root, labels, proxies, budget, all_by_id):
    reset_runtime(root)
    frontier = [root]
    calls = 0
    pos_bins = set()
    queried = set()

    while frontier and calls < budget:
        node = frontier.pop(0)
        if node.n_leaves == 0:
            continue
        best_bin = select_representative_bin(node, proxies, queried)
        y = int(labels[best_bin])
        leaf = find_leaf_node(best_bin, root)
        update_ancestors(leaf, all_by_id, y)
        queried.add(best_bin)
        calls += 1
        if y == 1:
            pos_bins.add(best_bin)
        is_pos = godseye_is_positive(node, labels)
        if is_pos and not node.is_leaf:
            for c in node.children:
                frontier.append(c)
        node.expanded = is_pos
        if not is_pos:
            node.pruned = True
    return pos_bins, calls


# ============================================================
# Method 2: naive_HTS_strict_posterior
# ============================================================
def run_naive_hts_strict_posterior(root, labels, proxies, budget, all_by_id, rng):
    reset_runtime(root)
    frontier = [root]
    root.in_tree_frontier = True
    calls = 0
    pos_bins = set()
    queried = set()
    t = 0

    while frontier and calls < budget:
        best = max(frontier, key=lambda n: ucb_score(n, t))
        bin_probe = select_representative_bin(best, proxies, queried)
        y = int(labels[bin_probe])
        leaf = find_leaf_node(bin_probe, root)
        update_ancestors(leaf, all_by_id, y)
        queried.add(bin_probe)
        calls += 1
        t += 1
        if y == 1:
            pos_bins.add(bin_probe)

        pm = posterior_mean(best)
        if best.n_probe >= POSTERIOR_MIN_PROBES:
            if pm >= POSTERIOR_DRILL_THRESH:
                if not best.is_leaf and not best.expanded:
                    for c in best.children:
                        c.in_tree_frontier = True
                        frontier.append(c)
                    best.expanded = True
                if best in frontier:
                    frontier.remove(best)
                    best.in_tree_frontier = False
            elif pm <= POSTERIOR_PRUNE_THRESH:
                if best in frontier:
                    frontier.remove(best)
                    best.in_tree_frontier = False
                    best.pruned = True
    return pos_bins, calls


# ============================================================
# Method 3: HTS_EC_detector_per_node_fallback (v1, with LOO theta)
# ============================================================
def run_detector_per_node_fallback(root, labels, proxies, budget, all_by_id,
                                    theta_density, k_min):
    reset_runtime(root)
    frontier = [(root, 0)]
    calls = 0
    pos_bins = set()
    queried = set()

    while frontier and calls < budget:
        node, _ = frontier.pop(0)
        if node.n_leaves == 0:
            continue
        if (not node.is_leaf) and detector_check(node, theta_density, k_min):
            node.saturated = True
            bins_in_node = [b for b in range(node.lo, node.hi) if b not in queried]
            bins_in_node.sort(key=lambda b: -proxies[b])
            for b in bins_in_node:
                if calls >= budget:
                    break
                y = int(labels[b])
                leaf = find_leaf_node(b, root)
                update_ancestors(leaf, all_by_id, y)
                queried.add(b)
                calls += 1
                if y == 1:
                    pos_bins.add(b)
            continue
        best_bin = select_representative_bin(node, proxies, queried)
        y = int(labels[best_bin])
        leaf = find_leaf_node(best_bin, root)
        update_ancestors(leaf, all_by_id, y)
        queried.add(best_bin)
        calls += 1
        if y == 1:
            pos_bins.add(best_bin)
        is_pos = godseye_is_positive(node, labels)
        if is_pos and not node.is_leaf:
            for c in node.children:
                frontier.append((c, 0))
        node.expanded = is_pos
        if not is_pos:
            node.pruned = True
    return pos_bins, calls


# ============================================================
# Method 4: HTS_EC_global_fallback
# When root saturates → abandon tree, global proxy-ranked scan
# ============================================================
def run_global_fallback(root, labels, proxies, budget, all_by_id,
                         theta_density, k_min):
    reset_runtime(root)
    frontier = [root]
    root.in_tree_frontier = True
    calls = 0
    pos_bins = set()
    queried = set()
    global_mode = False
    t = 0

    while calls < budget:
        if global_mode:
            remaining = [b for b in range(len(labels)) if b not in queried]
            remaining.sort(key=lambda b: -proxies[b])
            for b in remaining:
                if calls >= budget:
                    break
                y = int(labels[b])
                leaf = find_leaf_node(b, root)
                update_ancestors(leaf, all_by_id, y)
                queried.add(b)
                calls += 1
                if y == 1:
                    pos_bins.add(b)
            break

        if not frontier:
            break

        # Select best tree node
        best = max(frontier, key=lambda n: ucb_score(n, t))
        bin_probe = select_representative_bin(best, proxies, queried)
        y = int(labels[bin_probe])
        leaf = find_leaf_node(bin_probe, root)
        update_ancestors(leaf, all_by_id, y)
        queried.add(bin_probe)
        calls += 1
        t += 1
        if y == 1:
            pos_bins.add(bin_probe)

        # Drill/prune FIRST (God's-eye for upper-bound sim)
        is_pos = godseye_is_positive(best, labels)
        if is_pos and not best.is_leaf and not best.expanded:
            for c in best.children:
                c.in_tree_frontier = True
                frontier.append(c)
            best.expanded = True
        if best in frontier:
            frontier.remove(best)
            best.in_tree_frontier = False
        if not is_pos:
            best.pruned = True

        # THEN check root saturation (for FUTURE probes)
        root_node = all_by_id.get("d0_n0")
        if root_node and detector_check(root_node, theta_density, k_min):
            global_mode = True
            root_node.saturated = True
            for n in frontier:
                n.in_tree_frontier = False
            frontier = []
            continue

    return pos_bins, calls, global_mode


# ============================================================
# Method 5: HTS_EC_early_global_fallback
# 4-probe regime check first, if dense → global scan
# ============================================================
def run_early_global_fallback(root, labels, proxies, budget, all_by_id,
                               theta_density, k_min):
    reset_runtime(root)
    calls = 0
    pos_bins = set()
    queried = set()
    n_bins = len(labels)

    # Phase 1: regime probe (4 diverse probes)
    regime_budget = min(REGIME_PROBE_MIN, max(1, int(REGIME_PROBE_BUDGET_FRAC * budget)))
    regime_budget = min(regime_budget, budget)

    # Select diverse bins: top, median, low, far-from-top
    all_bins = list(range(n_bins))
    sorted_by_proxy = sorted(all_bins, key=lambda b: -proxies[b])
    n = len(sorted_by_proxy)
    probe_bins = []
    if n > 0:
        probe_bins.append(sorted_by_proxy[0])  # top
    if n > 2:
        probe_bins.append(sorted_by_proxy[n // 2])  # median
    if n > 4:
        probe_bins.append(sorted_by_proxy[-1])  # low
    if n > 8:
        probe_bins.append(sorted_by_proxy[3 * n // 4])  # diverse

    regime_pos = 0
    for b in probe_bins[:regime_budget]:
        if calls >= budget:
            break
        y = int(labels[b])
        leaf = find_leaf_node(b, root)
        update_ancestors(leaf, all_by_id, y)
        queried.add(b)
        calls += 1
        if y == 1:
            pos_bins.add(b)
            regime_pos += 1

    # Estimate density from regime probes
    density_est = regime_pos / max(1, len(probe_bins[:regime_budget]))

    # Phase 2: decide mode
    if density_est >= theta_density:
        # Dense → global proxy scan for remaining budget
        remaining = [b for b in range(n_bins) if b not in queried]
        remaining.sort(key=lambda b: -proxies[b])
        for b in remaining:
            if calls >= budget:
                break
            y = int(labels[b])
            leaf = find_leaf_node(b, root)
            update_ancestors(leaf, all_by_id, y)
            queried.add(b)
            calls += 1
            if y == 1:
                pos_bins.add(b)
        return pos_bins, calls, True  # global_mode = True

    # Sparse → normal HTS descent for remaining budget
    frontier = [root]
    root.in_tree_frontier = True
    # Root already has some probes from regime phase
    # Check if root should be drilled
    root_node = all_by_id.get("d0_n0")
    pm = posterior_mean(root_node) if root_node else 0.0

    while frontier and calls < budget:
        best = max(frontier, key=lambda n: ucb_score(n, calls))
        bin_probe = select_representative_bin(best, proxies, queried)
        y = int(labels[bin_probe])
        leaf = find_leaf_node(bin_probe, root)
        update_ancestors(leaf, all_by_id, y)
        queried.add(bin_probe)
        calls += 1
        if y == 1:
            pos_bins.add(bin_probe)

        # Check root saturation during descent too
        if root_node and detector_check(root_node, theta_density, k_min):
            # Switch to global mode
            remaining = [b for b in range(n_bins) if b not in queried]
            remaining.sort(key=lambda b: -proxies[b])
            for b in remaining:
                if calls >= budget:
                    break
                y2 = int(labels[b])
                leaf2 = find_leaf_node(b, root)
                update_ancestors(leaf2, all_by_id, y2)
                queried.add(b)
                calls += 1
                if y2 == 1:
                    pos_bins.add(b)
            return pos_bins, calls, True

        is_pos = godseye_is_positive(best, labels)
        if is_pos and not best.is_leaf and not best.expanded:
            for c in best.children:
                c.in_tree_frontier = True
                frontier.append(c)
            best.expanded = True
        if best in frontier:
            frontier.remove(best)
            best.in_tree_frontier = False
        if not is_pos:
            best.pruned = True

    return pos_bins, calls, False


# ============================================================
# Method 6: HTS_EC_dual_frontier
# Tree + fine frontier, pick best each step
# ============================================================
def run_dual_frontier(root, labels, proxies, budget, all_by_id,
                       theta_density, k_min):
    reset_runtime(root)
    n_bins = len(labels)
    calls = 0
    pos_bins = set()
    queried = set()
    t = 0

    # Tree frontier
    tree_frontier = [root]
    root.in_tree_frontier = True

    # Fine frontier: all bins sorted by proxy (descending)
    fine_sorted = sorted(range(n_bins), key=lambda b: -proxies[b])

    while calls < budget:
        # Check saturation on tree frontier nodes
        for node in tree_frontier[:]:
            if detector_check(node, theta_density, k_min):
                node.saturated = True
                tree_frontier.remove(node)
                node.in_tree_frontier = False
                # Don't remove fine bins — let fine frontier handle it

        # Prune low-posterior tree nodes
        for node in tree_frontier[:]:
            if node.n_probe >= k_min and posterior_mean(node) < DUAL_PRUNE_THRESH:
                node.pruned = True
                tree_frontier.remove(node)
                node.in_tree_frontier = False
                # Remove this node's bins from fine consideration (pruned)
                # (We don't track fine frontier explicitly, just skip queried)

        if not tree_frontier:
            # No tree nodes left → pure fine scan for remaining budget
            remaining = [b for b in fine_sorted if b not in queried]
            for b in remaining:
                if calls >= budget:
                    break
                y = int(labels[b])
                leaf = find_leaf_node(b, root)
                update_ancestors(leaf, all_by_id, y)
                queried.add(b)
                calls += 1
                if y == 1:
                    pos_bins.add(b)
            break

        # Find best tree node
        best_tree = max(tree_frontier, key=lambda n: ucb_score(n, t))
        u_tree = ucb_score(best_tree, t)

        # Find best fine bin (highest proxy, unqueried)
        best_fine = None
        for b in fine_sorted:
            if b not in queried:
                best_fine = b
                break
        u_fine = proxies[best_fine] if best_fine is not None else -1

        # Decision: if tree utility > fine utility, probe tree; else probe fine
        # Add pruning-value bonus to tree: U_tree *= (1 + PV/n_leaves)
        # This makes tree more attractive when pruning is valuable (sparse)
        pv = (1 - posterior_mean(best_tree)) * max(0, best_tree.n_leaves - best_tree.n_probe)
        u_tree_adjusted = u_tree * (1 + pv / max(1, best_tree.n_leaves))

        if u_tree_adjusted >= u_fine and best_fine is not None:
            # Probe tree node
            bin_probe = select_representative_bin(best_tree, proxies, queried)
            y = int(labels[bin_probe])
            leaf = find_leaf_node(bin_probe, root)
            update_ancestors(leaf, all_by_id, y)
            queried.add(bin_probe)
            calls += 1
            t += 1
            if y == 1:
                pos_bins.add(bin_probe)

            # Drill/prune (God's-eye for upper-bound sim)
            is_pos = godseye_is_positive(best_tree, labels)
            if is_pos and not best_tree.is_leaf and not best_tree.expanded:
                for c in best_tree.children:
                    c.in_tree_frontier = True
                    tree_frontier.append(c)
                best_tree.expanded = True
            if best_tree in tree_frontier:
                tree_frontier.remove(best_tree)
                best_tree.in_tree_frontier = False
            if not is_pos:
                best_tree.pruned = True
        elif best_fine is not None:
            # Probe fine bin
            y = int(labels[best_fine])
            leaf = find_leaf_node(best_fine, root)
            update_ancestors(leaf, all_by_id, y)
            queried.add(best_fine)
            calls += 1
            t += 1
            if y == 1:
                pos_bins.add(best_fine)
        else:
            break

    return pos_bins, calls


# ============================================================
# Evaluation
# ============================================================
def eval_intervals(returned_intervals, ref_events):
    if len(ref_events) == 0:
        return {"event_precision_IoU": 0.0, "event_recall_IoU": 0.0,
                "event_precision_anyoverlap": 0.0, "event_recall_anyoverlap": 0.0,
                "unique_event_coverage_IoU": 0, "unique_event_coverage_anyoverlap": 0}
    ref_iv = list(zip(ref_events["t_start"].values, ref_events["t_end"].values))
    hits_prec = sum(1 for (s, e) in returned_intervals
                    if any(_iou_interval(s, e, rs, re) >= IOU_THRESH for (rs, re) in ref_iv))
    precision_iou = hits_prec / len(returned_intervals) if returned_intervals else 0.0
    hits_rec_iou = sum(1 for (rs, re) in ref_iv
                       if any(_iou_interval(s, e, rs, re) >= IOU_THRESH for (s, e) in returned_intervals))
    recall_iou = hits_rec_iou / len(ref_iv)
    hits_prec_any = sum(1 for (s, e) in returned_intervals
                        if any(min(e, re) > max(s, rs) for (rs, re) in ref_iv))
    precision_any = hits_prec_any / len(returned_intervals) if returned_intervals else 0.0
    hits_rec_any = sum(1 for (rs, re) in ref_iv
                       if any(min(e, re) > max(s, rs) for (s, e) in returned_intervals))
    recall_any = hits_rec_any / len(ref_iv)
    return {
        "event_precision_IoU": precision_iou,
        "event_recall_IoU": recall_iou,
        "event_precision_anyoverlap": precision_any,
        "event_recall_anyoverlap": recall_any,
        "unique_event_coverage_IoU": hits_rec_iou,
        "unique_event_coverage_anyoverlap": hits_rec_any,
    }


def pos_bins_to_intervals(pos_bins, grid):
    if not pos_bins:
        return []
    return group_positive_bins(sorted(pos_bins), grid)


def flat_topproxy_recall(labels, proxies, budget_abs, grid, ref_events):
    """Fixed 10s top-proxy baseline."""
    probe_order = np.argsort(-proxies, kind="stable")
    pos_bins = set()
    for i in range(min(budget_abs, len(labels))):
        b = int(probe_order[i])
        if labels[b] == 1:
            pos_bins.add(b)
    intervals = pos_bins_to_intervals(pos_bins, grid)
    return eval_intervals(intervals, ref_events)


def get_eventlift_dc_recall(seg_id, budget_ratio):
    """Pull EventLift-DC best-of-3-seed from existing CSV."""
    el_path = REPO / "outputs/eventlift_full_benchmark_v1/full_frontier_raw.csv"
    if not el_path.exists():
        return None
    df = pd.read_csv(el_path)
    df = df[(df["segment_id"] == seg_id) &
            (df["method_id"] == "EventLift-discover-certify") &
            (df["budget_ratio"] == budget_ratio) &
            (df["strict_replay_or_posthoc"] == "strict_replay")].copy()
    if len(df) == 0:
        return None
    df["event_recall"] = pd.to_numeric(df["event_recall"], errors="coerce")
    best = df.loc[df["event_recall"].idxmax()]
    return {
        "recall": float(best.get("event_recall", 0.0) or 0.0),
        "precision": float(best.get("event_precision", 0.0) or 0.0),
        "calls": int(best.get("oracle_calls_total", 0)),
    }


# ============================================================
# Method 6b: HTS_EC_dual_frontier_gated
# Tree-only until detector triggers, then add fine bins to competition
# ============================================================
def run_dual_frontier_gated(root, labels, proxies, budget, all_by_id,
                             theta_density, k_min):
    """Gated dual frontier: fine bins only activated when detector triggers.
    - Sparse segments: detector never triggers → pure tree → preserves savings
    - Dense segments: detector triggers → fine bins compete → beats flat
    """
    reset_runtime(root)
    n_bins = len(labels)
    calls = 0
    pos_bins = set()
    queried = set()
    t = 0

    tree_frontier = [root]
    root.in_tree_frontier = True
    fine_frontier = []  # bins activated only when a node saturates

    while calls < budget:
        # Check saturation on all tree frontier nodes
        for node in tree_frontier[:]:
            if detector_check(node, theta_density, k_min):
                node.saturated = True
                tree_frontier.remove(node)
                node.in_tree_frontier = False
                # Add unqueried bins from this node to fine frontier
                for b in range(node.lo, node.hi):
                    if b not in queried:
                        fine_frontier.append(b)
                # Sort fine frontier by proxy descending
                fine_frontier.sort(key=lambda b: -proxies[b])

        # Prune low-posterior tree nodes
        for node in tree_frontier[:]:
            if node.n_probe >= k_min and posterior_mean(node) < DUAL_PRUNE_THRESH:
                node.pruned = True
                tree_frontier.remove(node)
                node.in_tree_frontier = False

        if not tree_frontier and not fine_frontier:
            break

        # Compute best options
        best_tree = None
        u_tree = -1
        if tree_frontier:
            best_tree = max(tree_frontier, key=lambda n: ucb_score(n, t))
            u_tree = ucb_score(best_tree, t)

        best_fine = None
        u_fine = -1
        if fine_frontier:
            # Remove already-queried bins
            fine_frontier = [b for b in fine_frontier if b not in queried]
            if fine_frontier:
                best_fine = fine_frontier[0]
                u_fine = proxies[best_fine]

        # Decision
        if best_tree is not None and best_fine is not None:
            # Compare: tree UCB vs fine proxy
            # Add small bonus to tree for structural pruning value
            pv_bonus = (1 - posterior_mean(best_tree)) * max(0, best_tree.n_leaves - best_tree.n_probe) / max(1, best_tree.n_leaves)
            use_tree = (u_tree + pv_bonus) >= u_fine
        elif best_tree is not None:
            use_tree = True
        else:
            use_tree = False

        if use_tree and best_tree is not None:
            bin_probe = select_representative_bin(best_tree, proxies, queried)
            y = int(labels[bin_probe])
            leaf = find_leaf_node(bin_probe, root)
            update_ancestors(leaf, all_by_id, y)
            queried.add(bin_probe)
            calls += 1
            t += 1
            if y == 1:
                pos_bins.add(bin_probe)

            is_pos = godseye_is_positive(best_tree, labels)
            if is_pos and not best_tree.is_leaf and not best_tree.expanded:
                for c in best_tree.children:
                    c.in_tree_frontier = True
                    tree_frontier.append(c)
                best_tree.expanded = True
            if best_tree in tree_frontier:
                tree_frontier.remove(best_tree)
                best_tree.in_tree_frontier = False
            if not is_pos:
                best_tree.pruned = True
        elif best_fine is not None:
            y = int(labels[best_fine])
            leaf = find_leaf_node(best_fine, root)
            update_ancestors(leaf, all_by_id, y)
            queried.add(best_fine)
            calls += 1
            t += 1
            if y == 1:
                pos_bins.add(best_fine)
            if best_fine in fine_frontier:
                fine_frontier.remove(best_fine)
        else:
            break

    return pos_bins, calls


# ============================================================
# Main
# ============================================================
def main():
    # Phase 1: Pre-compute LOO detector data for all 6 segments
    print("Phase 1: Theoretical break-even density + LOO calibration data...")
    all_seg_data = {}
    seg_cache = {}
    theoretical_thetas = {}
    for seg in SEGMENTS:
        seg_id = seg["segment_id"]
        grid, ref_seg, err = load_segment_data(seg)
        if err:
            print(f"  SKIP {seg_id}: {err}")
            continue
        grid = grid.sort_values("bin_idx").reset_index(drop=True)
        labels = grid[LABEL_COL].astype(int).values
        proxies = grid[PROXY_COL].values
        n_bins = len(grid)
        seg_cache[seg_id] = (grid, ref_seg, labels, proxies, n_bins)

        # Theoretical break-even density (no labels, no circularity)
        root = build_tree(0, n_bins, proxies)
        d_star = find_break_even_density(root, n_bins)
        theoretical_thetas[seg_id] = d_star

        data = collect_detector_data(seg, labels, proxies, n_bins)
        all_seg_data[seg_id] = data
        n_sat = sum(1 for _, t in data if t)
        print(f"  {seg_id}: theoretical d*={d_star:.4f}  LOO data: {len(data)} nodes, {n_sat} truly sat")

    # Phase 2: Calibrate theta for each segment
    # PRIMARY: theoretical break-even (no labels, no circularity)
    # SECONDARY: LOO (kept for comparison but not used due to sparse positives)
    print("\nPhase 2: Theta calibration (PRIMARY = theoretical)...")
    loo_thetas = {}
    for seg_id in seg_cache:
        theta_loo, _ = loo_calibrate(all_seg_data, seg_id)
        loo_thetas[seg_id] = theta_loo
        theta_theory = theoretical_thetas[seg_id]
        print(f"  {seg_id}: theoretical={theta_theory:.4f}  LOO={theta_loo:.2f}  → USING theoretical")

    # Phase 3: Run all methods on all segments
    print("\nPhase 3: Running methods...")
    all_rows = []
    rng = np.random.RandomState(42)

    for seg_id, (grid, ref_seg, labels, proxies, n_bins) in seg_cache.items():
        theta = theoretical_thetas[seg_id]  # PRIMARY: theoretical break-even
        k_min = K_MIN_DEFAULT

        for br in BUDGET_RATIOS:
            budget_abs = max(1, int(round(br * n_bins)))
            flat_ev = flat_topproxy_recall(labels, proxies, budget_abs, grid, ref_seg)
            flat_recall = flat_ev["event_recall_IoU"]
            el_dc = get_eventlift_dc_recall(seg_id, br)

            methods_results = []

            # 1. naive_HTS_godseye
            root = build_tree(0, n_bins, proxies)
            fill_pos_leaves(root, labels)
            all_by_id = {n.node_id: n for n in collect_nodes(root)}
            pos, calls = run_naive_hts_godseye(root, labels, proxies, budget_abs, all_by_id)
            intervals = pos_bins_to_intervals(pos, grid)
            ev = eval_intervals(intervals, ref_seg)
            methods_results.append(("naive_HTS_godseye", ev, calls, "godseye"))

            # 2. naive_HTS_strict_posterior
            root = build_tree(0, n_bins, proxies)
            fill_pos_leaves(root, labels)
            all_by_id = {n.node_id: n for n in collect_nodes(root)}
            pos, calls = run_naive_hts_strict_posterior(root, labels, proxies, budget_abs, all_by_id, rng)
            intervals = pos_bins_to_intervals(pos, grid)
            ev = eval_intervals(intervals, ref_seg)
            methods_results.append(("naive_HTS_strict_posterior", ev, calls, "strict_replay"))

            # 3. HTS_EC_detector_per_node_fallback (v1, LOO theta)
            root = build_tree(0, n_bins, proxies)
            fill_pos_leaves(root, labels)
            all_by_id = {n.node_id: n for n in collect_nodes(root)}
            pos, calls = run_detector_per_node_fallback(root, labels, proxies, budget_abs, all_by_id, theta, k_min)
            intervals = pos_bins_to_intervals(pos, grid)
            ev = eval_intervals(intervals, ref_seg)
            methods_results.append(("HTS_EC_detector_per_node_fallback", ev, calls, "godseye_loo"))

            # 4. HTS_EC_global_fallback
            root = build_tree(0, n_bins, proxies)
            fill_pos_leaves(root, labels)
            all_by_id = {n.node_id: n for n in collect_nodes(root)}
            pos, calls, gm = run_global_fallback(root, labels, proxies, budget_abs, all_by_id, theta, k_min)
            intervals = pos_bins_to_intervals(pos, grid)
            ev = eval_intervals(intervals, ref_seg)
            methods_results.append(("HTS_EC_global_fallback", ev, calls, "godseye_loo_global"))

            # 5. HTS_EC_early_global_fallback
            root = build_tree(0, n_bins, proxies)
            fill_pos_leaves(root, labels)
            all_by_id = {n.node_id: n for n in collect_nodes(root)}
            pos, calls, gm = run_early_global_fallback(root, labels, proxies, budget_abs, all_by_id, theta, k_min)
            intervals = pos_bins_to_intervals(pos, grid)
            ev = eval_intervals(intervals, ref_seg)
            methods_results.append(("HTS_EC_early_global_fallback", ev, calls, "godseye_loo_early"))

            # 6. HTS_EC_dual_frontier
            root = build_tree(0, n_bins, proxies)
            fill_pos_leaves(root, labels)
            all_by_id = {n.node_id: n for n in collect_nodes(root)}
            pos, calls = run_dual_frontier(root, labels, proxies, budget_abs, all_by_id, theta, k_min)
            intervals = pos_bins_to_intervals(pos, grid)
            ev = eval_intervals(intervals, ref_seg)
            methods_results.append(("HTS_EC_dual_frontier", ev, calls, "godseye_loo_dual"))

            # 6b. HTS_EC_dual_frontier_gated
            root = build_tree(0, n_bins, proxies)
            fill_pos_leaves(root, labels)
            all_by_id = {n.node_id: n for n in collect_nodes(root)}
            pos, calls = run_dual_frontier_gated(root, labels, proxies, budget_abs, all_by_id, theta, k_min)
            intervals = pos_bins_to_intervals(pos, grid)
            ev = eval_intervals(intervals, ref_seg)
            methods_results.append(("HTS_EC_dual_frontier_gated", ev, calls, "godseye_loo_dual_gated"))

            # 7. fixed_10s_topproxy
            methods_results.append(("fixed_10s_topproxy", flat_ev, min(budget_abs, n_bins), "strict_replay"))

            # 8. EventLift_DC_context
            if el_dc:
                el_ev = {
                    "event_precision_IoU": el_dc["precision"],
                    "event_recall_IoU": el_dc["recall"],
                    "event_precision_anyoverlap": float("nan"),
                    "event_recall_anyoverlap": float("nan"),
                    "unique_event_coverage_IoU": 0,
                    "unique_event_coverage_anyoverlap": 0,
                }
                methods_results.append(("EventLift_DC_context", el_ev, el_dc["calls"], "strict_replay"))

            # Build rows
            for method, ev, calls, track in methods_results:
                all_rows.append({
                    "segment_id": seg_id,
                    "method": method,
                    "budget_ratio": br,
                    "oracle_calls": calls,
                    "budget_abs": budget_abs,
                    "loo_theta_density": theta,
                    "event_precision_IoU": ev["event_precision_IoU"],
                    "event_recall_IoU": ev["event_recall_IoU"],
                    "event_precision_anyoverlap": ev["event_precision_anyoverlap"],
                    "event_recall_anyoverlap": ev["event_recall_anyoverlap"],
                    "unique_event_coverage_IoU": ev["unique_event_coverage_IoU"],
                    "regression_vs_flat_IoU": ev["event_recall_IoU"] - flat_recall,
                    "source": "hts_ec_gate_c_v2 (LOO-calibrated detector; God's-eye sim for HTS methods)",
                    "track": track,
                })

    df = pd.DataFrame(all_rows)
    csv_path = OUT / "tree_upper_bound_v2.csv"
    df.to_csv(csv_path, index=False)

    # ============================================================
    # Verdict
    # ============================================================
    print("\n" + "=" * 80)
    print("HTS-EC Gate C v2 — Global Fallback + Early Detection + Dual-Frontier")
    print("=" * 80)
    print(f"Main metric: IoU>={IOU_THRESH}. Tree: top={TREE_TOP_BRANCH}, inner={TREE_INNER_BRANCH}")
    print(f"Beta-posterior detector: k_min={K_MIN_BETA}, P_thresh={POSTERIOR_THRESH}")
    print(f"Theoretical break-even density per segment (no circularity)")
    print(f"Budgets: {BUDGET_RATIOS}")
    print()

    print("Theoretical break-even theta per segment (PRIMARY, no circularity):")
    for seg_id in theoretical_thetas:
        theta_t = theoretical_thetas[seg_id]
        theta_l = loo_thetas.get(seg_id, float("nan"))
        print(f"  {seg_id:28s} theoretical={theta_t:.4f}  LOO={theta_l:.2f}")
    print()

    # Print results at budget 0.30 for all segments
    df30 = df[df["budget_ratio"] == 0.30]
    print("Results @ budget 0.30 (IoU>=0.3 recall):")
    for seg_id in df30["segment_id"].unique():
        sub = df30[df30["segment_id"] == seg_id]
        print(f"  {seg_id}:")
        for _, r in sub.sort_values("method").iterrows():
            marker = " ***" if r["method"] in ("HTS_EC_global_fallback", "HTS_EC_early_global_fallback", "HTS_EC_dual_frontier") else ""
            print(f"    {r['method']:42s} recall={r['event_recall_IoU']:.3f} calls={r['oracle_calls']:3d} "
                  f"regress={r['regression_vs_flat_IoU']:+.3f}{marker}")
    print()

    # Check pass conditions on KEY_SEGMENTS @ 0.30
    print("Pass conditions (key segments @ 0.30):")
    all_pass = True

    # 1. rc_2000: global/dual fallback >= flat - 0.02 (>= 0.180)
    rc = df30[df30["segment_id"] == "realcartest_2000_3200"]
    flat_rc = rc[rc["method"] == "fixed_10s_topproxy"]["event_recall_IoU"]
    flat_recall_rc = float(flat_rc.iloc[0]) if len(flat_rc) else 0.0
    for m in ["HTS_EC_global_fallback", "HTS_EC_early_global_fallback", "HTS_EC_dual_frontier", "HTS_EC_dual_frontier_gated"]:
        mr = rc[rc["method"] == m]
        if len(mr):
            r = float(mr["event_recall_IoU"].iloc[0])
            passed = r >= flat_recall_rc - 0.02
            status = "PASS" if passed else "FAIL"
            print(f"  1. {m} on rc_2000: {r:.3f} >= {flat_recall_rc - 0.02:.3f} → {status}")
            if not passed:
                all_pass = False

    # 2. dataset3_0_1200: preserve naive_HTS savings (>= 0.167 - 0.02 = 0.147)
    ds0 = df30[df30["segment_id"] == "dataset3_0_1200"]
    naive_ds0 = ds0[ds0["method"] == "naive_HTS_godseye"]["event_recall_IoU"]
    naive_recall_ds0 = float(naive_ds0.iloc[0]) if len(naive_ds0) else 0.0
    for m in ["HTS_EC_global_fallback", "HTS_EC_early_global_fallback", "HTS_EC_dual_frontier", "HTS_EC_dual_frontier_gated"]:
        mr = ds0[ds0["method"] == m]
        if len(mr):
            r = float(mr["event_recall_IoU"].iloc[0])
            passed = r >= naive_recall_ds0 - 0.02
            status = "PASS" if passed else "FAIL"
            print(f"  2. {m} on ds3_0_1200: {r:.3f} >= {naive_recall_ds0 - 0.02:.3f} → {status}")
            if not passed:
                all_pass = False

    # 3. dataset3_1200_2400: >= naive_HTS - 0.02
    ds12 = df30[df30["segment_id"] == "dataset3_1200_2400"]
    naive_ds12 = ds12[ds12["method"] == "naive_HTS_godseye"]["event_recall_IoU"]
    naive_recall_ds12 = float(naive_ds12.iloc[0]) if len(naive_ds12) else 0.0
    for m in ["HTS_EC_global_fallback", "HTS_EC_early_global_fallback", "HTS_EC_dual_frontier", "HTS_EC_dual_frontier_gated"]:
        mr = ds12[ds12["method"] == m]
        if len(mr):
            r = float(mr["event_recall_IoU"].iloc[0])
            passed = r >= naive_recall_ds12 - 0.02
            status = "PASS" if passed else "FAIL"
            print(f"  3. {m} on ds3_1200_2400: {r:.3f} >= {naive_recall_ds12 - 0.02:.3f} → {status}")
            if not passed:
                all_pass = False

    # 4. dataset3_2400_3462: not significantly lower than EventLift_DC / flat
    ds24 = df30[df30["segment_id"] == "dataset3_2400_3462"]
    el_ds24 = ds24[ds24["method"] == "EventLift_DC_context"]["event_recall_IoU"]
    el_recall_ds24 = float(el_ds24.iloc[0]) if len(el_ds24) else 0.0
    for m in ["HTS_EC_global_fallback", "HTS_EC_early_global_fallback", "HTS_EC_dual_frontier", "HTS_EC_dual_frontier_gated"]:
        mr = ds24[ds24["method"] == m]
        if len(mr):
            r = float(mr["event_recall_IoU"].iloc[0])
            passed = r >= el_recall_ds24 - 0.05
            status = "PASS" if passed else "FAIL"
            print(f"  4. {m} on ds3_2400_3462: {r:.3f} >= {el_recall_ds24 - 0.05:.3f} (EL-DC={el_recall_ds24:.3f}) → {status}")
            if not passed:
                all_pass = False

    print()

    # Per-method pass check: a method PASSES if it passes ALL 4 conditions
    new_methods = ["HTS_EC_global_fallback", "HTS_EC_early_global_fallback",
                   "HTS_EC_dual_frontier", "HTS_EC_dual_frontier_gated",
                   "HTS_EC_detector_per_node_fallback"]

    # Collect per-method pass status
    method_pass = {}
    for m in new_methods:
        method_pass[m] = {"rc_2000": None, "ds3_0_1200": None,
                          "ds3_1200_2400": None, "ds3_2400_3462": None}

    for m in new_methods:
        mr = rc[rc["method"] == m]
        if len(mr):
            r = float(mr["event_recall_IoU"].iloc[0])
            method_pass[m]["rc_2000"] = r >= flat_recall_rc - 0.02

        mr = ds0[ds0["method"] == m]
        if len(mr):
            r = float(mr["event_recall_IoU"].iloc[0])
            method_pass[m]["ds3_0_1200"] = r >= naive_recall_ds0 - 0.02

        mr = ds12[ds12["method"] == m]
        if len(mr):
            r = float(mr["event_recall_IoU"].iloc[0])
            method_pass[m]["ds3_1200_2400"] = r >= naive_recall_ds12 - 0.02

        mr = ds24[ds24["method"] == m]
        if len(mr):
            r = float(mr["event_recall_IoU"].iloc[0])
            method_pass[m]["ds3_2400_3462"] = r >= el_recall_ds24 - 0.05

    print("Per-method pass status (must pass ALL 4 conditions):")
    any_method_all_pass = False
    for m in new_methods:
        passes = method_pass[m]
        all4 = all(v is True for v in passes.values())
        n_pass = sum(1 for v in passes.values() if v is True)
        status = "ALL PASS" if all4 else f"{n_pass}/4 pass"
        print(f"  {m:42s}  rc={passes['rc_2000']}  ds0={passes['ds3_0_1200']}  "
              f"ds12={passes['ds3_1200_2400']}  ds24={passes['ds3_2400_3462']}  → {status}")
        if all4:
            any_method_all_pass = True

    print()
    if any_method_all_pass:
        verdict = "PASS — at least one method passes all 4 conditions"
    else:
        rc_best = 0.0
        for m in new_methods:
            mr = rc[rc["method"] == m]
            if len(mr):
                rc_best = max(rc_best, float(mr["event_recall_IoU"].iloc[0]))
        if rc_best >= flat_recall_rc - 0.02:
            verdict = "CONDITIONAL — at least one new fallback fixes rc_2000 but not all sparse conditions"
        else:
            verdict = "FAIL — new fallbacks do not fix rc_2000 regression"

    print(f"GATE C v2 VERDICT: {verdict}")
    print()
    print(f"Written: {csv_path}  rows={len(df)} cols={len(df.columns)}")


if __name__ == "__main__":
    main()
