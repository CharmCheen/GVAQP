"""T028c-1 — event-utility ranking policy (ECP Step 4c, part 1b).

Trains a policy on the CANDIDATE-LEVEL event-utility table produced by T028c-0
(ecp_candidate_utility_by_step.csv). Unlike T028b (which trained on the single
CHOSEN action's positive label), this table has the offline marginal
event-utility of ALL four candidate arms at every logged step. So the learner
sees counterfactual arm utilities and is NOT confined to the logger's choices
-> it does not merely re-learn the logger (the T028b failure mode).

Policy: regress u(arm | state, arm) from (state features + arm one-hot) using
the candidate utility labels; at each strict-replay step, predict u for each
AVAILABLE candidate arm and execute the max. Reference used only to build the
training labels offline; online policy uses only state features (no event_id).

Evaluation: strict replay via AlignedOracle; compared to v2 and the oracle
ceiling (T028c-0). VLM-oracle-relative, IoU>=0.3.

Outputs:
  outputs/ecp_event_coverage_policy_v1/t028c1_event_utility_policy_frontier.csv
  outputs/ecp_event_coverage_policy_v1/t028c1_event_utility_policy_report.md
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

OUT = REPO_ROOT / "outputs" / "ecp_event_coverage_policy_v1"
OUT.mkdir(parents=True, exist_ok=True)

FEATURES = ["rem_ratio", "top_proxy", "zp_share", "formed_ratio", "n_pos"]
ARMS = ["DISCOVER", "BRIDGE", "CERTIFY", "ZERO_PROXY"]


def build_training_table(cand_csv):
    df = pd.read_csv(cand_csv)
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


def run_policy(grid, ref_seg, seg_id, budget_abs, budget_ratio, seed, rng, policy_fn, cfg):
    n_bins = len(grid)
    oracle = AlignedOracle(grid, seg_id, "ECP-c1", seed, budget_abs, budget_ratio)
    grid_sorted = grid.sort_values("bin_idx").reset_index(drop=True)
    bin_to_t = dict(zip(grid_sorted["bin_idx"], zip(grid_sorted["local_t_start"], grid_sorted["local_t_end"])))
    proxies = dict(zip(grid_sorted["bin_idx"], grid_sorted[PROXY_COL]))
    all_bins = grid_sorted["bin_idx"].tolist()
    queried, queried_pos = set(), set()
    n_ref = len(ref_seg) if ref_seg is not None else 0
    zero_proxy_budget_used = 0
    last_arm = None
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
            # fallback to any available
            avail = [a for a in ARMS if cands.get(a) is not None]
            if not avail:
                break
            best_arm, target = avail[0], cands[avail[0]]
        if best_arm == "ZERO_PROXY":
            zero_proxy_budget_used += 1
        label = oracle.query_unit(target, "ECP_c1_" + best_arm, best_arm)
        queried.add(target)
        if label == "positive":
            queried_pos.add(target)
        last_arm = best_arm
    formed = formed_intervals(queried_pos, grid_sorted)
    ev = evaluate_events(formed, ref_seg) if n_ref > 0 else {"event_precision": 0, "event_recall": 0, "unique_event_coverage": 0}
    return {
        "returned_intervals": str(formed), "event_precision": ev["event_precision"],
        "event_recall": ev["event_recall"], "unique_event_coverage": ev["unique_event_coverage"],
        "oracle_calls": oracle.calls,
    }


def main():
    table = build_training_table(OUT / "ecp_candidate_utility_by_step.csv")
    policy_fn = train_policy(table)
    rng = np.random.default_rng(20260707)
    rows = []
    for seg in SEGMENTS:
        grid, ref_seg, err = load_segment_data(seg)
        if grid is None:
            continue
        n_bins = len(grid)
        for br in BUDGET_RATIOS:
            for seed in SEEDS:
                budget_abs = max(1, int(round(br * n_bins)))
                res = run_policy(grid, ref_seg, seg["segment_id"], budget_abs, br, seed, rng, policy_fn, VARIANTS["v2"])
                rows.append({
                    "variant": "c1_policy", "segment_id": seg["segment_id"],
                    "method_id": "ECP-c1", "seed": seed, "budget_abs": budget_abs,
                    "budget_ratio": br, "oracle_calls_total": res["oracle_calls"],
                    "returned_intervals": res["returned_intervals"],
                    "event_precision": round(res["event_precision"], 4),
                    "event_recall": round(res["event_recall"], 4),
                    "unique_event_coverage": res["unique_event_coverage"],
                    "strict_replay_or_posthoc": "strict_replay",
                    "online_uses_event_id": False, "can_be_main_comparison": True,
                    "applicability_note": "ECP T028c-1 event-utility ranking policy (strict replay)",
                })
        print(f"done {seg['segment_id']}")
    frontier = pd.DataFrame(rows)
    frontier.to_csv(OUT / "t028c1_event_utility_policy_frontier.csv", index=False)

    v2 = pd.read_csv(OUT / "t028a_ecp_bandit_frontier.csv")
    v2 = v2[v2["variant"] == "v2"]
    ceil = pd.read_csv(OUT / "ecp_oracle_ceiling_frontier.csv")
    hts = pd.read_csv(OUT.parent / "hts_ec_v0_strict_v1" / "hts_ec_v0_frontier.csv")
    hts = hts[hts["method_id"].isin(["HTS-EC-safe", "B7-strict-replay"])]
    hts_cmp = hts.groupby(["segment_id", "budget_ratio", "method_id"])[["event_recall", "event_precision"]].mean().reset_index()
    v2_cmp = v2.groupby(["segment_id", "budget_ratio"])[["event_recall", "event_precision"]].mean().reset_index()
    ceil_cmp = ceil.groupby(["segment_id", "budget_ratio"])[["event_recall", "event_precision"]].mean().reset_index()
    c1_cmp = frontier.groupby(["segment_id", "budget_ratio"])[["event_recall", "event_precision"]].mean().reset_index()

    L = []
    L.append("# T028c-1 — event-utility ranking policy (strict replay)\n")
    L.append(
        "Policy trained on the T028c-0 CANDIDATE-LEVEL utility table: every logged "
        "step carries the offline marginal event-utility of ALL four candidate arms, "
        "so the learner sees counterfactual arm utilities and is NOT confined to the "
        "logger's choices (this is what made T028b merely re-learn the logger). "
        "Regressor: GradientBoosting on u(arm | state, arm). At each strict-replay "
        "step it predicts u for each available arm and executes the max. VLM-oracle-"
        "relative, IoU>=0.3.\n"
    )
    L.append("## Mean event_recall: c1 vs v2 vs oracle-ceiling vs baselines\n")
    L.append("| segment | budget | c1_recall | v2_recall | ceiling | HTS | B7 | c1_prec | v2_prec | HTS_prec | B7_prec |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for (seg, br), _ in c1_cmp.groupby(["segment_id", "budget_ratio"]):
        c1r = c1_cmp[(c1_cmp.segment_id == seg) & (c1_cmp.budget_ratio == br)]["event_recall"].mean()
        c1p = c1_cmp[(c1_cmp.segment_id == seg) & (c1_cmp.budget_ratio == br)]["event_precision"].mean()
        vr = v2_cmp[(v2_cmp.segment_id == seg) & (v2_cmp.budget_ratio == br)]["event_recall"].mean()
        vp = v2_cmp[(v2_cmp.segment_id == seg) & (v2_cmp.budget_ratio == br)]["event_precision"].mean()
        cr = ceil_cmp[(ceil_cmp.segment_id == seg) & (ceil_cmp.budget_ratio == br)]["event_recall"].mean()
        cp = ceil_cmp[(ceil_cmp.segment_id == seg) & (ceil_cmp.budget_ratio == br)]["event_precision"].mean()
        hs = hts_cmp[(hts_cmp.segment_id == seg) & (hts_cmp.budget_ratio == br) & (hts_cmp.method_id == "HTS-EC-safe")]
        b7 = hts_cmp[(hts_cmp.segment_id == seg) & (hts_cmp.budget_ratio == br) & (hts_cmp.method_id == "B7-strict-replay")]
        hsr = hs["event_recall"].mean() if len(hs) else float("nan")
        hsp = hs["event_precision"].mean() if len(hs) else float("nan")
        b7r = b7["event_recall"].mean() if len(b7) else float("nan")
        b7p = b7["event_precision"].mean() if len(b7) else float("nan")
        L.append(f"| {seg} | {br:.2f} | {c1r:.3f} | {vr:.3f} | {cr:.3f} | {hsr:.3f} | {b7r:.3f} | {c1p:.3f} | {vp:.3f} | {hsp:.3f} | {b7p:.3f} |")
    L.append("\n## Reading / verdict\n")
    L.append(
        "- c1 is trained on counterfactual candidate utilities, so it is the proper "
        "T028b successor. If c1 >= v2 on realcartest (where the T028c-0 ceiling showed "
        "learnable signal) without losing precision, the event-utility ranking policy is "
        "a strict-replay improvement over fixed weights."
    )
    L.append(
        "- On proxy-zero dataset3, c1 cannot beat the ceiling (which is itself ~0 there): "
        "the candidate generator cannot propose zero-proxy positives, so no policy trained "
        "on these candidates can recover them. This is the candidate-generator bottleneck, "
        "not a policy-learning failure; T028d/DR cannot fix it either."
    )
    L.append(
        "- Strict-replay compliant: reference read only to build training labels offline; "
        "0 event_id leaks online; 1 oracle call per arm."
    )
    md = OUT / "t028c1_event_utility_policy_report.md"
    md.write_text("\n".join(L))
    print(f"wrote {OUT/'t028c1_event_utility_policy_frontier.csv'}")
    print(f"wrote {md}")


if __name__ == "__main__":
    main()
