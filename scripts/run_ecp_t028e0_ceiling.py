"""T028e-0 — proxy-free candidate generator ceiling audit (ECP Step 4e).

Extends the candidate arm set with proxy-free families that do NOT depend on
proxy=0 filtering. The goal is to raise the dataset3 proxy-zero oracle ceiling
(currently ~0 because the original candidate generator never proposes zero-proxy
true positive bins).

New proxy-free arm families:
  ZERO_PROXY_SPACE_FILLING  — middle of largest zero-proxy unqueried run
  ZERO_PROXY_LARGEST_GAP    — midpoint of largest temporal gap among unqueried
  ZERO_PROXY_VDC            — Van der Corput low-discrepancy index into zero-proxy bins
  ZERO_PROXY_MIDBAND        — zero-proxy bin closest to temporal median of unqueried
  ZERO_PROXY_LOCAL_GAP_FLANK — zero-proxy bin farthest from queried negatives

Pass condition: at least one dataset3 proxy-zero segment's oracle ceiling
rises above v2/c1.

This is an OFFLINE CEILING (selection reads reference); NOT strict-replay.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from run_ecp_t027_bandit import (  # noqa: E402
    SEGMENTS, BUDGET_RATIOS, SEEDS, PROXY_COL, LABEL_COL, GAP,
    VARIANTS, load_segment_data, AlignedOracle, group_positive_bins,
    evaluate_events, candidate_targets_module, formed_intervals,
)
from run_ecp_t028c_ceiling import marginal_utility, iou_intervals  # noqa: E402

OUT = REPO_ROOT / "outputs" / "ecp_event_coverage_policy_v1"
OUT.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Extended candidate generator with proxy-free arms
# ---------------------------------------------------------------------------
def candidate_targets_extended(grid_sorted, proxies, bin_to_t, queried, queried_pos,
                               unqueried, all_bins, zero_proxy_budget_used, budget_abs,
                               cfg, gap=GAP):
    """Extended candidate generator: original 4 arms + 5 proxy-free arms.

    Returns dict arm -> target bin (or None). Each proxy-free arm proposes a
    DIFFERENT unqueried zero-proxy bin (no duplicates across arms or steps).
    """
    base = candidate_targets_module(
        grid_sorted, proxies, bin_to_t, queried, queried_pos,
        unqueried, all_bins, zero_proxy_budget_used, budget_abs, cfg, gap=gap
    )

    zp_bins = [b for b in unqueried if proxies[b] == 0.0]
    if not zp_bins:
        for arm in ["ZERO_PROXY_SPACE_FILLING", "ZERO_PROXY_LARGEST_GAP",
                     "ZERO_PROXY_VDC", "ZERO_PROXY_MIDBAND", "ZERO_PROXY_LOCAL_GAP_FLANK"]:
            base[arm] = None
        return base

    used_bins = set()
    zp_set = set(zp_bins)

    def _pick(candidates):
        """Pick first candidate not yet used by another proxy-free arm."""
        for b in candidates:
            if b not in used_bins and b in zp_set:
                used_bins.add(b)
                return b
        return None

    # --- ZERO_PROXY_SPACE_FILLING: middle of largest zero-proxy unqueried run ---
    best, bestlen = None, -1
    run = []
    for b in all_bins:
        if b in zp_set:
            run.append(b)
        else:
            if len(run) > bestlen:
                bestlen, best = len(run), run
            run = []
    if run and len(run) > bestlen:
        best = run
    if best:
        # try middle, then expand outward
        mid = len(best) // 2
        order = [best[mid]]
        for offset in range(1, len(best)):
            if mid - offset >= 0:
                order.append(best[mid - offset])
            if mid + offset < len(best):
                order.append(best[mid + offset])
        base["ZERO_PROXY_SPACE_FILLING"] = _pick(order)
    else:
        base["ZERO_PROXY_SPACE_FILLING"] = None

    # --- ZERO_PROXY_LARGEST_GAP: midpoint of largest temporal gap ---
    queried_sorted = sorted(queried)
    gaps = []
    if queried_sorted:
        first_q = queried_sorted[0]
        gap_bins = [b for b in zp_bins if b < first_q]
        if gap_bins:
            gaps.append((gap_bins, gap_bins[0], first_q))
    for i in range(len(queried_sorted) - 1):
        left, right = queried_sorted[i], queried_sorted[i + 1]
        gap_bins = [b for b in zp_bins if left < b < right]
        if gap_bins:
            gaps.append((gap_bins, left, right))
    if queried_sorted:
        last_q = queried_sorted[-1]
        gap_bins = [b for b in zp_bins if b > last_q]
        if gap_bins:
            gaps.append((gap_bins, last_q, gap_bins[-1]))
    if gaps:
        gaps.sort(key=lambda x: len(x[0]), reverse=True)
        # try largest gap first, then next largest, etc.
        gap_order = []
        for gap_bins, _, _ in gaps:
            mid = len(gap_bins) // 2
            gap_order.append(gap_bins[mid])
            for offset in range(1, len(gap_bins)):
                if mid - offset >= 0:
                    gap_order.append(gap_bins[mid - offset])
                if mid + offset < len(gap_bins):
                    gap_order.append(gap_bins[mid + offset])
        base["ZERO_PROXY_LARGEST_GAP"] = _pick(gap_order)
    else:
        base["ZERO_PROXY_LARGEST_GAP"] = _pick(zp_bins)

    # --- ZERO_PROXY_VDC: Van der Corput low-discrepancy sequence ---
    n_zp = len(zp_bins)
    n_queried_zp = sum(1 for b in queried if proxies.get(b, -1) == 0.0)
    vdc_idx = n_queried_zp
    vdc_val = 0.0
    denom = 1.0
    n = vdc_idx + 1
    while n > 0:
        denom *= 2.0
        vdc_val += (n % 2) / denom
        n //= 2
    # try VDC position and neighbors
    primary = min(int(vdc_val * n_zp), n_zp - 1)
    vdc_order = [zp_bins[primary]]
    for offset in range(1, n_zp):
        if primary - offset >= 0:
            vdc_order.append(zp_bins[primary - offset])
        if primary + offset < n_zp:
            vdc_order.append(zp_bins[primary + offset])
    base["ZERO_PROXY_VDC"] = _pick(vdc_order)

    # --- ZERO_PROXY_MIDBAND: zero-proxy bin closest to temporal median of unqueried ---
    unqueried_times = [(b, np.mean(bin_to_t[b])) for b in unqueried]
    unqueried_times.sort(key=lambda x: x[1])
    temporal_median = unqueried_times[len(unqueried_times) // 2][1]
    zp_with_time = [(b, np.mean(bin_to_t[b])) for b in zp_bins]
    zp_with_time.sort(key=lambda x: abs(x[1] - temporal_median))
    midband_order = [b for b, _ in zp_with_time]
    base["ZERO_PROXY_MIDBAND"] = _pick(midband_order)

    # --- ZERO_PROXY_LOCAL_GAP_FLANK: zero-proxy bin farthest from any queried bin ---
    queried_set = set(queried)
    flank_dists = []
    for b in zp_bins:
        bt = np.mean(bin_to_t[b])
        min_dist = min((abs(bt - np.mean(bin_to_t[q])) for q in queried_set), default=1e9)
        flank_dists.append((b, min_dist))
    flank_dists.sort(key=lambda x: -x[1])  # farthest first
    flank_order = [b for b, _ in flank_dists]
    base["ZERO_PROXY_LOCAL_GAP_FLANK"] = _pick(flank_order)

    return base


# ---------------------------------------------------------------------------
# Oracle ceiling with extended arms
# ---------------------------------------------------------------------------
def run_ceiling_extended(grid, ref_seg, seg_id, budget_abs, budget_ratio, seed, rng, cfg):
    """Oracle ceiling using the extended candidate set."""
    n_bins = len(grid)
    oracle = AlignedOracle(grid, seg_id, "ECP-ceiling-ext", seed, budget_abs, budget_ratio)
    grid_sorted = grid.sort_values("bin_idx").reset_index(drop=True)
    bin_to_t = dict(zip(grid_sorted["bin_idx"], zip(grid_sorted["local_t_start"], grid_sorted["local_t_end"])))
    proxies = dict(zip(grid_sorted["bin_idx"], grid_sorted[PROXY_COL]))
    true_labels = dict(zip(grid_sorted["bin_idx"], grid_sorted[LABEL_COL]))
    all_bins = grid_sorted["bin_idx"].tolist()
    queried = set()
    queried_pos = set()
    n_ref = len(ref_seg) if ref_seg is not None else 0
    zero_proxy_budget_used = 0
    step_rows = []

    while oracle.calls < oracle.budget_abs:
        unqueried = [b for b in all_bins if b not in queried]
        if not unqueried:
            break
        cands = candidate_targets_extended(
            grid_sorted, proxies, bin_to_t, queried, queried_pos, unqueried,
            all_bins, zero_proxy_budget_used, budget_abs, cfg,
        )
        # compute offline marginal utility for each candidate
        best_arm, best_u, best_target = None, -1e9, None
        cand_utils = {}
        for arm, target in cands.items():
            if target is None:
                cand_utils[arm] = None
                continue
            tl = "positive" if true_labels[target] else "negative"
            u, neh, ig = marginal_utility(queried_pos, target, tl, grid_sorted, bin_to_t, ref_seg, n_ref)
            cand_utils[arm] = {"target": target, "u": u, "new_event_hit": neh, "iou_gain": ig, "true_label": tl}
            if u > best_u:
                best_u, best_arm, best_target = u, arm, target
        if best_arm is None:
            break
        if best_u <= 0.02 and cands.get("DISCOVER") is not None:
            best_arm, best_target, best_u = "DISCOVER", cands["DISCOVER"], 0.02
        # track zero-proxy budget
        if "ZERO_PROXY" in best_arm:
            zero_proxy_budget_used += 1
        label = oracle.query_unit(best_target, "ECP_ceiling_ext_" + best_arm, best_arm)
        queried.add(best_target)
        if label == "positive":
            queried_pos.add(best_target)
        # state features
        formed = formed_intervals(queried_pos, grid_sorted)
        ev = evaluate_events(formed, ref_seg) if n_ref > 0 else {"unique_event_coverage": 0}
        formed_ratio = ev["unique_event_coverage"] / n_ref if n_ref > 0 else 0
        rem_ratio = (oracle.budget_abs - oracle.calls) / oracle.budget_abs
        top_proxy = max(proxies[b] for b in unqueried) if unqueried else 0.0
        zp = sum(1 for b in unqueried if proxies[b] == 0.0)
        zp_share = zp / len(unqueried) if unqueried else 0.0
        step_rows.append({
            "segment_id": seg_id, "seed": seed, "budget_ratio": budget_ratio,
            "call_idx": oracle.calls, "chosen_arm": best_arm, "chosen_bin": best_target,
            "chosen_u": round(best_u, 4), "chosen_true_label": label,
            "rem_ratio": round(rem_ratio, 3), "top_proxy": round(top_proxy, 3),
            "zp_share": round(zp_share, 3), "formed_ratio": round(formed_ratio, 3),
            "n_pos": len(queried_pos),
            # record all arm utilities
            **{f"u_{arm.lower()}": (round(cand_utils[arm]["u"], 4) if cand_utils[arm] else None)
               for arm in cands},
            # record target bin for each arm
            **{f"target_{arm.lower()}": (cand_utils[arm]["target"] if cand_utils[arm] else None)
               for arm in cands},
        })
    formed = formed_intervals(queried_pos, grid_sorted)
    ev = evaluate_events(formed, ref_seg) if n_ref > 0 else {"event_precision": 0, "event_recall": 0, "unique_event_coverage": 0}
    return {
        "returned_intervals": str(formed),
        "event_precision": ev["event_precision"],
        "event_recall": ev["event_recall"],
        "unique_event_coverage": ev["unique_event_coverage"],
        "oracle_calls": oracle.calls,
        "step_rows": step_rows,
    }


# ---------------------------------------------------------------------------
# Also run original ceiling (c1 baseline) for head-to-head comparison
# ---------------------------------------------------------------------------
def run_ceiling_original(grid, ref_seg, seg_id, budget_abs, budget_ratio, seed, rng, cfg):
    """Original T028c-0 ceiling with 4 arms only."""
    from run_ecp_t028c_ceiling import run_oracle_ceiling
    return run_oracle_ceiling(grid, ref_seg, seg_id, budget_abs, budget_ratio, seed, rng, cfg)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    rng = np.random.default_rng(20260709)
    rows = []
    step_all = []

    for seg in SEGMENTS:
        grid, ref_seg, err = load_segment_data(seg)
        if grid is None:
            print(f"SKIP {seg['segment_id']}: {err}")
            continue
        n_bins = len(grid)
        for br in BUDGET_RATIOS:
            for seed in SEEDS:
                budget_abs = max(1, int(round(br * n_bins)))

                # --- original ceiling (4 arms) ---
                orig = run_ceiling_original(grid, ref_seg, seg["segment_id"], budget_abs, br, seed, rng, VARIANTS["v2"])
                rows.append({
                    "variant": "ceiling_original_4arms",
                    "segment_id": seg["segment_id"], "seed": seed,
                    "budget_abs": budget_abs, "budget_ratio": br,
                    "oracle_calls_total": orig["oracle_calls"],
                    "returned_intervals": orig["returned_intervals"],
                    "event_precision": round(orig["event_precision"], 4),
                    "event_recall": round(orig["event_recall"], 4),
                    "unique_event_coverage": orig["unique_event_coverage"],
                    "strict_replay_or_posthoc": "OFFLINE_CEILING",
                    "online_uses_event_id": False, "can_be_main_comparison": False,
                    "applicability_note": "T028e-0 original 4-arm ceiling (baseline)",
                })

                # --- extended ceiling (4 + 5 proxy-free arms) ---
                ext = run_ceiling_extended(grid, ref_seg, seg["segment_id"], budget_abs, br, seed, rng, VARIANTS["v2"])
                rows.append({
                    "variant": "ceiling_extended_9arms",
                    "segment_id": seg["segment_id"], "seed": seed,
                    "budget_abs": budget_abs, "budget_ratio": br,
                    "oracle_calls_total": ext["oracle_calls"],
                    "returned_intervals": ext["returned_intervals"],
                    "event_precision": round(ext["event_precision"], 4),
                    "event_recall": round(ext["event_recall"], 4),
                    "unique_event_coverage": ext["unique_event_coverage"],
                    "strict_replay_or_posthoc": "OFFLINE_CEILING",
                    "online_uses_event_id": False, "can_be_main_comparison": False,
                    "applicability_note": "T028e-0 extended 9-arm ceiling (4 original + 5 proxy-free)",
                })

                for sr in ext["step_rows"]:
                    step_all.append(sr)

        print(f"done {seg['segment_id']}")

    frontier = pd.DataFrame(rows)
    frontier.to_csv(OUT / "t028e0_ceiling_frontier.csv", index=False)
    steps = pd.DataFrame(step_all)
    steps.to_csv(OUT / "t028e0_ceiling_steps.csv", index=False)

    # --- v2 strict-replay for reference ---
    v2 = pd.read_csv(OUT / "t028a_ecp_bandit_frontier.csv")
    v2 = v2[v2["variant"] == "v2"]

    # --- aggregate comparison ---
    orig_cmp = frontier[frontier.variant == "ceiling_original_4arms"].groupby(
        ["segment_id", "budget_ratio"])[["event_recall", "event_precision"]].mean().reset_index()
    ext_cmp = frontier[frontier.variant == "ceiling_extended_9arms"].groupby(
        ["segment_id", "budget_ratio"])[["event_recall", "event_precision"]].mean().reset_index()
    v2_cmp = v2.groupby(["segment_id", "budget_ratio"])[["event_recall", "event_precision"]].mean().reset_index()

    # --- build report ---
    L = []
    L.append("# T028e-0 — proxy-free candidate generator ceiling audit\n")
    L.append(
        "Extended candidate set with 5 proxy-free arms (SPACE_FILLING, LARGEST_GAP, "
        "VDC, MIDBAND, LOCAL_GAP_FLANK) on top of the original 4 (DISCOVER, BRIDGE, "
        "CERTIFY, ZERO_PROXY). Oracle ceiling selects the max-marginal-utility arm "
        "at each step (reads reference -> NOT strict-replay). Pass condition: at "
        "least one dataset3 proxy-zero segment ceiling rises above v2/c1.\n"
    )

    L.append("## Mean event_recall: extended-ceiling vs original-ceiling vs v2\n")
    L.append("| segment | budget | ext_ceiling | orig_ceiling | v2 | ext-orig | ext-v2 |")
    L.append("|---|---|---|---|---|---|---|")
    for (seg, br), _ in ext_cmp.groupby(["segment_id", "budget_ratio"]):
        er = ext_cmp[(ext_cmp.segment_id == seg) & (ext_cmp.budget_ratio == br)]["event_recall"].mean()
        ep = ext_cmp[(ext_cmp.segment_id == seg) & (ext_cmp.budget_ratio == br)]["event_precision"].mean()
        or_ = orig_cmp[(orig_cmp.segment_id == seg) & (orig_cmp.budget_ratio == br)]["event_recall"].mean()
        op = orig_cmp[(orig_cmp.segment_id == seg) & (orig_cmp.budget_ratio == br)]["event_precision"].mean()
        vr = v2_cmp[(v2_cmp.segment_id == seg) & (v2_cmp.budget_ratio == br)]["event_recall"].mean()
        vp = v2_cmp[(v2_cmp.segment_id == seg) & (v2_cmp.budget_ratio == br)]["event_precision"].mean()
        L.append(f"| {seg} | {br:.2f} | {er:.3f} ({ep:.3f}) | {or_:.3f} ({op:.3f}) | {vr:.3f} ({vp:.3f}) | {er-or_:+.3f} | {er-vr:+.3f} |")

    # --- arm usage of extended ceiling ---
    L.append("\n## Extended-ceiling arm usage\n")
    L.append("| arm | n_calls | positive_rate | mean_u |")
    L.append("|---|---|---|---|")
    all_arms = ["DISCOVER", "BRIDGE", "CERTIFY", "ZERO_PROXY",
                "ZERO_PROXY_SPACE_FILLING", "ZERO_PROXY_LARGEST_GAP",
                "ZERO_PROXY_VDC", "ZERO_PROXY_MIDBAND", "ZERO_PROXY_LOCAL_GAP_FLANK"]
    for arm in all_arms:
        sub = steps[steps["chosen_arm"] == arm]
        pr = (sub["chosen_true_label"] == "positive").mean() if len(sub) else 0.0
        mu = sub["chosen_u"].mean() if len(sub) else 0.0
        L.append(f"| {arm} | {len(sub)} | {pr:.3f} | {mu:.3f} |")

    # --- per-video delta summary ---
    L.append("\n## Ceiling lift by video\n")
    for video in ["realcartest", "dataset3"]:
        v_ext = ext_cmp[ext_cmp.segment_id.str.startswith(video)]
        v_orig = orig_cmp[orig_cmp.segment_id.str.startswith(video)]
        v_v2 = v2_cmp[v2_cmp.segment_id.str.startswith(video)]
        if len(v_ext) == 0:
            continue
        mean_ext = v_ext["event_recall"].mean()
        mean_orig = v_orig["event_recall"].mean()
        mean_v2 = v_v2["event_recall"].mean()
        L.append(f"- **{video}**: ext_ceiling={mean_ext:.3f}, orig_ceiling={mean_orig:.3f}, v2={mean_v2:.3f}, "
                 f"ext-orig={mean_ext-mean_orig:+.3f}, ext-v2={mean_ext-mean_v2:+.3f}")

    L.append("\n## Pass/fail verdict\n")
    # check pass condition: dataset3 ceiling rises
    d3_ext = ext_cmp[ext_cmp.segment_id.str.startswith("dataset3")]
    d3_orig = orig_cmp[orig_cmp.segment_id.str.startswith("dataset3")]
    d3_lift = (d3_ext["event_recall"].values - d3_orig["event_recall"].values)
    d3_any_lift = (d3_lift > 0).any()
    rc_ext = ext_cmp[ext_cmp.segment_id.str.startswith("realcartest")]
    rc_orig = orig_cmp[orig_cmp.segment_id.str.startswith("realcartest")]
    rc_any_regression = (rc_ext["event_recall"].values < rc_orig["event_recall"].values - 0.01).any()

    if d3_any_lift:
        L.append("- **PASS**: dataset3 proxy-zero ceiling LIFTS above original 4-arm ceiling.")
        L.append(f"  Max lift: +{d3_lift.max():.3f}")
    else:
        L.append("- **FAIL**: dataset3 proxy-zero ceiling does NOT lift above original 4-arm ceiling.")
        L.append(f"  Deltas: {d3_lift}")

    if rc_any_regression:
        L.append("- **WARNING**: realcartest ceiling REGRESSES with extended arms.")
    else:
        L.append("- OK: realcartest ceiling does not regress (or regresses <0.01).")

    L.append(
        "- This is an OFFLINE CEILING: selection reads reference, NOT strict-replay. "
        "If ceiling rises, proceed to T028e-1 (train event-utility selector with "
        "extended arm set, strict-replay LOSO). If ceiling does not rise, the "
        "proxy-free candidate families are insufficient and need redesign."
    )

    md = OUT / "t028e0_ceiling_report.md"
    md.write_text("\n".join(L))
    print(f"\nwrote {OUT/'t028e0_ceiling_frontier.csv'}")
    print(f"wrote {OUT/'t028e0_ceiling_steps.csv'}")
    print(f"wrote {md}")


if __name__ == "__main__":
    main()
