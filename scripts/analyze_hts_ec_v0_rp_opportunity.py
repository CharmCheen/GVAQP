#!/usr/bin/env python3
"""HTS-EC-v0 Phase 2A-RP opportunity audit (offline read-only analysis).

Reads the 5 CSVs produced by run_hts_ec_v0_phase2a_rp_preflight.py and answers
three attribution questions before any online-algorithm change is made:

    X = of the 30 stagmix-chosen nodes, how many actually contained at least
        one remaining true-positive bin at the moment stagmix picked them?
        X > 0  -> the RepMix strategy is the problem (probe the wrong bin
                  inside the right node).
        X = 0  -> stagmix never picked an eventful node -> cross-node priority
                  or eligibility is the problem.

    Y = of all eligible steps, how many had >=1 eligible node that contained
        >=1 remaining true-positive bin? (independent of which node the
        scheduler actually chose).
        Y = 0  -> the stagnation predicate never covers eventful nodes ->
                  fix eligibility. Do NOT touch strategy/priority.
        Y > 0  but X = 0 -> cross-node priority is the problem.

    Z (per node, for dataset3_2400_3462) = why did this segment produce zero
        stagmix-eligible steps? Per-node near-miss breakdown.

This script re-reads the true `is_positive` label column OFFLINE (after the
run finished). The label never touches the online decision path; it is only
used here to attribute why stagmix probes missed. No online algorithm code is
modified by running this audit.

Inputs (--input):
    hts_ec_v0_frontier.csv
    hts_ec_v0_call_trace.csv
    hts_ec_v0_diagnostics.csv
    hts_ec_v0_probe_log.csv
    hts_ec_v0_scheduler_decision_log.csv

Outputs (--output):
    rp_opportunity_by_step.csv
    rp_opportunity_by_node.csv
    rp_strategy_miss_analysis.csv
    rp_near_miss_stagnation.csv

Usage:
    python scripts/analyze_hts_ec_v0_rp_opportunity.py \
        --input  outputs/hts_ec_v0_phase2a_rp_preflight_v1 \
        --output outputs/hts_ec_v0_phase2a_rp_opportunity_v1
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
# Helpers
# ---------------------------------------------------------------------------

def reconstruct_queried_set_at_step(run_trace, step_t):
    """Bins queried before scheduler global_step == step_t.

    The runner increments `t` after every paid probe, and the scheduler log
    row is emitted at the TOP of the while loop with the current `global_step`.
    Therefore at global_step == t the set of paid bins = rows with call_idx <= t
    (call_idx is 1-based within a run).
    """
    return set(int(b) for b in run_trace.loc[run_trace["call_idx"] <= step_t, "bin_id"])


def node_to_bins(node):
    return list(range(node.lo, node.hi))


def remaining_true_pos_in_node(node, true_pos_bins, queried_set):
    """Count + ids of true-positive bins inside `node` that have NOT yet been
    paid-for."""
    return [b for b in range(node.lo, node.hi)
            if b in true_pos_bins and b not in queried_set]


def all_nodes_eventful_count(eligible_node_ids, node_by_id, true_pos_bins,
                              queried_set):
    """Of the eligible_node_ids, how many contain >=1 remaining true-positive
    bin (i.e. an eventful candidate exists in the pool)."""
    cnt = 0
    eventful_ids = []
    for nid in eligible_node_ids:
        node = node_by_id.get(nid)
        if node is None:
            continue
        rtp = remaining_true_pos_in_node(node, true_pos_bins, queried_set)
        if rtp:
            cnt += 1
            eventful_ids.append(nid)
    return cnt, eventful_ids


def rebuild_node_index(seg, config):
    """Rebuild the deterministic HTS-EC v0 tree for one segment and return
    {node_id: node}. The tree structure depends only on n_bins + config.top/
    inner_branch, so it can be reconstructed offline without touching the
    oracle / the online decision path."""
    grid, ref_seg, err = load_segment_data(seg)
    if err:
        return None, None, None
    grid = grid.sort_values("bin_idx").reset_index(drop=True)
    n_bins = len(grid)
    proxies = grid[PROXY_COL].values
    labels = grid[LABEL_COL].astype(int).values
    root = build_tree(0, n_bins, proxies, config)
    all_nodes = collect_nodes(root)
    return {n.node_id: n for n in all_nodes}, grid, labels


def safe_literal(val, default):
    """Parse a CSV cell that was originally a Python list/dict. NaN -> default."""
    if pd.isna(val):
        return default
    if isinstance(val, (list, tuple)):
        return list(val)
    try:
        return ast.literal_eval(str(val))
    except Exception:
        return default


def proxy_rank_in_node(bin_idx, node, proxies):
    """0-based rank of bin by descending proxy score within the node."""
    bins = list(range(node.lo, node.hi))
    bins.sort(key=lambda b: -proxies[b])
    return bins.index(bin_idx) if bin_idx in bins else -1


def temporal_quantile_in_node(bin_idx, node):
    """Where in [0,1] the bin falls temporally inside the node."""
    if node.hi <= node.lo:
        return 0.0
    return (bin_idx - node.lo) / max(1, (node.hi - node.lo - 1))


# ---------------------------------------------------------------------------
# Main audit
# ---------------------------------------------------------------------------

def run_audit(input_dir, output_dir):
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load the 5 source CSVs.
    sl = pd.read_csv(input_dir / "hts_ec_v0_scheduler_decision_log.csv")
    pl = pd.read_csv(input_dir / "hts_ec_v0_probe_log.csv")
    tr = pd.read_csv(input_dir / "hts_ec_v0_call_trace.csv")
    fr = pd.read_csv(input_dir / "hts_ec_v0_frontier.csv")
    di = pd.read_csv(input_dir / "hts_ec_v0_diagnostics.csv")

    # Only the StagRepMix-force variant produces actionable stagmix rows, but
    # we still audit the shadow variant too (it logs the same `eligible_nodes`
    # pool without consuming probes, so it tells us whether wider eligibility
    # would have exposed eventful candidates). safe (no flags) has no stag
    # logging -> skip.
    STAG_METHODS = [
        "HTS-EC-safe-StagRepMix-force",
        "HTS-EC-safe-shadow-stag",
    ]
    sl_stag = sl[sl["method"].isin(STAG_METHODS)].copy()
    pl_stag = pl[pl["method"].isin(STAG_METHODS)].copy()

    # Tree structure used by the preflight is the default HtsEcV0Config (same
    # top_branch=4 / inner_branch=2). We rebuild the deterministic tree per
    # segment so we can map node_id -> (lo, hi) offline.
    REF_CONFIG = HtsEcV0Config()
    node_index_cache = {}
    labels_cache = {}
    proxies_cache = {}
    for seg in SEGMENTS:
        seg_id = seg["segment_id"]
        by_id, grid, labels = rebuild_node_index(seg, REF_CONFIG)
        if by_id is None:
            print(f"  SKIP {seg_id}: grid load error")
            continue
        node_index_cache[seg_id] = by_id
        labels_cache[seg_id] = set(int(b) for b, y in enumerate(labels) if y == 1)
        proxies_cache[seg_id] = grid[PROXY_COL].values

    # ---------------- per-step audit table --------------------------------
    print()
    print("=" * 78)
    print("Building rp_opportunity_by_step.csv ...")
    print("=" * 78)
    step_rows = []

    # Group scheduler_decision_log per run and walk in step order. For each
    # step we also need the queried-set reconstruction from call_trace.
    RUN_KEY = ["segment_id", "method", "budget_config", "seed"]
    for run_key, run_sl in sl_stag.groupby(RUN_KEY):
        seg_id, method, budget_config, seed = run_key
        node_by_id = node_index_cache.get(seg_id)
        if node_by_id is None:
            continue
        true_pos_bins = labels_cache[seg_id]
        proxies = proxies_cache[seg_id]

        # call_trace for this run (budget_config is the str in the trace too).
        run_tr = tr[(tr["segment_id"] == seg_id)
                    & (tr["method_id"] == method)
                    & (tr["budget_ratio"].astype(str) == str(budget_config))
                    & (tr["seed"] == seed)].copy()
        run_tr["call_idx"] = run_tr["call_idx"].astype(int)

        run_sl_sorted = run_sl.sort_values("global_step").reset_index(drop=True)

        for _, sl_row in run_sl_sorted.iterrows():
            step_t = int(sl_row["global_step"])
            queried_set = reconstruct_queried_set_at_step(run_tr, step_t)
            eligible_ids = safe_literal(sl_row["stagnation_eligible_nodes_this_step"], [])

            # How many eligible nodes carry a remaining true-positive bin?
            eventful_eligible_count, eventful_eligible_ids = all_nodes_eventful_count(
                eligible_ids, node_by_id, true_pos_bins, queried_set)

            chosen_source = sl_row.get("chosen_source")
            chosen_node_id = sl_row.get("chosen_node_id")
            chosen_bin = sl_row.get("chosen_bin_idx")

            # Remaining true-positive bins in the chosen node at this step.
            chosen_rtp = []
            chosen_node_obj = None
            if isinstance(chosen_node_id, str) and chosen_node_id in node_by_id:
                chosen_node_obj = node_by_id[chosen_node_id]
                chosen_rtp = remaining_true_pos_in_node(
                    chosen_node_obj, true_pos_bins, queried_set)

            # Best-ranked eventful eligible rank (0 = top of the eligible
            # priority list). `ranked_ids` is the scheduler's cross-node sort.
            ranked_ids = safe_literal(sl_row["stagmix_candidate_nodes_ranked"], [])
            best_eventful_rank = None
            for r, nid in enumerate(ranked_ids):
                node = node_by_id.get(nid)
                if node is None:
                    continue
                rtp = remaining_true_pos_in_node(node, true_pos_bins, queried_set)
                if rtp:
                    best_eventful_rank = r
                    break

            # Stagmix strategy (only meaningful when chosen_source == stagmix).
            # Match the probe_log entry for this step.
            strat = None
            strat_pos = None
            if chosen_source == "stagmix":
                pl_match = pl_stag[(pl_stag["segment_id"] == seg_id)
                                   & (pl_stag["method"] == method)
                                   & (pl_stag["budget_config"] == budget_config)
                                   & (pl_stag["seed"] == seed)
                                   & (pl_stag["global_step"] == step_t)]
                if len(pl_match):
                    strat = pl_match.iloc[0].get("stagmix_strategy")
                    strat_pos = pl_match.iloc[0].get("stagmix_strategy_position")

            step_rows.append({
                "run_id": sl_row.get("run_id"),
                "segment_id": seg_id,
                "method": method,
                "budget_config": budget_config,
                "seed": int(seed),
                "global_step": step_t,
                "eligible_node_count": len(eligible_ids),
                "eligible_node_ids": str(eligible_ids),
                "eventful_eligible_count": eventful_eligible_count,
                "eventful_eligible_ids": str(eventful_eligible_ids),
                "chosen_source": chosen_source,
                "chosen_node_id": chosen_node_id,
                "chosen_bin_idx": chosen_bin,
                "chosen_stagmix_strategy": strat,
                "chosen_stagmix_strategy_position": strat_pos,
                "chosen_node_remaining_true_pos": len(chosen_rtp),
                "chosen_node_remaining_true_pos_ids": str(chosen_rtp),
                "best_ranked_eventful_candidate_rank": best_eventful_rank,
                "stagmix_budget_used": int(sl_row.get("diverse_probe_budget_used", 0)),
                "stagmix_budget_cap": int(sl_row.get("diverse_probe_budget_cap", 0)),
            })

    step_df = pd.DataFrame(step_rows)
    step_path = output_dir / "rp_opportunity_by_step.csv"
    step_df.to_csv(step_path, index=False)
    print(f"  Wrote {step_path}  rows={len(step_df)}")

    # ---------------- per-node audit table -------------------------------
    print()
    print("=" * 78)
    print("Building rp_opportunity_by_node.csv ...")
    print("=" * 78)
    # We must record each node that was *ever* eligible on any step.
    # first_eligible_step per (run, node).
    node_rows = {}
    for run_key, run_sl in sl_stag.groupby(RUN_KEY):
        seg_id, method, budget_config, seed = run_key
        node_by_id = node_index_cache.get(seg_id)
        if node_by_id is None:
            continue
        true_pos_bins = labels_cache[seg_id]
        proxies = proxies_cache[seg_id]

        run_tr = tr[(tr["segment_id"] == seg_id)
                    & (tr["method_id"] == method)
                    & (tr["budget_ratio"].astype(str) == str(budget_config))
                    & (tr["seed"] == seed)].copy()
        run_tr["call_idx"] = run_tr["call_idx"].astype(int)

        run_sl_sorted = run_sl.sort_values("global_step").reset_index(drop=True)

        # Track per (run, node_id) the history.
        node_hist = {}  # node_id -> dict with accumulated fields
        chosen_steps_by_node = {}
        pos_hits_by_node = {}

        # First pass: walk steps to fill first_eligible / last_eligible /
        # eligible_step_count and record queried_set at first_eligible.
        for _, sl_row in run_sl_sorted.iterrows():
            step_t = int(sl_row["global_step"])
            eligible_ids = safe_literal(sl_row["stagnation_eligible_nodes_this_step"], [])
            chosen_node_id = sl_row.get("chosen_node_id")
            chosen_source = sl_row.get("chosen_source")
            if not eligible_ids:
                continue
            queried_at_step = reconstruct_queried_set_at_step(run_tr, step_t)

            for nid in eligible_ids:
                node = node_by_id.get(nid)
                if node is None:
                    continue
                if nid not in node_hist:
                    rtp_first = remaining_true_pos_in_node(node, true_pos_bins, queried_at_step)
                    node_hist[nid] = {
                        "run_id": sl_row.get("run_id"),
                        "segment_id": seg_id,
                        "method": method,
                        "budget_config": budget_config,
                        "seed": int(seed),
                        "node_id": nid,
                        "first_eligible_step": step_t,
                        "last_eligible_step": step_t,
                        "eligible_step_count": 1,
                        "n_leaves": node.n_leaves,
                        "unqueried_leaves_at_first_eligible": len(
                            [b for b in range(node.lo, node.hi)
                             if b not in queried_at_step]),
                        "remaining_true_positive_bins_at_first_eligible": len(rtp_first),
                        "remaining_true_positive_bins_at_first_eligible_ids": str(rtp_first),
                        "was_chosen_by_stagmix": False,
                        "stagmix_probe_count": 0,
                        "stagmix_positive_count": 0,
                        "true_positive_proxy_ranks_in_node": sorted(
                            proxy_rank_in_node(b, node, proxies)
                            for b in range(node.lo, node.hi)
                            if b in true_pos_bins),
                        "true_positive_temporal_positions_in_node": sorted(
                            temporal_quantile_in_node(b, node)
                            for b in range(node.lo, node.hi)
                            if b in true_pos_bins),
                    }
                else:
                    h = node_hist[nid]
                    h["last_eligible_step"] = step_t
                    h["eligible_step_count"] += 1

            if chosen_source == "stagmix" and isinstance(chosen_node_id, str):
                h = node_hist.get(chosen_node_id)
                if h is not None:
                    h["was_chosen_by_stagmix"] = True
                    h["stagmix_probe_count"] += 1
                    # Find the actual probe_log row for this step to get the
                    # oracle label (positive recovery).
                    pl_match = pl_stag[(pl_stag["segment_id"] == seg_id)
                                       & (pl_stag["method"] == method)
                                       & (pl_stag["budget_config"] == budget_config)
                                       & (pl_stag["seed"] == seed)
                                       & (pl_stag["global_step"] == step_t)
                                       & (pl_stag["frontier_source"] == "stagmix")]
                    if len(pl_match):
                        y = int(pl_match.iloc[0]["oracle_label"])
                        h["stagmix_positive_count"] += y

        # Second pass: query count of negatives in this node before first
        # eligibility. For nodes that were ever eligible.
        for nid, h in node_hist.items():
            node = node_by_id.get(nid)
            if node is None:
                continue
            first_step = h["first_eligible_step"]
            queried_before = reconstruct_queried_set_at_step(run_tr, first_step)
            neg_queried_in_node = [b for b in range(node.lo, node.hi)
                                   if b in queried_before and b not in true_pos_bins]
            h["queried_negative_positions_before_stagmix"] = str(neg_queried_in_node)
            # remaining_true_positive_bins_when_chosen: for chosen nodes, take
            # the lowest-step stagmix choice and reconstruct the queried_set
            # just before that step.
            if h["was_chosen_by_stagmix"]:
                chosen_steps = [
                    int(s) for s in run_sl_sorted.loc[
                        (run_sl_sorted["chosen_source"] == "stagmix")
                        & (run_sl_sorted["chosen_node_id"] == nid),
                        "global_step"
                    ]
                ]
                if chosen_steps:
                    first_chosen = min(chosen_steps)
                    q_then = reconstruct_queried_set_at_step(run_tr, first_chosen)
                    rtp_then = remaining_true_pos_in_node(node, true_pos_bins, q_then)
                    h["remaining_true_positive_bins_when_chosen"] = len(rtp_then)
                    h["remaining_true_positive_bins_when_chosen_ids"] = str(rtp_then)
                else:
                    h["remaining_true_positive_bins_when_chosen"] = 0
                    h["remaining_true_positive_bins_when_chosen_ids"] = "[]"
            else:
                h["remaining_true_positive_bins_when_chosen"] = -1
                h["remaining_true_positive_bins_when_chosen_ids"] = "N/A"

        for h in node_hist.values():
            node_rows[(h["run_id"], h["node_id"], h["segment_id"],
                       h["budget_config"], h["seed"])] = h

    node_df = pd.DataFrame(list(node_rows.values()))
    node_path = output_dir / "rp_opportunity_by_node.csv"
    node_df.to_csv(node_path, index=False)
    print(f"  Wrote {node_path}  rows={len(node_df)}")

    # ---------------- strategy miss analysis ------------------------------
    print()
    print("=" * 78)
    print("Building rp_strategy_miss_analysis.csv ...")
    print("=" * 78)
    strat_rows = []
    sm_probes = pl_stag[pl_stag["frontier_source"] == "stagmix"].copy()
    for _, prow in sm_probes.iterrows():
        seg_id = prow["segment_id"]
        node_by_id = node_index_cache.get(seg_id)
        if node_by_id is None:
            continue
        true_pos_bins = labels_cache[seg_id]
        proxies = proxies_cache[seg_id]

        run_tr = tr[(tr["segment_id"] == seg_id)
                    & (tr["method_id"] == prow["method"])
                    & (tr["budget_ratio"].astype(str) == str(prow["budget_config"]))
                    & (tr["seed"] == prow["seed"])].copy()
        run_tr["call_idx"] = run_tr["call_idx"].astype(int)

        step_t = int(prow["global_step"])
        queried_set = reconstruct_queried_set_at_step(run_tr, step_t)
        sel_bin = int(prow["bin_idx"])
        node_id = prow["node_id"]
        node = node_by_id.get(node_id) if isinstance(node_id, str) else None
        if node is None:
            continue

        rtp = remaining_true_pos_in_node(node, true_pos_bins, queried_set)
        all_tp_in_node = [b for b in range(node.lo, node.hi) if b in true_pos_bins]

        # Distance to nearest remaining true-positive bin.
        if rtp:
            dist_to_tp = min(abs(sel_bin - b) for b in rtp)
        else:
            dist_to_tp = None

        # Proxy ranks of true-positive bins inside the node.
        tp_ranks = sorted(proxy_rank_in_node(b, node, proxies)
                          for b in all_tp_in_node)

        strat_rows.append({
            "run_id": prow.get("run_id"),
            "segment_id": seg_id,
            "method": prow["method"],
            "budget_config": prow["budget_config"],
            "seed": int(prow["seed"]),
            "global_step": step_t,
            "node_id": node_id,
            "strategy": prow.get("stagmix_strategy"),
            "strategy_position": prow.get("stagmix_strategy_position"),
            "selected_bin": sel_bin,
            "oracle_label": int(prow["oracle_label"]),
            "chosen_node_remaining_true_pos": len(rtp),
            "chosen_node_remaining_true_pos_ids": str(rtp),
            "distance_to_nearest_true_positive_bin": dist_to_tp,
            "true_positive_bins_in_node": len(all_tp_in_node),
            "selected_bin_proxy_rank": proxy_rank_in_node(sel_bin, node, proxies),
            "true_positive_proxy_rank_min": tp_ranks[0] if tp_ranks else None,
            "true_positive_proxy_rank_median": (tp_ranks[len(tp_ranks) // 2]
                                                 if tp_ranks else None),
            "selected_bin_temporal_quantile": temporal_quantile_in_node(sel_bin, node),
            "true_positive_temporal_quantiles": str(sorted(
                temporal_quantile_in_node(b, node) for b in all_tp_in_node)),
        })

    strat_df = pd.DataFrame(strat_rows)
    strat_path = output_dir / "rp_strategy_miss_analysis.csv"
    strat_df.to_csv(strat_path, index=False)
    print(f"  Wrote {strat_path}  rows={len(strat_df)}")

    # ---------------- near-miss stagnation (dataset3_2400_3462) -----------
    print()
    print("=" * 78)
    print("Building rp_near_miss_stagnation.csv ...")
    print("=" * 78)

    # Hard-coded config used by the preflight's three variants.
    KSTAG_BY_METHOD = {
        "HTS-EC-safe": 4,
        "HTS-EC-safe-shadow-stag": 4,
        "HTS-EC-safe-StagRepMix-force": 4,
    }
    STAG_DRILL_THRESH = 0.5
    MIN_UNQUERIED = 2
    MAX_DIVERSE_PER_NODE = 2
    MAX_DIVERSE_SHARE = 0.15

    # Use probe_log + scheduler_log to obtain per-node n_probe/n_pos/unqueried
    # history. We sample the maximum state reached over the run.
    near_miss_rows = []
    SEGMENTS_OF_INTEREST = [
        "dataset3_2400_3462",
        "dataset3_0_1200",
        "dataset3_1200_2400",
    ]
    # For each (segment, run), walk probe_log and accumulate per-node counters.
    # We synthesize every "near-miss" reason for each node that was probed but
    # never became stagmix-eligible.
    for seg in SEGMENTS_OF_INTEREST:
        seg_sl = sl_stag[sl_stag["segment_id"] == seg]
        if not len(seg_sl):
            continue
        for run_key, run_pl in pl_stag[pl_stag["segment_id"] == seg].groupby(
                ["method", "budget_config", "seed"]):
            method, budget_config, seed = run_key
            node_by_id = node_index_cache.get(seg)
            if node_by_id is None:
                continue
            true_pos_bins = labels_cache[seg]

            run_tr = tr[(tr["segment_id"] == seg)
                        & (tr["method_id"] == method)
                        & (tr["budget_ratio"].astype(str) == str(budget_config))
                        & (tr["seed"] == seed)].copy()
            run_tr["call_idx"] = run_tr["call_idx"].astype(int)
            budget_abs = int(run_tr["budget_abs"].iloc[0]) if len(run_tr) else 0

            # Accumulate per-node counters across time.
            node_state = {}  # node_id -> dict(n_probe, n_pos, n_neg,
                             #                 max_unqueried, ever_expanded,
                             #                 ever_pruned, min_posterior_mean)
            # We replay tree/fine/stagmix probes in call_idx order. Each
            # oracle answer folds into every ancestor's n_probe/n_pos/n_neg
            # using the same evidence_bins dedup that the runner does (we
            # emulate it so offline counts match online counts exactly).
            # Build ancestor chains via find_leaf_node + parent_id walk.
            from garc_eval.hts_ec_v0 import find_leaf_node, posterior_mean
            root_lookup = None
            # We need the tree root. Rebuild just to find nodes; root is the
            # one with parent_id is None.
            roots = [n for n in node_by_id.values() if n.parent_id is None]
            root = roots[0] if roots else None
            if root is None:
                continue

            # Replay labels to recover n_probe etc. per node.
            for _, trow in run_tr.sort_values("call_idx").iterrows():
                y = 1 if trow["oracle_label"] == "positive" else 0
                b = int(trow["bin_id"])
                leaf = find_leaf_node(b, root)
                cur = leaf
                while cur is not None:
                    s = node_state.setdefault(cur.node_id, {
                        "n_probe": 0, "n_pos": 0, "n_neg": 0,
                        "max_unqueried": cur.n_leaves,
                        "ever_expanded": False,
                        "ever_pruned": False,
                        "min_posterior_mean": 1.0,
                    })
                    s["n_probe"] += 1
                    if y == 1:
                        s["n_pos"] += 1
                    else:
                        s["n_neg"] += 1
                    s["min_posterior_mean"] = min(
                        s["min_posterior_mean"],
                        posterior_mean(cur))
                    cur = node_by_id.get(cur.parent_id) if cur.parent_id else None

            # For each probed tree node, diagnose the eligibility gate at the
            # step where it had the MOST probes (since the gate was hardest
            # to satisfy at the end).
            run_sl_seg = sl_stag[(sl_stag["segment_id"] == seg)
                                 & (sl_stag["method"] == method)
                                 & (sl_stag["budget_config"] == budget_config)
                                 & (sl_stag["seed"] == seed)]
            ever_eligible_ids = set()
            for _, sl_row in run_sl_seg.iterrows():
                for nid in safe_literal(sl_row["stagnation_eligible_nodes_this_step"], []):
                    ever_eligible_ids.add(nid)

            # For nodes that were PROBED but never became eligible, attribute
            # reasons.
            for nid, s in node_state.items():
                if nid in ever_eligible_ids:
                    continue
                node = node_by_id.get(nid)
                if node is None:
                    continue
                k_stag = KSTAG_BY_METHOD.get(method, 4)
                fail_nprobe = s["n_probe"] < k_stag
                fail_has_pos = s["n_pos"] > 0
                fail_posterior_gate = s["min_posterior_mean"] >= STAG_DRILL_THRESH
                fail_expanded = False  # cannot tell from probe_log alone; we
                                       # only mark as expanded if a child of
                                       # this node appeared in the probe log
                # If any child node was ever probed, the parent was expanded.
                for other_nid in node_state:
                    other = node_by_id.get(other_nid)
                    if other is None or other_nid == nid:
                        continue
                    if other.parent_id == nid and node_state[other_nid]["n_probe"] > 0:
                        fail_expanded = True
                        break
                cur_unqueried = max(0, node.n_leaves - s["n_probe"])
                fail_unqueried_gate = cur_unqueried < MIN_UNQUERIED
                # Budget / cap reason: only meaningful if probe fell on the
                # final step (last call_idx). Otherwise it would have had
                # budget. We mark it True only when, at the time the node had
                # enough probes, the global stag budget was already spent.
                # As an offline approximation, leave it False here: we surface
                # it via separate per-run summary in the printout.
                near_miss_rows.append({
                    "run_id": run_pl.iloc[0].get("run_id") if len(run_pl) else None,
                    "segment_id": seg,
                    "method": method,
                    "budget_config": budget_config,
                    "seed": int(seed),
                    "node_id": nid,
                    "max_n_probe": s["n_probe"],
                    "max_n_pos_probe": s["n_pos"],
                    "max_n_neg_probe": s["n_neg"],
                    "max_unqueried_leaves": cur_unqueried,
                    "min_posterior_mean": s["min_posterior_mean"],
                    "ever_expanded": fail_expanded,
                    "ever_pruned": False,
                    "fail_reason_n_probe_lt_k_stag": bool(fail_nprobe),
                    "fail_reason_has_positive": bool(fail_has_pos),
                    "fail_reason_posterior_mean_gate": bool(fail_posterior_gate),
                    "fail_reason_expanded": bool(fail_expanded),
                    "fail_reason_unqueried_gate": bool(fail_unqueried_gate),
                    "fail_reason_budget_or_cap": False,
                    "was_ever_eligible": False,
                })

    near_miss_df = pd.DataFrame(near_miss_rows)
    near_path = output_dir / "rp_near_miss_stagnation.csv"
    near_miss_df.to_csv(near_path, index=False)
    print(f"  Wrote {near_path}  rows={len(near_miss_df)}")

    # ---------------- key conclusion printout ----------------------------
    print()
    print("=" * 78)
    print("KEY ATTRIBUTION (the 3 numbers that decide the next branch)")
    print("=" * 78)

    # X: of stagmix-chosen nodes (force variant), how many had >=1 remaining
    #    true-positive bin at the moment stagmix picked them.
    force_chosen = step_df[
        (step_df["method"] == "HTS-EC-safe-StagRepMix-force")
        & (step_df["chosen_source"] == "stagmix")
    ]
    n_chosen = len(force_chosen)
    if n_chosen:
        x = int((force_chosen["chosen_node_remaining_true_pos"] > 0).sum())
    else:
        x = 0
    print(f"  X = {x} / {n_chosen} stagmix-chosen steps had a remaining "
          f"true-positive bin in the chosen node.")

    # Y: of all eligible steps (force + shadow), how many had >=1 eligible
    #    node (in the pool) with >=1 remaining true-positive bin?
    eligible_steps = step_df[step_df["eligible_node_count"] > 0]
    n_elig_steps = len(eligible_steps)
    if n_elig_steps:
        y = int((eligible_steps["eventful_eligible_count"] > 0).sum())
    else:
        y = 0
    print(f"  Y = {y} / {n_elig_steps} eligible steps had >=1 eventful "
          f"eligible node in the pool.")

    # Per-method breakdown (force vs shadow).
    print()
    print("  Per-method eligible steps (pool had eventful candidate?):")
    for meth in STAG_METHODS:
        sl_m = eligible_steps[eligible_steps["method"] == meth]
        if len(sl_m):
            y_m = int((sl_m["eventful_eligible_count"] > 0).sum())
        else:
            y_m = 0
        print(f"    {meth:38s} Y={y_m:4d} / {len(sl_m):4d}")

    # Per-segment eligible steps (force only).
    print()
    print("  Per-segment (force) eligible steps:")
    force_elig = eligible_steps[
        eligible_steps["method"] == "HTS-EC-safe-StagRepMix-force"]
    for seg, grp in force_elig.groupby("segment_id"):
        n = len(grp)
        y_seg = int((grp["eventful_eligible_count"] > 0).sum())
        print(f"    {seg:28s} eligible-steps={n:4d}  eventful-eligible-steps={y_seg:4d}")

    # Z: dataset3_2400_3462 near-miss reason breakdown.
    print()
    print("  Z (dataset3_2400_3462 near-miss reasons, force only):")
    nm_force = near_miss_df[
        (near_miss_df["segment_id"] == "dataset3_2400_3462")
        & (near_miss_df["method"] == "HTS-EC-safe-StagRepMix-force")
    ]
    if len(nm_force):
        reasons = [
            "fail_reason_n_probe_lt_k_stag",
            "fail_reason_has_positive",
            "fail_reason_posterior_mean_gate",
            "fail_reason_expanded",
            "fail_reason_unqueried_gate",
            "fail_reason_budget_or_cap",
        ]
        for r in reasons:
            print(f"    {r:42s} {int(nm_force[r].sum()):4d} / {len(nm_force):4d}")
    else:
        print("    (no probed-but-ineligible nodes logged for this segment)")

    print()
    print("=" * 78)
    print("DECISION BRANCH")
    print("=" * 78)
    if n_chosen and x > 0:
        print("  -> X > 0  : RepMix STRATEGY is the problem (right node, wrong bin)")
        print("              Fix: redesign RepMix strategy (gap-midpoint etc.)")
    elif n_elig_steps and y > 0:
        print("  -> X = 0 but Y > 0  : CROSS-NODE PRIORITY is the problem")
        print("                        (eventful candidates existed but were not picked)")
        print("                        Fix: revise cross-node priority; do NOT touch strategy")
    else:
        print("  -> Y = 0  : ELIGIBILITY / predicate is the problem")
        print("             (no eventful node ever satisfied the stagnation gate)")
        print("             Fix: relax k_stag or move posterior_mean from hard gate")
        print("                 to ranking feature")
    print("=" * 78)


def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", default="outputs/hts_ec_v0_phase2a_rp_preflight_v1")
    p.add_argument("--output", default="outputs/hts_ec_v0_phase2a_rp_opportunity_v1")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_audit(args.input, args.output)