"""T033a — full-policy oracle router ceiling.

Given existing per-seed strict-replay results for all methods, computes:
  - Per (segment, budget, seed): which policy achieves best event_recall?
  - Per (segment, budget): policy win counts across seeds
  - Oracle router ceiling: if a perfect oracle picks the best policy per cell,
    what's the aggregate recall?

This answers: "is there enough complementarity across methods that a router
could provide significant lift over any single method?"

Data sources (per-seed):
  hts_ec_v0_strict_v1/hts_ec_v0_frontier.csv  — B7, D3, EventLift, HTS-EC, TopProxy
  ecp_event_coverage_policy_v1/t028e1_loso_frontier.csv — ECP-c2 (LOSO)
  ecp_event_coverage_policy_v1/t028c2_loso_frontier.csv — ECP-c1 (LOSO)
  ecp_event_coverage_policy_v1/t028a_ecp_bandit_frontier.csv — ECP-v2

Policies considered:
  B7-strict-replay, D3-norepair-core-strict, EventLift-discover-certify,
  HTS-EC-safe, fixed_10s_topproxy, ECP-c2-globalcap, ECP-c1, ECP-v2

Outputs:
  outputs/ecp_event_coverage_policy_v1/t033a_router_ceiling.csv
  outputs/ecp_event_coverage_policy_v1/t033a_policy_win_matrix.csv
  outputs/ecp_event_coverage_policy_v1/t033a_router_report.md
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from run_ecp_t027_bandit import SEGMENTS, BUDGET_RATIOS  # noqa: E402

OUT = REPO_ROOT / "outputs" / "ecp_event_coverage_policy_v1"
OUT.mkdir(parents=True, exist_ok=True)

ALL_SEGMENTS = [s["segment_id"] for s in SEGMENTS]


def load_hts_per_seed():
    """Load baselines from hts_ec_v0_strict_v1 (seed=-1 is best-of-3 per-cell aggregate)."""
    df = pd.read_csv(REPO_ROOT / "outputs/hts_ec_v0_strict_v1/hts_ec_v0_frontier.csv")
    # Use all seeds — seed=-1 is the per-cell aggregate for baselines
    methods = {
        "B7-strict-replay": "B7",
        "D3-norepair-core-strict": "D3",
        "EventLift-discover-certify": "EventLift-DC",
        "HTS-EC-safe": "HTS-EC",
        "fixed_10s_topproxy": "TopProxy",
    }
    rows = []
    for mid, label in methods.items():
        sub = df[df["method_id"] == mid]
        for _, r in sub.iterrows():
            rows.append({
                "policy": label,
                "segment_id": r["segment_id"],
                "budget_ratio": r["budget_ratio"],
                "seed": r["seed"],
                "event_recall": r["event_recall"],
                "event_precision": r["event_precision"],
                "unique_event_coverage": r.get("unique_event_coverage", 0),
            })
    return pd.DataFrame(rows)


def load_ecp_per_seed(path, var_map):
    """Load ECP LOSO or non-LOSO results with per-seed granularity."""
    df = pd.read_csv(path)
    rows = []
    for var, label in var_map.items():
        sub = df[df["variant"] == var]
        # For LOSO, segment_id = held_out_segment
        seg_col = "held_out_segment" if "held_out_segment" in sub.columns else "segment_id"
        for _, r in sub.iterrows():
            rows.append({
                "policy": label,
                "segment_id": r[seg_col],
                "budget_ratio": r["budget_ratio"],
                "seed": r["seed"],
                "event_recall": r["event_recall"],
                "event_precision": r["event_precision"],
                "unique_event_coverage": r.get("unique_event_coverage", 0),
            })
    return pd.DataFrame(rows)


def compute_router_ceiling(all_data):
    """Compute mean recall per (segment, budget, policy), then oracle picks best per cell.
    Seeds are aggregated first per method, then the router selects best method per cell."""
    # Aggregate to mean per (segment, budget, policy)
    mean_data = all_data.groupby(["policy", "segment_id", "budget_ratio"]).agg(
        recall=("event_recall", "mean"),
        prec=("event_precision", "mean"),
    ).reset_index()

    router_agg_rows = []
    win_matrix = {}

    for seg in ALL_SEGMENTS:
        win_matrix[seg] = {}
        for br in BUDGET_RATIOS:
            key = (seg, br)
            win_matrix[seg][br] = {}

            seg_data = mean_data[(mean_data["segment_id"] == seg)
                                 & (abs(mean_data["budget_ratio"] - br) < 0.001)]
            if len(seg_data) == 0:
                continue

            best_idx = seg_data["recall"].idxmax()
            best_policy = seg_data.loc[best_idx, "policy"]
            best_recall = seg_data.loc[best_idx, "recall"]
            best_prec = seg_data.loc[best_idx, "prec"]

            router_agg_rows.append({
                "segment_id": seg,
                "budget_ratio": br,
                "router_recall": best_recall,
                "router_precision": best_prec,
                "best_policy": best_policy,
            })
            win_matrix[seg][br][best_policy] = 1

    router_agg = pd.DataFrame(router_agg_rows)
    return router_agg, mean_data, win_matrix


def compute_policy_aggregate(all_data):
    """Compute per-policy mean recall over seeds."""
    agg = all_data.groupby(["policy", "segment_id", "budget_ratio"]).agg(
        recall=("event_recall", "mean"),
        prec=("event_precision", "mean"),
    ).reset_index()
    return agg


def main():
    # Load all data
    hts_df = load_hts_per_seed()

    c2_df = load_ecp_per_seed(OUT / "t028e1_loso_frontier.csv",
                               {"c2_loso": "ECP-c2"})
    c1_df = load_ecp_per_seed(OUT / "t028c2_loso_frontier.csv",
                               {"c1_loso": "ECP-c1"})
    v2_df = load_ecp_per_seed(OUT / "t028a_ecp_bandit_frontier.csv",
                               {"v2": "ECP-v2"})

    all_data = pd.concat([hts_df, c2_df, c1_df, v2_df], ignore_index=True)
    all_policies = sorted(all_data["policy"].unique())

    # Router ceiling
    router_agg, mean_data, win_matrix = compute_router_ceiling(all_data)
    router_agg.to_csv(OUT / "t033a_router_ceiling.csv", index=False)

    # Per-policy aggregate
    policy_agg = mean_data.copy()

    # Best single method aggregate (per cell: max over policies)
    best_single = mean_data.groupby(["segment_id", "budget_ratio"]).agg(
        best_single_recall=("recall", "max"),
        best_single_policy=("recall", lambda x: mean_data.loc[x.idxmax(), "policy"]),
    ).reset_index()

    # Rename router_agg columns for consistency
    router_cmp = router_agg.rename(columns={"router_recall": "recall", "router_precision": "prec"})

    # --- Win matrix ---
    win_rows = []
    for seg in ALL_SEGMENTS:
        for br in BUDGET_RATIOS:
            row = {"segment": seg, "budget": br}
            for pol in all_policies:
                wins = win_matrix.get(seg, {}).get(br, {}).get(pol, 0)
                row[pol] = int(wins)
            win_rows.append(row)
    win_df = pd.DataFrame(win_rows)
    win_df.to_csv(OUT / "t033a_policy_win_matrix.csv", index=False)

    # --- Report ---
    L = []
    L.append("# T033a — Full-policy oracle router ceiling\n")
    L.append(
        "For each (segment, budget, seed), the oracle router selects the policy "
        "with the best `event_recall`. This gives an upper bound for what a learned "
        "router could achieve IF it could perfectly identify the best policy per cell.\n"
    )
    L.append(f"Policies: {', '.join(all_policies)}\n")

    L.append("## Router ceiling vs best single method\n")
    L.append("| segment | budget | router_recall | best_single | router_policy | best_policy |")
    L.append("|---|---|---|---|---|---|")

    total_router_recall = []
    total_best_recall = []

    for seg in ALL_SEGMENTS:
        for br in BUDGET_RATIOS:
            rr = router_agg[(router_agg.segment_id == seg)
                            & (abs(router_agg.budget_ratio - br) < 0.001)]
            bs = best_single[(best_single.segment_id == seg)
                             & (abs(best_single.budget_ratio - br) < 0.001)]
            if len(rr) == 0 or len(bs) == 0:
                continue
            rr_val = rr.iloc[0]["router_recall"]
            bs_val = bs.iloc[0]["best_single_recall"]
            rp = rr.iloc[0]["best_policy"]
            bp = bs.iloc[0]["best_single_policy"]

            total_router_recall.append(rr_val)
            total_best_recall.append(bs_val)

            L.append(f"| {seg} | {br:.2f} | {rr_val:.3f} | {bs_val:.3f} | {rp} | {bp} |")

    L.append(f"\n**Macro router recall: {np.mean(total_router_recall):.3f}**")
    L.append(f"**Macro best single recall: {np.mean(total_best_recall):.3f}**")
    L.append(f"**Router lift: {np.mean(total_router_recall) - np.mean(total_best_recall):+.3f}**\n")

    # Per-video summary
    for video in ["realcartest", "dataset3"]:
        L.append(f"\n### {video}\n")
        for pol in all_policies:
            sub = policy_agg[(policy_agg.policy == pol) & policy_agg.segment_id.str.startswith(video)]
            if len(sub):
                L.append(f"- **{pol}**: recall={sub['recall'].mean():.3f}, prec={sub['prec'].mean():.3f}")
        rr_sub = router_agg[router_agg.segment_id.str.startswith(video)]
        if len(rr_sub):
            L.append(f"- **Oracle Router**: recall={rr_sub['router_recall'].mean():.3f}")

    # Policy win matrix
    L.append("\n## Policy win matrix (1 = best recall for that cell)\n")
    L.append("| segment | budget | " + " | ".join(p[:10] for p in all_policies) + " |")
    L.append("| " + " | ".join(["-"] * (3 + len(all_policies))) + " |")
    for _, row in win_df.iterrows():
        cells = []
        for pol in all_policies:
            w = int(row.get(pol, 0))
            cells.append(str(w))
        L.append(f"| {row['segment']} | {row['budget']:.2f} | " + " | ".join(cells) + " |")

    # Policy win count summary
    L.append("\n## Policy composition: which policies dominate?\n")
    total_wins = {p: int(win_df[p].sum()) for p in all_policies}
    total_all = sum(total_wins.values())
    for pol in sorted(all_policies, key=lambda p: -total_wins[p]):
        L.append(f"- **{pol}**: {total_wins[pol]} wins ({total_wins[pol]/max(1,total_all)*100:.1f}%)")

    L.append("\n## Verdict\n")
    rc_router = np.mean(total_router_recall)
    rc_best = np.mean(total_best_recall)

    # Find best single methods
    pol_macro = {}
    for pol in all_policies:
        sub = policy_agg[policy_agg.policy == pol]
        pol_macro[pol] = sub["recall"].mean()
    best_pol_name = max(pol_macro, key=pol_macro.get)
    best_pol_recall = pol_macro[best_pol_name]

    lift_over_best_single = rc_router - best_pol_recall
    lift_over_second = rc_router - sorted(pol_macro.values(), reverse=True)[1] if len(pol_macro) > 1 else 0

    if lift_over_best_single > 0.05:
        L.append(f"- **POSITIVE**: oracle router (per-cell max) achieves {rc_router:.3f} vs best single method {best_pol_name} ({best_pol_recall:.3f}), lift = +{lift_over_best_single:.3f}.")
        L.append(f"  Significant complementarity — a router could provide meaningful lift.")
    elif lift_over_best_single > 0.02:
        L.append(f"- **MARGINAL**: oracle router ({rc_router:.3f}) lifts +{lift_over_best_single:.3f} over {best_pol_name} ({best_pol_recall:.3f}).")
    else:
        L.append(f"- **NEGLIGIBLE**: oracle router ({rc_router:.3f}) lifts only +{lift_over_best_single:.3f} over {best_pol_name} ({best_pol_recall:.3f}).")

    L.append(
        "\n- Oracle router is an OFFLINE CEILING — it picks the best policy per cell "
        "with knowledge of final recall. A learned router (T033b) would need to predict "
        "the best policy from early-state features without seeing future labels."
    )

    md = OUT / "t033a_router_report.md"
    md.write_text("\n".join(L))
    print(f"\nwrote {OUT / 't033a_router_ceiling.csv'}")
    print(f"wrote {OUT / 't033a_policy_win_matrix.csv'}")
    print(f"wrote {md}")

    print(f"\n=== Oracle Router Ceiling ===")
    print(f"Router (per-cell max):     {rc_router:.3f}")
    print(f"Best single method (B7):   {best_pol_recall:.3f}")
    print(f"Lift over best single:     +{lift_over_best_single:.3f}")
    print(f"Cell wins:")
    for pol in sorted(all_policies, key=lambda x: -total_wins[x]):
        if total_wins[pol] > 0:
            print(f"  {pol}: {total_wins[pol]} cell wins")


if __name__ == "__main__":
    main()
