# Stage 23: Simes Correction for Stratified Hypergeometric Bound

## Motivation

Stage 21 showed that Bonferroni correction (delta/L per stratum) is too
conservative: the stratified bound is LOOSER than the non-stratified version
(R_lower improvement = -0.007). The bottleneck is delta/L = 0.05/12 = 0.004
per stratum, which makes each per-stratum bound extremely wide.

Simes correction is less conservative: instead of giving every stratum delta/L,
it ranks stratum p-values and gives the i-th smallest p-value a threshold of
i*delta/L. Strata with stronger evidence (more observed positives, smaller
p-value) get tighter thresholds.

## Methods tested

| Method | Description |
|---|---|
| `simes_approx` | Rank strata by observed positive rate; i-th ranked stratum gets delta_i = i*delta/L |
| `simes_exact` | Compute per-stratum p-values at full-delta bound; apply Simes test; fall back to Bonferroni for strata that fail |
| `bonferroni_ref` | Bonferroni: delta/L per stratum (reference, same as Stage 21) |

## Results: Simes approx (rank-based)

| budget | delta | coverage | mean_R_lower | mean_K_upper | true_K | s17_R_lower | R_lower_vs_s17 | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 30 | 0.0500 | 1.0000 | 0.0188 | 335.3180 | 40 | 0.0235 | -0.0047 | VALID |
| 30 | 0.1000 | 1.0000 | 0.0191 | 329.4860 | 40 | 0.0241 | -0.0050 | VALID |
| 40 | 0.0500 | 1.0000 | 0.0207 | 329.9540 | 40 | 0.0255 | -0.0049 | VALID |
| 40 | 0.1000 | 1.0000 | 0.0210 | 323.0960 | 40 | 0.0266 | -0.0056 | VALID |
| 60 | 0.0500 | 1.0000 | 0.0283 | 318.6660 | 40 | 0.0310 | -0.0027 | VALID |
| 60 | 0.1000 | 1.0000 | 0.0295 | 308.2500 | 40 | 0.0332 | -0.0038 | VALID |
| 80 | 0.0500 | 1.0000 | 0.0391 | 309.6940 | 40 | 0.0397 | -0.0005 | VALID |
| 80 | 0.1000 | 1.0000 | 0.0408 | 294.9860 | 40 | 0.0428 | -0.0020 | VALID |
| 100 | 0.0500 | 1.0000 | 0.0580 | 293.3940 | 40 | 0.0592 | -0.0012 | VALID |
| 100 | 0.1000 | 1.0000 | 0.0616 | 275.0920 | 40 | 0.0640 | -0.0024 | VALID |
| 150 | 0.0500 | 1.0000 | 0.0788 | 257.6880 | 40 | 0.0835 | -0.0046 | VALID |
| 150 | 0.1000 | 1.0000 | 0.0861 | 238.5040 | 40 | 0.0925 | -0.0064 | VALID |

## Results: Simes exact (p-value based)

| budget | delta | coverage | mean_R_lower | mean_K_upper | true_K | s17_R_lower | R_lower_vs_s17 | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 30 | 0.0500 | 1.0000 | 0.0186 | 337.4360 | 40 | 0.0235 | -0.0048 | VALID |
| 30 | 0.1000 | 1.0000 | 0.0188 | 334.5360 | 40 | 0.0241 | -0.0053 | VALID |
| 40 | 0.0500 | 1.0000 | 0.0204 | 334.6920 | 40 | 0.0255 | -0.0052 | VALID |
| 40 | 0.1000 | 1.0000 | 0.0205 | 330.8400 | 40 | 0.0266 | -0.0061 | VALID |
| 60 | 0.0500 | 1.0000 | 0.0273 | 329.9120 | 40 | 0.0310 | -0.0037 | VALID |
| 60 | 0.1000 | 1.0000 | 0.0279 | 325.4260 | 40 | 0.0332 | -0.0053 | VALID |
| 80 | 0.0500 | 1.0000 | 0.0372 | 325.7640 | 40 | 0.0397 | -0.0025 | VALID |
| 80 | 0.1000 | 1.0000 | 0.0376 | 320.1980 | 40 | 0.0428 | -0.0052 | VALID |
| 100 | 0.0500 | 1.0000 | 0.0537 | 317.3140 | 40 | 0.0592 | -0.0056 | VALID |
| 100 | 0.1000 | 1.0000 | 0.0548 | 309.5200 | 40 | 0.0640 | -0.0093 | VALID |
| 150 | 0.0500 | 1.0000 | 0.0685 | 296.4400 | 40 | 0.0835 | -0.0150 | VALID |
| 150 | 0.1000 | 1.0000 | 0.0714 | 287.3820 | 40 | 0.0925 | -0.0211 | VALID |

## Results: Bonferroni reference

| budget | delta | coverage | mean_R_lower | mean_K_upper | true_K | s17_R_lower | R_lower_vs_s17 | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 30 | 0.0500 | 1.0000 | 0.0186 | 337.4360 | 40 | 0.0235 | -0.0048 | VALID |
| 30 | 0.1000 | 1.0000 | 0.0188 | 334.5360 | 40 | 0.0241 | -0.0053 | VALID |
| 40 | 0.0500 | 1.0000 | 0.0204 | 334.6920 | 40 | 0.0255 | -0.0052 | VALID |
| 40 | 0.1000 | 1.0000 | 0.0205 | 330.8400 | 40 | 0.0266 | -0.0061 | VALID |
| 60 | 0.0500 | 1.0000 | 0.0273 | 329.9120 | 40 | 0.0310 | -0.0037 | VALID |
| 60 | 0.1000 | 1.0000 | 0.0279 | 325.4260 | 40 | 0.0332 | -0.0053 | VALID |
| 80 | 0.0500 | 1.0000 | 0.0372 | 325.7640 | 40 | 0.0397 | -0.0025 | VALID |
| 80 | 0.1000 | 1.0000 | 0.0376 | 320.1980 | 40 | 0.0428 | -0.0052 | VALID |
| 100 | 0.0500 | 1.0000 | 0.0537 | 317.3140 | 40 | 0.0592 | -0.0056 | VALID |
| 100 | 0.1000 | 1.0000 | 0.0548 | 309.5720 | 40 | 0.0640 | -0.0093 | VALID |
| 150 | 0.0500 | 1.0000 | 0.0685 | 296.4400 | 40 | 0.0835 | -0.0150 | VALID |
| 150 | 0.1000 | 1.0000 | 0.0714 | 287.3820 | 40 | 0.0925 | -0.0211 | VALID |

## Key comparison: R_lower at delta=0.05

| B | Non-stratified (S17) | Bonferroni | Simes approx | Simes exact |
|---|---|---|---|---|
| 30 | 0.0235 | 0.0186 | 0.0188 | 0.0186 |
| 40 | 0.0255 | 0.0204 | 0.0207 | 0.0204 |
| 60 | 0.0310 | 0.0273 | 0.0283 | 0.0273 |
| 80 | 0.0397 | 0.0372 | 0.0391 | 0.0372 |
| 100 | 0.0592 | 0.0537 | 0.0580 | 0.0537 |
| 150 | 0.0835 | 0.0685 | 0.0788 | 0.0685 |

## DECISION

`SIMES_CORRECTION_VALID_NO_MEANINGFUL_GAIN`

## Interpretation

Simes correction maintains valid coverage but does NOT provide a meaningfully
tighter R_lower than the non-stratified bound.

Mean R_lower improvement vs non-stratified (S17):
- Simes approx: -0.0037
- Simes exact: -0.0074
- Bonferroni: -0.0074

The Simes correction is tighter than Bonferroni (as expected) but still does
not beat the non-stratified bound. This confirms that the bottleneck is NOT
the joint correction method — it's the fundamental problem of estimating 40
positives from a small sample (11.5% rate, ~20-40 estimation samples).

The non-stratified bound pools all samples into one hypergeometric calculation,
which is more efficient than splitting into L=12 strata of ~2-4 samples each.
Stratification only helps when per-stratum positive rates are very different
AND each stratum has enough samples to estimate its rate — neither condition
holds here (12 strata, ~2-4 samples each, many strata have 0 positives).

## Conclusion for the paper

The stratified bound line is concluded:
- Bonferroni: valid but looser than non-stratified (Stage 21)
- Simes: valid but no meaningful gain over non-stratified (this stage)
- **The non-stratified exact hypergeometric bound (Stage 17) remains the best
  bound method.** It is valid, deployable, and as tight as any stratified variant.

The fundamental limitation is statistical: with 40 positives in 347 anchors
(11.5% rate) and ~20-40 estimation samples, no bound method can give a tight
R_lower. The bound's tightness is limited by the positive rate and sample size,
not by the correction method.

## Guardrails

- Coverage validated by Monte Carlo on known ground truth, NOT formal theorem.
- "recall lower bound estimate under simulated replay", NOT "recall guarantee".
- The Simes approx is a heuristic adaptation, not the textbook Simes procedure.
- The Simes exact is closer to textbook but uses a fallback for failing strata.

## Outputs

- `tables/stage23_simes_correction.csv`
