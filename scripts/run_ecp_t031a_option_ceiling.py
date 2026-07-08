"""T031a — Interval-level option closed-loop ceiling.

Tests whether temporally extended options (B7-style expansion,
anchor-bridge, certify-boundary, merge-gap) can recover the recall
gap between ECP-c2 and strong baselines like B7.

Options (multi-step, each consumes >= 1 oracle call):
  1. DISCOVER            — highest-proxy unqueried (cost 1)
  2. CERTIFY             — ECP certify boundary (cost 1)
  3. BRIDGE              — gap-bridge (cost 1)
  4. ZERO_PROXY_VDC      — VDC low-discrepancy (cost 1)
  5. B7_EXPAND_FIXED_R3  — around positive anchor, query ±1,±2,±3 (cost up to 6)
  6. B7_EXPAND_STOP_NEG  — like R3 but stops direction on negative (cost variable)
  7. ANCHOR_BRIDGE       — isolated positive: bidirectional local sweep (cost up to 4)
  8. CERTIFY_BOUNDARY    — interval boundary refinement (cost up to 4)
  9. MERGE_GAP           — gap query between nearby anchors (cost 1-3)
  10. SUPPRESS_ABSTAIN   — suppress low-conf single-bin intervals (cost 0)

Ceiling: closed-loop oracle. At each step, enumerate ALL applicable options,
simulate each using true_labels, compute marginal event-utility per call,
pick max, execute option's queries through oracle.

Key pass condition: realcartest_3200_3830 ceiling significantly > ECP-c2 (0.286),
approaching B7-strict-replay (0.429-0.571).

Outputs:
  outputs/ecp_event_coverage_policy_v1/t031a_option_frontier.csv
  outputs/ecp_event_coverage_policy_v1/t031a_option_trace.csv
  outputs/ecp_event_coverage_policy_v1/t031a_option_report.md
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from run_ecp_t027_bandit import (  # noqa: E402
    SEGMENTS, BUDGET_RATIOS, SEEDS, PROXY_COL, LABEL_COL, VARIANTS,
    load_segment_data, AlignedOracle, group_positive_bins, evaluate_events,
    candidate_targets_module, formed_intervals,
)
from run_ecp_t028c_ceiling import marginal_utility, iou_intervals  # noqa: E402
from run_ecp_t028e0_ceiling import candidate_targets_extended  # noqa: E402

OUT = REPO_ROOT / "outputs" / "ecp_event_coverage_policy_v1"
OUT.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Option definitions — each returns (is_applicable: bool, query_sequence: List[int], cost: int)
# ---------------------------------------------------------------------------
def option_discover(cands):
    if cands.get("DISCOVER") is not None:
        return [cands["DISCOVER"]]
    return None


def option_certify(cands):
    if cands.get("CERTIFY") is not None:
        return [cands["CERTIFY"]]
    return None


def option_bridge(cands):
    if cands.get("BRIDGE") is not None:
        return [cands["BRIDGE"]]
    return None


def option_zero_proxy_vdc(cands):
    if cands.get("ZERO_PROXY_VDC") is not None:
        return [cands["ZERO_PROXY_VDC"]]
    return None


def option_b7_expand_fixed_r3(queried_pos, queried, all_bins):
    """B7_EXPAND_FIXED_R3: expand ±3 around each unexpanded positive anchor."""
    # Find anchors that haven't been fully expanded
    for anchor_raw in sorted(queried_pos, key=lambda b: int(b)):
        anchor = int(anchor_raw)
        unqueried_neighbors = []
        for offset in [1, -1, 2, -2, 3, -3]:
            nb = anchor + offset
            if nb in all_bins and nb not in queried:
                unqueried_neighbors.append(nb)
        if unqueried_neighbors:
            # Take first unexpanded anchor, return its expansion plan
            # Fixed R3: query ALL unqueried neighbors within ±3
            return unqueried_neighbors
    return None


def option_b7_expand_stop_neg(queried_pos, queried, all_bins, true_labels):
    """B7_EXPAND_STOP_NEG: expand ±3 but stop direction on negative."""
    for anchor_raw in sorted(queried_pos, key=lambda b: int(b)):
        anchor = int(anchor_raw)
        plan = []
        # Expand right
        for offset in range(1, 4):
            nb = anchor + offset
            if nb not in all_bins or nb in queried:
                break
            plan.append(nb)
            # Check if this would be negative
            if nb in true_labels and not true_labels[nb]:
                break
        # Expand left
        for offset in range(1, 4):
            nb = anchor - offset
            if nb not in all_bins or nb in queried:
                break
            plan.append(nb)
            if nb in true_labels and not true_labels[nb]:
                break
        if plan:
            return plan
    return None


def option_anchor_bridge(queried_pos, queried, all_bins):
    """ANCHOR_BRIDGE: for an isolated positive anchor (no adjacent positive
    in +-3), do bidirectional local sweep to find nearest positive."""
    pos_sorted = sorted(queried_pos)
    for anchor in pos_sorted:
        anchor = int(anchor)
        # Check if isolated: no other positive within ±2
        has_nearby_pos = any(
            p != anchor and abs(p - anchor) <= 2
            for p in pos_sorted
        )
        if has_nearby_pos:
            continue
        # Bridge: sweep ±1, ±2 on each side (up to 4 calls)
        plan = []
        for offset in [1, -1, 2, -2]:
            nb = anchor + offset
            if nb in all_bins and nb not in queried:
                plan.append(nb)
        if plan:
            return plan
    return None


def option_certify_boundary(queried_pos, queried, all_bins, grid_sorted):
    """CERTIFY_BOUNDARY: around a candidate interval, query 1-2 boundary bins."""
    formed = formed_intervals(queried_pos, grid_sorted)
    if not formed:
        return None
    # Pick the interval with the most unqueried boundary bins
    best_plan = None
    best_count = 0
    for (s, e) in formed:
        plan = []
        # Outside boundaries
        if s - 1 in all_bins and s - 1 not in queried:
            plan.append(s - 1)
        if e + 1 in all_bins and e + 1 not in queried:
            plan.append(e + 1)
        # Inside boundaries (adjacent to interval edge but unqueried)
        if s + 1 in all_bins and s + 1 not in queried and s + 1 not in queried_pos:
            plan.append(s + 1)
        if e - 1 in all_bins and e - 1 not in queried and e - 1 not in queried_pos:
            plan.append(e - 1)
        if len(plan) > best_count:
            best_count = len(plan)
            best_plan = plan
    return best_plan


def option_merge_gap(queried_pos, queried, all_bins):
    """MERGE_GAP: between two nearby positive anchors/intervals, query gap."""
    pos_sorted = sorted(queried_pos)
    # Find pairs within gap ≤ 6
    best_plan = None
    best_gap = 1e9
    for i in range(len(pos_sorted) - 1):
        a, b = int(pos_sorted[i]), int(pos_sorted[i + 1])
        gap = b - a
        if 3 <= gap <= 8:
            # Find unqueried bins in the gap
            plan = [x for x in range(a + 1, b) if x in all_bins and x not in queried]
            if plan and gap < best_gap:
                best_gap = gap
                best_plan = plan[:4]  # max 4 calls
    return best_plan


def option_suppress_abstain(queried_pos, grid_sorted, ref_seg):
    """SUPPRESS_ABSTAIN: suppress single-bin low-confidence intervals (cost 0).
    Returns empty list (no queries) but the ceiling may choose it for precision gain."""
    formed = formed_intervals(queried_pos, grid_sorted)
    if not formed:
        return None
    # Check if there are single-bin intervals
    single_bin = [(s, e) for (s, e) in formed if s == e]
    if not single_bin:
        return None
    # This option has cost 0 — it "suppresses" the single-bin intervals
    # We signal applicability by returning an empty list
    return []  # cost 0 option


# ---------------------------------------------------------------------------
# Option registry
# ---------------------------------------------------------------------------
OPTIONS = [
    ("DISCOVER", option_discover, 1),
    ("CERTIFY", option_certify, 1),
    ("BRIDGE", option_bridge, 1),
    ("ZERO_PROXY_VDC", option_zero_proxy_vdc, 1),
    ("B7_EXPAND_FIXED_R3", option_b7_expand_fixed_r3, None),  # cost varies
    ("B7_EXPAND_STOP_NEG", option_b7_expand_stop_neg, None),
    ("ANCHOR_BRIDGE", option_anchor_bridge, None),
    ("CERTIFY_BOUNDARY", option_certify_boundary, None),
    ("MERGE_GAP", option_merge_gap, None),
    ("SUPPRESS_ABSTAIN", option_suppress_abstain, 0),
]


# ---------------------------------------------------------------------------
# Option simulation: given a query sequence and true labels, compute
# the marginal event-utility contributed by executing all these queries
# ---------------------------------------------------------------------------
def simulate_option_utility(query_seq, true_labels, queried, queried_pos,
                            grid_sorted, bin_to_t, ref_seg, n_ref, cost):
    """Simulate executing query_seq and return total marginal utility."""
    if not query_seq:
        return 0.0, 0, 0.0

    # Start from current state
    cur_queried = set(queried)
    cur_pos = set(queried_pos)
    total_u = 0.0
    total_new_events = 0
    total_iou_gain = 0.0

    for target in query_seq:
        tl = "positive" if true_labels.get(target, False) else "negative"
        u, neh, ig = marginal_utility(cur_pos, target, tl, grid_sorted,
                                       bin_to_t, ref_seg, n_ref)
        total_u += u
        total_new_events += neh
        total_iou_gain += ig
        cur_queried.add(target)
        if tl == "positive":
            cur_pos.add(target)

    # Subtract option cost penalty
    cost_penalty = 0.05 * cost
    total_u -= cost_penalty

    return total_u, total_new_events, total_iou_gain


# ---------------------------------------------------------------------------
# Closed-loop oracle ceiling with interval options
# ---------------------------------------------------------------------------
def run_option_ceiling(grid, ref_seg, seg_id, budget_abs, budget_ratio, seed, rng):
    n_bins = len(grid)
    oracle = AlignedOracle(grid, seg_id, "ECP-option-ceiling", seed, budget_abs, budget_ratio)
    grid_sorted = grid.sort_values("bin_idx").reset_index(drop=True)
    bin_to_t = dict(zip(grid_sorted["bin_idx"],
                        zip(grid_sorted["local_t_start"], grid_sorted["local_t_end"])))
    proxies = dict(zip(grid_sorted["bin_idx"], grid_sorted[PROXY_COL]))
    true_labels = dict(zip(grid_sorted["bin_idx"], grid_sorted[LABEL_COL]))
    all_bins = grid_sorted["bin_idx"].tolist()
    queried, queried_pos = set(), set()
    n_ref = len(ref_seg) if ref_seg is not None else 0
    zp_budget_used = 0
    step_count = 0
    trace_rows = []
    option_calls = {}

    while oracle.calls < oracle.budget_abs:
        unqueried = [b for b in all_bins if b not in queried]
        if not unqueried:
            break
        step_count += 1

        # Compute ECP base candidates (for DISCOVER/CERTIFY/BRIDGE/VDC)
        cfg = VARIANTS["v2"]
        # Ensure pos_set has ints for downstream arithmetic
        pos_for_cands = set(int(b) for b in queried_pos)
        cands = candidate_targets_extended(
            grid_sorted, proxies, bin_to_t, queried, pos_for_cands, unqueried,
            all_bins, zp_budget_used, budget_abs, cfg,
        )

        zp_share_val = (sum(1 for b in unqueried if proxies.get(b, -1) == 0.0)
                        / len(unqueried)) if unqueried else 0.0

        # State before
        formed_before = formed_intervals(queried_pos, grid_sorted)
        ev_before = evaluate_events(formed_before, ref_seg) if n_ref > 0 else {
            "event_recall": 0, "event_precision": 0, "unique_event_coverage": 0}

        # Enumerate all options
        best_option = None
        best_query_seq = None
        best_utility_per_call = -1e9
        best_total_u = 0

        for opt_name, opt_fn, fixed_cost in OPTIONS:
            # Get query sequence
            query_seq = None
            if opt_name in ("DISCOVER", "CERTIFY", "BRIDGE", "ZERO_PROXY_VDC"):
                query_seq = opt_fn(cands)
            elif opt_name == "B7_EXPAND_FIXED_R3":
                query_seq = opt_fn(queried_pos, queried, all_bins)
            elif opt_name == "B7_EXPAND_STOP_NEG":
                query_seq = opt_fn(queried_pos, queried, all_bins, true_labels)
            elif opt_name == "ANCHOR_BRIDGE":
                query_seq = opt_fn(queried_pos, queried, all_bins)
            elif opt_name == "CERTIFY_BOUNDARY":
                query_seq = opt_fn(queried_pos, queried, all_bins, grid_sorted)
            elif opt_name == "MERGE_GAP":
                query_seq = opt_fn(queried_pos, queried, all_bins)
            elif opt_name == "SUPPRESS_ABSTAIN":
                query_seq = opt_fn(queried_pos, grid_sorted, ref_seg)

            if query_seq is None:
                continue

            cost = fixed_cost if fixed_cost is not None else len(query_seq)
            if cost == 0:
                # Suppress: check if it would improve precision
                # Simulate: would suppressing single-bin intervals help?
                formed_now = formed_intervals(queried_pos, grid_sorted)
                single_bin = [(s, e) for (s, e) in formed_now if s == e]
                if not single_bin:
                    continue
                # Compute precision gain from suppressing
                multi_bin = [(s, e) for (s, e) in formed_now if s != e]
                ev_without_single = evaluate_events(multi_bin, ref_seg) if n_ref > 0 else {"event_precision": ev_before["event_precision"]}
                precision_gain = ev_without_single.get("event_precision", 0) - ev_before.get("event_precision", 0)
                if precision_gain > 0:
                    total_u = 0.5 * precision_gain  # free utility from precision gain
                    if total_u > best_utility_per_call:
                        best_utility_per_call = total_u
                        best_total_u = total_u
                        best_option = opt_name
                        best_query_seq = query_seq
                continue

            if oracle.calls + cost > oracle.budget_abs:
                # Option costs too much for remaining budget
                continue

            # Simulate option using true labels
            total_u, neh, ig = simulate_option_utility(
                query_seq, true_labels, queried, queried_pos,
                grid_sorted, bin_to_t, ref_seg, n_ref, cost,
            )
            utility_per_call = total_u / cost if cost > 0 else total_u

            # Exploration bonus for zp options in high-zp regime
            if opt_name == "ZERO_PROXY_VDC" and zp_share_val >= 0.30:
                utility_per_call += 0.04

            if utility_per_call > best_utility_per_call:
                best_utility_per_call = utility_per_call
                best_total_u = total_u
                best_option = opt_name
                best_query_seq = query_seq

        if best_option is None or best_query_seq is None:
            break

        # Execute all queries in the selected option
        n_positive_in_option = 0
        for target in best_query_seq:
            is_zp = "ZERO_PROXY" in best_option
            if is_zp:
                zp_budget_used += 1
            label = oracle.query_unit(target, "ECP_option_" + best_option, best_option)
            queried.add(target)
            if label == "positive":
                queried_pos.add(int(target))
                n_positive_in_option += 1

        option_calls[best_option] = option_calls.get(best_option, 0) + 1

        # State after
        formed_after = formed_intervals(queried_pos, grid_sorted)
        ev_after = evaluate_events(formed_after, ref_seg) if n_ref > 0 else {
            "event_recall": 0, "event_precision": 0, "unique_event_coverage": 0}

        trace_rows.append({
            "segment_id": seg_id, "seed": seed, "budget_ratio": budget_ratio,
            "call_idx": step_count, "option": best_option,
            "n_queries": len(best_query_seq), "cost": len(best_query_seq),
            "n_pos_in_option": n_positive_in_option,
            "utility_total": round(best_total_u, 4),
            "utility_per_call": round(best_utility_per_call, 4),
            "recall_before": round(ev_before.get("event_recall", 0), 4),
            "recall_after": round(ev_after.get("event_recall", 0), 4),
            "precision_before": round(ev_before.get("event_precision", 0), 4),
            "precision_after": round(ev_after.get("event_precision", 0), 4),
            "zp_share": round(zp_share_val, 3),
        })

    formed = formed_intervals(queried_pos, grid_sorted)
    ev = evaluate_events(formed, ref_seg) if n_ref > 0 else {"event_precision": 0, "event_recall": 0, "unique_event_coverage": 0}
    return {
        "event_recall": ev["event_recall"],
        "event_precision": ev["event_precision"],
        "unique_event_coverage": ev["unique_event_coverage"],
        "oracle_calls": oracle.calls,
        "option_calls": option_calls,
        "trace_rows": trace_rows,
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    rng = np.random.default_rng(20260711)
    frontier_rows = []
    option_call_rows = []
    trace_all = []

    for seg in SEGMENTS:
        grid, ref_seg, err = load_segment_data(seg)
        if grid is None:
            continue
        n_bins = len(grid)
        sid = seg["segment_id"]
        for br in BUDGET_RATIOS:
            for seed in SEEDS:
                budget_abs = max(1, int(round(br * n_bins)))
                res = run_option_ceiling(grid, ref_seg, sid, budget_abs, br, seed, rng)
                frontier_rows.append({
                    "variant": "option_ceiling",
                    "segment_id": sid, "seed": seed,
                    "budget_ratio": br, "budget_abs": budget_abs,
                    "event_recall": round(res["event_recall"], 4),
                    "event_precision": round(res["event_precision"], 4),
                    "unique_event_coverage": res["unique_event_coverage"],
                    "oracle_calls": res["oracle_calls"],
                })
                for opt, count in res["option_calls"].items():
                    option_call_rows.append({
                        "segment_id": sid, "seed": seed,
                        "budget_ratio": br, "option": opt, "count": count,
                    })
                trace_all.extend(res["trace_rows"])
        print(f"done {sid}")

    frontier = pd.DataFrame(frontier_rows)
    frontier.to_csv(OUT / "t031a_option_frontier.csv", index=False)
    trace_df = pd.DataFrame(trace_all)
    trace_df.to_csv(OUT / "t031a_option_trace.csv", index=False)
    options = pd.DataFrame(option_call_rows)
    options.to_csv(OUT / "t031a_option_usage.csv", index=False)

    # Aggregate
    pf_agg = frontier.groupby(["segment_id", "budget_ratio"]).agg(
        recall=("event_recall", "mean"),
        prec=("event_precision", "mean"),
    ).reset_index()

    # Compare to baselines
    hts = pd.read_csv(REPO_ROOT / "outputs/hts_ec_v0_strict_v1/hts_ec_v0_frontier.csv")
    ecp_c2 = pd.read_csv(OUT / "t028e1_loso_frontier.csv")
    c2_agg = ecp_c2[ecp_c2["variant"] == "c2_loso"].groupby(
        ["held_out_segment", "budget_ratio"]).agg(
        recall=("event_recall", "mean"), prec=("event_precision", "mean")).reset_index()
    c2_agg["segment_id"] = c2_agg["held_out_segment"]

    baseline_map = {"B7-strict-replay": "B7", "D3-norepair-core-strict": "D3",
                    "EventLift-discover-certify": "EventLift"}
    bl_agg_all = []
    for mid, label in baseline_map.items():
        sub = hts[hts["method_id"] == mid]
        if len(sub) == 0:
            continue
        agg = sub.groupby(["segment_id", "budget_ratio"]).agg(
            recall=("event_recall", "mean"), prec=("event_precision", "mean")).reset_index()
        agg["method"] = label
        bl_agg_all.append(agg)
    bl_all = pd.concat(bl_agg_all, ignore_index=True)

    all_seg_ids = [s["segment_id"] for s in SEGMENTS]

    # Report
    L = []
    L.append("# T031a — Interval-option closed-loop ceiling\n")
    L.append(
        "Closed-loop oracle ceiling with 10 interval-level options. "
        "Multi-step options (B7_EXPAND, ANCHOR_BRIDGE, etc.) simulate multiple "
        "queries internally; utility is computed per-call. "
        "Ceiling uses true labels to evaluate options offline — NOT strict replay.\n"
    )

    L.append("## Recall ceiling: options vs baselines\n")
    L.append("| segment | budget | OptionCeil | ECP-c2 | B7 | D3 | EventLift |")
    L.append("|---|---|---|---|---|---|---|")
    for seg in all_seg_ids:
        for br in BUDGET_RATIOS:
            pf = pf_agg[(pf_agg.segment_id == seg) & (pf_agg.budget_ratio == br)]
            c2 = c2_agg[(c2_agg.segment_id == seg) & (c2_agg.budget_ratio == br)]
            if len(pf) == 0:
                continue
            pf_r = pf.iloc[0]["recall"]
            pf_p = pf.iloc[0]["prec"]
            cells = [f"R{pf_r:.3f}/P{pf_p:.3f}"]
            for m in ["ECP-c2", "B7", "D3", "EventLift"]:
                if m == "ECP-c2":
                    sub = c2
                    if len(sub):
                        cells.append(f"R{sub.iloc[0]['recall']:.3f}")
                    else:
                        cells.append("-")
                else:
                    sub = bl_all[(bl_all.method == m) & (bl_all.segment_id == seg)
                                 & (bl_all.budget_ratio == br)]
                    if len(sub):
                        cells.append(f"R{sub.iloc[0]['recall']:.3f}")
                    else:
                        cells.append("-")
            L.append(f"| {seg} | {br:.2f} | " + " | ".join(cells) + " |")

    L.append("\n## Key deltas: OptionCeil vs ECP-c2 vs B7\n")
    L.append("| segment | budget | option_recall | c2_recall | B7_recall | opt-c2 | opt-B7 |")
    L.append("|---|---|---|---|---|---|---|")
    for seg in all_seg_ids:
        for br in BUDGET_RATIOS:
            pf = pf_agg[(pf_agg.segment_id == seg) & (pf_agg.budget_ratio == br)]
            c2 = c2_agg[(c2_agg.segment_id == seg) & (c2_agg.budget_ratio == br)]
            b7 = bl_all[(bl_all.method == "B7") & (bl_all.segment_id == seg)
                        & (bl_all.budget_ratio == br)]
            if len(pf) == 0:
                continue
            pf_r = pf.iloc[0]["recall"]
            c2_r = c2.iloc[0]["recall"] if len(c2) else 0
            b7_r = b7.iloc[0]["recall"] if len(b7) else 0
            L.append(f"| {seg} | {br:.2f} | {pf_r:.3f} | {c2_r:.3f} | {b7_r:.3f} | {pf_r-c2_r:+.3f} | {pf_r-b7_r:+.3f} |")

    # Option usage
    L.append("\n## Option usage (mean calls)\n")
    L.append("| option | mean_calls |")
    L.append("|---|---|")
    opt_agg = options.groupby("option")["count"].mean().sort_values(ascending=False)
    for opt, cnt in opt_agg.items():
        L.append(f"| {opt} | {cnt:.1f} |")

    # Per-video summary
    L.append("\n## Per-video mean recall\n")
    for video in ["realcartest", "dataset3"]:
        L.append(f"\n### {video}\n")
        pf_v = pf_agg[pf_agg.segment_id.str.startswith(video)]
        c2_v = c2_agg[c2_agg.segment_id.str.startswith(video)]
        L.append(f"- Option ceiling: recall={pf_v['recall'].mean():.3f}, prec={pf_v['prec'].mean():.3f}")
        L.append(f"- ECP-c2: recall={c2_v['recall'].mean():.3f}")
        for m in ["B7", "D3", "EventLift"]:
            sub = bl_all[(bl_all.method == m) & bl_all.segment_id.str.startswith(video)]
            if len(sub):
                L.append(f"- {m}: recall={sub['recall'].mean():.3f}")

    # Pass/fail
    rc_opt = pf_agg[pf_agg.segment_id.str.startswith("realcartest")]["recall"].mean()
    rc_c2 = c2_agg[c2_agg.segment_id.str.startswith("realcartest")]["recall"].mean()
    rc_b7 = bl_all[(bl_all.method == "B7") & bl_all.segment_id.str.startswith("realcartest")]["recall"].mean()

    d3_opt = pf_agg[pf_agg.segment_id.str.startswith("dataset3")]["recall"].mean()
    d3_c2 = c2_agg[c2_agg.segment_id.str.startswith("dataset3")]["recall"].mean()

    # Focus on realcartest_3200_3830
    rc3830_opt = pf_agg[(pf_agg.segment_id == "realcartest_3200_3830")
                        & (pf_agg.budget_ratio == 0.30)]["recall"].values
    rc3830_b7 = bl_all[(bl_all.method == "B7") & (bl_all.segment_id == "realcartest_3200_3830")
                       & (bl_all.budget_ratio == 0.30)]["recall"].values
    rc3830_opt_val = rc3830_opt[0] if len(rc3830_opt) else 0
    rc3830_b7_val = rc3830_b7[0] if len(rc3830_b7) else 0

    L.append(f"\n## Pass/fail\n")
    L.append(f"- realcartest: option={rc_opt:.3f}, c2={rc_c2:.3f}, B7={rc_b7:.3f}")
    L.append(f"- dataset3: option={d3_opt:.3f}, c2={d3_c2:.3f}")
    L.append(f"- realcartest_3200_3830 @0.30: option={rc3830_opt_val:.3f}, B7={rc3830_b7_val:.3f}")

    if rc_opt > rc_c2 + 0.02:
        L.append(f"- **PASS**: Option ceiling boosts realcartest recall +{rc_opt-rc_c2:.3f} over c2.")
    else:
        L.append(f"- **FAIL**: Option ceiling ({rc_opt:.3f}) does not significantly exceed c2 ({rc_c2:.3f}).")

    if rc3830_opt_val >= rc3830_b7_val - 0.05:
        L.append(f"- **PASS**: B7_EXPAND recovers realcartest_3200_3830 ({rc3830_opt_val:.3f} vs B7 {rc3830_b7_val:.3f}).")
    else:
        L.append(f"- **FAIL**: B7_EXPAND ({rc3830_opt_val:.3f}) still far from B7 ({rc3830_b7_val:.3f}) on realcartest_3200_3830.")

    L.append(
        "\n- This is an OFFLINE CEILING. If option ceiling significantly exceeds c2 "
        "and approaches B7 on realcartest_3200_3830, proceed to T031b (train option "
        "policy for strict replay)."
    )

    md = OUT / "t031a_option_report.md"
    md.write_text("\n".join(L))
    print(f"\nwrote {OUT / 't031a_option_frontier.csv'}")
    print(f"wrote {OUT / 't031a_option_trace.csv'}")
    print(f"wrote {OUT / 't031a_option_usage.csv'}")
    print(f"wrote {md}")

    print(f"\n=== Summary ===")
    print(f"realcartest: option={rc_opt:.3f}, c2={rc_c2:.3f}, B7={rc_b7:.3f}")
    print(f"rc_3200_3830 @0.30: option={rc3830_opt_val:.3f}, B7={rc3830_b7_val:.3f}")
    print(f"dataset3: option={d3_opt:.3f}, c2={d3_c2:.3f}")


if __name__ == "__main__":
    main()
