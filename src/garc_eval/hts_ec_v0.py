"""HTS-EC v0 — Saturation-Aware Gated Dual-Frontier (strict-replay, no certify).

This module implements the HTS-EC-v0 algorithm validated in Gate C v2
(`outputs/hts_ec_feasibility_v1/tree_upper_bound_v2.csv`), adapted from
God's-eye simulation to strict-replay (posterior-based drill/prune, no
full-label access online).

Key design (per `HTS_EC_DELTA_AND_FEASIBILITY.md` §12):
  - Tree: top_branch=4, inner_branch=2 (HTS-EC v0 candidate structure)
  - Posterior-based drill/prune (NOT God's-eye): drill if P(pos)>thresh after
    >=2 probes; prune if P(pos)<thresh after >=2 probes
  - Theoretical break-even density d* (no labels, no circularity): computed
    from tree structure alone via expected_drill_cost vs flat_scan_cost
  - Beta-posterior saturation detector: P(density >= d* | Beta(1+n+,1+n-))
    > posterior_thresh, with k_min minimum probes
  - Gated dual frontier: tree-only until detector triggers on a node, then
    that node's unqueried bins are added to a competing fine frontier.
    Each step: best tree node (UCB) vs best fine bin (proxy) compete.
    On sparse segments, detector never triggers -> pure tree -> preserves
    savings. On dense segments, detector triggers -> fine bins compete.

Hard constraints (per AGENTS.md):
  - No event_id online. Use AlignedOracle from run_aligned_baselines_v1.
  - oracle_calls_total <= budget_abs asserted.
  - No certify, no suppress, no residual stop, no temporal expansion.
  - Returned intervals = positive bins grouped by temporal adjacency.
  - No safe-stopping / formal-guarantee / statistical-bound claim.

Variants (configurable via HtsEcV0Config):
  - HTS-EC-safe: posterior_thresh=0.85, k_min=6 (conservative, rarely triggers)
  - HTS-EC-gated-dual: posterior_thresh=0.75, k_min=5 (default, balanced)
  - HTS-EC-gated-dual-conservative: posterior_thresh=0.85, k_min=5,
    tree_preference_bonus higher (avoid over-triggering on weak-proxy sparse)

Phase 2A node-level stagnation + StagRepMix (all behind flags, off by default):
  - use_node_stagnation: shadow predicate + probe_log/scheduler_decision_log
    (does NOT change the call sequence; G0 invariance).
  - use_stag_repmix: eligible stagnant nodes receive bounded diverse probes
    (max_diverse_probe_share + max_diverse_probes_per_node). Separate from the
    legacy global escape_hatch (kept off by default).
  - Invariant enforced at init when either flag is on:
    posterior_prune_min_probes >= k_stag + max_diverse_probes_per_node
    (so a stagnant node has a diversification window before pruning).
"""
import math
import hashlib
from dataclasses import dataclass, field
from typing import List, Optional, Set, Dict, Tuple
import numpy as np

try:
    from scipy.stats import beta as beta_dist
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False
    # Fallback: incomplete beta via normal approximation (less accurate)
    def _beta_cdf(x, a, b):
        from math import lgamma, log
        if x <= 0:
            return 0.0
        if x >= 1:
            return 1.0
        # Regularized incomplete beta via series expansion (Lentz)
        # This is a simplified version; for our use (threshold comparison),
        # we can use the normal approximation to Beta(mean, var)
        mean = a / (a + b)
        var = a * b / ((a + b) ** 2 * (a + b + 1))
        if var <= 0:
            return 1.0 if x >= mean else 0.0
        std = math.sqrt(var)
        z = (x - mean) / std
        # Normal CDF
        return 0.5 * (1 + math.erf(z / math.sqrt(2)))


EPS = 1e-6


def _beta_sf(x, a, b):
    """Survival function P(X > x) for Beta(a, b)."""
    if _HAS_SCIPY:
        return float(beta_dist.sf(x, a, b))
    else:
        return 1.0 - _beta_cdf(x, a, b)


@dataclass
class HtsEcV0Config:
    """Configuration for HTS-EC-v0 strict-replay run."""
    # Tree structure
    top_branch: int = 4
    inner_branch: int = 2

    # Beta-UCB params (for tree frontier scoring)
    k0_prior: float = 3.0
    ucb_c: float = 0.5

    # Posterior-based drill/prune (replaces God's-eye)
    posterior_drill_thresh: float = 0.5   # drill if P(pos) > this after >=2 probes
    posterior_prune_thresh: float = 0.05  # very conservative prune — only prune if very confident negative
    posterior_min_probes: int = 2         # need 2 probes before drill/prune decision
    posterior_prune_min_probes: int = 6   # need 6 probes before pruning (avoid early root prune)

    # Saturation detector
    detector_posterior_thresh: float = 0.75  # P(d >= d*) > this -> saturated
    detector_k_min: int = 5
    detector_min_leaves: int = 4

    # Dual frontier arbitration
    tree_preference_bonus: float = 0.1  # bonus added to tree UCB in competition
    fine_covered_penalty: float = 0.0   # penalty for bins near already-found events
    dual_prune_thresh: float = 0.15     # prune tree node if P(pos) < this after k_min

    # Phase 2A improvements
    # ELFine: EventLift-style fine frontier utility (proxy + diversity + distance)
    use_elfine: bool = False            # if True, use ELFine utility for fine bin selection
    elfine_diversity_weight: float = 0.3  # weight for temporal diversity in fine selection
    elfine_distance_weight: float = 0.2   # weight for distance from covered intervals
    elfine_uncertainty_weight: float = 0.15  # weight for exploration bonus

    # RepMix: mixed representative bin selection for tree probes
    use_repmix: bool = False            # if True, alternate selection strategies
    repmix_first_k: int = 4             # first k probes use mixed strategy

    # Tree escape hatch: low-frequency global diverse probe
    use_escape_hatch: bool = False
    escape_hatch_budget_frac: float = 0.05  # max 5% budget for escape probes
    escape_hatch_stagnation_window: int = 10  # trigger after N steps with no new positive

    # Proxy-mass drill: drill if proxy_mass is high even if posterior is uncertain
    use_proxy_mass_drill: bool = False
    proxy_mass_drill_frac: float = 0.6  # drill if node's proxy mass > this fraction of max

    # Node-level stagnation predicate + StagRepMix (Phase 2A, behind flags)
    # Neither flag changes HTS-EC-safe behavior unless explicitly enabled.
    use_node_stagnation: bool = False  # shadow predicate + logging (no behavior change)
    use_stag_repmix: bool = False      # StagRepMix actor (diverse probe on stagnant nodes)
    k_stag: int = 4                    # min probes w/ 0 positive before node is "stagnant"
    stag_drill_thresh: float = 0.5     # eligible only if posterior_mean(node) < this (not drilling)
    max_diverse_probe_share: float = 0.15   # global cap on stagmix probes (fraction of budget)
    max_diverse_probes_per_node: int = 2    # max stagmix probes per node
    min_unqueried_for_stag: int = 2    # min unqueried leaves for a node to be eligible
    stagmix_priority_policy: str = "inf_when_eligible"  # force eligible stagnant node
    stagmix_strategy_set: str = "legacy"  # "legacy" | "gap_flank_v2"
    stagmix_gap_flank_radius: int = 3  # ±r bins window for gap_flank_v2 probe

    # Method variant name
    method_id: str = "HTS-EC-gated-dual"


class TreeNode:
    """Multi-resolution temporal tree node."""
    __slots__ = ("node_id", "parent_id", "depth", "lo", "hi", "children",
                 "is_leaf", "n_leaves", "alpha", "beta", "n_probe",
                 "n_pos_probe", "n_neg_probe", "mean_proxy",
                 "in_tree_frontier", "expanded", "pruned", "saturated",
                 "evidence_bins")

    def __init__(self, node_id, parent_id, depth, lo, hi, mean_proxy=0.0,
                 k0_prior=3.0):
        self.node_id = node_id
        self.parent_id = parent_id
        self.depth = depth
        self.lo = lo  # inclusive bin index
        self.hi = hi  # exclusive
        self.children = []
        self.is_leaf = (hi - lo) <= 1
        self.n_leaves = hi - lo
        self.alpha = 1.0 + k0_prior * mean_proxy
        self.beta = 1.0 + k0_prior * (1.0 - mean_proxy)
        self.n_probe = 0
        self.n_pos_probe = 0
        self.n_neg_probe = 0
        self.mean_proxy = mean_proxy
        self.in_tree_frontier = False
        self.expanded = False
        self.pruned = False
        self.saturated = False
        # Per-node set of bin indices whose label has already been folded into
        # this node's posterior. Guards against double-counting even if a future
        # cache-propagation path re-feeds the same label.
        self.evidence_bins = set()


def build_tree(lo, hi, proxies, config, depth=0, parent_id=None,
               counter=None, top_level=True):
    """Build multi-resolution tree. top_branch at root, inner_branch below."""
    if counter is None:
        counter = [0]
    node_id = f"d{depth}_n{counter[0]}"
    counter[0] += 1
    mean_proxy = float(np.mean(proxies[lo:hi])) if hi > lo else 0.0
    node = TreeNode(node_id, parent_id, depth, lo, hi, mean_proxy, config.k0_prior)
    width = hi - lo
    if width <= 1:
        node.is_leaf = True
        return node
    b = config.top_branch if top_level else config.inner_branch
    if width <= b:
        for i in range(width):
            child = build_tree(lo + i, lo + i + 1, proxies, config,
                              depth + 1, node_id, counter, False)
            node.children.append(child)
        return node
    sub_width = width / b
    for i in range(b):
        cs = lo + int(round(i * sub_width))
        ce = lo + int(round((i + 1) * sub_width))
        cs = max(lo, min(hi, cs))
        ce = max(cs + 1, min(hi, ce))
        child = build_tree(cs, ce, proxies, config,
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


def find_leaf_node(bin_idx, root):
    if root.is_leaf:
        return root
    for c in root.children:
        if c.lo <= bin_idx < c.hi:
            return find_leaf_node(bin_idx, c)
    return root


def expected_drill_cost(node, d):
    """Expected God's-eye drill cost at bin-density d (Bernoulli assumption).
    No labels used — purely structural + density assumption."""
    if node.is_leaf:
        return 1.0
    p_pos = 1.0 - (1.0 - d) ** node.n_leaves
    return 1.0 + p_pos * sum(expected_drill_cost(c, d) for c in node.children)


def find_break_even_density(root, n_bins, tol=1e-4):
    """Find d* where expected_drill_cost(root, d*) = n_bins (flat cost).
    Binary search over d in [0, 1]. No labels, no circularity."""
    def cost_at(d):
        return expected_drill_cost(root, d)
    lo, hi = 0.001, 0.999
    for _ in range(50):
        mid = (lo + hi) / 2.0
        c = cost_at(mid)
        if c < n_bins:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def posterior_mean(node):
    return node.alpha / (node.alpha + node.beta + EPS)


def ucb_score(node, t, config):
    mean = posterior_mean(node)
    exploration = config.ucb_c * math.sqrt(
        math.log(max(t, 1) + 1) / (node.n_probe + 1 + EPS))
    return mean + exploration


def select_representative_bin(node, proxies, queried_bins, rng=None,
                               config=None, t_start_arr=None, n_probes_in_node=0):
    """Select representative bin within a node.

    If config.use_repmix and n_probes_in_node < config.repmix_first_k:
      Alternate strategies: probe 0 = top proxy, 1 = temporal center,
      2 = low/medium proxy, 3 = farthest-unqueried.
    Else:
      Highest proxy among unqueried (default).
    """
    bins_in_node = list(range(node.lo, node.hi))
    candidates = [b for b in bins_in_node if b not in queried_bins]
    # S-1 invariant: never (re-)query a bin that has already been queried.
    # If every leaf in the node has been paid for, return None and let the
    # caller drop the node from the frontier (it has no information to add).
    if not candidates:
        return None

    use_repmix = (config is not None and config.use_repmix and
                  n_probes_in_node < config.repmix_first_k)

    if use_repmix:
        strategy = n_probes_in_node % 4
        if strategy == 0:
            # Top proxy
            candidates.sort(key=lambda b: -proxies[b])
        elif strategy == 1:
            # Temporal center (median bin in node)
            candidates.sort(key=lambda b: abs(b - (node.lo + node.hi) / 2.0))
        elif strategy == 2:
            # Low/medium proxy (bottom half by proxy, pick highest of those)
            candidates.sort(key=lambda b: proxies[b])
            half = max(1, len(candidates) // 2)
            candidates = candidates[:half]
            candidates.sort(key=lambda b: -proxies[b])
        else:
            # Farthest from already-queried bins
            if queried_bins:
                candidates.sort(key=lambda b: -min(abs(b - q) for q in queried_bins))
            else:
                candidates.sort(key=lambda b: -proxies[b])
        return candidates[0]

    # Default: highest proxy
    if rng is not None:
        candidates.sort(key=lambda b: (-proxies[b], rng.random()))
    else:
        candidates.sort(key=lambda b: -proxies[b])
    return candidates[0]


def compute_elfine_utility(bin_idx, proxies, queried_bins, pos_bins,
                            t_start_arr, t_end_arr, config, n_bins):
    """EventLift-style fine frontier utility.

    Combines:
      - proxy score (normalized)
      - temporal diversity (distance from already-queried bins)
      - distance from covered intervals (positive bins)
      - exploration bonus (unqueried neighbors)
    """
    proxy_val = proxies[bin_idx]

    # Temporal diversity: distance from nearest queried bin
    if queried_bins:
        min_dist_to_queried = min(abs(bin_idx - q) for q in queried_bins)
        diversity = min(1.0, min_dist_to_queried / max(1, n_bins // 10))
    else:
        diversity = 1.0

    # Distance from covered (positive) bins — prefer bins far from found events
    if pos_bins:
        min_dist_to_pos = min(abs(bin_idx - p) for p in pos_bins)
        distance_score = min(1.0, min_dist_to_pos / max(1, n_bins // 6))
    else:
        distance_score = 1.0

    # Uncertainty: unqueried neighbors count
    neighbors = [bin_idx - 1, bin_idx + 1]
    unqueried_neighbors = sum(1 for nb in neighbors if 0 <= nb < n_bins and nb not in queried_bins)
    uncertainty = unqueried_neighbors / 2.0

    utility = (proxy_val
               + config.elfine_diversity_weight * diversity
               + config.elfine_distance_weight * distance_score
               + config.elfine_uncertainty_weight * uncertainty)
    return utility


def select_fine_bin_elfine(fine_frontier, proxies, queried_bins, pos_bins,
                            t_start_arr, t_end_arr, config, n_bins):
    """Select best fine bin using EventLift-style utility."""
    if not fine_frontier:
        return None
    best_bin = None
    best_util = -float("inf")
    for b in fine_frontier:
        if b in queried_bins:
            continue
        u = compute_elfine_utility(b, proxies, queried_bins, pos_bins,
                                    t_start_arr, t_end_arr, config, n_bins)
        if u > best_util:
            best_util = u
            best_bin = b
    return best_bin


def detector_check(node, d_star, config):
    """Beta-posterior saturation detector.
    Triggers when P(density >= d* | Beta(1+n+, 1+n-)) > posterior_thresh."""
    if node.n_probe < config.detector_k_min:
        return False, 0.0
    if node.n_leaves < config.detector_min_leaves:
        return False, 0.0
    a = 1 + node.n_pos_probe
    b = 1 + node.n_neg_probe
    p_density_above = _beta_sf(d_star, a, b)
    return p_density_above > config.detector_posterior_thresh, p_density_above


def update_ancestors(node, all_by_id, y, bin_idx):
    """Fold one oracle label for `bin_idx` into the posterior of `node` and all
    of its ancestors. Uses `node.evidence_bins` to drop duplicates, so a cached
    label re-fed via cache propagation cannot inflate the posterior."""
    cur = node
    while cur is not None:
        if bin_idx not in cur.evidence_bins:
            cur.evidence_bins.add(bin_idx)
            cur.n_probe += 1
            if y == 1:
                cur.n_pos_probe += 1
                cur.alpha += 1
            else:
                cur.n_neg_probe += 1
                cur.beta += 1
        cur = all_by_id.get(cur.parent_id) if cur.parent_id else None


# ---------------------------------------------------------------------------
# Node-level stagnation predicate + StagRepMix helpers (Phase 2A, behind flags)
# ---------------------------------------------------------------------------

_STAG_CYCLE = ("temporal_center", "farthest_unqueried", "median_proxy",
               "low_proxy_diverse")

# -- gap_flank_v2 cycle (Phase 2A-RP strategy shadow win) -------------------
_GAP_FLANK_V2_CYCLE = ("largest_gap_local_proxy_flank",
                       "second_gap_local_proxy_flank",
                       "largest_unqueried_gap_midpoint")  # fallback


def _unqueried_gaps(node, queried):
    """Return sorted list of (start, end_excl, length) for contiguous unqueried
    runs inside [node.lo, node.hi). Sorted by (-length, start)."""
    gaps = []
    i = node.lo
    while i < node.hi:
        if i not in queried:
            j = i
            while j < node.hi and j not in queried:
                j += 1
            gaps.append((i, j, j - i))
            i = j
        else:
            i += 1
    gaps.sort(key=lambda g: (-g[2], g[0]))
    return gaps


def _gap_mean_proxy(gap, proxies):
    lo, hi, _ = gap
    return float(np.mean([proxies[b] for b in range(lo, hi)]))


def _temporal_center(node):
    return (node.lo + node.hi - 1) / 2.0


def _best_largest_gap(gaps, node, proxies):
    """Pick the largest gap. Tie-break: closer to temporal centre, then higher
    mean proxy, then earlier start. Returns (lo, hi, length)."""
    if not gaps:
        return None
    top_len = gaps[0][2]
    tied = [g for g in gaps if g[2] == top_len]
    tied.sort(key=lambda g: (
        abs((g[0] + g[1] - 1) / 2.0 - _temporal_center(node)),
        -_gap_mean_proxy(g, proxies),
        g[0]))
    return tied[0]


def _gap_flank_v2_pick(node, queried, proxies, config, excluded_bins=frozenset()):
    """Single gap_flank_v2 representative selection.

    Finds the largest unqueried gap in the node, uses its midpoint as an
    *anchor*, then picks the highest-proxy unqueried bin within ±r bins of
    the anchor that is NOT the anchor itself (the shadow sweep showed that
    the gap midpoint alone yielded 0/30 hits while the local flank hit
    11/30). If the ±r window is empty the search window is expanded up to
    the gap boundary. Falls back to the anchor midpoint only as last resort.

    Loops through the gap list in tie-break order (same ordering as
    `_best_largest_gap`), so if a node has multiple equal-length longest
    gaps the cycle naturally probes different gaps on successive calls to
    this function (because position 0's excluded_bins prunes the first gap
    for position 1). The cycle therefore obtains cross-gap coverage within
    the same node without needing a hashed cycle offset.

    Returns (bin_idx, strategy_name, gap_lo, gap_hi, gap_len, anchor_mid).
    """
    r = config.stagmix_gap_flank_radius
    unq_set = {b for b in range(node.lo, node.hi)
               if b not in queried and b not in excluded_bins}
    if not unq_set:
        return None, None, None, None, None, None

    gaps = _unqueried_gaps(node, queried | set(excluded_bins))
    best = _best_largest_gap(gaps, node, proxies)
    if best is None:
        return None, None, None, None, None, None

    gap_lo, gap_hi, gap_len = best
    anchor_mid = gap_lo + (gap_len - 1) // 2

    candidates = []
    for off in range(-r, r + 1):
        b = anchor_mid + off
        if b == anchor_mid:
            continue
        if gap_lo <= b < gap_hi and b in unq_set:
            candidates.append(b)
    if not candidates:
        candidates = [b for b in range(gap_lo, gap_hi) if b in unq_set and b != anchor_mid]
    if not candidates:
        # Absolute last resort: anchor midpoint itself (gap_mid fallback).
        if anchor_mid in unq_set:
            candidates = [anchor_mid]
    if not candidates:
        return None, None, None, None, None, None

    candidates.sort(key=lambda b: (
        -proxies[b],
        b))
    return (candidates[0], "largest_gap_local_proxy_flank",
            int(gap_lo), int(gap_hi), int(gap_len), int(anchor_mid))


def pick_stag_bin(node, queried, proxies, config, diverse_count_node,
                  segment_id, seed):
    """Pick the diverse representative bin for a stagnant node.

    Two strategy sets:
      - "legacy"          : deterministic per-node rotation across the
                            original _STAG_CYCLE (preserved for backward
                            comparability / ablated group).
      - "gap_flank_v2"    : gap-bracket-v2 cycle — twice local flank
                            around the largest-gap midpoint, then gap_mid
                            fallback (position 0 / 1 / 2+). The per-node
                            diverse_count drives which position is taken
                            so the existing max_diverse_probes_per_node=2
                            cap naturally gives position 0 + position 1.

    Returns (bin_idx, strategy_name, strategy_position) as before.
    """
    unq = _unqueried_in_node(node, queried)
    if not unq:
        return None, None, None
    pos = diverse_count_node.get(node.node_id, 0)

    ss = config.stagmix_strategy_set
    if ss == "gap_flank_v2":
        if pos == 0:
            # Position 0: largest_gap_local_proxy_flank.
            b, strat, glo, ghi, glen, anchor = _gap_flank_v2_pick(
                node, queried, proxies, config)
            if b is not None:
                # Store gap anchor info so position 1 can exclude the gap.
                return b, strat, pos
            # Fall through to legacy / generic gap_mid.
            b2 = _gap_flank_v2_pick(
                node, queried, proxies, config,
                excluded_bins=frozenset())
            return (b2[0] if b2[0] is not None else None,
                    b2[1] if b2[0] is not None else None, pos)
        elif pos == 1:
            # Position 1: second_gap_local_proxy_flank.
            # Re-run position-0 to find the bin it would have picked,
            # then exclude that bin so we probe a DIFFERENT leaf.
            p0_result = _gap_flank_v2_pick(node, queried, proxies, config)
            exclude = frozenset([p0_result[0]]) if p0_result[0] is not None else frozenset()
            b, strat, glo, ghi, glen, anchor = _gap_flank_v2_pick(
                node, queried, proxies, config, excluded_bins=exclude)
            if b is not None:
                return b, strat, pos
            exclude_all = frozenset()
            b3, s3, _, _, _, _ = _gap_flank_v2_pick(
                node, queried, proxies, config,
                excluded_bins=exclude_all)
            return b3, s3, pos
        else:
            # Position 2+: largest_unqueried_gap_midpoint fallback.
            gaps = _unqueried_gaps(node, queried)
            if gaps:
                best = _best_largest_gap(gaps, node, proxies)
                if best:
                    gap_lo, _, gap_len = best
                    mid = gap_lo + (gap_len - 1) // 2
                    return mid, "largest_unqueried_gap_midpoint", pos
            return None, None, None

    # Legacy fallthrough (unchanged).
    offset = _stable_hash(segment_id, seed, node.node_id) % len(_STAG_CYCLE)
    cycle = _rotate(_STAG_CYCLE, offset)
    strategy = cycle[pos % len(cycle)]
    if strategy == "temporal_center":
        b = unq[len(unq) // 2]
    elif strategy == "farthest_unqueried":
        if queried:
            b = max(unq, key=lambda x: min(abs(x - q) for q in queried))
        else:
            b = unq[len(unq) // 2]
    elif strategy == "median_proxy":
        unq_sorted = sorted(unq, key=lambda x: proxies[x])
        b = unq_sorted[len(unq_sorted) // 2]
    else:  # low_proxy_diverse
        b = min(unq, key=lambda x: proxies[x])
    return b, strategy, pos


def _stable_hash(*parts) -> int:
    """Deterministic, seed/segment/node-stable int hash (no RNG)."""
    h = hashlib.md5("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()
    return int(h, 16)


def _rotate(seq, offset):
    n = len(seq)
    offset %= n
    return seq[offset:] + seq[:offset]


def _unqueried_in_node(node, queried):
    return [b for b in range(node.lo, node.hi) if b not in queried]


def _frontier_node_of(bin_idx, root, all_by_id):
    """Lowest ancestor (incl. self) that is still in the tree frontier."""
    cur = find_leaf_node(bin_idx, root)
    while cur is not None:
        if cur.in_tree_frontier or cur is root:
            return cur
        cur = all_by_id.get(cur.parent_id) if cur.parent_id else None
    return root


def stag_eligible(node, config, diverse_count_node, diverse_count_global,
                  budget_abs, unqueried_count, budget_remaining):
    """Per-node stagnation predicate (§9.3 / Phase 2A spec).

    A node is eligible for a StagRepMix diverse probe when it has accumulated
    k_stag probes with zero positives, is not drilling, not yet expanded, still
    has unqueried leaves, and the per-node + global diverse budgets remain.
    """
    return (config.use_node_stagnation
            and node.n_probe >= config.k_stag
            and node.n_pos_probe == 0
            and posterior_mean(node) < config.stag_drill_thresh
            and not node.expanded
            and unqueried_count >= config.min_unqueried_for_stag
            and diverse_count_node.get(node.node_id, 0) < config.max_diverse_probes_per_node
            and diverse_count_global < int(config.max_diverse_probe_share * budget_abs)
            and budget_remaining >= 1)


def _append_probe_log(probe_log, bin_idx, source, strategy, strat_pos, y,
                      root, all_by_id, proxies, queried, d_star,
                      eligible_set, fine_frontier, config, t, seed,
                      run_id, segment_id, budget_config):
    """Append one probe_log row (one oracle call). Offline-only fields are
    left as None for later join with reference/event labels."""
    leaf = find_leaf_node(bin_idx, root)
    fn = _frontier_node_of(bin_idx, root, all_by_id)
    unq = _unqueried_in_node(fn, queried)
    prune_min = max(config.detector_k_min, config.posterior_prune_min_probes)
    would_prune = (fn.n_probe >= prune_min
                   and posterior_mean(fn) < config.dual_prune_thresh)
    node_bins = list(range(fn.lo, fn.hi))
    proxy_rank = 0
    if node_bins:
        order = sorted(node_bins, key=lambda b: -proxies[b])
        proxy_rank = order.index(bin_idx) if bin_idx in order else 0
    probe_log.append({
        "run_id": run_id,
        "segment_id": segment_id,
        "method": config.method_id,
        "budget_config": budget_config,
        "seed": seed,
        "global_step": t,
        "bin_idx": bin_idx,
        "node_id": fn.node_id,
        "frontier_source": source,
        "stagmix_strategy": strategy,
        "stagmix_strategy_position": strat_pos,
        "proxy_score": float(proxies[bin_idx]),
        "proxy_rank_in_node": proxy_rank,
        "oracle_label": int(y),
        "node_n_probe_before": fn.n_probe,
        "node_n_pos_before": fn.n_pos_probe,
        "node_n_neg_before": fn.n_neg_probe,
        "posterior_mean_before": posterior_mean(fn),
        "saturation_prob_before": _beta_sf(d_star, 1 + fn.n_pos_probe,
                                           1 + fn.n_neg_probe),
        "node_stagnant_before": fn.node_id in eligible_set,
        "node_saturated_before": fn.saturated,
        "node_fine_active_before": bin_idx in fine_frontier,
        "prune_condition_before": bool(would_prune),
        "would_prune_without_stagmix": bool(would_prune),
        "node_n_leaves": fn.n_leaves,
        "node_unqueried_leaves": len(unq),
        # gap_flank_v2 logging (offline-interpretable; populated only when
        # strategy_set == "gap_flank_v2" and source == "stagmix").
        "stagmix_strategy_set": config.stagmix_strategy_set,
        "stagmix_gap_lo": None,
        "stagmix_gap_hi": None,
        "stagmix_gap_len": None,
        "stagmix_anchor_mid": None,
        "stagmix_flank_radius": None,
        "stagmix_candidate_rank_reason": "",
        "true_label_offline": None,
        "true_event_id_offline": None,
    })
    # Populate gap_flank_v2 fields after append to avoid mutation.
    if (config.stagmix_strategy_set == "gap_flank_v2"
            and source == "stagmix"):
        gaps = _unqueried_gaps(fn, queried)
        if gaps:
            best = _best_largest_gap(gaps, fn, proxies)
            if best:
                r = config.stagmix_gap_flank_radius
                mid = best[0] + (best[2] - 1) // 2
                probe_log[-1]["stagmix_gap_lo"] = int(best[0])
                probe_log[-1]["stagmix_gap_hi"] = int(best[1])
                probe_log[-1]["stagmix_gap_len"] = int(best[2])
                probe_log[-1]["stagmix_anchor_mid"] = int(mid)
                probe_log[-1]["stagmix_flank_radius"] = int(r)
                reason = (f"gap=[{best[0]},{best[1]}) len={best[2]} "
                          f"anchor={mid} r={r} "
                          f"bin={bin_idx} proxy={proxies[bin_idx]:.4f}")
                probe_log[-1]["stagmix_candidate_rank_reason"] = reason


class HtsEcV0Runner:
    """HTS-EC-v0 strict-replay runner with gated dual frontier."""

    def __init__(self, config: HtsEcV0Config):
        self.config = config
        # Invariant (per Phase 2A spec): a node must reach k_stag stale probes AND
        # still have room for max_diverse_probes_per_node diverse probes before it
        # can be pruned. Enforced only when the stagnation feature is active so it
        # cannot surprise existing variant configs.
        if config.use_node_stagnation or config.use_stag_repmix:
            assert config.posterior_prune_min_probes >= (
                config.k_stag + config.max_diverse_probes_per_node
            ), (
                "invariant violated: posterior_prune_min_probes "
                f"({config.posterior_prune_min_probes}) must be >= k_stag "
                f"({config.k_stag}) + max_diverse_probes_per_node "
                f"({config.max_diverse_probes_per_node}) so a stagnant node has a "
                "diversification window before pruning."
            )

    def _paid_query(self, bin_idx, oracle, queried_bins, label_cache,
                    action_type, source_action, node_id=None, notes=""):
        """Single funnel for paid oracle queries. Enforces S-1:
        no duplicate paid query of the same bin within one run.

        All paths that need an oracle label for some bin MUST route through
        this helper so the cache + assert stay glob MT consistent. A future
        cache-propagation path that reuses an already-paid label MUST go
        through `label_cache` instead of calling this (or call this with a
        separate `cache_propagation` source_action that skips the assert).
        """
        if bin_idx in queried_bins:
            raise AssertionError(
                f"duplicate paid query: bin={bin_idx}, source={source_action}, "
                f"action={action_type}, node={node_id}, notes={notes}. "
                f"Label already cached as {label_cache.get(bin_idx)}. "
                f"This is a S-1 invariant violation: use label_cache for "
                f"propagation, or filter candidates by queried_bins before "
                f"calling this helper.")
        result = oracle.query_unit(
            bin_idx, action_type=action_type, source_action=source_action,
            notes=notes)
        y = 1 if result == "positive" else 0
        queried_bins.add(bin_idx)
        label_cache[bin_idx] = bool(y)
        return y, result

    def run(self, grid, oracle, budget_abs, seed=0,
            run_id="", segment_id="", budget_config=""):
        """Run HTS-EC-v0 on a segment grid.

        Args:
            grid: DataFrame with bin_idx, local_t_start, local_t_end,
                  is_positive, prior_score_max columns (sorted by bin_idx).
            oracle: AlignedOracle instance (from run_aligned_baselines_v1).
            budget_abs: absolute oracle budget.
            seed: random seed for tie-breaking.

        Returns:
            dict with: pos_bins (set), calls (int), intervals (list),
                      diagnostics (dict), global_mode (bool)
        """
        config = self.config
        grid_sorted = grid.sort_values("bin_idx").reset_index(drop=True)
        n_bins = len(grid_sorted)
        proxies = grid_sorted["prior_score_max"].values
        labels = grid_sorted["is_positive"].astype(int).values
        t_start_arr = grid_sorted["local_t_start"].values
        t_end_arr = grid_sorted["local_t_end"].values

        rng = np.random.RandomState(seed)

        # Build tree
        root = build_tree(0, n_bins, proxies, config)
        all_nodes = collect_nodes(root)
        all_by_id = {n.node_id: n for n in all_nodes}

        # Compute theoretical break-even density d* (no labels)
        d_star = find_break_even_density(root, n_bins)

        # Compute max proxy mass for proxy-mass drill (if enabled)
        max_proxy_mass = float(proxies.max()) if n_bins > 0 else 1.0

        # Initialize frontier
        tree_frontier = [root]
        root.in_tree_frontier = True
        fine_frontier = []  # bins activated only when detector triggers

        queried = set()
        # S-1: label cache keyed by bin_idx; populated by _paid_query so that
        # cache-propagation paths (if added later) can read a label without
        # re-paying for it.
        label_cache = {}
        pos_bins = set()
        calls = 0
        t = 0
        detector_triggers = 0
        fine_frontier_steps = 0
        tree_frontier_steps = 0
        escape_hatch_steps = 0
        global_mode = False
        steps_since_last_positive = 0
        escape_budget_remaining = int(config.escape_hatch_budget_frac * budget_abs) if config.use_escape_hatch else 0

        # Track probe count per node for RepMix
        node_probe_count = {}

        probe_log = []
        scheduler_log = []
        diverse_count_node = {}
        diverse_count_global = 0
        diverse_cap = int(config.max_diverse_probe_share * budget_abs)
        node_stag_start_step = {}  # first global_step a node became eligible
        # Logging is active only when a stagnation flag is on, so the default
        # HTS-EC-safe call sequence is byte-for-byte unchanged when both off.
        logging_on = config.use_node_stagnation or config.use_stag_repmix

        while calls < budget_abs:
            # 1. saturation detection (baseline behavior preserved)
            saturation_active_nodes = [n.node_id for n in all_nodes if n.saturated]
            for node in tree_frontier[:]:
                triggered, conf = detector_check(node, d_star, config)
                if triggered:
                    node.saturated = True
                    detector_triggers += 1
                    tree_frontier.remove(node)
                    node.in_tree_frontier = False
                    # Add unqueried bins from this node to fine frontier
                    for b in range(node.lo, node.hi):
                        if b not in queried:
                            fine_frontier.append(b)
                    if config.use_elfine:
                        # ELFine: don't sort by proxy, will use utility function
                        pass
                    else:
                        fine_frontier.sort(key=lambda b: -proxies[b])

            # 2. stagnation-eligible nodes computed BEFORE prune removal
            eligible_nodes = []
            prune_eligible_ids = set()
            if logging_on or config.use_stag_repmix:
                prune_min = max(config.detector_k_min,
                                config.posterior_prune_min_probes)
                for node in tree_frontier:
                    if (node.n_probe >= prune_min
                            and posterior_mean(node) < config.dual_prune_thresh):
                        prune_eligible_ids.add(node.node_id)
                    if stag_eligible(node, config, diverse_count_node,
                                     diverse_count_global, budget_abs,
                                     len(_unqueried_in_node(node, queried)),
                                     budget_abs - calls):
                        eligible_nodes.append(node)
                        # Record first eligibility step for cross-node priority
                        # (age = current_step - first_eligible_step).
                        node_stag_start_step.setdefault(node.node_id, t)
            eligible_ids = [n.node_id for n in eligible_nodes]
            eligible_set = set(eligible_ids)

            # Deterministic cross-node priority among stagmix-eligible nodes:
            # older stagnation > more unqueried leaves > fewer prior diverse
            # probes > higher posterior mean > stable node_id tie-break.
            eligible_nodes_sorted = sorted(
                eligible_nodes,
                key=lambda n: (
                    -(t - node_stag_start_step.get(n.node_id, t)),
                    -len(_unqueried_in_node(n, queried)),
                    diverse_count_node.get(n.node_id, 0),
                    -posterior_mean(n),
                    n.node_id,
                ))

            # 3. scheduler_decision_log (recorded before prune removal so the
            #    "eligible but pruned" window is observable — §5 ordering rule)
            legacy_would_trigger = (config.use_escape_hatch
                                    and escape_budget_remaining > 0
                                    and steps_since_last_positive
                                        >= config.escape_hatch_stagnation_window
                                    and not fine_frontier)
            if logging_on:
                scheduler_log.append({
                    "run_id": run_id,
                    "segment_id": segment_id,
                    "method": config.method_id,
                    "budget_config": budget_config,
                    "seed": seed,
                    "global_step": t,
                    "chosen_source": None,
                    "chosen_node_id": None,
                    "chosen_bin_idx": None,
                    "tree_candidate_count": len(tree_frontier),
                    "fine_candidate_count": len(fine_frontier),
                    "stagmix_candidate_count": len(eligible_nodes),
                    "stagnation_eligible_nodes_this_step": eligible_ids,
                    "saturation_active_nodes_this_step": saturation_active_nodes,
                    "prune_eligible_nodes_this_step": sorted(prune_eligible_ids),
                    "stagmix_candidate_nodes_ranked": [
                        n.node_id for n in eligible_nodes_sorted],
                    "stagmix_chosen_rank": None,
                    "stagmix_priority_policy": config.stagmix_priority_policy,
                    "stagmix_priority_score": None,
                    "diverse_probe_budget_used": diverse_count_global,
                    "diverse_probe_budget_cap": diverse_cap,
                    "diverse_probe_budget_remaining_share":
                        (diverse_cap - diverse_count_global) / max(1, diverse_cap),
                    "fine_frontier_nonempty": bool(fine_frontier),
                    "legacy_escape_hatch_would_trigger": bool(legacy_would_trigger),
                    "legacy_escape_hatch_suppressed_by_fine":
                        bool(legacy_would_trigger and fine_frontier),
                    "pruned_nodes_this_step": [],
                    "expanded_nodes_this_step": [],
                })

            # 4. prune removal (AFTER eligible computed + logged; defer only
            #    actionable StagRepMix candidates — i.e. nodes that satisfy the
            #    full stag_eligible predicate while use_stag_repmix is on and
            #    diverse budget remains. Shadow-log-only mode must NOT defer,
            #    otherwise G0 invariance is violated.
            for node in tree_frontier[:]:
                if (config.use_stag_repmix
                        and node.node_id in eligible_set):
                    # Actionable stagmix candidate: give it this step's chance
                    # at a diverse probe before removing.
                    continue
                if (node.n_probe >= max(config.detector_k_min,
                                        config.posterior_prune_min_probes)
                        and posterior_mean(node) < config.dual_prune_thresh):
                    node.pruned = True
                    tree_frontier.remove(node)
                    node.in_tree_frontier = False
                    if logging_on:
                        scheduler_log[-1]["pruned_nodes_this_step"].append(
                            node.node_id)

            # 5. legacy escape hatch (kept separate from StagRepMix; gated,
            #    default off — §3: do NOT mix into Phase 2A ablation)
            if (config.use_escape_hatch and escape_budget_remaining > 0 and
                steps_since_last_positive >= config.escape_hatch_stagnation_window and
                not fine_frontier):
                # Find a diverse unqueried bin far from queried
                all_unqueried = [b for b in range(n_bins) if b not in queried]
                if all_unqueried:
                    # Pick the bin farthest from all queried bins
                    all_unqueried.sort(
                        key=lambda b: -min(abs(b - q) for q in queried) if queried else 0)
                    escape_bin = all_unqueried[0]
                    y, _ = self._paid_query(
                        escape_bin, oracle, queried, label_cache,
                        action_type="ESCAPE_PROBE",
                        source_action="hts_ec_v0_escape",
                        notes=f"escape_hatch stagnation={steps_since_last_positive}")
                    leaf = find_leaf_node(escape_bin, root)
                    update_ancestors(leaf, all_by_id, y, escape_bin)
                    calls += 1
                    t += 1
                    escape_hatch_steps += 1
                    escape_budget_remaining -= 1
                    if y == 1:
                        pos_bins.add(escape_bin)
                        steps_since_last_positive = 0
                        # Activate fine frontier around this positive
                        for nb in [escape_bin - 1, escape_bin + 1]:
                            if 0 <= nb < n_bins and nb not in queried:
                                fine_frontier.append(nb)
                    else:
                        steps_since_last_positive += 1
                    if logging_on:
                        _append_probe_log(
                            probe_log, escape_bin, "legacy_escape", None, None, y,
                            root, all_by_id, proxies, queried, d_star,
                            eligible_set, fine_frontier, config, t, seed,
                            run_id, segment_id, budget_config)
                    continue

            if not tree_frontier and not fine_frontier:
                break

            # 6. compute best tree node + representative bin
            best_tree = None
            u_tree = -float("inf")
            best_tree_bin = None
            if tree_frontier:
                best_tree = max(tree_frontier, key=lambda n: ucb_score(n, t, config))
                u_tree = ucb_score(best_tree, t, config)
                # Add pruning value bonus + tree preference bonus
                pv_bonus = ((1 - posterior_mean(best_tree)) *
                            max(0, best_tree.n_leaves - best_tree.n_probe) /
                            max(1, best_tree.n_leaves))
                u_tree += pv_bonus + config.tree_preference_bonus
                n_probes_this = node_probe_count.get(best_tree.node_id, 0)
                best_tree_bin = select_representative_bin(
                    best_tree, proxies, queried, rng, config=config,
                    t_start_arr=t_start_arr,
                    n_probes_in_node=n_probes_this)
                # S-1 fallout: if every leaf in this node has already been
                # paid for (no duplicate paid query allowed), the node is
                # exhausted. Pull it out of the frontier so the next loop
                # iteration actually picks a different node with unqueried
                # leaves instead of starving the schedule. Re-enters the while
                # loop without consuming budget.
                if best_tree_bin is None:
                    best_tree.in_tree_frontier = False
                    best_tree.pruned = True
                    tree_frontier.remove(best_tree)
                    continue

            # 7. compute best fine bin
            best_fine = None
            u_fine = -float("inf")
            # Clean fine frontier of queried bins
            fine_frontier = [b for b in fine_frontier if b not in queried]
            if fine_frontier:
                if config.use_elfine:
                    best_fine = select_fine_bin_elfine(
                        fine_frontier, proxies, queried, pos_bins,
                        t_start_arr, t_end_arr, config, n_bins)
                    if best_fine is not None:
                        u_fine = compute_elfine_utility(
                            best_fine, proxies, queried, pos_bins,
                            t_start_arr, t_end_arr, config, n_bins)
                else:
                    best_fine = fine_frontier[0]
                    u_fine = proxies[best_fine] - config.fine_covered_penalty

            # 8. compute best stagmix candidate (only when actor enabled)
            best_stag = None
            stag_bin = None
            stag_strategy = None
            stag_pos = None
            u_stag = -float("inf")
            stag_priority_score = None
            if (config.use_stag_repmix and eligible_nodes_sorted
                    and diverse_count_global < diverse_cap):
                cand = eligible_nodes_sorted[0]
                b, strat, pos = pick_stag_bin(
                    cand, queried, proxies, config, diverse_count_node,
                    segment_id, seed)
                if b is not None:
                    best_stag = cand
                    stag_bin = b
                    stag_strategy = strat
                    stag_pos = pos
                    # Eligible-stagnant nodes get the diverse probe by default;
                    # total stagmix spend is already bounded by
                    # max_diverse_probe_share + max_diverse_probes_per_node, so
                    # it cannot starve the tree frontier.
                    u_stag = float("inf")
                    age = t - node_stag_start_step.get(cand.node_id, t)
                    unq = len(_unqueried_in_node(cand, queried))
                    dc = diverse_count_node.get(cand.node_id, 0)
                    pm = posterior_mean(cand)
                    stag_priority_score = (
                        f"age={age};unq={unq};dc={dc};"
                        f"pm={pm:.4f};node={cand.node_id}")

            # 9. three-way decision (tree vs fine vs stagmix)
            cands = []
            if best_tree is not None and best_tree_bin is not None:
                cands.append(("tree", best_tree, best_tree_bin, u_tree))
            if best_fine is not None:
                cands.append(("fine", None, best_fine, u_fine))
            if best_stag is not None:
                cands.append(("stagmix", best_stag, stag_bin, u_stag))
            if not cands:
                break
            chosen_source, chosen_node, chosen_bin, chosen_util = max(
                cands, key=lambda c: c[3])

            if logging_on:
                sl = scheduler_log[-1]
                sl["chosen_source"] = chosen_source
                sl["chosen_node_id"] = (chosen_node.node_id
                                        if chosen_node is not None else None)
                sl["chosen_bin_idx"] = chosen_bin
                if chosen_source == "stagmix":
                    sl["stagmix_priority_score"] = stag_priority_score
                    sl["stagmix_chosen_rank"] = next(
                        (i for i, n in enumerate(eligible_nodes_sorted)
                         if n.node_id == chosen_node.node_id), 0)

            # Hard sanity check for the scheduler ordering invariant:
            # if any eligible stagnant node exists and diverse budget remains,
            # u_stag=inf must make stagmix the chosen source. If not, the
            # candidate was invalidated between eligibility and decision —
            # almost always a prune-before-decision bug.
            if config.use_stag_repmix:
                n_stagmix_candidates = len(eligible_nodes_sorted)
                if (n_stagmix_candidates > 0
                        and diverse_count_global < diverse_cap
                        and chosen_source != "stagmix"):
                    raise AssertionError(
                        "scheduler ordering bug: eligible stagnant node(s) "
                        "existed and diverse budget remained, but stagmix was "
                        f"not chosen (chosen={chosen_source}). Candidate node "
                        f"IDs: {eligible_ids}. This usually means a node was "
                        "pruned between eligibility computation and decision.")

            # 10. dispatch execution
            if chosen_source == "tree":
                y, _ = self._paid_query(
                    chosen_bin, oracle, queried, label_cache,
                    action_type="COARSE_PROBE",
                    source_action="hts_ec_v0_tree",
                    node_id=chosen_node.node_id,
                    notes=f"node={chosen_node.node_id} depth={chosen_node.depth} "
                          f"ucb={u_tree:.4f} d*={d_star:.4f}")
                leaf = find_leaf_node(chosen_bin, root)
                update_ancestors(leaf, all_by_id, y, chosen_bin)
                calls += 1
                t += 1
                tree_frontier_steps += 1
                node_probe_count[chosen_node.node_id] = (
                    node_probe_count.get(chosen_node.node_id, 0) + 1)
                if y == 1:
                    pos_bins.add(chosen_bin)
                    steps_since_last_positive = 0
                else:
                    steps_since_last_positive += 1

                # Posterior-based drill/prune (NOT God's-eye)
                pm = posterior_mean(chosen_node)
                if chosen_node.n_probe >= config.posterior_min_probes:
                    # Proxy-mass drill: drill if proxy mass is high
                    proxy_mass = sum(proxies[b] for b in range(chosen_node.lo, chosen_node.hi)) / max(1, chosen_node.n_leaves)
                    proxy_mass_high = (config.use_proxy_mass_drill and
                                       proxy_mass >= config.proxy_mass_drill_frac * max_proxy_mass)

                    if pm >= config.posterior_drill_thresh or proxy_mass_high:
                        if not chosen_node.is_leaf and not chosen_node.expanded:
                            for c in chosen_node.children:
                                c.in_tree_frontier = True
                                tree_frontier.append(c)
                            chosen_node.expanded = True
                            if logging_on:
                                scheduler_log[-1]["expanded_nodes_this_step"].append(
                                    chosen_node.node_id)
                        if chosen_node in tree_frontier:
                            tree_frontier.remove(chosen_node)
                            chosen_node.in_tree_frontier = False
                    elif (pm <= config.posterior_prune_thresh
                          and chosen_node.n_probe >= config.posterior_prune_min_probes):
                        if chosen_node in tree_frontier:
                            tree_frontier.remove(chosen_node)
                            chosen_node.in_tree_frontier = False
                            chosen_node.pruned = True
                    # else: keep in frontier for more probing
                if logging_on:
                    _append_probe_log(
                        probe_log, chosen_bin, "tree", None, None, y,
                        root, all_by_id, proxies, queried, d_star,
                        eligible_set, fine_frontier, config, t, seed,
                        run_id, segment_id, budget_config)

            elif chosen_source == "fine":
                y, _ = self._paid_query(
                    chosen_bin, oracle, queried, label_cache,
                    action_type="FINE_PROBE",
                    source_action="hts_ec_v0_fine",
                    notes=f"fine_frontier {'elfine' if config.use_elfine else 'proxy'} "
                          f"proxy={proxies[chosen_bin]:.4f}")
                leaf = find_leaf_node(chosen_bin, root)
                update_ancestors(leaf, all_by_id, y, chosen_bin)
                calls += 1
                t += 1
                fine_frontier_steps += 1
                if y == 1:
                    pos_bins.add(chosen_bin)
                    steps_since_last_positive = 0
                    # Activate neighbors for local expansion
                    for nb in [chosen_bin - 1, chosen_bin + 1]:
                        if (0 <= nb < n_bins and nb not in queried
                            and nb not in fine_frontier):
                            fine_frontier.append(nb)
                else:
                    steps_since_last_positive += 1
                if chosen_bin in fine_frontier:
                    fine_frontier.remove(chosen_bin)
                if logging_on:
                    _append_probe_log(
                        probe_log, chosen_bin, "fine", None, None, y,
                        root, all_by_id, proxies, queried, d_star,
                        eligible_set, fine_frontier, config, t, seed,
                        run_id, segment_id, budget_config)

            else:  # stagmix
                y, _ = self._paid_query(
                    chosen_bin, oracle, queried, label_cache,
                    action_type="DIVERSE_PROBE",
                    source_action="hts_ec_v0_stagmix",
                    node_id=chosen_node.node_id,
                    notes=f"stagmix node={chosen_node.node_id} "
                          f"strategy={stag_strategy} pos={stag_pos}")
                leaf = find_leaf_node(chosen_bin, root)
                update_ancestors(leaf, all_by_id, y, chosen_bin)
                calls += 1
                t += 1
                diverse_count_node[chosen_node.node_id] = (
                    diverse_count_node.get(chosen_node.node_id, 0) + 1)
                diverse_count_global += 1
                if y == 1:
                    pos_bins.add(chosen_bin)
                    steps_since_last_positive = 0
                else:
                    steps_since_last_positive += 1
                if logging_on:
                    _append_probe_log(
                        probe_log, chosen_bin, "stagmix", stag_strategy,
                        stag_pos, y, root, all_by_id, proxies, queried,
                        d_star, eligible_set, fine_frontier, config, t, seed,
                        run_id, segment_id, budget_config)

        # Build returned intervals from positive bins (adjacency grouping)
        pos_bin_list = sorted(pos_bins)
        intervals = self._group_positive_bins(pos_bin_list, grid_sorted)

        diagnostics = {
            "n_bins": n_bins,
            "d_star": d_star,
            "detector_triggers": detector_triggers,
            "tree_frontier_steps": tree_frontier_steps,
            "fine_frontier_steps": fine_frontier_steps,
            "escape_hatch_steps": escape_hatch_steps,
            "fine_fraction": fine_frontier_steps / max(1, calls),
            "n_pruned_nodes": sum(1 for n in all_nodes if n.pruned),
            "n_expanded_nodes": sum(1 for n in all_nodes if n.expanded),
            "n_saturated_nodes": sum(1 for n in all_nodes if n.saturated),
            "tree_total_nodes": len(all_nodes),
            "n_tree_frontier_final": len(tree_frontier),
            "n_fine_frontier_final": len(fine_frontier),
            "use_elfine": int(config.use_elfine),
            "use_repmix": int(config.use_repmix),
            "use_escape_hatch": int(config.use_escape_hatch),
            "use_proxy_mass_drill": int(config.use_proxy_mass_drill),
            "use_node_stagnation": int(config.use_node_stagnation),
            "use_stag_repmix": int(config.use_stag_repmix),
            "stagmix_priority_policy": config.stagmix_priority_policy,
            "n_probe_log_rows": len(probe_log),
            "n_scheduler_log_rows": len(scheduler_log),
        }

        return {
            "pos_bins": pos_bins,
            "calls": calls,
            "intervals": intervals,
            "diagnostics": diagnostics,
            "global_mode": global_mode,
            "probe_log": probe_log,
            "scheduler_decision_log": scheduler_log,
        }

    def _group_positive_bins(self, pos_bin_idxs, grid):
        """Group positive bins by temporal adjacency (strict, no event_id).
        Reuses group_positive_bins logic from run_aligned_baselines_v1."""
        if not pos_bin_idxs:
            return []
        grid_sorted = grid.sort_values("bin_idx").reset_index(drop=True)
        bin_to_t = dict(zip(grid_sorted["bin_idx"],
                           zip(grid_sorted["local_t_start"],
                               grid_sorted["local_t_end"])))
        sorted_bins = sorted(pos_bin_idxs)
        intervals = []
        cur_start_bin = sorted_bins[0]
        cur_end_bin = sorted_bins[0]
        for b in sorted_bins[1:]:
            if b == cur_end_bin + 1:
                cur_end_bin = b
            else:
                s, _ = bin_to_t[cur_start_bin]
                _, e = bin_to_t[cur_end_bin]
                intervals.append((s, e))
                cur_start_bin = b
                cur_end_bin = b
        s, _ = bin_to_t[cur_start_bin]
        _, e = bin_to_t[cur_end_bin]
        intervals.append((s, e))
        return intervals
