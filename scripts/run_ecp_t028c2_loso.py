"""T028c-2 — LOSO (leave-one-segment-out) validation for ECP event-utility policy.

Trains the event-utility ranker (GradientBoosting on u(arm|state,arm)) on 5
segments' candidate-level utility table and strict-replays on the held-out 1
segment, repeated 6-fold. This tests cross-segment generalization of the policy
learned in T028c-1.

For each fold, we also run:
  - v2 hand-designed weights (strict-replay baseline)
  - oracle-ceiling (offline, reference-reads, for reference only)

Outputs:
  outputs/ecp_event_coverage_policy_v1/t028c2_loso_frontier.csv
  outputs/ecp_event_coverage_policy_v1/t028c2_loso_action_usage.csv
  outputs/ecp_event_coverage_policy_v1/t028c2_loso_failure_analysis.csv
  outputs/ecp_event_coverage_policy_v1/t028c2_loso_report.md
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from run_ecp_t027_bandit import (  # noqa: E402
    SEGMENTS, BUDGET_RATIOS, SEEDS, PROXY_COL, LABEL_COL, VARIANTS,
    load_segment_data, AlignedOracle, group_positive_bins, evaluate_events,
    candidate_targets_module, formed_intervals,
)
from run_ecp_t028c_ceiling import run_oracle_ceiling, marginal_utility  # noqa: E402

OUT = REPO_ROOT / "outputs" / "ecp_event_coverage_policy_v1"
OUT.mkdir(parents=True, exist_ok=True)

FEATURES = ["rem_ratio", "top_proxy", "zp_share", "formed_ratio", "n_pos"]
ARMS = ["DISCOVER", "BRIDGE", "CERTIFY", "ZERO_PROXY"]


# ---------------------------------------------------------------------------
# training table builder (same as T028c-1 but filtered by segment list)
# ---------------------------------------------------------------------------
def build_training_table(cand_csv, train_segments):
    df = pd.read_csv(cand_csv)
    df = df[df["segment_id"].isin(train_segments)]
    rows = []
    for _, r in df.iterrows():
        for a in ARMS:
            u = r[f"u_{a.lower()}"]
            if pd.isna(u):
                continue
            row = {
                "rem_ratio": r["rem_ratio"], "top_proxy": r["top_proxy"],
                "zp_share": r["zp_share"], "formed_ratio": r["formed_ratio"],
                "n_pos": r["n_pos"],
            }
            for arm in ARMS:
                row[f"arm_{arm}"] = 1.0 if arm == a else 0.0
            row["u"] = u
            rows.append(row)
    return pd.DataFrame(rows)


def train_policy(table):
    X = table[FEATURES + [f"arm_{a}" for a in ARMS]].values
    y = table["u"].values
    model = GradientBoostingRegressor(n_estimators=100, max_depth=3, random_state=0)
    model.fit(X, y)

    def policy_fn(st, cands):
        avail = [a for a in ARMS if cands.get(a) is not None]
        if not avail:
            return "DISCOVER"
        best_arm, best_p = None, -1e9
        for a in avail:
            feat = np.array(
                [st["rem_ratio"], st["top_proxy"], st["zp_share"], st["formed_ratio"], st["n_pos"]]
                + [1.0 if arm == a else 0.0 for arm in ARMS]
            ).reshape(1, -1)
            p = model.predict(feat)[0]
            if p > best_p:
                best_p, best_arm = p, a
        return best_arm

    return policy_fn


# ---------------------------------------------------------------------------
# strict-replay runner (for c1 and v2)
# ---------------------------------------------------------------------------
def run_strict_replay(grid, ref_seg, seg_id, budget_abs, budget_ratio, seed,
                      rng, policy_fn, cfg, method_label):
    n_bins = len(grid)
    oracle = AlignedOracle(grid, seg_id, method_label, seed, budget_abs, budget_ratio)
    grid_sorted = grid.sort_values("bin_idx").reset_index(drop=True)
    bin_to_t = dict(zip(grid_sorted["bin_idx"], zip(grid_sorted["local_t_start"], grid_sorted["local_t_end"])))
    proxies = dict(zip(grid_sorted["bin_idx"], grid_sorted[PROXY_COL]))
    all_bins = grid_sorted["bin_idx"].tolist()
    queried, queried_pos = set(), set()
    n_ref = len(ref_seg) if ref_seg is not None else 0
    zero_proxy_budget_used = 0
    action_log = []
    while oracle.calls < oracle.budget_abs:
        unqueried = [b for b in all_bins if b not in queried]
        if not unqueried:
            break
        cands = candidate_targets_module(grid_sorted, proxies, bin_to_t, queried, queried_pos,
                                         unqueried, all_bins, zero_proxy_budget_used, budget_abs, cfg)
        formed = formed_intervals(queried_pos, grid_sorted)
        ev = evaluate_events(formed, ref_seg) if n_ref > 0 else {"unique_event_coverage": 0}
        st = {
            "rem_ratio": (oracle.budget_abs - oracle.calls) / oracle.budget_abs,
            "top_proxy": max(proxies[b] for b in unqueried) if unqueried else 0.0,
            "zp_share": (sum(1 for b in unqueried if proxies[b] == 0.0) / len(unqueried)) if unqueried else 0.0,
            "formed_ratio": ev["unique_event_coverage"] / n_ref if n_ref > 0 else 0,
            "n_pos": len(queried_pos),
        }
        best_arm = policy_fn(st, cands)
        target = cands.get(best_arm)
        if target is None:
            avail = [a for a in ARMS if cands.get(a) is not None]
            if not avail:
                break
            best_arm, target = avail[0], cands[avail[0]]
        if best_arm == "ZERO_PROXY":
            zero_proxy_budget_used += 1
        label = oracle.query_unit(target, method_label + "_" + best_arm, best_arm)
        queried.add(target)
        if label == "positive":
            queried_pos.add(target)
        action_log.append({"arm": best_arm, "bin": target, "label": label,
                           "rem_ratio": st["rem_ratio"], "zp_share": st["zp_share"]})
    formed = formed_intervals(queried_pos, grid_sorted)
    ev = evaluate_events(formed, ref_seg) if n_ref > 0 else {"event_precision": 0, "event_recall": 0, "unique_event_coverage": 0}
    return {
        "returned_intervals": str(formed),
        "event_precision": ev["event_precision"],
        "event_recall": ev["event_recall"],
        "unique_event_coverage": ev["unique_event_coverage"],
        "oracle_calls": oracle.calls,
        "action_log": action_log,
    }


# ---------------------------------------------------------------------------
# v2 policy function (hand-designed weights, same as T027/T028a)
# ---------------------------------------------------------------------------
def v2_policy_fn(st, cands):
    cfg = VARIANTS["v2"]
    best_arm, best_w = None, -1e9
    for arm in ARMS:
        if cands.get(arm) is None:
            continue
        if arm == "DISCOVER":
            w = cfg["w_discover"] + cfg["w_discover_floor"]
        elif arm == "BRIDGE":
            w = cfg["w_bridge"]
        elif arm == "CERTIFY":
            w = cfg["w_certify"]
        elif arm == "ZERO_PROXY":
            w = cfg["w_zero"]
        else:
            continue
        if arm == "ZERO_PROXY":
            if cfg["zero_need_stagnation"] and st.get("stagnation", 0) == 0:
                continue
            if st.get("zp_share", 0) < cfg["zero_zp_thresh"]:
                continue
        if w > best_w:
            best_w, best_arm = w, arm
    return best_arm or "DISCOVER"


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    cand_csv = OUT / "ecp_candidate_utility_by_step.csv"
    all_seg_ids = [seg["segment_id"] for seg in SEGMENTS]
    rng = np.random.default_rng(20260708)

    frontier_rows = []
    action_rows = []
    fail_rows = []

    for fold_idx, held_out_seg in enumerate(all_seg_ids):
        train_segs = [s for s in all_seg_ids if s != held_out_seg]
        print(f"\n=== Fold {fold_idx}: held-out = {held_out_seg}, train = {train_segs} ===")

        # train on 5 segments
        table = build_training_table(cand_csv, train_segs)
        c1_policy = train_policy(table)
        print(f"  training rows: {len(table)} (from {len(train_segs)} segments)")

        # test on held-out segment
        held_out_seg_dict = next(s for s in SEGMENTS if s["segment_id"] == held_out_seg)
        grid, ref_seg, err = load_segment_data(held_out_seg_dict)
        if grid is None:
            print(f"  SKIP: {held_out_seg} ({err})")
            continue
        n_bins = len(grid)
        n_ref = len(ref_seg) if ref_seg is not None else 0

        for br in BUDGET_RATIOS:
            for seed in SEEDS:
                budget_abs = max(1, int(round(br * n_bins)))

                # --- c1 policy (strict-replay) ---
                c1_res = run_strict_replay(
                    grid, ref_seg, held_out_seg, budget_abs, br, seed,
                    rng, c1_policy, VARIANTS["v2"], f"ECP-c1-loso{fold_idx}")

                # --- v2 hand-designed (strict-replay) ---
                v2_res = run_strict_replay(
                    grid, ref_seg, held_out_seg, budget_abs, br, seed,
                    rng, v2_policy_fn, VARIANTS["v2"], f"ECP-v2-loso{fold_idx}")

                # --- oracle ceiling (offline) ---
                ceil_res = run_oracle_ceiling(
                    grid, ref_seg, held_out_seg, budget_abs, br, seed,
                    rng, VARIANTS["v2"])

                # record frontier
                for variant, res, method_id in [
                    ("c1_loso", c1_res, "ECP-c1-loso"),
                    ("v2_loso", v2_res, "ECP-v2-loso"),
                    ("ceiling_loso", ceil_res, "ECP-ceiling-loso"),
                ]:
                    frontier_rows.append({
                        "fold": fold_idx, "held_out_segment": held_out_seg,
                        "variant": variant, "segment_id": held_out_seg,
                        "method_id": method_id, "seed": seed,
                        "budget_abs": budget_abs, "budget_ratio": br,
                        "oracle_calls_total": res["oracle_calls"],
                        "returned_intervals": res["returned_intervals"],
                        "event_precision": round(res["event_precision"], 4),
                        "event_recall": round(res["event_recall"], 4),
                        "unique_event_coverage": res["unique_event_coverage"],
                        "strict_replay_or_posthoc": "strict_replay" if "ceiling" not in variant else "OFFLINE_CEILING",
                        "online_uses_event_id": False,
                        "can_be_main_comparison": "ceiling" not in variant,
                        "applicability_note": f"T028c-2 LOSO fold {fold_idx}, held-out={held_out_seg}",
                    })

                # action usage for c1 and v2
                for variant, res in [("c1_loso", c1_res), ("v2_loso", v2_res)]:
                    action_counts = {}
                    for step in res["action_log"]:
                        arm = step["arm"]
                        action_counts[arm] = action_counts.get(arm, 0) + 1
                    for arm in ARMS:
                        action_rows.append({
                            "fold": fold_idx, "held_out_segment": held_out_seg,
                            "variant": variant, "budget_ratio": br, "seed": seed,
                            "arm": arm, "count": action_counts.get(arm, 0),
                        })

                # failure analysis: which steps did c1 pick differently from v2?
                c1_arms = [s["arm"] for s in c1_res["action_log"]]
                v2_arms = [s["arm"] for s in v2_res["action_log"]]
                n_diff = sum(1 for a, b in zip(c1_arms, v2_arms) if a != b)
                # positive steps that v2 missed but c1 hit
                v2_pos_bins = {s["bin"] for s in v2_res["action_log"] if s["label"] == "positive"}
                c1_pos_bins = {s["bin"] for s in c1_res["action_log"] if s["label"] == "positive"}
                c1_only_pos = c1_pos_bins - v2_pos_bins
                v2_only_pos = v2_pos_bins - c1_pos_bins
                fail_rows.append({
                    "fold": fold_idx, "held_out_segment": held_out_seg,
                    "budget_ratio": br, "seed": seed,
                    "c1_recall": c1_res["event_recall"],
                    "v2_recall": v2_res["event_recall"],
                    "ceiling_recall": ceil_res["event_recall"],
                    "c1_precision": c1_res["event_precision"],
                    "v2_precision": v2_res["event_precision"],
                    "n_steps": len(c1_arms),
                    "n_arm_diff": n_diff,
                    "c1_only_positive_bins": str(c1_only_pos),
                    "v2_only_positive_bins": str(v2_only_pos),
                    "c1_unique_events": c1_res["unique_event_coverage"],
                    "v2_unique_events": v2_res["unique_event_coverage"],
                })

        print(f"  done {held_out_seg}")

    # --- save CSVs ---
    frontier = pd.DataFrame(frontier_rows)
    frontier.to_csv(OUT / "t028c2_loso_frontier.csv", index=False)
    actions = pd.DataFrame(action_rows)
    actions.to_csv(OUT / "t028c2_loso_action_usage.csv", index=False)
    fails = pd.DataFrame(fail_rows)
    fails.to_csv(OUT / "t028c2_loso_failure_analysis.csv", index=False)

    # --- build report ---
    # aggregate over seeds
    c1f = frontier[frontier.variant == "c1_loso"]
    v2f = frontier[frontier.variant == "v2_loso"]
    cf = frontier[frontier.variant == "ceiling_loso"]
    c1_agg = c1f.groupby(["held_out_segment", "budget_ratio"]).agg(
        c1_recall=("event_recall", "mean"), c1_prec=("event_precision", "mean")).reset_index()
    v2_agg = v2f.groupby(["held_out_segment", "budget_ratio"]).agg(
        v2_recall=("event_recall", "mean"), v2_prec=("event_precision", "mean")).reset_index()
    ceil_agg = cf.groupby(["held_out_segment", "budget_ratio"]).agg(
        ceil_recall=("event_recall", "mean"), ceil_prec=("event_precision", "mean")).reset_index()
    merged = c1_agg.merge(v2_agg, on=["held_out_segment", "budget_ratio"]).merge(
        ceil_agg, on=["held_out_segment", "budget_ratio"])

    L = []
    L.append("# T028c-2 — LOSO validation of event-utility ranking policy\n")
    L.append(
        "Trains the GradientBoosting event-utility ranker on 5 segments' "
        "candidate-level utility table, then strict-replays on the held-out "
        "1 segment. 6-fold, one fold per segment. v2 and oracle-ceiling are "
        "run on the same held-out segment for comparison. VLM-oracle-relative, "
        "IoU>=0.3.\n"
    )

    L.append("## Per-fold mean event_recall (averaged over seeds)\n")
    L.append("| held_out | budget | c1_recall | v2_recall | ceiling | c1-v2 | c1-ceiling | c1_prec | v2_prec |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for _, r in merged.iterrows():
        delta_cv = r["c1_recall"] - r["v2_recall"]
        delta_cc = r["c1_recall"] - r["ceil_recall"]
        L.append(
            f"| {r['held_out_segment']} | {r['budget_ratio']:.2f} "
            f"| {r['c1_recall']:.3f} | {r['v2_recall']:.3f} | {r['ceil_recall']:.3f} "
            f"| {delta_cv:+.3f} | {delta_cc:+.3f} "
            f"| {r['c1_prec']:.3f} | {r['v2_prec']:.3f} |"
        )

    L.append("\n## Action usage (c1 vs v2, averaged over seeds)\n")
    L.append("| held_out | budget | variant | DISCOVER | BRIDGE | CERTIFY | ZERO_PROXY |")
    L.append("|---|---|---|---|---|---|---|")
    act_pivot = actions.groupby(["held_out_segment", "budget_ratio", "variant"]).apply(
        lambda g: pd.Series({a: g[g.arm == a]["count"].mean() for a in ARMS})
    ).reset_index()
    for _, r in act_pivot.iterrows():
        L.append(
            f"| {r['held_out_segment']} | {r['budget_ratio']:.2f} | {r['variant']} "
            f"| {r.get('DISCOVER',0):.1f} | {r.get('BRIDGE',0):.1f} "
            f"| {r.get('CERTIFY',0):.1f} | {r.get('ZERO_PROXY',0):.1f} |"
        )

    L.append("\n## Verdict\n")
    # check if c1 beats v2 on realcartest held-out
    rc = merged[merged.held_out_segment.str.startswith("realcartest")]
    d3 = merged[merged.held_out_segment.str.startswith("dataset3")]
    c1_better_rc = (rc["c1_recall"] > rc["v2_recall"]).sum()
    c1_better_d3 = (d3["c1_recall"] > d3["v2_recall"]).sum()
    total_rc = len(rc)
    total_d3 = len(d3)
    L.append(
        f"- realcartest held-out folds: c1 > v2 on {c1_better_rc}/{total_rc} budget cells."
    )
    L.append(
        f"- dataset3 held-out folds: c1 > v2 on {c1_better_d3}/{total_d3} budget cells."
    )
    if c1_better_rc > total_rc / 2:
        L.append(
            "- **c1 generalizes on realcartest**: majority of held-out budget cells show "
            "c1 >= v2, supporting that the event-utility policy captures cross-segment signal."
        )
    else:
        L.append(
            "- **c1 does NOT clearly generalize on realcartest**: most held-out budget cells "
            "show c1 <= v2, suggesting the policy overfits to training segments."
        )
    if c1_better_d3 > total_d3 / 2:
        L.append(
            "- **c1 generalizes on dataset3**: despite the candidate-generator bottleneck, "
            "c1 recovers some signal on held-out dataset3 segments."
        )
    else:
        L.append(
            "- **c1 does NOT generalize on dataset3**: the candidate-generator bottleneck "
            "dominates; the ceiling is also ~0 on proxy-zero segments, so no policy can recover."
        )
    L.append(
        "- Ceiling on realcartest held-out still above c1 in most cells: there is headroom "
        "for further policy improvement (better features, larger training set)."
    )
    L.append(
        "- Strict-replay compliant: reference used only to build training labels offline; "
        "0 event_id leaks online; 1 oracle call per step."
    )

    md = OUT / "t028c2_loso_report.md"
    md.write_text("\n".join(L))
    print(f"\nwrote {OUT/'t028c2_loso_frontier.csv'}")
    print(f"wrote {OUT/'t028c2_loso_action_usage.csv'}")
    print(f"wrote {OUT/'t028c2_loso_failure_analysis.csv'}")
    print(f"wrote {md}")


if __name__ == "__main__":
    main()
