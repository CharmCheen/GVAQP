#!/usr/bin/env python3
"""HTS-EC-v0 Phase 2A-RP strategy shadow / counterfactual sweep.

Reads the 5 preflight CSVs + the 4 opportunity audit CSVs and,
WITHOUT touching the online `pick_stag_bin`, computes what alternative
RepMix strategies WOULD have picked at each of the 30 stagmix-chosen
steps of the StagRepMix-force run.

It scores each shadow pick against the offline true labels to decide which
strategy family should be promoted to a full replay. The score is purely
informational; it never mutates the persisted online state, never
re-feeds a label back into any posterior, and never crosses the S-1 /
no-duplicate-paid-query boundary.

Two families are tested (per handoff 2026-07-07 Step 4 spec):

FAMILY A — v2-cycle (four independently-scored first-probe strategies):
    - largest_unqueried_gap_midpoint
    - largest_gap_center_by_negative_barriers
    - proxy_quantile_25_or_75
    - low_proxy_temporal_diverse  (boundary-guarded in [0.20, 0.80])

FAMILY B — gap-bracket-v2 (two-stage probe, max=2 per node):
    - probe 1: largest_unqueried_gap_midpoint
    - probe 2: largest_gap_local_flank_or_proxy_neighbor (r=3 bins)

Pass conditions (informational, decide promote-to-replay):
    1. shadow_selected_bin_already_queried == 0 for every row
    2. boundary_selection_rate << old low_proxy_diverse (which had q==0.008)
    3. dataset3_0_1200 >= 2/3 seeds with >=1 shadow positive hit
    4. total shadow hits >= 3 / 30 across either family

Usage:
    python scripts/analyze_hts_ec_v0_rp_strategy_shadow.py \
        --input      outputs/hts_ec_v0_phase2a_rp_preflight_v1 \
        --opportunity outputs/hts_ec_v0_phase2a_rp_opportunity_v1 \
        --output     outputs/hts_ec_v0_phase2a_rp_strategy_shadow_v1
"""
import argparse
import ast
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from garc_eval.hts_ec_v0 import HtsEcV0Config, build_tree, collect_nodes
from run_aligned_baselines_v1 import (
    load_segment_data, SEGMENTS, LABEL_COL, PROXY_COL,
)


# ---------------------------------------------------------------------------
# State reconstruction helpers
# ---------------------------------------------------------------------------

def reconstruct_queried_set_at_step(run_trace, step_t):
    """Bins with paid labels BEFORE scheduler global_step == step_t.

    call_idx is 1-based; at global_step == t the runner has already paid
    for call_idx values in [1, t]. (Same convention as the opportunity
    audit so shadow picks are comparable.)
    """
    return set(int(b) for b in run_trace.loc[run_trace["call_idx"] <= step_t, "bin_id"])


def reconstruct_queried_negatives_at_step(run_trace, step_t):
    """Bins paid BEFORE step_t whose offline true label is negative."""
    sub = run_trace[(run_trace["call_idx"] <= step_t)
                    & (run_trace["oracle_label"] == "negative")]
    return set(int(b) for b in sub["bin_id"])


def safe_literal(val, default):
    if pd.isna(val):
        return default
    if isinstance(val, (list, tuple)):
        return list(val)
    try:
        return ast.literal_eval(str(val))
    except Exception:
        return default


# ---------------------------------------------------------------------------
# Strategy primitives (operate on one node + in-node queried set)
# ---------------------------------------------------------------------------

def longest_unqueried_runs(node_lo, node_hi, queried):
    """Return list of (gap_start, gap_end_exclusive, gap_len) over unqueried
    runs inside the node. Sorted by (-gap_len, start)."""
    runs = []
    i = node_lo
    while i < node_hi:
        if i not in queried:
            j = i
            while j < node_hi and j not in queried:
                j += 1
            runs.append((i, j, j - i))
            i = j
        else:
            i += 1
    runs.sort(key=lambda r: (-r[2], r[0]))
    return runs


def midpoint_of_run(run):
    """Discrete midpoint of a half-inclusive run (start, end_excl, len).
    For odd-length run this is the centered bin; for even it is the
    higher of the two central bins (deterministic)."""
    start, end_excl, _ = run
    n = end_excl - start
    mid = start + (n - 1) // 2  # for odd: central; for even: lower-central
    return mid


def proxy_rank_descending(bins, proxies):
    """Return bins sorted by descending proxy (stable on bin_idx)."""
    return sorted(bins, key=lambda b: (-proxies[b], b))


def temporal_quantile(bin_idx, node_lo, node_hi):
    """Temporal position of bin inside node in [0, 1]."""
    width = node_hi - node_lo - 1
    if width <= 0:
        return 0.0
    return (bin_idx - node_lo) / width


def is_boundary_bin(bin_idx, node_lo, node_hi):
    """A boundary bin is the leftmost or rightmost leaf in the node."""
    return bin_idx == node_lo or bin_idx == node_hi - 1


# --- v2-cycle strategies (all first-probe, independent) --------------------

def s_largest_unqueried_gap_midpoint(node, queried, proxies, rng_state=0):
    """Largest contiguous unqueried run midpoint. Tie-break by higher mean
    proxy of the run, then start (stable)."""
    runs = longest_unqueried_runs(node.lo, node.hi, queried)
    if not runs:
        return None
    # Group runs with max length, then tie-break by mean proxy.
    top_len = runs[0][2]
    tied = [r for r in runs if r[2] == top_len]
    # Higher mean proxy wins (we want the "denser" gap if multiple gaps tie).
    tied.sort(key=lambda r: (
        -float(np.mean([proxies[b] for b in range(r[0], r[1])])),
        r[0]))
    return midpoint_of_run(tied[0])


def s_largest_gap_center_by_negative_barriers(node, queried, queried_negatives,
                                              proxies):
    """Largest unqueried run whose BOTH flanks are bounded either by
    node-internal queried negatives or by node edges that are adjacent
    to queried negatives. Falls back to longest unqueried run if no
    negative-bounded run exists.

    Degenerate run at node boundary that is NOT adjacent to a negative is
    DISALLOWED as a negative-bounded run; we prefer interior-barrier gaps.
    """
    runs = longest_unqueried_runs(node.lo, node.hi, queried)
    if not runs:
        return None
    neg_bounded = []
    for (s, e, n) in runs:
        left_barrier = (s == node.lo) or (s - 1 in queried_negatives)
        right_barrier = (e == node.hi) or (e in queried_negatives)
        # Strict interior barrier: both flanks must come from queried negatives
        # (not node edges), unless the edge bin is itself queried negative.
        left_strict = (s - 1 in queried_negatives) if s > node.lo else False
        right_strict = (e in queried_negatives) if e < node.hi else False
        if left_strict and right_strict:
            neg_bounded.append((s, e, n, True, True))
        elif left_strict or right_strict:
            neg_bounded.append((s, e, n, "half", "half"))
        # else: not barrier-bounded
    if neg_bounded:
        # Prefer fully-bounded, then by length, then by mean proxy.
        neg_bounded.sort(key=lambda r: (
            0 if r[3] is True else 1,
            -r[2],
            -float(np.mean([proxies[b] for b in range(r[0], r[1])])),
            r[0]))
        return midpoint_of_run((neg_bounded[0][0], neg_bounded[0][1],
                                neg_bounded[0][2]))
    # Fallback: standard largest unqueried gap.
    return s_largest_unqueried_gap_midpoint(node, queried, proxies)


def s_proxy_quantile_25_or_75(node, queried, proxies, position=0):
    """Among unqueried bins in the node, sorted by descending proxy,
    pick the bin at the 25th-percentile rank on even positions, 75th on
    odd (deterministic rotation across probe position). Stable fallback
    to the median unqueried proxy rank if the node has <4 unqueried.
    """
    unq = [b for b in range(node.lo, node.hi) if b not in queried]
    if not unq:
        return None
    unq.sort(key=lambda b: (-proxies[b], b))
    n = len(unq)
    if n < 4:
        return unq[n // 2]  # median
    # 25th or 75th percentile rank (0-based), tie-break alternates.
    q_lo = max(0, int(round(0.25 * (n - 1))))
    q_hi = min(n - 1, int(round(0.75 * (n - 1))))
    rank = q_lo if position % 2 == 0 else q_hi
    return unq[rank]


def s_low_proxy_temporal_diverse(node, queried, proxies):
    """Lowest-proxy unqueried bin, but constrained to temporal quantile
    in [0.20, 0.80] (avoid picking node[0] every time, which is what
    old low_proxy_diverse did 3/3 times at q~0.008). Fall back to the
    second-lowest-proxy unqueried bin if all lowest-proxy variants are
    outside the band.
    """
    unq = [b for b in range(node.lo, node.hi) if b not in queried]
    if not unq:
        return None
    # Sort by ascending proxy (lowest first), stable.
    unq.sort(key=lambda b: (proxies[b], b))
    width = max(1, node.hi - node.lo - 1)
    for b in unq:
        q = (b - node.lo) / width
        if 0.20 <= q <= 0.80:
            return b
    # No qualifying bin in band: take the 2nd-lowest-proxy unqueried bin
    # (still a small diversity vs. bin[0]).
    return unq[min(1, len(unq) - 1)]


# --- gap-bracket-v2 family (probe-1 then probe-2, sequential) --------------

BRACKET_RADIUS = 3  # bins, see handoff 2026-07-07 spec


def s_gap_bracket_v2_probe1(node, queried, proxies):
    """Probe 1 = largest unqueried gap midpoint."""
    return s_largest_unqueried_gap_midpoint(node, queried, proxies)


def s_gap_bracket_v2_probe2(node, queried_including_probe1, proxies):
    """Probe 2 = within the gap used by probe 1, pick the bin in a ±r
    window around the probe-1 pick that has higher proxy. If the window
    is empty, fall back to the nearest unqueried flank inside the same
    gap. Worst case, fall back to the largest *remaining* gap's midpoint.
    """
    # Recompute probe-1 candidate (largest gap midpoint before adding probe 1).
    probe1 = s_gap_bracket_v2_probe1(node, queried_including_probe1 - {b for b in queried_including_probe1 if False}, proxies)
    # Simpler: just identify the run containing probe1 (if probe1 has been
    # marked as queried, the run that "_" used to be its center).
    # Find the largest run in the ORIGINAL queried set.
    # We approximate by recomputing: query set without probe1's bin should
    # still preserve the structure if probe1 was unique.
    # Easier: find the run that "contains" probe1 in the queried-minus-probe1
    # set. Lets us pick a probe-2 candidate inside the same gap.
    queried_minus_probe1 = set(queried_including_probe1)
    # We need probe1's identity; infer it: the gap bracket was designed so
    # the largest post-probe-1 gap still includes probe-2 territory.
    # Alternative cleaner path: caller passes probe1 explicitly.

    # Caller contract: this helper is invoked with queried INCLUDING the
    # probe-1 bin already. We need the probe-1 bin to find its sibling gap.
    # We infer probe-1 by recomputing it: largest unqueried gap midpoint in
    # (queried \ {the probe-1 bin}). Since the probe-1 bin is now queried
    # (in the including set), we need to enumerate candidates.

    # Easiest robust path: take the gap structure NOW (with probe1 queried).
    runs = longest_unqueried_runs(node.lo, node.hi, queried_including_probe1)
    if not runs:
        return None
    # Probe1 sits in the largest run BEFORE it was queried; it bisects that
    # run. The two flanking runs adjacent to probe1 (left & right, now
    # separated by the queried probe1 bin) come from that original gap.
    # Find probe1 as the queried bin flanked by largest remaining runs.
    # Simpler: assume the largest run NOW around probe1's vacated spot.

    # Use the simpler rule: pick the largest currently-unqueried run (this
    # should be either the leftover of the original gap, or a different
    # gap if probe1 closed the original). Then apply the ±r local bracket
    # window logic around the run's midpoint.
    top = runs[0]
    mid_candidate = midpoint_of_run(top)

    # ±r window around midpoint: pick higher-proxy unqueried bin inside.
    candidates = []
    for off in range(-BRACKET_RADIUS, BRACKET_RADIUS + 1):
        b = mid_candidate + off
        if b in range(top[0], top[1]):  # inside the same run
            candidates.append(b)
    # Remove the midpoint itself (it's the proxy "centre"), prefer
    # higher-proxy flank within window.
    candidates = [b for b in candidates if b != mid_candidate]
    if not candidates:
        # Window empty (run shorter than 2r+1). Take run's nearest flank.
        return top[0] if top[2] >= 1 else None
    candidates.sort(key=lambda b: (-proxies[b], b))
    return candidates[0]


# Cleaner gap_bracket_v2 entry: compute probe-1 and probe-2 in a single
# function so the caller doesn't have to fiddle with re-inferring probe1.

def gap_bracket_v2_seq(node, queried, proxies):
    """Return (probe1_bin, probe2_bin). probe-2 is the local flank /
    proxy-neighbor of probe-1 inside the same original largest gap."""
    # Probe 1.
    p1 = s_gap_bracket_v2_probe1(node, queried, proxies)
    if p1 is None:
        return None, None
    # Identify the original largest run (so we can place probe 2 INSIDE
    # the same run, on the other side of probe1).
    runs_pre = longest_unqueried_runs(node.lo, node.hi, queried)
    top_run_pre = runs_pre[0]  # already sorted by (-len, start)
    # Probe-1 is the midpoint of the largest pre-probe1 run.
    expected_p1 = midpoint_of_run(top_run_pre)
    # (assert expected_p1 == p1)
    # Now place probe-2 inside the same run, on the side of probe1 that
    # has higher mean proxy OR larger remaining room.
    s, e, _ = top_run_pre
    left_run = (s, p1, p1 - s)        # [s, p1)
    right_run = (p1 + 1, e, e - p1 - 1)  # (p1, e)
    # ±r window around probe1: prefer higher-proxy unqueried bin inside.
    candidates = []
    for off in range(-BRACKET_RADIUS, BRACKET_RADIUS + 1):
        b = p1 + off
        if b == p1:
            continue
        if s <= b < e:  # must be inside the ORIGINAL run, unqueried
            if b not in queried and b != p1:
                candidates.append(b)
    if candidates:
        candidates.sort(key=lambda b: (-proxies[b], b))
        p2 = candidates[0]
    elif right_run[2] > 0:
        p2 = right_run[0] + (right_run[2] - 1) // 2  # midpoint of right run
    elif left_run[2] > 0:
        p2 = left_run[0] + (left_run[2] - 1) // 2
    else:
        # Original run was just probe1: pick a different run.
        if len(runs_pre) > 1:
            p2 = midpoint_of_run(runs_pre[1])
        else:
            p2 = None
    return p1, p2


# ---------------------------------------------------------------------------
# Main shadow sweep
# ---------------------------------------------------------------------------

V2_CYCLE_STRATEGIES = [
    "largest_unqueried_gap_midpoint",
    "largest_gap_center_by_negative_barriers",
    "proxy_quantile_25_or_75",
    "low_proxy_temporal_diverse",
]


def shadow_pick(strategy, node, queried, queried_negatives, proxies, position=0):
    """Single strategy pick. Returns a bin index or None."""
    if strategy == "largest_unqueried_gap_midpoint":
        return s_largest_unqueried_gap_midpoint(node, queried, proxies)
    if strategy == "largest_gap_center_by_negative_barriers":
        return s_largest_gap_center_by_negative_barriers(
            node, queried, queried_negatives, proxies)
    if strategy == "proxy_quantile_25_or_75":
        return s_proxy_quantile_25_or_75(node, queried, proxies, position=position)
    if strategy == "low_proxy_temporal_diverse":
        return s_low_proxy_temporal_diverse(node, queried, proxies)
    raise ValueError(f"unknown strategy: {strategy}")


def run_shadow(input_dir, opportunity_dir, output_dir):
    input_dir = Path(input_dir)
    opportunity_dir = Path(opportunity_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load source + opportunity tables.
    sl = pd.read_csv(input_dir / "hts_ec_v0_scheduler_decision_log.csv")
    pl = pd.read_csv(input_dir / "hts_ec_v0_probe_log.csv")
    tr = pd.read_csv(input_dir / "hts_ec_v0_call_trace.csv")
    fr = pd.read_csv(input_dir / "hts_ec_v0_frontier.csv")
    di = pd.read_csv(input_dir / "hts_ec_v0_diagnostics.csv")
    step_audit = pd.read_csv(opportunity_dir / "rp_opportunity_by_step.csv")

    # Only the StagRepMix-force chosen steps are scorable here.
    chosen = step_audit[
        (step_audit["method"] == "HTS-EC-safe-StagRepMix-force")
        & (step_audit["chosen_source"] == "stagmix")
    ].copy()
    print(f"Viable counterfactual opportunities: {len(chosen)}")

    # Rebuild deterministic tree per segment for node_id -> (lo, hi).
    REF_CONFIG = HtsEcV0Config()
    labels_cache = {}
    proxies_cache = {}
    node_index_cache = {}
    for seg in SEGMENTS:
        seg_id = seg["segment_id"]
        by_id, grid, labels = None, None, None
        try:
            g, _, err = load_segment_data(seg)
            if err:
                continue
            g = g.sort_values("bin_idx").reset_index(drop=True)
            proxies = g[PROXY_COL].values
            root = build_tree(0, len(g), proxies, REF_CONFIG)
            all_nodes = collect_nodes(root)
            by_id = {n.node_id: n for n in all_nodes}
            labels = g[LABEL_COL].astype(int).values
        except Exception as e:
            print(f"  SKIP {seg_id}: {e}")
            continue
        node_index_cache[seg_id] = by_id
        labels_cache[seg_id] = {int(b): int(y) for b, y in enumerate(labels) if y == 1}
        proxies_cache[seg_id] = proxies

    rows = []
    for _, ch in chosen.iterrows():
        seg_id = ch["segment_id"]
        budget_config = ch["budget_config"]
        seed = int(ch["seed"])
        step_t = int(ch["global_step"])
        node_id = ch["chosen_node_id"]
        if not isinstance(node_id, str):
            continue
        node_by_id = node_index_cache.get(seg_id)
        if node_by_id is None:
            continue
        node = node_by_id.get(node_id)
        if node is None:
            continue
        true_pos = labels_cache[seg_id]
        proxies = proxies_cache[seg_id]

        # Reconstruct queried / negatives BEFORE this step.
        run_tr = tr[(tr["segment_id"] == seg_id)
                    & (tr["method_id"] == "HTS-EC-safe-StagRepMix-force")
                    & (tr["budget_ratio"].astype(str) == str(budget_config))
                    & (tr["seed"] == seed)].copy()
        run_tr["call_idx"] = run_tr["call_idx"].astype(int)
        queried = reconstruct_queried_set_at_step(run_tr, step_t)
        queried_neg = reconstruct_queried_negatives_at_step(run_tr, step_t)

        remaining_tp = [b for b in range(node.lo, node.hi)
                        if b in true_pos and b not in queried]

        for strategy in V2_CYCLE_STRATEGIES:
            b = shadow_pick(strategy, node, queried, queried_neg, proxies,
                             position=0)
            label = true_pos.get(b) if b is not None else None
            dist = min(abs(b - t) for t in remaining_tp) if (b is not None and remaining_tp) else (None if remaining_tp else 0)
            rows.append({
                "run_id": ch.get("run_id"),
                "segment_id": seg_id,
                "method": "HTS-EC-safe-StagRepMix-force",
                "budget_ratio": str(budget_config),
                "seed": seed,
                "global_step": step_t,
                "node_id": node_id,
                "strategy_family": "v2_cycle",
                "strategy_name": strategy,
                "strategy_position": 0,
                "shadow_selected_bin": b,
                "shadow_bin_already_queried": (b in queried) if b is not None else None,
                "shadow_oracle_label_offline": (1 if label == 1 else 0) if b is not None else None,
                "shadow_distance_to_nearest_tp": dist,
                "shadow_selected_temporal_quantile": temporal_quantile(b, node.lo, node.hi) if b is not None else None,
                "shadow_selected_proxy_rank": proxy_rank_descending([xb for xb in range(node.lo, node.hi)], proxies).index(b) if b is not None else None,
                "remaining_true_positive_bins_in_node": len(remaining_tp),
                "is_boundary_bin": is_boundary_bin(b, node.lo, node.hi) if b is not None else None,
            })

        # gap_bracket_v2 sequential (probe1 + probe2 within same node).
        p1, p2 = gap_bracket_v2_seq(node, queried, proxies)
        for pos, b in enumerate([p1, p2]):
            if b is None:
                continue
            label = true_pos.get(b)
            dist = min(abs(b - t) for t in remaining_tp) if remaining_tp else 0
            rows.append({
                "run_id": ch.get("run_id"),
                "segment_id": seg_id,
                "method": "HTS-EC-safe-StagRepMix-force",
                "budget_ratio": str(budget_config),
                "seed": seed,
                "global_step": step_t,
                "node_id": node_id,
                "strategy_family": "gap_bracket_v2",
                "strategy_name": (f"largest_unqueried_gap_midpoint" if pos == 0
                                  else f"largest_gap_local_flank_or_proxy_neighbor"),
                "strategy_position": pos,
                "shadow_selected_bin": b,
                "shadow_bin_already_queried": b in queried,
                "shadow_oracle_label_offline": 1 if label == 1 else 0,
                "shadow_distance_to_nearest_tp": dist,
                "shadow_selected_temporal_quantile": temporal_quantile(b, node.lo, node.hi),
                "shadow_selected_proxy_rank": proxy_rank_descending([xb for xb in range(node.lo, node.hi)], proxies).index(b),
                "remaining_true_positive_bins_in_node": len(remaining_tp),
                "is_boundary_bin": is_boundary_bin(b, node.lo, node.hi),
            })

    by_probe_df = pd.DataFrame(rows)
    by_probe_path = output_dir / "rp_strategy_shadow_by_probe.csv"
    by_probe_df.to_csv(by_probe_path, index=False)
    print(f"  Wrote {by_probe_path}  rows={len(by_probe_df)}")

    # ----- summary -----
    print()
    print("=" * 78)
    print("SUMMARY")
    print("=" * 78)

    if len(by_probe_df) == 0:
        print("(no rows)")
        return

    # Compute pass/fail metrics per (family, strategy).
    summary_rows = []
    for (fam, name), grp in by_probe_df.groupby(["strategy_family", "strategy_name"]):
        n = len(grp)
        hits = int(grp["shadow_oracle_label_offline"].fillna(0).sum())
        already = int(grp["shadow_bin_already_queried"].fillna(0).sum())
        boundary = int(grp["is_boundary_bin"].fillna(0).sum())
        # Boundary rate for old low_proxy_diverse was 3/3 picks at q~0.008 ->
        # boundary (~100% boundary). Here we want << that.
        bowl = grp["shadow_distance_to_nearest_tp"].dropna()
        avg_dist = float(bowl.mean()) if len(bowl) else None
        avg_q = grp["shadow_selected_temporal_quantile"].dropna()
        avg_q = float(avg_q.mean()) if len(avg_q) else None
        # Hits on dataset3_0_1200 specifically.
        d3_hits = int(grp[(grp["segment_id"] == "dataset3_0_1200")
                          & (grp["shadow_oracle_label_offline"] == 1)].shape[0])
        d3_seeds_with_hits = grp[(grp["segment_id"] == "dataset3_0_1200")
                                 & (grp["shadow_oracle_label_offline"] == 1)]["seed"].nunique()
        # New event first-hits: approximated as "any positive label that
        # the original preflight run had NOT already covered by the time
        # of this probe". We do the cheap version: count positive hits
        # (each is a candidate-new-event at the moment of probe).
        summary_rows.append({
            "strategy_family": fam,
            "strategy_name": name,
            "n_shadow_candidates": n,
            "shadow_positive_hits": hits,
            "shadow_new_event_first_hits": hits,  # placeholder; rerun
                                                   # confirms by checking
                                                   # if its event_id is new
            "shadow_hits_on_dataset3_0_1200": d3_hits,
            "shadow_hits_by_seed": int(grp[grp["shadow_oracle_label_offline"] == 1]["seed"].nunique()),
            "avg_distance_to_nearest_tp": avg_dist,
            "boundary_selection_rate": boundary / max(1, n),
            "already_queried_rate": already / max(1, n),
            "d3_0_1200_seeds_with_hits": int(d3_seeds_with_hits),
            "avg_selected_temporal_quantile": avg_q,
        })

    summary_df = pd.DataFrame(summary_rows)
    summary_path = output_dir / "rp_strategy_shadow_summary.csv"
    summary_df.to_csv(summary_path, index=False)
    print(f"  Wrote {summary_path}  rows={len(summary_df)}")
    print()
    print(summary_df[
        ["strategy_family", "strategy_name", "n_shadow_candidates",
         "shadow_positive_hits", "shadow_hits_on_dataset3_0_1200",
         "d3_0_1200_seeds_with_hits", "avg_distance_to_nearest_tp",
         "boundary_selection_rate", "already_queried_rate"]
    ].to_string(index=False))

    # Reference: old low_proxy_diverse boundary rate from audit.
    print()
    print("REFERENCE (old strategies, from opportunity audit):")
    print("  low_proxy_diverse     boundary_rate=~1.000 (3/3 at q~0.008)")
    print("  farthest_unqueried    avg_q~0.71  avg_dist~14.9   strategy hits=0/12")
    print("  median_proxy          avg_q~0.75  avg_dist~ 9.5  strategy hits=0/4")
    print("  temporal_center       avg_q~0.50  avg_dist~ 1.55 strategy hits=0/11")
    print()

    # ---- pass/fail decision preview ----
    print("=" * 78)
    print("PASS CHECKS (informational — decide promote to full replay)")
    print("=" * 78)
    overall = []
    for _, r in summary_df.iterrows():
        ok = (
            r["already_queried_rate"] == 0.0
            and (r["shadow_positive_hits"] >= 1)
        )
        overall.append(ok)
        print(f"  {r['strategy_family']}/{r['strategy_name']}:")
        print(f"     already_queried_rate = {r['already_queried_rate']:.3f}  "
              f"({'PASS' if r['already_queried_rate'] == 0 else 'FAIL'})")
        print(f"     boundary_selection_rate = {r['boundary_selection_rate']:.3f}  "
              f"({'PASS' if r['boundary_selection_rate'] < 0.3 else 'FAIL', 'target <0.3'})")
        print(f"     dataset3_0_1200 seeds with hits = {r['d3_0_1200_seeds_with_hits']} / 3  "
              f"({'PASS' if r['d3_0_1200_seeds_with_hits'] >= 2 else 'FAIL', 'target >=2'})")
        print(f"     total shadow hits = {r['shadow_positive_hits']}  "
              f"({'PASS' if r['shadow_positive_hits'] >= 1 and r['strategy_name'] != 'low_proxy_diverse' else 'FAIL', 'target >=3 in best family'})")
        print()

    # Family-level aggregations.
    print("FAMILY-LEVEL (gap_bracket_v2 vs v2_cycle):")
    for fam, grp in summary_df.groupby("strategy_family"):
        total_hits = int(grp["shadow_positive_hits"].sum())
        all_d3_seeds = set()
        for _, r in grp.iterrows():
            if r["shadow_positive_hits"] > 0:
                all_d3_seeds.add(int(r["d3_0_1200_seeds_with_hits"]))
        max_d3_seeds = max(all_d3_seeds) if all_d3_seeds else 0
        print(f"  {fam}: total hits={total_hits}  "
              f"max d3_0_1200 seeds w/ hits={max_d3_seeds}/3")
        if total_hits >= 3 and max_d3_seeds >= 2:
            print(f"  -> FAMILY PASS: promote {fam} to pick_stag_bin")
        else:
            print(f"  -> FAMILY FAIL (need >=3 hits AND >=2 d3_0_1200 seeds)")
    print("=" * 78)


def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", default="outputs/hts_ec_v0_phase2a_rp_preflight_v1")
    p.add_argument("--opportunity", default="outputs/hts_ec_v0_phase2a_rp_opportunity_v1")
    p.add_argument("--output", default="outputs/hts_ec_v0_phase2a_rp_strategy_shadow_v1")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_shadow(args.input, args.opportunity, args.output)