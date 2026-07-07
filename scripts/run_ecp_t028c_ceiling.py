"""T028c-0 — candidate-level event-utility ORACLE CEILING audit (ECP Step 4c).

Purpose (per user plan): BEFORE training any policy, prove that the candidate
action set contains event-level decisions better than v2. At each strict-replay
step we enumerate ALL legal candidate arms (DISCOVER/BRIDGE/CERTIFY/ZERO_PROXY)
and, using the OFFLINE true label (grid is_positive) + OFFLINE reference, compute
each candidate's marginal event-utility. The "oracle-candidate policy" then
executes the max-utility candidate. This is a CEILING (selection uses reference),
NOT a deployable strict-replay policy — it answers: "if selection were perfect,
how much better than v2 could we be?" If the ceiling is not better than v2, the
candidate set has no learnable event-level signal and training a policy is moot.

Marginal event-utility of a candidate (offline):
  u = 1.0 * new_event_hit
    + 0.5 * iou_gain            (sum over formed intervals of max-IoU improvement)
    + 0.3 * bridge_connect      (positive BRIDGE that merges two positive groups)
    - 0.3 * duplicate           (positive probe that adds no new coverage)
    - 0.1 * cost                (1 oracle call)
Negative/already-known probes get their small confirmation utility.

This is a pure offline counterfactual audit. It does NOT train a model and is
explicitly NOT a strict-replay method (it reads reference to select). The v2
strict-replay frontier (t028a_ecp_bandit_frontier.csv) is the fair comparison.

Outputs:
  outputs/ecp_event_coverage_policy_v1/ecp_candidate_utility_by_step.csv
  outputs/ecp_event_coverage_policy_v1/ecp_oracle_ceiling_frontier.csv
  outputs/ecp_event_coverage_policy_v1/t028c0_ceiling_report.md
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from run_ecp_t027_bandit import (  # noqa: E402
    SEGMENTS,
    BUDGET_RATIOS,
    SEEDS,
    PROXY_COL,
    LABEL_COL,
    GAP,
    VARIANTS,
    load_segment_data,
    AlignedOracle,
    group_positive_bins,
    evaluate_events,
    candidate_targets_module,
    formed_intervals,
)

OUT = REPO_ROOT / "outputs" / "ecp_event_coverage_policy_v1"
OUT.mkdir(parents=True, exist_ok=True)


def marginal_utility(queried_pos, target, label, grid_sorted, bin_to_t, ref_seg, n_ref):
    """Offline marginal event-utility of taking `target` (with true `label`).

    Credit-assignment fix: a step is credited not only when it COMPLETES an event
    (new_event_hit) but also when it BUILDS toward an uncovered event (adds a
    positive bin that overlaps a reference event not yet covered). This avoids
    the myopic "only the completing step gets credit" failure that made the first
    ceiling degenerate below v2.
    """
    new_pos = set(queried_pos)
    if label == "positive":
        new_pos.add(target)
    before = formed_intervals(queried_pos, grid_sorted)
    after = formed_intervals(new_pos, grid_sorted)
    ev_before = evaluate_events(before, ref_seg) if n_ref > 0 else {"unique_event_coverage": 0}
    ev_after = evaluate_events(after, ref_seg) if n_ref > 0 else {"unique_event_coverage": 0}
    new_event_hit = ev_after["unique_event_coverage"] - ev_before["unique_event_coverage"]
    # iou gain: best max-IoU per reference event before/after
    def best_iou(intervals):
        if n_ref == 0 or ref_seg is None:
            return 0.0
        tot = 0.0
        for (rs, re) in zip(ref_seg["t_start"].values, ref_seg["t_end"].values):
            best = max(([0.0] + [iou_intervals(s, e, rs, re) for (s, e) in intervals]))
            tot += best
        return tot
    iou_gain = best_iou(after) - best_iou(before)
    # build credit: positive bin overlapping an UNCOVERED reference event
    build_credit = 0.0
    if label == "positive" and n_ref > 0 and ref_seg is not None:
        bt_s, bt_e = bin_to_t[target]
        overlaps_uncovered = False
        for (rs, re) in zip(ref_seg["t_start"].values, ref_seg["t_end"].values):
            if iou_intervals(bt_s, bt_e, rs, re) > 0:  # bin time-overlaps this event
                # is this event already covered by `before`?
                if not any(iou_intervals(s, e, rs, re) >= 0.3 for (s, e) in before):
                    overlaps_uncovered = True
                    break
        if overlaps_uncovered and new_event_hit <= 0:
            build_credit = 0.5
    cost = 0.1
    if label == "positive":
        u = 1.0 * new_event_hit + 0.5 * build_credit + 0.5 * iou_gain - cost
    else:
        u = 0.02  # negative probe: no event progress (near-noop)
    return u, new_event_hit, iou_gain


def iou_intervals(a_s, a_e, b_s, b_e):
    inter = max(0.0, min(a_e, b_e) - max(a_s, b_s))
    union = max(a_e, b_e) - min(a_s, b_s)
    return inter / union if union > 0 else 0.0


def run_oracle_ceiling(grid, ref_seg, seg_id, budget_abs, budget_ratio, seed, rng, cfg):
    n_bins = len(grid)
    oracle = AlignedOracle(grid, seg_id, "ECP-ceiling", seed, budget_abs, budget_ratio)
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
        cands = candidate_targets_module(
            grid_sorted, proxies, bin_to_t, queried, queried_pos, unqueried,
            all_bins, zero_proxy_budget_used, budget_abs, cfg,
        )
        # compute offline marginal utility for each candidate (using true label)
        best_arm = None
        best_u = -1e9
        best_target = None
        cand_utils = {}
        for arm, target in cands.items():
            if target is None:
                cand_utils[arm] = None
                continue
            tl = "positive" if true_labels[target] else "negative"
            u, neh, ig = marginal_utility(queried_pos, target, tl, grid_sorted, bin_to_t, ref_seg, n_ref)
            cand_utils[arm] = {"target": target, "u": u, "new_event_hit": neh, "iou_gain": ig, "true_label": tl}
            if u > best_u:
                best_u = u
                best_arm = arm
                best_target = target
        if best_arm is None:
            break
        if best_u <= 0.02:
            # only no-op negatives available among proposed candidates:
            # fall back to DISCOVER highest-proxy to keep spending budget
            # realistically (candidate-generator cannot propose a better bin).
            if cands["DISCOVER"] is not None:
                best_arm = "DISCOVER"
                best_target = cands["DISCOVER"]
                best_u = 0.02
            else:
                break
        # execute best (pay 1 oracle call; true label already known but query to be consistent)
        is_zero = best_arm == "ZERO_PROXY"
        if is_zero:
            zero_proxy_budget_used += 1
        label = oracle.query_unit(best_target, "ECP_ceiling_" + best_arm, best_arm)
        queried.add(best_target)
        if label == "positive":
            queried_pos.add(best_target)
        # state features for T028c-1 training
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
            "u_discover": round(cand_utils["DISCOVER"]["u"], 4) if cand_utils["DISCOVER"] else None,
            "u_bridge": round(cand_utils["BRIDGE"]["u"], 4) if cand_utils["BRIDGE"] else None,
            "u_certify": round(cand_utils["CERTIFY"]["u"], 4) if cand_utils["CERTIFY"] else None,
            "u_zero_proxy": round(cand_utils["ZERO_PROXY"]["u"], 4) if cand_utils["ZERO_PROXY"] else None,
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


def main():
    rng = np.random.default_rng(20260707)
    rows = []
    step_all = []
    for seg in SEGMENTS:
        grid, ref_seg, err = load_segment_data(seg)
        if grid is None:
            continue
        n_bins = len(grid)
        for br in BUDGET_RATIOS:
            for seed in SEEDS:
                budget_abs = max(1, int(round(br * n_bins)))
                res = run_oracle_ceiling(grid, ref_seg, seg["segment_id"], budget_abs, br, seed, rng, VARIANTS["v2"])
                rows.append({
                    "variant": "oracle_ceiling", "segment_id": seg["segment_id"],
                    "method_id": "ECP-oracle-ceiling", "seed": seed,
                    "budget_abs": budget_abs, "budget_ratio": br,
                    "oracle_calls_total": res["oracle_calls"],
                    "returned_intervals": res["returned_intervals"],
                    "event_precision": round(res["event_precision"], 4),
                    "event_recall": round(res["event_recall"], 4),
                    "unique_event_coverage": res["unique_event_coverage"],
                    "strict_replay_or_posthoc": "OFFLINE_CEILING",
                    "online_uses_event_id": False,
                    "can_be_main_comparison": False,
                    "applicability_note": "T028c-0 candidate-level event-utility oracle ceiling (NOT strict-replay; uses reference to select)",
                })
                for sr in res["step_rows"]:
                    step_all.append(sr)
        print(f"done {seg['segment_id']}")

    frontier = pd.DataFrame(rows)
    frontier.to_csv(OUT / "ecp_oracle_ceiling_frontier.csv", index=False)
    steps = pd.DataFrame(step_all)
    steps.to_csv(OUT / "ecp_candidate_utility_by_step.csv", index=False)

    # compare to v2 strict-replay
    v2 = pd.read_csv(OUT / "t028a_ecp_bandit_frontier.csv")
    v2 = v2[v2["variant"] == "v2"]
    ceil_cmp = frontier.groupby(["segment_id", "budget_ratio"])[["event_recall", "event_precision"]].mean().reset_index()
    v2_cmp = v2.groupby(["segment_id", "budget_ratio"])[["event_recall", "event_precision"]].mean().reset_index()

    L = []
    L.append("# T028c-0 — candidate-level event-utility ORACLE CEILING\n")
    L.append(
        "At each step, ALL candidate arms are enumerated and their offline marginal "
        "event-utility is computed (using true label + reference); the max-utility "
        "candidate is executed. This is a CEILING (selection reads reference) and is "
        "NOT a deployable strict-replay policy. It answers: does the candidate action "
        "set contain event-level decisions better than v2? If not, training a policy "
        "(T028c-1) is moot.\n"
    )
    L.append("## Mean event_recall: oracle-ceiling vs v2 (strict-replay)\n")
    L.append("| segment | budget | ceiling_recall | v2_recall | ceiling_prec | v2_prec | delta_recall |")
    L.append("|---|---|---|---|---|---|---|")
    for (seg, br), _ in ceil_cmp.groupby(["segment_id", "budget_ratio"]):
        cr = ceil_cmp[(ceil_cmp.segment_id == seg) & (ceil_cmp.budget_ratio == br)]["event_recall"].mean()
        cp = ceil_cmp[(ceil_cmp.segment_id == seg) & (ceil_cmp.budget_ratio == br)]["event_precision"].mean()
        vr = v2_cmp[(v2_cmp.segment_id == seg) & (v2_cmp.budget_ratio == br)]["event_recall"].mean()
        vp = v2_cmp[(v2_cmp.segment_id == seg) & (v2_cmp.budget_ratio == br)]["event_precision"].mean()
        L.append(f"| {seg} | {br:.2f} | {cr:.3f} | {vr:.3f} | {cp:.3f} | {vp:.3f} | {cr-vr:+.3f} |")
    # arm distribution of ceiling
    L.append("\n## Oracle-ceiling arm usage\n")
    L.append("| arm | n_calls | positive_rate | mean_chosen_u |")
    L.append("|---|---|---|---|")
    for arm in ["DISCOVER", "BRIDGE", "CERTIFY", "ZERO_PROXY"]:
        sub = steps[steps["chosen_arm"] == arm]
        pr = (sub["chosen_true_label"] == "positive").mean() if len(sub) else 0.0
        mu = sub["chosen_u"].mean() if len(sub) else 0.0
        L.append(f"| {arm} | {len(sub)} | {pr:.3f} | {mu:.3f} |")
    L.append("\n## Reading / verdict\n")
    L.append(
        "- If ceiling_recall >> v2 on every segment, the candidate set HAS learnable "
        "event-level signal -> proceed to T028c-1 (train event-utility ranker)."
    )
    L.append(
        "- If ceiling ≈ v2, the candidate arms do not contain better event-level "
        "decisions than v2 already makes -> the bottleneck is the CANDIDATE GENERATOR "
        "or the proxy-zero regime, not the selection policy. Training T028c-1 would "
        "just re-learn v2. In that case T028d/DR cannot help either (no counterfactual "
        "support)."
    )
    L.append(
        "- This is an OFFLINE CEILING: it reads reference to select, so it is NOT a "
        "strict-replay result and must never be reported as one. v2 (strict-replay) is "
        "the fair baseline in the table above."
    )
    md = OUT / "t028c0_ceiling_report.md"
    md.write_text("\n".join(L))
    print(f"wrote {OUT/'ecp_oracle_ceiling_frontier.csv'}")
    print(f"wrote {OUT/'ecp_candidate_utility_by_step.csv'}")
    print(f"wrote {md}")


if __name__ == "__main__":
    main()
