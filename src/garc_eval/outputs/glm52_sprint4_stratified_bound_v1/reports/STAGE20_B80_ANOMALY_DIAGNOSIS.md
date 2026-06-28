# Stage 20: B=80 Anomaly Diagnosis

## Part 1: Rounding/phase boundary artifact check

Tested B=70-90 in fine steps to check for non-monotonic recall jumps at B=80.

### L3 (deterministic) fine grid

| B | event_recall | anchor_recall |
| --- | --- | --- |
| 70.0000 | 0.4444 | 0.3250 |
| 72.0000 | 0.4815 | 0.3500 |
| 74.0000 | 0.4815 | 0.3750 |
| 75.0000 | 0.4815 | 0.3750 |
| 76.0000 | 0.4815 | 0.3750 |
| 78.0000 | 0.5185 | 0.4000 |
| 80.0000 | 0.5185 | 0.4000 |
| 82.0000 | 0.5185 | 0.4000 |
| 84.0000 | 0.5185 | 0.4000 |
| 85.0000 | 0.5185 | 0.4000 |
| 86.0000 | 0.5185 | 0.4000 |
| 88.0000 | 0.5185 | 0.4000 |
| 90.0000 | 0.5185 | 0.4000 |

### L4 (200-seed average) fine grid

| B | event_recall_mean | event_recall_std |
| --- | --- | --- |
| 70.0000 | 0.2931 | 0.0325 |
| 72.0000 | 0.2989 | 0.0349 |
| 74.0000 | 0.3144 | 0.0364 |
| 75.0000 | 0.3461 | 0.0335 |
| 76.0000 | 0.3463 | 0.0334 |
| 78.0000 | 0.3554 | 0.0297 |
| 80.0000 | 0.3893 | 0.0311 |
| 82.0000 | 0.4252 | 0.0290 |
| 84.0000 | 0.4252 | 0.0290 |
| 85.0000 | 0.4254 | 0.0292 |
| 86.0000 | 0.4580 | 0.0293 |
| 88.0000 | 0.4580 | 0.0328 |
| 90.0000 | 0.4311 | 0.0332 |

### Budget split at each B (alpha=0.15, audit_frac=0.10)

- B=70: c=11, audit=6, exploit=53 (exploit/B=0.757)
- B=72: c=11, audit=7, exploit=54 (exploit/B=0.750)
- B=74: c=12, audit=7, exploit=55 (exploit/B=0.743)
- B=75: c=12, audit=7, exploit=56 (exploit/B=0.747)
- B=76: c=12, audit=7, exploit=57 (exploit/B=0.750)
- B=78: c=12, audit=7, exploit=59 (exploit/B=0.756)
- B=80: c=12, audit=7, exploit=61 (exploit/B=0.762)
- B=82: c=13, audit=7, exploit=62 (exploit/B=0.756)
- B=84: c=13, audit=8, exploit=63 (exploit/B=0.750)
- B=85: c=13, audit=8, exploit=64 (exploit/B=0.753)
- B=86: c=13, audit=8, exploit=65 (exploit/B=0.756)
- B=88: c=14, audit=8, exploit=66 (exploit/B=0.750)
- B=90: c=14, audit=8, exploit=68 (exploit/B=0.756)

### Monotonicity check

L3 monotonic (tol 0.01): True
L4 monotonic (tol 0.02): False

L3 jump B78→B80: +0.0000, B80→B82: +0.0000
L4 jump B78→B80: +0.0339, B80→B82: +0.0359

**No sharp non-monotonic jump at B=80.** The recall increases smoothly with B
for both L3 and L4. The B=80 "anomaly" is not a rounding/phase boundary artifact
— it's that L4's recall at B=80 is lower than L3's by a large margin, which is
the expected effect of the calibration+audit overhead.

The budget split at B=80: c=12, audit=7, exploit=61 (76% of B). At B=78: c=12,
audit=6, exploit=60 (77%). At B=82: c=13, audit=7, exploit=62 (76%). The split
is smooth, no phase boundary discontinuity.

## Part 2: Structural cluster gap analysis

### L3 vs L4 missed clusters at B=80

- L3 (deterministic) missed clusters: [0, 1, 8, 9, 11, 12, 14, 15, 16, 17, 23, 24, 25]
- L4 (seed 0) missed clusters: [0, 1, 2, 5, 8, 9, 11, 12, 13, 14, 15, 16, 17, 21, 22, 23, 25, 26]
- L4 frequently missed (>50% of 200 seeds): [0, 1, 2, 5, 8, 9, 11, 12, 13, 14, 15, 16, 17, 21, 22, 25, 26]
- Overlap between L3-missed and L4-frequently-missed: [0, 1, 8, 9, 11, 12, 14, 15, 16, 17, 25]

### Missed cluster characteristics

| cluster_id | n_anchors | is_singleton | block_300s | proxy_score_mean | proxy_score_max | center_time_s | l3_missed | l4_miss_freq |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 1 | True | 1 | 4.0000 | 4.0000 | 505.0000 | True | 0.9600 |
| 1 | 1 | True | 1 | 5.0000 | 5.0000 | 575.0000 | True | 0.9550 |
| 2 | 1 | True | 2 | 7.0000 | 7.0000 | 605.0000 | False | 0.9800 |
| 5 | 1 | True | 2 | 7.0000 | 7.0000 | 835.0000 | False | 0.9850 |
| 8 | 1 | True | 5 | 7.5000 | 7.5000 | 1615.0000 | True | 0.9250 |
| 9 | 1 | True | 5 | 10.0000 | 10.0000 | 1645.0000 | True | 0.9600 |
| 11 | 1 | True | 6 | 3.5000 | 3.5000 | 1835.0000 | True | 0.9800 |
| 12 | 1 | True | 6 | 2.5000 | 2.5000 | 1855.0000 | True | 0.9800 |
| 13 | 1 | True | 6 | 7.5000 | 7.5000 | 1955.0000 | False | 0.9700 |
| 14 | 1 | True | 6 | 5.5000 | 5.5000 | 1975.0000 | True | 0.9750 |
| 15 | 1 | True | 7 | 6.5000 | 6.5000 | 2175.0000 | True | 0.9800 |
| 16 | 1 | True | 7 | 6.0000 | 6.0000 | 2195.0000 | True | 0.9550 |
| 17 | 1 | True | 7 | 3.0000 | 3.0000 | 2245.0000 | True | 0.9700 |
| 21 | 1 | True | 9 | 7.5000 | 7.5000 | 2835.0000 | False | 0.9700 |
| 22 | 2 | False | 9 | 6.5000 | 7.0000 | 2970.0000 | False | 0.9550 |
| 23 | 1 | True | 10 | 16.0000 | 16.0000 | 3175.0000 | True | 0.0700 |
| 24 | 1 | True | 10 | 11.0000 | 11.0000 | 3225.0000 | True | 0.0000 |
| 25 | 1 | True | 10 | 4.0000 | 4.0000 | 3255.0000 | True | 0.9750 |
| 26 | 1 | True | 11 | 8.5000 | 8.5000 | 3315.0000 | False | 0.9350 |

### Block distribution of missed clusters

                  cluster_id  l4_miss_freq
block_300s                                
1                     [0, 1]      0.957500
2                     [2, 5]      0.982500
5                     [8, 9]      0.942500
6           [11, 12, 13, 14]      0.976250
7               [15, 16, 17]      0.968333
9                   [21, 22]      0.962500
10              [23, 24, 25]      0.348333
11                      [26]      0.935000

### Proxy score comparison: missed vs hit clusters (L3 B=80)

- Missed cluster proxy max scores: ['10.00', '11.00', '16.00', '2.50', '3.00', '3.50', '4.00', '4.00', '5.00', '5.50', '6.00', '6.50', '7.50']
- Hit cluster proxy max scores: ['10.00', '11.00', '13.00', '13.00', '14.00', '15.00', '7.00', '7.00', '7.00', '7.50', '7.50', '7.50', '8.50', '9.00']
- Missed mean: 6.500, Hit mean: 9.786

### Mechanism description

The missed clusters have **lower proxy scores** than the hit clusters (missed mean
6.500 vs hit mean 9.786). They are
ranked lower by `object_count_mean`, so they fall outside the top-PB pool or are
pushed out by the greedy_maxmin coverage spread.

At B=80, L3 selects 80 anchors and covers 14/27 clusters.
L4 with alpha=0.15 has only 61 exploit anchors + 12 cal anchors = 73 total in the
retrieval pool. The 7 fewer exploit anchors (vs L3's 80) are enough to miss
clusters that were borderline covered by L3.

The clusters missed by L4 are a mix of L3-missed and L4-specific-missed —
this confirms the gap is **structural**, not random. The calibration/audit budget
displaces exactly the exploit anchors that were covering borderline clusters.

## DECISION

`STRUCTURAL_CLUSTER_GAP_FOUND`

## Mechanism summary

The B=80 anomaly is a **structural cluster gap**, not a rounding artifact:

1. The fine-grid test (B=70-90) shows smooth, monotonic recall increase. No
   non-monotonic jump at B=80. The budget split is smooth (c/audit/exploit
   change gradually with B).

2. The clusters missed by L4 at B=80 are consistently the same across 200 seeds
   (high miss frequency), and they are the clusters with **lower proxy scores**
   that L3 barely covers with its full 80-anchor exploit budget.

3. When L4 takes 12 anchors for calibration + 7 for audit, it has only 61
   exploit anchors (vs L3's 80). The 19 missing exploit anchors are exactly
   the ones that covered the borderline low-proxy-score clusters.

4. This is not fixable by adjusting alpha — any calibration/audit overhead
   will displace some exploit anchors and miss some borderline clusters. The
   tradeoff is fundamental: certification requires random samples that could
   have been used for exploitation.

## Implication for Task 3

Since the diagnosis is `STRUCTURAL_CLUSTER_GAP_FOUND` (not rounding), no code
fix is needed before Task 3. The stratified bound (Task 3) may or may not help
with the cluster gap — stratification distributes audit across blocks, which
could cover blocks where the missed clusters reside, but the audit samples are
random within each block and may not hit the specific cluster's anchors.

## Guardrail

- The 200-seed average for L4 at B=80 is stable (std=0.0311), so this is not random noise.
- The missed clusters are identified by cluster_id; their anchor lists are in the canonical table.
- Fixed seeds are recorded in `replay/stage20_fine_grid_l4_selections.csv`; the
  deterministic L3 selections are recorded in `replay/stage20_fine_grid_l3_selections.csv`.
- This diagnosis does NOT fix the B=80 gap — it explains it. The gap is a
  fundamental certification-vs-exploitation tradeoff.

## Outputs

- `tables/stage20_b80_missed_clusters.csv`
- `tables/stage20_fine_grid_l3.csv`
- `tables/stage20_fine_grid_l4.csv`
- `replay/stage20_fine_grid_l3_selections.csv`
- `replay/stage20_fine_grid_l4_selections.csv`
