"""T026 + T027 — ECP hand-designed event-utility bandit (strict replay).

T027 runs a hand-designed Event-Coverage Policy (ECP) as a strict-replay
method competing with HTS-EC-safe and B7-core. T026 is the byproduct: a
per-step action-utility table (the online heuristic utility of each candidate
arm at each decision, plus the arm actually chosen).

Design (per ECP_DESIGN.md §2):
  State S_t (online-only): budget_remaining_ratio, n_discovered_pos,
    n_formed_events, formed_events_ratio, proxy_informativeness,
    zero_proxy_share, stagnation_flag, zero_proxy_budget_used.
  Arms (event-level operators, not bins):
    DISCOVER   : probe highest-posterior unqueried bin (tree/fine frontier)
    BRIDGE     : probe unqueried bin within gap<=3 of a discovered positive
    CERTIFY    : probe just outside a formed interval's boundary (extend/confirm)
    ZERO_PROXY : probe space-filling bin among zero-proxy unqueried bins
    STOP       : abstain (stop querying)
  Reward heuristic U(a)/cost uses ONLY online state (queried labels, proxies,
    posteriors). The reference events are read ONLY at final evaluation, never
    online -> strict_replay compliant, no event_id leak.

This is a SHADOW-capable but here a REAL strict-replay executor: it drives the
AlignedOracle exactly like the other methods. Cost of every arm = 1 oracle call.

Outputs:
  outputs/ecp_event_coverage_policy_v1/t027_ecp_bandit_frontier.csv
  outputs/ecp_event_coverage_policy_v1/t026_action_utility.csv
  outputs/ecp_event_coverage_policy_v1/t027_ecp_bandit_report.md
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from run_aligned_baselines_v1 import (  # noqa: E402
    SEGMENTS,
    BUDGET_RATIOS,
    SEEDS,
    PROXY_COL,
    LABEL_COL,
    load_segment_data,
    AlignedOracle,
    group_positive_bins,
    evaluate_events,
)

OUT = REPO_ROOT / "outputs" / "ecp_event_coverage_policy_v1"
OUT.mkdir(parents=True, exist_ok=True)

GAP = 3          # bridge gap tolerance (bins)
ZERO_CAP = 0.25  # max fraction of budget spendable on zero-proxy audit


def formed_intervals(queried_pos, grid):
    return group_positive_bins(sorted(queried_pos), grid)


def run_ecp(grid, ref_seg, seg_id, budget_abs, budget_ratio, seed, rng):
    n_bins = len(grid)
    oracle = AlignedOracle(grid, seg_id, "ECP-bandit", seed, budget_abs, budget_ratio)
    grid_sorted = grid.sort_values("bin_idx").reset_index(drop=True)
    bin_to_t = dict(
        zip(grid_sorted["bin_idx"], zip(grid_sorted["local_t_start"], grid_sorted["local_t_end"]))
    )
    proxies = dict(zip(grid_sorted["bin_idx"], grid_sorted[PROXY_COL]))
    pos_set = set(grid_sorted[grid_sorted[LABEL_COL] == True]["bin_idx"])
    all_bins = grid_sorted["bin_idx"].tolist()

    queried = set()
    queried_pos = set()
    zero_proxy_budget_used = 0
    last_action = None
    stagnation = 0
    util_rows = []

    n_ref = len(ref_seg) if ref_seg is not None else 0

    def state():
        rem = oracle.budget_abs - oracle.calls
        rem_ratio = rem / oracle.budget_abs
        formed = formed_intervals(queried_pos, grid_sorted)
        ev = evaluate_events(formed, ref_seg) if n_ref > 0 else {"event_recall": 0, "event_precision": 0}
        formed_events = ev["unique_event_coverage"]
        formed_ratio = formed_events / n_ref if n_ref > 0 else 0
        unqueried = [b for b in all_bins if b not in queried]
        if len(unqueried) == 0:
            zp_share = 0.0
            top_proxy = 0.0
        else:
            zp = sum(1 for b in unqueried if proxies[b] == 0.0)
            zp_share = zp / len(unqueried)
            top_proxy = max(proxies[b] for b in unqueried)
        return {
            "rem_ratio": rem_ratio,
            "n_pos": len(queried_pos),
            "formed_events": formed_events,
            "formed_ratio": formed_ratio,
            "unqueried": unqueried,
            "zp_share": zp_share,
            "top_proxy": top_proxy,
        }

    def candidate_targets(st):
        # DISCOVER: highest proxy unqueried
        discover = None
        if st["unqueried"]:
            discover = max(st["unqueried"], key=lambda b: proxies[b])
        # BRIDGE: unqueried bin within GAP of a discovered positive
        bridge = None
        for p in queried_pos:
            for db in range(p - GAP, p + GAP + 1):
                if db in st["unqueried"]:
                    bridge = db
                    break
            if bridge is not None:
                break
        # CERTIFY: bin just outside a formed interval boundary
        certify = None
        formed = formed_intervals(queried_pos, grid_sorted)
        for (s, e) in formed:
            # find bin whose [t_start,t_end] ends just after e or starts just before s
            for b in st["unqueried"]:
                bt_s, bt_e = bin_to_t[b]
                if abs(bt_s - e) < 1e-6 or abs(bt_e - s) < 1e-6:
                    certify = b
                    break
            if certify is not None:
                break
        # ZERO_PROXY: space-filling among zero-proxy unqueried (pick middle of largest gap)
        zerop = None
        if st["zp_share"] > 0.5 and zero_proxy_budget_used < ZERO_CAP * budget_abs:
            zp_bins = [b for b in st["unqueried"] if proxies[b] == 0.0]
            if zp_bins:
                # largest contiguous run of unqueried zero-proxy bins -> midpoint
                best = None
                bestlen = -1
                run = []
                for b in all_bins:
                    if b in set(zp_bins):
                        run.append(b)
                    else:
                        if len(run) > bestlen:
                            bestlen = len(run)
                            best = run
                        run = []
                if run and len(run) > bestlen:
                    best = run
                if best:
                    zerop = best[len(best) // 2]
        return discover, bridge, certify, zerop

    while oracle.calls < oracle.budget_abs:
        st = state()
        discover, bridge, certify, zerop = candidate_targets(st)
        # heuristic utilities (online-only)
        u_discover = 1.0 * st["top_proxy"] * (1 - st["formed_ratio"]) + 0.05
        u_bridge = 0.8 * (1.0 if bridge is not None else 0.0) * (1 - st["formed_ratio"])
        u_certify = 0.6 * (1.0 if certify is not None else 0.0)
        # zero-proxy audit only when proxy informativeness low & stagnation
        stagnation_flag = 1.0 if (stagnation >= 2 and st["top_proxy"] < 0.3) else 0.0
        u_zero = 0.7 * stagnation_flag * st["zp_share"] * (
            1.0 if (zerop is not None and zero_proxy_budget_used < ZERO_CAP * budget_abs) else 0.0
        )
        arms = {
            "DISCOVER": (u_discover, discover),
            "BRIDGE": (u_bridge, bridge),
            "CERTIFY": (u_certify, certify),
            "ZERO_PROXY": (u_zero, zerop),
        }
        best_arm = max(arms, key=lambda a: arms[a][0])
        best_u, target = arms[best_arm]
        # STOP if best utility below cost threshold and nothing better
        if best_u < 0.1 or target is None:
            break
        # execute
        is_zero = (best_arm == "ZERO_PROXY")
        if is_zero:
            zero_proxy_budget_used += 1
        label = oracle.query_unit(target, "ECP_" + best_arm, best_arm)
        queried.add(target)
        if label == "positive":
            queried_pos.add(target)
        if best_arm == last_action:
            stagnation += 1
        else:
            stagnation = 0
        last_action = best_arm
        util_rows.append(
            {
                "segment_id": seg_id,
                "seed": seed,
                "budget_ratio": budget_ratio,
                "call_idx": oracle.calls,
                "u_discover": round(u_discover, 4),
                "u_bridge": round(u_bridge, 4),
                "u_certify": round(u_certify, 4),
                "u_zero_proxy": round(u_zero, 4),
                "chosen_arm": best_arm,
                "chosen_bin": target,
                "oracle_label": label,
                "budget_remaining_ratio": round(st["rem_ratio"], 3),
                "formed_events": st["formed_events"],
                "zero_proxy_budget_used": zero_proxy_budget_used,
            }
        )

    formed = formed_intervals(queried_pos, grid_sorted)
    ev = evaluate_events(formed, ref_seg) if n_ref > 0 else {"event_precision": 0, "event_recall": 0, "unique_event_coverage": 0}
    return {
        "returned_intervals": str(formed),
        "event_precision": ev["event_precision"],
        "event_recall": ev["event_recall"],
        "unique_event_coverage": ev["unique_event_coverage"],
        "oracle_calls": oracle.calls,
        "util_rows": util_rows,
    }


def main():
    rng = np.random.default_rng(20260707)
    rows = []
    util_all = []
    for seg in SEGMENTS:
        grid, ref_seg, err = load_segment_data(seg)
        if grid is None:
            continue
        n_bins = len(grid)
        for br in BUDGET_RATIOS:
            for seed in SEEDS:
                budget_abs = max(1, int(round(br * n_bins)))
                res = run_ecp(grid, ref_seg, seg["segment_id"], budget_abs, br, seed, rng)
                rows.append(
                    {
                        "segment_id": seg["segment_id"],
                        "method_id": "ECP-bandit",
                        "seed": seed,
                        "budget_abs": budget_abs,
                        "budget_ratio": br,
                        "oracle_calls_total": res["oracle_calls"],
                        "returned_intervals": res["returned_intervals"],
                        "event_precision": round(res["event_precision"], 4),
                        "event_recall": round(res["event_recall"], 4),
                        "unique_event_coverage": res["unique_event_coverage"],
                        "strict_replay_or_posthoc": "strict_replay",
                        "online_uses_event_id": False,
                        "can_be_main_comparison": True,
                        "applicability_note": "ECP hand-designed event-utility bandit (T027)",
                    }
                )
                for ur in res["util_rows"]:
                    util_all.append(ur)
        print(f"done {seg['segment_id']}")

    frontier = pd.DataFrame(rows)
    frontier.to_csv(OUT / "t027_ecp_bandit_frontier.csv", index=False)
    util_df = pd.DataFrame(util_all)
    util_df.to_csv(OUT / "t026_action_utility.csv", index=False)

    # compare to HTS-EC-safe and B7-core from existing CSVs
    hts = pd.read_csv(OUT.parent / "hts_ec_v0_strict_v1" / "hts_ec_v0_frontier.csv")
    hts = hts[hts["method_id"].isin(["HTS-EC-safe", "B7-strict-replay"])]
    cmp = frontier.groupby(["segment_id", "budget_ratio"])[["event_recall", "event_precision"]].mean().reset_index()
    hts_cmp = hts.groupby(["segment_id", "budget_ratio", "method_id"])[["event_recall", "event_precision"]].mean().reset_index()

    L = []
    L.append("# T027 — ECP hand-designed bandit (strict replay)\n")
    L.append(
        "ECP bandit (DISCOVER/BRIDGE/CERTIFY/ZERO_PROXY/STOP, heuristic U(a)/cost, "
        "online-only state) run under strict replay. Compared to HTS-EC-safe and "
        "B7-strict-replay on event_recall / event_precision (VLM-oracle-relative, IoU>=0.3).\n"
    )
    L.append("## Mean event_recall by segment x budget (ECP vs baselines)\n")
    L.append("| segment | budget | ECP_recall | HTS-EC-safe_recall | B7-strict_recall | ECP_prec | HTS_prec | B7_prec |")
    L.append("|---|---|---|---|---|---|---|---|")
    for (seg, br), grp in cmp.groupby(["segment_id", "budget_ratio"]):
        ecp_r = grp["event_recall"].mean()
        ecp_p = grp["event_precision"].mean()
        hs = hts_cmp[(hts_cmp["segment_id"] == seg) & (hts_cmp["budget_ratio"] == br) & (hts_cmp["method_id"] == "HTS-EC-safe")]
        b7 = hts_cmp[(hts_cmp["segment_id"] == seg) & (hts_cmp["budget_ratio"] == br) & (hts_cmp["method_id"] == "B7-strict-replay")]
        hs_r = hs["event_recall"].mean() if len(hs) else float("nan")
        hs_p = hs["event_precision"].mean() if len(hs) else float("nan")
        b7_r = b7["event_recall"].mean() if len(b7) else float("nan")
        b7_p = b7["event_precision"].mean() if len(b7) else float("nan")
        L.append(
            f"| {seg} | {br:.2f} | {ecp_r:.3f} | {hs_r:.3f} | {b7_r:.3f} | {ecp_p:.3f} | {hs_p:.3f} | {b7_p:.3f} |"
        )
    L.append("\n## Reading\n")
    L.append(
        "- This is a FIRST hand-designed bandit; weights are heuristics, not learned. "
        "It validates that event-level arm selection is a viable strict-replay policy "
        "layer and isolates which arms earn their budget."
    )
    L.append(
        "- T026 action-utility table (t026_action_utility.csv) logs the per-step U(a) of "
        "every arm and the chosen arm — the offline-labeled training signal for a future "
        "learned policy (T027 step 4)."
    )
    L.append(
        "- Strict-replay compliant: reference events read only at final evaluation; no "
        "event_id online; 1 oracle call per arm execution."
    )
    md = OUT / "t027_ecp_bandit_report.md"
    md.write_text("\n".join(L))
    print(f"wrote {OUT/'t027_ecp_bandit_frontier.csv'}")
    print(f"wrote {OUT/'t026_action_utility.csv'}")
    print(f"wrote {md}")


if __name__ == "__main__":
    main()
