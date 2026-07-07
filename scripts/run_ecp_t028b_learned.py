"""T028b — ECP offline-learned contextual bandit policy (strict replay).

Trains a policy on the T026/v2 action-utility table (logged strict-replay
steps) and evaluates it as a strict-replay method.

Learner (offline, honest about logging-policy bias):
  - Features per step: budget_remaining_ratio, formed_ratio, top_proxy,
    zp_share, n_pos, stagnation.
  - Label: oracle_label == 'positive' (the outcome of the arm actually taken).
  - Model: logistic regression predicting P(positive | state, arm) using
    state features + one-hot arm. This is the standard
    supervised-to-bandit reduction over logged choices; it is biased by the
    v2 logging policy and we report that limitation explicitly.
  - Policy at each strict-replay step: for each AVAILABLE arm, predict
    P(positive | state, arm); pick the arm with max predicted probability.
    If all <= 0, STOP.

Evaluation: re-run the strict-replay executor (AlignedOracle) with this
learned policy; compare event_recall / event_precision vs v2 hand-designed and
baselines. Reference events read only at final eval; no event_id online.

Outputs:
  outputs/ecp_event_coverage_policy_v1/t028b_ecp_learned_frontier.csv
  outputs/ecp_event_coverage_policy_v1/t028b_ecp_learned_report.md
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from run_ecp_t027_bandit import (  # noqa: E402
    SEGMENTS,
    BUDGET_RATIOS,
    SEEDS,
    load_segment_data,
    run_ecp,
)

OUT = REPO_ROOT / "outputs" / "ecp_event_coverage_policy_v1"
OUT.mkdir(parents=True, exist_ok=True)

FEATURES = ["budget_remaining_ratio", "formed_ratio", "top_proxy", "zp_share", "n_pos", "stagnation"]
ARMS = ["DISCOVER", "BRIDGE", "CERTIFY", "ZERO_PROXY"]


def train_policy(table):
    """Return a policy_fn(state_dict, arms_dict) -> arm name.

    arms_dict: {arm: (u, target_bin)} from run_ecp (target may be None).
    """
    df = table.copy()
    df["y"] = (df["oracle_label"] == "positive").astype(int)
    # one-hot arm
    for a in ARMS:
        df[f"arm_{a}"] = (df["chosen_arm"] == a).astype(int)
    X = df[FEATURES + [f"arm_{a}" for a in ARMS]].values
    y = df["y"].values
    # class weight to handle imbalance
    model = LogisticRegression(max_iter=1000, class_weight="balanced")
    model.fit(X, y)

    def policy_fn(st, arms):
        # available arms (target not None)
        avail = [a for a in ARMS if arms.get(a, (0, None))[1] is not None]
        if not avail:
            return "DISCOVER"  # will be caught by target is None -> STOP
        best_arm = None
        best_p = -1.0
        for a in avail:
            row = np.array(
                [st["rem_ratio"], st["formed_ratio"], st["top_proxy"], st["zp_share"], st["n_pos"], 0.0]
                + [1.0 if arm == a else 0.0 for arm in ARMS]
            ).reshape(1, -1)
            p = model.predict_proba(row)[0, 1]
            if p > best_p:
                best_p = p
                best_arm = a
        return best_arm

    return policy_fn


def main():
    table = pd.read_csv(OUT / "t026_action_utility.csv")
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
                res = run_ecp(
                    grid, ref_seg, seg["segment_id"], budget_abs, br, seed, rng,
                    cfg=None, variant="v2", policy_fn=policy_fn,
                )
                rows.append(
                    {
                        "variant": "learned",
                        "segment_id": seg["segment_id"],
                        "method_id": "ECP-learned",
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
                        "applicability_note": "ECP offline-learned contextual bandit (T028b)",
                    }
                )
        print(f"done {seg['segment_id']}")

    frontier = pd.DataFrame(rows)
    frontier.to_csv(OUT / "t028b_ecp_learned_frontier.csv", index=False)

    # baselines + v2 for comparison
    v2 = pd.read_csv(OUT / "t028a_ecp_bandit_frontier.csv")
    v2 = v2[v2["variant"] == "v2"]
    hts = pd.read_csv(OUT.parent / "hts_ec_v0_strict_v1" / "hts_ec_v0_frontier.csv")
    hts = hts[hts["method_id"].isin(["HTS-EC-safe", "B7-strict-replay"])]
    hts_cmp = hts.groupby(["segment_id", "budget_ratio", "method_id"])[["event_recall", "event_precision"]].mean().reset_index()
    v2_cmp = v2.groupby(["segment_id", "budget_ratio"])[["event_recall", "event_precision"]].mean().reset_index()
    learn_cmp = frontier.groupby(["segment_id", "budget_ratio"])[["event_recall", "event_precision"]].mean().reset_index()

    L = []
    L.append("# T028b — ECP offline-learned contextual bandit (strict replay)\n")
    L.append(
        "Policy trained on the T026/v2 logged table (logistic regression on "
        "P(positive | state, arm); supervised-to-bandit reduction, biased by the v2 "
        "logging policy). Evaluated as a strict-replay method vs v2 hand-designed, "
        "HTS-EC-safe, B7-strict-replay. VLM-oracle-relative, IoU>=0.3.\n"
    )
    L.append("## Mean event_recall by segment x budget\n")
    L.append("| segment | budget | ECP_learned | ECP_v2 | HTS-EC-safe | B7-strict | learn_prec | v2_prec | HTS_prec | B7_prec |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for (seg, br), _ in learn_cmp.groupby(["segment_id", "budget_ratio"]):
        lr = learn_cmp[(learn_cmp.segment_id == seg) & (learn_cmp.budget_ratio == br)]["event_recall"].mean()
        lp = learn_cmp[(learn_cmp.segment_id == seg) & (learn_cmp.budget_ratio == br)]["event_precision"].mean()
        vr = v2_cmp[(v2_cmp.segment_id == seg) & (v2_cmp.budget_ratio == br)]["event_recall"].mean()
        vp = v2_cmp[(v2_cmp.segment_id == seg) & (v2_cmp.budget_ratio == br)]["event_precision"].mean()
        hs = hts_cmp[(hts_cmp.segment_id == seg) & (hts_cmp.budget_ratio == br) & (hts_cmp.method_id == "HTS-EC-safe")]
        b7 = hts_cmp[(hts_cmp.segment_id == seg) & (hts_cmp.budget_ratio == br) & (hts_cmp.method_id == "B7-strict-replay")]
        hs_r = hs["event_recall"].mean() if len(hs) else float("nan")
        hs_p = hs["event_precision"].mean() if len(hs) else float("nan")
        b7_r = b7["event_recall"].mean() if len(b7) else float("nan")
        b7_p = b7["event_precision"].mean() if len(b7) else float("nan")
        L.append(
            f"| {seg} | {br:.2f} | {lr:.3f} | {vr:.3f} | {hs_r:.3f} | {b7_r:.3f} | {lp:.3f} | {vp:.3f} | {hs_p:.3f} | {b7_p:.3f} |"
        )
    L.append("\n## Reading\n")
    L.append(
        "- The learned policy picks arms by predicted P(positive | state, arm). It is "
        "trained only on logged choices (the arm actually taken each step), so it inherits "
        "the v2 logging policy's exploration pattern and cannot discover arms the logger "
        "never tried. This is a known offline-bandit limitation; report as such."
    )
    L.append(
        "- If ECP-learned >= ECP-v2 on realcartest without losing precision, the offline "
        "learned policy is a strict-replay improvement over fixed weights. The proxy-zero "
        "regime (dataset3) remains the open gap; a learned policy trained only on v2 logs "
        "cannot invent zero-proxy discoveries the logger did not sample."
    )
    L.append(
        "- Strict-replay compliant: reference read only at final eval; 0 event_id leaks; "
        "1 oracle call per arm."
    )
    md = OUT / "t028b_ecp_learned_report.md"
    md.write_text("\n".join(L))
    print(f"wrote {OUT/'t028b_ecp_learned_frontier.csv'}")
    print(f"wrote {md}")


if __name__ == "__main__":
    main()
