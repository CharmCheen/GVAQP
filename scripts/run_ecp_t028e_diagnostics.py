"""T028e diagnostics — ceiling clarification + per-candidate trace tables.

Resolves the "c2 > ceiling" paradox:
  - "static trajectory ceiling" (current T028e-0): myopic marginal_utility
    with `best_u <= 0.02` safety-override always falling back to DISCOVER.
    On dataset3_0_1200 this chains DISCOVER → all negatives → recall=0.
  - "closed-loop oracle ceiling" (new): same iterative loop but WITHOUT the
    safety override: when all arms have u ≤ 0.02, prefers zero-proxy arms
    over DISCOVER in high-zp regimes. This is a more rational explorer.

Outputs:
  outputs/ecp_event_coverage_policy_v1/t028e_candidate_table.csv      (per-step per-arm)
  outputs/ecp_event_coverage_policy_v1/t028e_zero_proxy_hits.csv     (zp-positive hits only)
  outputs/ecp_event_coverage_policy_v1/t028e_arm_utility_summary.csv  (aggregated)
  outputs/ecp_event_coverage_policy_v1/t028e_diagnostics_report.md
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
from run_ecp_t028c_ceiling import marginal_utility  # noqa: E402
from run_ecp_t028e0_ceiling import candidate_targets_extended, run_ceiling_extended  # noqa: E402

OUT = REPO_ROOT / "outputs" / "ecp_event_coverage_policy_v1"
OUT.mkdir(parents=True, exist_ok=True)

ALL_ARMS = ["DISCOVER", "BRIDGE", "CERTIFY", "ZERO_PROXY",
            "ZERO_PROXY_SPACE_FILLING", "ZERO_PROXY_LARGEST_GAP",
            "ZERO_PROXY_VDC", "ZERO_PROXY_MIDBAND", "ZERO_PROXY_LOCAL_GAP_FLANK"]


# ---------------------------------------------------------------------------
# 1. Static trajectory ceiling (current T028e-0 logic) — with full diagnostics
# ---------------------------------------------------------------------------
def run_ceiling_static(grid, ref_seg, seg_id, budget_abs, budget_ratio, seed, rng, cfg):
    """Current T028e-0 ceiling with safety override. Full per-arm diagnostics."""
    n_bins = len(grid)
    oracle = AlignedOracle(grid, seg_id, "ECP-ceiling-static", seed, budget_abs, budget_ratio)
    grid_sorted = grid.sort_values("bin_idx").reset_index(drop=True)
    bin_to_t = dict(zip(grid_sorted["bin_idx"],
                        zip(grid_sorted["local_t_start"], grid_sorted["local_t_end"])))
    proxies = dict(zip(grid_sorted["bin_idx"], grid_sorted[PROXY_COL]))
    true_labels = dict(zip(grid_sorted["bin_idx"], grid_sorted[LABEL_COL]))
    all_bins = grid_sorted["bin_idx"].tolist()
    queried, queried_pos = set(), set()
    n_ref = len(ref_seg) if ref_seg is not None else 0
    zp_budget_used = 0
    candidate_rows = []

    while oracle.calls < oracle.budget_abs:
        unqueried = [b for b in all_bins if b not in queried]
        if not unqueried:
            break
        cands = candidate_targets_extended(
            grid_sorted, proxies, bin_to_t, queried, queried_pos, unqueried,
            all_bins, zp_budget_used, budget_abs, cfg,
        )
        # state features
        formed = formed_intervals(queried_pos, grid_sorted)
        ev = evaluate_events(formed, ref_seg) if n_ref > 0 else {"unique_event_coverage": 0}
        rem_ratio = (oracle.budget_abs - oracle.calls) / oracle.budget_abs
        top_proxy = max(proxies[b] for b in unqueried) if unqueried else 0.0
        zp = sum(1 for b in unqueried if proxies[b] == 0.0)
        zp_share = zp / len(unqueried) if unqueried else 0.0
        formed_ratio = ev["unique_event_coverage"] / n_ref if n_ref > 0 else 0

        # Compute utility for each candidate
        best_arm, best_u, best_target = None, -1e9, None
        for arm, target in cands.items():
            if target is None:
                candidate_rows.append({
                    "segment_id": seg_id, "seed": seed, "budget_ratio": budget_ratio,
                    "call_idx": oracle.calls + 1, "arm_name": arm, "target_bin": None,
                    "available": False,
                    "u_offline": None, "new_event_hit": None, "iou_gain": None,
                    "oracle_label_offline": None,
                    "selected_by_candidate_ceiling": False, "selected_by_ceiling_explore": False,
                    "rem_ratio": rem_ratio, "top_proxy": top_proxy, "zp_share": zp_share,
                    "formed_ratio": formed_ratio, "n_pos_queried": len(queried_pos),
                })
                continue
            tl = "positive" if true_labels[target] else "negative"
            u, neh, ig = marginal_utility(queried_pos, target, tl, grid_sorted,
                                           bin_to_t, ref_seg, n_ref)
            candidate_rows.append({
                "segment_id": seg_id, "seed": seed, "budget_ratio": budget_ratio,
                "call_idx": oracle.calls + 1, "arm_name": arm, "target_bin": target,
                "available": True,
                "u_offline": round(u, 4), "new_event_hit": round(neh, 4),
                "iou_gain": round(ig, 4),
                "oracle_label_offline": tl,
                "selected_by_candidate_ceiling": False, "selected_by_ceiling_explore": False,
                "rem_ratio": round(rem_ratio, 3), "top_proxy": round(top_proxy, 3),
                "zp_share": round(zp_share, 3), "formed_ratio": round(formed_ratio, 3),
                "n_pos_queried": len(queried_pos),
            })
            if u > best_u:
                best_u, best_arm, best_target = u, arm, target

        if best_arm is None:
            break

        # Safety override (this is what creates the discrepancy)
        safety_override = False
        if best_u <= 0.02 and cands.get("DISCOVER") is not None:
            best_arm, best_target, best_u = "DISCOVER", cands["DISCOVER"], 0.02
            safety_override = True

        last_idx = len(candidate_rows) - 1
        for i in range(len(candidate_rows) - len([a for a in ALL_ARMS if cands.get(a) is not None or True]), len(candidate_rows)):
            # Mark the selected arm in the just-added rows
            if i >= 0 and i < len(candidate_rows) and candidate_rows[i]["arm_name"] == best_arm:
                candidate_rows[i]["selected_by_candidate_ceiling"] = True
                candidate_rows[i]["candidate_static_safety_override"] = safety_override

        if "ZERO_PROXY" in best_arm:
            zp_budget_used += 1
        label = oracle.query_unit(best_target, "ECP_ceil_static_" + best_arm, best_arm)
        queried.add(best_target)
        if label == "positive":
            queried_pos.add(best_target)

    formed = formed_intervals(queried_pos, grid_sorted)
    ev = evaluate_events(formed, ref_seg) if n_ref > 0 else {"event_precision": 0, "event_recall": 0}
    return {
        "variant": "ceiling_static",
        "event_recall": ev["event_recall"],
        "event_precision": ev["event_precision"],
        "oracle_calls": oracle.calls,
        "candidate_rows": candidate_rows,
    }


# ---------------------------------------------------------------------------
# 2. Closed-loop oracle ceiling — no safety override, exploration bonus
# ---------------------------------------------------------------------------
def run_ceiling_closedloop(grid, ref_seg, seg_id, budget_abs, budget_ratio, seed, rng, cfg):
    """Closed-loop oracle: same iterative ceiling, but NO safety override.
    When all arms have u <= 0.02, proxy-free arms get +0.03 exploration bonus
    so they are preferred over DISCOVER in high-zp regimes."""
    n_bins = len(grid)
    oracle = AlignedOracle(grid, seg_id, "ECP-ceiling-closed", seed, budget_abs, budget_ratio)
    grid_sorted = grid.sort_values("bin_idx").reset_index(drop=True)
    bin_to_t = dict(zip(grid_sorted["bin_idx"],
                        zip(grid_sorted["local_t_start"], grid_sorted["local_t_end"])))
    proxies = dict(zip(grid_sorted["bin_idx"], grid_sorted[PROXY_COL]))
    true_labels = dict(zip(grid_sorted["bin_idx"], grid_sorted[LABEL_COL]))
    all_bins = grid_sorted["bin_idx"].tolist()
    queried, queried_pos = set(), set()
    n_ref = len(ref_seg) if ref_seg is not None else 0
    zp_budget_used = 0
    candidate_rows = []

    while oracle.calls < oracle.budget_abs:
        unqueried = [b for b in all_bins if b not in queried]
        if not unqueried:
            break
        cands = candidate_targets_extended(
            grid_sorted, proxies, bin_to_t, queried, queried_pos, unqueried,
            all_bins, zp_budget_used, budget_abs, cfg,
        )
        formed = formed_intervals(queried_pos, grid_sorted)
        ev = evaluate_events(formed, ref_seg) if n_ref > 0 else {"unique_event_coverage": 0}
        rem_ratio = (oracle.budget_abs - oracle.calls) / oracle.budget_abs
        top_proxy = max(proxies[b] for b in unqueried) if unqueried else 0.0
        zp = sum(1 for b in unqueried if proxies[b] == 0.0)
        zp_share = zp / len(unqueried) if unqueried else 0.0
        formed_ratio = ev["unique_event_coverage"] / n_ref if n_ref > 0 else 0

        best_arm, best_u, best_target = None, -1e9, None
        for arm, target in cands.items():
            if target is None:
                candidate_rows.append({
                    "segment_id": seg_id, "seed": seed, "budget_ratio": budget_ratio,
                    "call_idx": oracle.calls + 1, "arm_name": arm, "target_bin": None,
                    "available": False,
                    "u_offline": None, "new_event_hit": None, "iou_gain": None,
                    "oracle_label_offline": None,
                    "selected_by_candidate_ceiling": False, "selected_by_ceiling_explore": False,
                    "rem_ratio": rem_ratio, "top_proxy": top_proxy, "zp_share": zp_share,
                    "formed_ratio": formed_ratio, "n_pos_queried": len(queried_pos),
                })
                continue
            tl = "positive" if true_labels[target] else "negative"
            u, neh, ig = marginal_utility(queried_pos, target, tl, grid_sorted,
                                           bin_to_t, ref_seg, n_ref)
            u_raw = u  # un-bonused utility for recording
            # exploration bonus: in high-zp regimes, prefer proxy-free arms
            if "ZERO_PROXY" in arm and zp_share >= 0.30:
                u += 0.04  # small bonus to prefer exploration over repeated DISCOVER
            candidate_rows.append({
                "segment_id": seg_id, "seed": seed, "budget_ratio": budget_ratio,
                "call_idx": oracle.calls + 1, "arm_name": arm, "target_bin": target,
                "available": True,
                "u_offline": round(u_raw, 4), "new_event_hit": round(neh, 4),
                "iou_gain": round(ig, 4),
                "oracle_label_offline": tl,
                "selected_by_candidate_ceiling": False, "selected_by_ceiling_explore": False,
                "rem_ratio": round(rem_ratio, 3), "top_proxy": round(top_proxy, 3),
                "zp_share": round(zp_share, 3), "formed_ratio": round(formed_ratio, 3),
                "n_pos_queried": len(queried_pos),
            })
            if u > best_u:
                best_u, best_arm, best_target = u, arm, target

        if best_arm is None:
            break

        # Mark selected arm in the just-added rows
        n_arms = len([a for a in ALL_ARMS if a in cands])
        for i in range(max(0, len(candidate_rows) - n_arms), len(candidate_rows)):
            if candidate_rows[i]["arm_name"] == best_arm and candidate_rows[i]["available"]:
                candidate_rows[i]["selected_by_ceiling_explore"] = True

        if "ZERO_PROXY" in best_arm:
            zp_budget_used += 1
        label = oracle.query_unit(best_target, "ECP_ceil_closed_" + best_arm, best_arm)
        queried.add(best_target)
        if label == "positive":
            queried_pos.add(best_target)

    formed = formed_intervals(queried_pos, grid_sorted)
    ev = evaluate_events(formed, ref_seg) if n_ref > 0 else {"event_precision": 0, "event_recall": 0}
    return {
        "variant": "ceiling_closedloop",
        "event_recall": ev["event_recall"],
        "event_precision": ev["event_precision"],
        "oracle_calls": oracle.calls,
        "candidate_rows": candidate_rows,
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    rng = np.random.default_rng(20260710)
    frontier_rows = []
    all_candidates = []

    for seg in SEGMENTS:
        grid, ref_seg, err = load_segment_data(seg)
        if grid is None:
            print(f"SKIP {seg['segment_id']}: {err}")
            continue
        n_bins = len(grid)
        for br in BUDGET_RATIOS:
            for seed in SEEDS:
                budget_abs = max(1, int(round(br * n_bins)))
                sid = seg["segment_id"]

                # static ceiling (current T028e-0 logic with diagnostics)
                static = run_ceiling_static(grid, ref_seg, sid, budget_abs, br, seed, rng, VARIANTS["v2"])
                frontier_rows.append({
                    "variant": "ceiling_static",
                    "segment_id": sid, "seed": seed, "budget_ratio": br,
                    "event_recall": round(static["event_recall"], 4),
                    "event_precision": round(static["event_precision"], 4),
                    "strict_replay_or_posthoc": "OFFLINE_CEILING",
                    "applicability_note": "T028e static trajectory ceiling (current, with safety override)",
                })
                all_candidates.extend(static["candidate_rows"])

                # closed-loop oracle ceiling
                closed = run_ceiling_closedloop(grid, ref_seg, sid, budget_abs, br, seed, rng, VARIANTS["v2"])
                frontier_rows.append({
                    "variant": "ceiling_closedloop",
                    "segment_id": sid, "seed": seed, "budget_ratio": br,
                    "event_recall": round(closed["event_recall"], 4),
                    "event_precision": round(closed["event_precision"], 4),
                    "strict_replay_or_posthoc": "OFFLINE_CEILING",
                    "applicability_note": "T028e closed-loop oracle ceiling (no safety override, exploration bonus)",
                })
                all_candidates.extend(closed["candidate_rows"])

        print(f"done {sid}")

    # --- Write CSVs ---
    candidates_df = pd.DataFrame(all_candidates)
    candidates_df.to_csv(OUT / "t028e_candidate_table.csv", index=False)

    frontier_df = pd.DataFrame(frontier_rows)
    frontier_df.to_csv(OUT / "t028e_diagnostics_frontier.csv", index=False)

    # zero-proxy hits only
    zp_hits = candidates_df[
        candidates_df["arm_name"].str.contains("ZERO_PROXY", na=False)
        & (candidates_df["oracle_label_offline"] == "positive")
        & candidates_df["available"]
    ]
    if len(zp_hits):
        zp_hits.to_csv(OUT / "t028e_zero_proxy_hits.csv", index=False)

    # arm utility summary
    arm_summary = candidates_df[candidates_df["available"]].groupby("arm_name").agg(
        n_proposed=("target_bin", "count"),
        n_positive=("oracle_label_offline", lambda x: (x == "positive").sum()),
        mean_u=("u_offline", "mean"),
        max_u=("u_offline", "max"),
        selected_static=("selected_by_candidate_ceiling", "sum"),
        selected_closedloop=("selected_by_ceiling_explore", "sum"),
        mean_zp_share=("zp_share", "mean"),
    ).reset_index()
    arm_summary["positive_rate"] = arm_summary["n_positive"] / arm_summary["n_proposed"]
    arm_summary.to_csv(OUT / "t028e_arm_utility_summary.csv", index=False)

    # --- Report ---
    static_f = frontier_df[frontier_df.variant == "ceiling_static"]
    closed_f = frontier_df[frontier_df.variant == "ceiling_closedloop"]

    # Also load c2 LOSO and v2 for comparison
    c2f = pd.read_csv(OUT / "t028e1_loso_frontier.csv")
    c2f = c2f[c2f.variant == "c2_loso"]

    L = []
    L.append("# T028e diagnostics — ceiling clarification\n")
    L.append(
        "Resolves the discrepancy where c2 (strict-replay LOSO, 0.167) exceeded "
        "the T028e-0 extended ceiling (0.000) on dataset3_0_1200.\n\n"
        "The T028e-0 ceiling is ITERATIVE (closed-loop) but MYOPIC: the "
        "`marginal_utility` function assigns u=0.02 to ALL negative probes, and "
        "the `best_u <= 0.02` safety override ALWAYS falls back to DISCOVER. "
        "On dataset3_0_1200 where all proxy scores are 0, DISCOVER = no-op forever, "
        "making the ceiling a **static trajectory ceiling** rather than a true oracle.\n\n"
        "The **closed-loop oracle ceiling** removes the safety override and adds a "
        "small exploration bonus (+0.04) for zero-proxy arms when zp_share >= 0.30, "
        "preferring exploration over repeated DISCOVER.\n"
    )

    L.append("## Ceiling comparison: static vs closed-loop oracle\n")
    L.append("| segment | budget | static_recall | closed_recall | delta |")
    L.append("|---|---|---|---|---|")
    static_agg = static_f.groupby(["segment_id", "budget_ratio"])["event_recall"].mean().reset_index()
    closed_agg = closed_f.groupby(["segment_id", "budget_ratio"])["event_recall"].mean().reset_index()
    for _, sr in static_agg.iterrows():
        cr = closed_agg[(closed_agg.segment_id == sr["segment_id"])
                        & (closed_agg.budget_ratio == sr["budget_ratio"])]["event_recall"].values
        cr_val = cr[0] if len(cr) else 0.0
        L.append(f"| {sr['segment_id']} | {sr['budget_ratio']:.2f} | {sr['event_recall']:.3f} | {cr_val:.3f} | {cr_val - sr['event_recall']:+.3f} |")

    L.append("\n## Cross-check: c2 (strict-replay LOSO) vs ceilings\n")
    L.append("| segment | budget | static_ceil | closed_ceil | c2_loso | c2-static | c2-closed |")
    L.append("|---|---|---|---|---|---|---|")
    c2_agg = c2f.groupby(["held_out_segment", "budget_ratio"])["event_recall"].mean().reset_index()
    for _, sr in c2_agg.iterrows():
        seg = sr["held_out_segment"]
        br = sr["budget_ratio"]
        sc = static_agg[(static_agg.segment_id == seg) & (static_agg.budget_ratio == br)]["event_recall"].values
        cc = closed_agg[(closed_agg.segment_id == seg) & (closed_agg.budget_ratio == br)]["event_recall"].values
        scv = sc[0] if len(sc) else 0.0
        ccv = cc[0] if len(cc) else 0.0
        L.append(f"| {seg} | {br:.2f} | {scv:.3f} | {ccv:.3f} | {sr['event_recall']:.3f} | {sr['event_recall']-scv:+.3f} | {sr['event_recall']-ccv:+.3f} |")

    L.append("\n## Arm utility summary\n")
    L.append("| arm | n_proposed | n_positive | positive_rate | mean_u | selected_static | selected_closed |")
    L.append("|---|---|---|---|---|---|---|")
    for _, r in arm_summary.iterrows():
        L.append(f"| {r['arm_name']} | {r['n_proposed']} | {r['n_positive']} | {r['positive_rate']:.3f} | {r['mean_u']:.3f} | {r['selected_static']} | {r['selected_closedloop']} |")

    L.append("\n## Verdict\n")
    # Check if paradox resolved
    d30_static = static_agg[(static_agg.segment_id == "dataset3_0_1200") & (static_agg.budget_ratio > 0.15)]["event_recall"].max()
    d30_closed = closed_agg[(closed_agg.segment_id == "dataset3_0_1200") & (closed_agg.budget_ratio > 0.15)]["event_recall"].max()
    d30_c2 = c2_agg[(c2_agg.held_out_segment == "dataset3_0_1200") & (c2_agg.budget_ratio > 0.15)]["event_recall"].max()

    L.append(f"- dataset3_0_1200 static ceiling max: {d30_static:.3f}")
    L.append(f"- dataset3_0_1200 closed-loop ceiling max: {d30_closed:.3f}")
    L.append(f"- dataset3_0_1200 c2 LOSO max: {d30_c2:.3f}")

    if d30_closed >= d30_c2 - 0.01:
        L.append("- **PASS**: closed-loop oracle ceiling >= c2, paradox resolved.")
    else:
        L.append("- **NOTE**: closed-loop oracle ceiling < c2. The exploration bonus may be insufficient; or the policy learned something the oracle cannot express with marginal_utility alone.")

    L.append(
        "\n- The original T028e-0 ceiling is a **static trajectory ceiling** — it is iterative but follows a fixed greedy path due to the safety override. The closed-loop oracle ceiling with exploration bonus is a closer approximation of an ideal oracle. Neither achieves the global optimal (which would require DP), but the closed-loop variant doesn't get stuck in DISCOVER-only chains."
    )

    md = OUT / "t028e_diagnostics_report.md"
    md.write_text("\n".join(L))
    print(f"\nwrote {OUT / 't028e_candidate_table.csv'}")
    print(f"wrote {OUT / 't028e_arm_utility_summary.csv'}")
    if len(zp_hits):
        print(f"wrote {OUT / 't028e_zero_proxy_hits.csv'}")
    print(f"wrote {OUT / 't028e_diagnostics_frontier.csv'}")
    print(f"wrote {md}")


if __name__ == "__main__":
    main()
