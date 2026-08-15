#!/usr/bin/env python3
"""ERAEA E1/E2/E5 analysis + reports. CPU-only synthesis over BASELINE_MATRIX
and MATERIALIZER_DECOUPLING outputs."""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "outputs/eraea_cpu_novelty_gate_v1"
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "scripts/mab_cpu_gate"))

import numpy as np
import pandas as pd

from common import VIDEOS, QUERY_VULN, BUDGETS, any_time_auc
from phase2_action_table import Cluster, visible_rewards
from run_eraea_gate import policy_order, trace_metrics

GENERIC_SET = ["mmr", "temporal_coverage", "new_component", "facility", "exsample",
               "seiden_ucb", "stratified"]


def main():
    df = pd.read_csv(GATE / "BASELINE_MATRIX.csv")
    df = df[df["query_id"] == QUERY_VULN]

    # ================= E2: G_generic / eta_explained =================
    per_cluster = df.groupby(["video_id", "policy"])["eventf1_auc"].mean().unstack()
    e2 = []
    for v in VIDEOS:
        rel = per_cluster.loc[v, "relation_greedy"]
        top = per_cluster.loc[v, "top_proxy"]
        gen = {p: per_cluster.loc[v, p] for p in GENERIC_SET}
        best_gen = max(gen, key=gen.get)
        g_gen = rel - gen[best_gen]
        denom = rel - top
        eta = (gen[best_gen] - top) / denom if abs(denom) > 1e-4 else float("nan")
        e2.append({"cluster": v, "relation_greedy_auc": rel, "top_proxy_auc": top,
                   "best_generic": best_gen, "best_generic_auc": gen[best_gen],
                   "g_generic": g_gen, "eta_explained": eta})
    e2df = pd.DataFrame(e2)
    g_gen_med = float(e2df["g_generic"].median())
    # ================= E1: equal-yield pairs =================
    pair_rows = []
    methods = sorted(df["policy"].unique())
    for v in VIDEOS:
        for b in BUDGETS:
            sub = df[(df["video_id"] == v) & (df["budget"] == b)]
            rows = {r["policy"]: r for _, r in sub.iterrows()}
            for i, mi in enumerate(methods):
                for mj in methods[i + 1:]:
                    if mi not in rows or mj not in rows:
                        continue
                    ri, rj = rows[mi], rows[mj]
                    dy = abs(ri["yield"] - rj["yield"])
                    cov_max = max(ri["coverage_fraction"], rj["coverage_fraction"])
                    dc = abs(ri["coverage_fraction"] - rj["coverage_fraction"]) / cov_max if cov_max > 0 else 0.0
                    if dy <= 1 and dc <= 0.05:
                        pair_rows.append({
                            "video_id": v, "budget": b, "method_i": mi, "method_j": mj,
                            "yield_i": int(ri["yield"]), "yield_j": int(rj["yield"]),
                            "coverage_i": ri["coverage_fraction"], "coverage_j": rj["coverage_fraction"],
                            "EventF1_i": ri["EventF1"], "EventF1_j": rj["EventF1"],
                            "delta_EventF1": ri["EventF1"] - rj["EventF1"],
                            "recall_i": ri["EventRecall"], "recall_j": rj["EventRecall"],
                            "boundary_iou_i": ri["boundary_iou"], "boundary_iou_j": rj["boundary_iou"],
                            "overmerge_i": ri["overmerge"], "overmerge_j": rj["overmerge"],
                            "split_i": ri["split"], "split_j": rj["split"],
                            "dup_i": ri["duplicate_evidence_rate"], "dup_j": rj["duplicate_evidence_rate"],
                            "auc_i": ri["eventf1_auc"], "auc_j": rj["eventf1_auc"],
                        })
    pairs = pd.DataFrame(pair_rows)
    pairs.to_parquet(GATE / "EQUAL_YIELD_PAIRS.parquet", index=False)
    # relation-greedy-centric pairs
    rel_pairs = pairs[(pairs["method_i"] == "relation_greedy") | (pairs["method_j"] == "relation_greedy")].copy()
    rel_pairs["delta_rel_minus_other"] = rel_pairs.apply(
        lambda r: r["delta_EventF1"] if r["method_i"] == "relation_greedy" else -r["delta_EventF1"], axis=1)
    ey = {}
    for v in VIDEOS:
        sub = rel_pairs[rel_pairs["video_id"] == v]
        ey[v] = {"n_pairs": len(sub),
                 "median_delta_F1": float(sub["delta_rel_minus_other"].median()) if len(sub) else None,
                 "positive_direction_share": float((sub["delta_rel_minus_other"] > 0).mean()) if len(sub) else None,
                 "abs_ge_0_03_share": float((sub["delta_rel_minus_other"].abs() >= 0.03).mean()) if len(sub) else None}
    ey_pooled = {"n_pairs": len(rel_pairs),
                 "median_delta_F1": float(rel_pairs["delta_rel_minus_other"].median()) if len(rel_pairs) else None,
                 "positive_direction_share": float((rel_pairs["delta_rel_minus_other"] > 0).mean()) if len(rel_pairs) else None,
                 "abs_ge_0_03_share": float((rel_pairs["delta_rel_minus_other"].abs() >= 0.03).mean()) if len(rel_pairs) else None}

    # ================= E3 summary from decoupling file =================
    dec = pd.read_csv(GATE / "MATERIALIZER_DECOUPLING.csv")
    e3 = dec[dec["reward"].notna()]
    r_auc = e3.groupby(["video_id", "reward"])["eventf1_auc"].mean().unstack()
    reward_gain_R1 = float((r_auc["R1"] - r_auc["R0"]).median())
    reward_gain_R2 = float((r_auc["R2"] - r_auc["R1"]).median())
    reward_gain_R3 = float((r_auc["R3"] - r_auc["R2"]).median())
    reward_gain_R4 = float((r_auc["R4"] - r_auc["R3"]).median())
    e4 = dec[dec["experiment"] == "E4"]
    e4p = e4.pivot_table(index=["scoring", "materializer"], values="eventf1_auc", aggfunc="mean")
    g_c1 = float(e4p.loc[("gap_aware", "C1"), "eventf1_auc"] - e4p.loc[("agnostic", "C1"), "eventf1_auc"])
    g_c3 = float(e4p.loc[("gap_aware", "C3"), "eventf1_auc"] - e4p.loc[("agnostic", "C3"), "eventf1_auc"])
    g_k0 = float(e4p.loc[("gap_aware", "K0"), "eventf1_auc"] - e4p.loc[("agnostic", "K0"), "eventf1_auc"])
    best_mat_gain = max(g_c1, g_c3, g_k0)
    retention_gap = g_c1 / best_mat_gain if abs(best_mat_gain) > 1e-6 else float("nan")
    # ranking reversals across materializers
    rev = []
    for v in VIDEOS:
        for b in BUDGETS:
            sub = e4[(e4["video_id"] == v) & (e4["budget"] == b)]
            for mat in ("C1", "C3", "K0"):
                a = sub[(sub["materializer"] == mat) & (sub["scoring"] == "agnostic")]["eventf1_auc"].iloc[0]
                g_ = sub[(sub["materializer"] == mat) & (sub["scoring"] == "gap_aware")]["eventf1_auc"].iloc[0]
                rev.append({"video": v, "budget": b, "mat": mat, "sign_gap_minus_agnostic": np.sign(g_ - a)})
    revdf = pd.DataFrame(rev)
    reversal_rate = float((revdf.groupby(["video", "budget"])["sign_gap_minus_agnostic"].nunique() > 1).mean())
    # E4GAP
    gapdf = dec[dec["experiment"] == "E4GAP"]
    gap_med = gapdf.groupby(["gap_threshold", "policy"])["eventf1_auc"].mean().unstack()
    gap_delta = (gap_med["relation_greedy"] - gap_med["top_proxy"])

    metrics = {
        "g_generic_median": round(g_gen_med, 4),
        "g_generic_per_cluster": e2df[["cluster", "relation_greedy_auc", "top_proxy_auc",
                                       "best_generic", "best_generic_auc", "g_generic", "eta_explained"]].round(4).to_dict("records"),
        "equal_yield": {"per_cluster": ey, "pooled": ey_pooled},
        "reward_ablation": {"median_gain_R1_over_R0": round(reward_gain_R1, 4),
                            "median_gain_R2_over_R1": round(reward_gain_R2, 4),
                            "median_gain_R3_over_R2": round(reward_gain_R3, 4),
                            "median_gain_R4_over_R3": round(reward_gain_R4, 4),
                            "per_cluster_R_auc": r_auc.round(4).to_dict()},
        "materializer_decoupling": {"gain_gap_aware_C1": round(g_c1, 4), "gain_gap_aware_C3": round(g_c3, 4),
                                    "gain_gap_aware_K0": round(g_k0, 4),
                                    "retention_gap": round(retention_gap, 4) if retention_gap == retention_gap else None,
                                    "reversal_rate_across_materializers": round(reversal_rate, 4),
                                    "gap_threshold_delta_rel_minus_top": gap_delta.round(4).to_dict()},
    }
    (GATE / "NOVELTY_GATE_METRICS.json").write_text(json.dumps(metrics, indent=2, sort_keys=True, default=str))
    print(json.dumps(metrics, indent=1, default=str)[:3000])
    # save E2 table
    e2df.round(4).to_csv(GATE / "GENERIC_COMPARISON.csv", index=False)


if __name__ == "__main__":
    main()
