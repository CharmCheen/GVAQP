# Stage 13: Ablation Ladder L0-L4

## Setup

Five levels, each tested at B=[30,40,60,80,100,150], seeds 0..199 (200 repeats).
All selections saved. No new VLM. Dataset3 oracle labels (347 anchors, 40 positives).

- **L0**: random / temporal_grid (no proxy)
- **L1**: top-B by `score_fusion_geometry_motion` (ORIGINAL proxy, AUROC 0.550)
- **L2**: top-B by `object_count_mean` (CORRECTED deployable proxy, AUROC 0.627)
- **L3**: L2 + diversity prefilter (P=2.0) + `greedy_maxmin_time`
- **L4**: L3 skeleton + coverage/calibration (20% of B, stratified temporal, known prob)
  + exploit (remaining minus audit) + audit (10% of exec, stratified temporal, known prob)
  + certificate: R_lower = H / U_{1-delta}(N_pos), delta=0.05

L4 uses fixed P=2.0 (no online quality assessment per task spec).
L4 strictly separates retrieval_pool (S_cal + S_exploit, for recall) from
estimation_pool (S_cal + S_audit, for HT estimate — known probability only).

## L4 vs L3: event-cluster recall comparison

| budget | L3_diversity_greedy_maxmin | L4_acce_certificate | L4_minus_L3 |
| --- | --- | --- | --- |
| 30.0000 | 0.2222 | 0.2319 | 0.0097 |
| 40.0000 | 0.2593 | 0.2774 | 0.0181 |
| 60.0000 | 0.3704 | 0.2913 | -0.0791 |
| 80.0000 | 0.5185 | 0.3591 | -0.1594 |
| 100.0000 | 0.4815 | 0.5198 | 0.0383 |
| 150.0000 | 0.6667 | 0.6102 | -0.0565 |

## Key finding: L4 has a MAJOR recall drop at B=60 and B=80

At B=80: L4 event recall = 0.3591 vs L3 = 0.5185.
**Drop = -0.1594 (-30.8% relative).**

This is because L4 spends 20% of B on calibration + ~8% on audit, leaving only ~72% for
exploit. At B=80: c=16, audit=6, exploit=58 (vs L3's full 80). The 27.5% exploit budget
reduction causes a 31% relative recall loss.

**Budget breakdown at B=80:** c=16, exec=64, audit=6, exploit=58.

At B=30 and B=100, L4 is comparable or slightly better than L3 — at very low budgets,
coverage helps (temporal spread > proxy precision); at high budgets, there's enough for both.

## Full ranking at B=80

| level | event_cluster_recall_mean | anchor_recall_mean | singleton_cluster_recall_mean | precision_mean | R_lower_mean |
| --- | --- | --- | --- | --- | --- |
| L3_diversity_greedy_maxmin | 0.5185 | 0.4000 | 0.3810 | 0.2000 | nan |
| L1_top_score_fusion | 0.3704 | 0.2500 | 0.3333 | 0.1250 | nan |
| L2_top_object_count | 0.3704 | 0.3750 | 0.2857 | 0.1875 | nan |
| L4_acce_certificate | 0.3591 | 0.2816 | 0.2698 | 0.1543 | 0.6427 |
| L0_random | 0.2846 | 0.2283 | 0.2333 | 0.1141 | nan |
| L0_temporal_grid | 0.2593 | 0.2000 | 0.1905 | 0.1000 | nan |

## R_lower analysis

L4 produces a recall lower bound (R_lower) that L3 cannot. But the values are concerning:

| B | L4 recall | R_lower | est_pool_size |
|---|---|---|---|
| 30 | 0.2319 | 2.7391 | 9 |
| 40 | 0.2774 | 2.1980 | 12 |
| 60 | 0.2913 | 1.2908 | 17 |
| 80 | 0.3591 | 0.6427 | 23 |
| 100 | 0.5198 | 0.6407 | 28 |
| 150 | 0.6102 | 0.3571 | 42 |

**WARNING**: At B=30, R_lower=2.74 (>1.0, vacuous). At B=80, R_lower=0.64 > actual recall 0.36.
This suggests the HT upper bound on N_pos is UNDERESTIMATING the true total (40), making
R_lower invalid (higher than actual recall). The certificate mechanism may be unreliable
with small estimation pools. This is formally tested in Stage 14.

## L1 vs L2: proxy swap effect

L1 (score_fusion, AUROC 0.550) vs L2 (object_count_mean, AUROC 0.627):
At B=80: L1 event recall = 0.3704,
L2 = 0.3704.
The proxy swap alone (L1→L2) changes recall by +0.0000.

## L2 vs L3: diversity + greedy_maxmin effect

L2 (top-proxy) vs L3 (diversity + greedy_maxmin):
At B=80: L2 = 0.3704,
L3 = 0.5185.
Diversity + greedy_maxmin adds +0.1481.

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
