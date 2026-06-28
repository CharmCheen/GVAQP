#!/usr/bin/env python3
"""Stage 13 report writer."""
import pandas as pd, numpy as np, math
import common as C

long = pd.read_csv(C.REPLAY / "ablation_ladder_results.csv")
summary = pd.read_csv(C.REPLAY / "ablation_ladder_summary.csv")

# L4 vs L3 comparison
l3l4 = summary[summary["level"].isin(["L3_diversity_greedy_maxmin", "L4_acce_certificate"])]
l3l4_piv = l3l4.pivot(index="budget", columns="level", values="event_cluster_recall_mean").round(4)
l3l4_piv["L4_minus_L3"] = (l3l4_piv["L4_acce_certificate"] - l3l4_piv["L3_diversity_greedy_maxmin"]).round(4)
l3l4_piv = l3l4_piv.reset_index()

# Budget breakdown for L4 at B=80
b80_l4 = summary[(summary["budget"] == 80) & (summary["level"] == "L4_acce_certificate")].iloc[0]
b80_l3 = summary[(summary["budget"] == 80) & (summary["level"] == "L3_diversity_greedy_maxmin")].iloc[0]

# Full ranking at B=80
b80 = summary[summary["budget"] == 80].sort_values("event_cluster_recall_mean", ascending=False)

report = f"""# Stage 13: Ablation Ladder L0-L4

## Setup

Five levels, each tested at B=[30,40,60,80,100,150], seeds 0..199 (200 repeats).
All selections saved. No new VLM. Dataset3 oracle labels (347 anchors, 40 positives).

- **L0**: random / temporal_grid (no proxy)
- **L1**: top-B by `score_fusion_geometry_motion` (ORIGINAL proxy, AUROC 0.550)
- **L2**: top-B by `object_count_mean` (CORRECTED deployable proxy, AUROC 0.627)
- **L3**: L2 + diversity prefilter (P=2.0) + `greedy_maxmin_time`
- **L4**: L3 skeleton + coverage/calibration (20% of B, stratified temporal, known prob)
  + exploit (remaining minus audit) + audit (10% of exec, stratified temporal, known prob)
  + certificate: R_lower = H / U_{{1-delta}}(N_pos), delta=0.05

L4 uses fixed P=2.0 (no online quality assessment per task spec).
L4 strictly separates retrieval_pool (S_cal + S_exploit, for recall) from
estimation_pool (S_cal + S_audit, for HT estimate — known probability only).

## L4 vs L3: event-cluster recall comparison

{C.md_table(l3l4_piv)}

## Key finding: L4 has a MAJOR recall drop at B=60 and B=80

At B=80: L4 event recall = {b80_l4['event_cluster_recall_mean']:.4f} vs L3 = {b80_l3['event_cluster_recall_mean']:.4f}.
**Drop = {b80_l4['event_cluster_recall_mean'] - b80_l3['event_cluster_recall_mean']:+.4f} ({(b80_l4['event_cluster_recall_mean'] - b80_l3['event_cluster_recall_mean'])/b80_l3['event_cluster_recall_mean']*100:+.1f}% relative).**

This is because L4 spends 20% of B on calibration + ~8% on audit, leaving only ~72% for
exploit. At B=80: c=16, audit=6, exploit=58 (vs L3's full 80). The 27.5% exploit budget
reduction causes a 31% relative recall loss.

**Budget breakdown at B=80:** c={int(0.20*80)}, exec={80-int(0.20*80)}, audit={int(0.10*(80-int(0.20*80)))}, exploit={80-int(0.20*80)-int(0.10*(80-int(0.20*80)))}.

At B=30 and B=100, L4 is comparable or slightly better than L3 — at very low budgets,
coverage helps (temporal spread > proxy precision); at high budgets, there's enough for both.

## Full ranking at B=80

{C.md_table(b80[["level", "event_cluster_recall_mean", "anchor_recall_mean", "singleton_cluster_recall_mean", "precision_mean", "R_lower_mean"]])}

## R_lower analysis

L4 produces a recall lower bound (R_lower) that L3 cannot. But the values are concerning:

| B | L4 recall | R_lower | est_pool_size |
|---|---|---|---|
"""
for B in C.BUDGETS:
    r = summary[(summary["budget"] == B) & (summary["level"] == "L4_acce_certificate")]
    if not r.empty:
        report += f"| {B} | {r['event_cluster_recall_mean'].iloc[0]:.4f} | {r['R_lower_mean'].iloc[0]:.4f} | {r['est_pool_size_mean'].iloc[0]:.0f} |\n"

report += f"""
**WARNING**: At B=30, R_lower=2.74 (>1.0, vacuous). At B=80, R_lower=0.64 > actual recall 0.36.
This suggests the HT upper bound on N_pos is UNDERESTIMATING the true total (40), making
R_lower invalid (higher than actual recall). The certificate mechanism may be unreliable
with small estimation pools. This is formally tested in Stage 14.

## L1 vs L2: proxy swap effect

L1 (score_fusion, AUROC 0.550) vs L2 (object_count_mean, AUROC 0.627):
At B=80: L1 event recall = {summary[(summary['budget']==80)&(summary['level']=='L1_top_score_fusion')]['event_cluster_recall_mean'].iloc[0]:.4f},
L2 = {summary[(summary['budget']==80)&(summary['level']=='L2_top_object_count')]['event_cluster_recall_mean'].iloc[0]:.4f}.
The proxy swap alone (L1→L2) changes recall by {summary[(summary['budget']==80)&(summary['level']=='L2_top_object_count')]['event_cluster_recall_mean'].iloc[0] - summary[(summary['budget']==80)&(summary['level']=='L1_top_score_fusion')]['event_cluster_recall_mean'].iloc[0]:+.4f}.

## L2 vs L3: diversity + greedy_maxmin effect

L2 (top-proxy) vs L3 (diversity + greedy_maxmin):
At B=80: L2 = {summary[(summary['budget']==80)&(summary['level']=='L2_top_object_count')]['event_cluster_recall_mean'].iloc[0]:.4f},
L3 = {summary[(summary['budget']==80)&(summary['level']=='L3_diversity_greedy_maxmin')]['event_cluster_recall_mean'].iloc[0]:.4f}.
Diversity + greedy_maxmin adds {summary[(summary['budget']==80)&(summary['level']=='L3_diversity_greedy_maxmin')]['event_cluster_recall_mean'].iloc[0] - summary[(summary['budget']==80)&(summary['level']=='L2_top_object_count')]['event_cluster_recall_mean'].iloc[0]:+.4f}.

## DECISION

`ABLATION_LADDER_L4_RECALL_DROP_AT_MID_BUDGET`

L4 has unacceptable recall loss at B=60-80 (-0.079 and -0.160 vs L3).
The certificate R_lower is potentially invalid (R_lower > actual recall at several budgets).
L3 (`object_count_mean + P=2.0 + greedy_maxmin`) remains the strongest deployable method
without a certificate. L4's certificate mechanism needs fixing before it can be deployed.

**Task 6 (L5 quality-adaptive P) is triggered**: L4's recall drop at mid-budget is
unacceptable, so the fixed P=2.0 allocation is insufficient. However, the primary issue
is the budget split (20% cal + 10% audit = 30% overhead), not the P value. A quality-
adaptive P would not fix the budget-split problem. The more productive fix is to reduce
the calibration/audit overhead at mid-budgets (alpha schedule) rather than adapt P.

## Guardrail notes

- All numbers are from dataset3 single video (40 positives). Small-N caveats apply.
- R_lower > 1.0 at B=30 means the certificate is vacuous (trivially true).
- R_lower > actual recall at B=80 means the certificate is INVALID (anti-conservative).
- Do NOT claim "ACCE provides a valid recall certificate" from these results.
- The estimation_pool is strictly known-probability (stratified temporal) — no proxy-
  ranked samples were mixed in, per the guardrail requirement.

## Outputs

- `replay/ablation_ladder_results.csv` (7200 rows: 6 levels x 7 budgets x 200 seeds + L4 extras)
- `replay/ablation_ladder_summary.csv`
- `replay/ablation_ladder_selections_sample.csv` (first 5 seeds per level/budget with full anchor lists)
"""
(C.REPORTS / "STAGE13_ABLATION_LADDER_L0_L4.md").write_text(report, encoding="utf-8")
print("Stage 13 report written.")
