# Stage 14: Certificate Coverage Monte Carlo Self-Check

## Setup

500 simulations per (B, delta) combo. Each simulation:
1. Draw stratified temporal calibration sample (known prob)
2. Draw proxy-based exploit sample (NOT known prob)
3. Draw stratified temporal audit sample (known prob, from remaining)
4. Compute HT estimate of total positives from estimation_pool (cal + audit)
5. Compute N_pos_upper = HT + z * SE (one-sided)
6. Compute R_lower = H / N_pos_upper (H = positives found in retrieval pool)
7. Check: R_lower <= true_recall?

True total positives = 40 (known from full oracle).
delta tested: 0.05 and 0.10.

## Results

| budget | delta | est_pool_size | coverage | nominal | coverage_gap | mean_R_lower | mean_true_recall | mean_HT_estimate | true_total_pos | mean_N_pos_upper | frac_R_lower_gt_1 | frac_R_lower_gt_recall | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 30 | 0.0500 | 9 | 0.2160 | 0.9500 | -0.7340 | 2.6092 | 0.1880 | 26.1740 | 40 | 28.5099 | 0.3600 | 0.7840 | UNRELIABLE |
| 30 | 0.1000 | 9 | 0.2160 | 0.9000 | -0.6840 | 2.6115 | 0.1880 | 26.1740 | 40 | 28.0735 | 0.3600 | 0.7840 | UNRELIABLE |
| 40 | 0.0500 | 12 | 0.2900 | 0.9500 | -0.6600 | 2.0637 | 0.1979 | 32.2900 | 40 | 34.6151 | 0.2700 | 0.7100 | UNRELIABLE |
| 40 | 0.1000 | 12 | 0.2900 | 0.9000 | -0.6100 | 2.0659 | 0.1979 | 32.2900 | 40 | 34.1612 | 0.2700 | 0.7100 | UNRELIABLE |
| 60 | 0.0500 | 17 | 0.4680 | 0.9500 | -0.4820 | 1.3473 | 0.2316 | 44.7540 | 40 | 47.1076 | 0.1440 | 0.5320 | UNRELIABLE |
| 60 | 0.1000 | 17 | 0.4680 | 0.9000 | -0.4320 | 1.3497 | 0.2316 | 44.7540 | 40 | 46.6196 | 0.1440 | 0.5320 | UNRELIABLE |
| 80 | 0.0500 | 23 | 0.8300 | 0.9500 | -0.1200 | 0.5115 | 0.2818 | 99.3600 | 40 | 102.3985 | 0.0380 | 0.1700 | UNRELIABLE |
| 80 | 0.1000 | 23 | 0.8300 | 0.9000 | -0.0700 | 0.5130 | 0.2818 | 99.3600 | 40 | 101.7358 | 0.0380 | 0.1700 | UNRELIABLE |
| 100 | 0.0500 | 28 | 0.8760 | 0.9500 | -0.0740 | 0.6174 | 0.3972 | 94.0565 | 40 | 96.7404 | 0.0280 | 0.1240 | UNRELIABLE |
| 100 | 0.1000 | 28 | 0.8760 | 0.9000 | -0.0240 | 0.6191 | 0.3972 | 94.0565 | 40 | 96.1538 | 0.0280 | 0.1240 | UNRELIABLE |
| 150 | 0.0500 | 42 | 0.9060 | 0.9500 | -0.0440 | 0.3400 | 0.5024 | 95.6610 | 40 | 97.9106 | 0.0280 | 0.0940 | UNRELIABLE |
| 150 | 0.1000 | 42 | 0.9060 | 0.9000 | 0.0060 | 0.3419 | 0.5024 | 95.6610 | 40 | 97.4146 | 0.0280 | 0.0940 | VALID |

## Diagnosis

### 1. Coverage is FAR below nominal

At delta=0.05 (nominal 95%):
- B=30: coverage=0.216 (nominal 0.95, gap=-0.734)
- B=40: coverage=0.290 (nominal 0.95, gap=-0.660)
- B=60: coverage=0.468 (nominal 0.95, gap=-0.482)
- B=80: coverage=0.830 (nominal 0.95, gap=-0.120)
- B=100: coverage=0.876 (nominal 0.95, gap=-0.074)
- B=150: coverage=0.906 (nominal 0.95, gap=-0.044)

At delta=0.10 (nominal 90%):
- B=30: coverage=0.216 (nominal 0.90, gap=-0.684)
- B=40: coverage=0.290 (nominal 0.90, gap=-0.610)
- B=60: coverage=0.468 (nominal 0.90, gap=-0.432)
- B=80: coverage=0.830 (nominal 0.90, gap=-0.070)
- B=100: coverage=0.876 (nominal 0.90, gap=-0.024)
- B=150: coverage=0.906 (nominal 0.90, gap=+0.006)

### 2. Root cause: HT estimator UNDERESTIMATES total positives

Mean HT estimate across all sims: 95.66
True total positives: 40
**HT bias = +55.66 (underestimates by 55.7 positives on average)**

This is because the estimation_pool is small (9 anchors at B=80)
and the stratified temporal sample often misses positives (positive rate is 11.5%, so a
22-anchor sample expects ~2.5 positives, but the HT weight inflation makes the estimate
high-variance and biased downward when few positives are sampled).

### 3. R_lower > true_recall (anti-conservative)

Fraction of sims where R_lower > true_recall:
- B=30: 0.784
- B=40: 0.710
- B=60: 0.532
- B=80: 0.170
- B=100: 0.124
- B=150: 0.094

This means the "lower bound" is actually ABOVE the true recall in many simulations —
the certificate is anti-conservative (claims higher recall than actually achieved).

### 4. R_lower > 1.0 (vacuous) at low budgets

Fraction of sims where R_lower > 1.0:
- B=30: 0.360
- B=40: 0.270
- B=60: 0.144
- B=80: 0.038
- B=100: 0.028
- B=150: 0.028

## DECISION

`CERTIFICATE_MECHANISM_UNRELIABLE`

The certificate mechanism as implemented (HT + normal approx on small stratified samples)
is **UNRELIABLE**. Coverage is far below nominal at all budgets and both delta levels.

## Why it fails and what would fix it

1. **Estimation pool too small**: at B=80, only ~22 anchors (16 cal + 6 audit) for HT
   estimation of 40 positives among 347 anchors. The HT estimator needs more known-
   probability samples to be reliable.
2. **Normal approximation inappropriate**: with ~2-5 positive observations in the
   estimation pool, the normal approximation for the HT variance is invalid. A
   Wilson/Clopper-Pearson interval or a bootstrap interval would be more appropriate.
3. **Stratified design variance underestimation**: the simplified HT variance ignores
   within-stratum correlation and second-order inclusion probabilities, underestimating
   the true variance.
4. **Potential fix**: increase the estimation pool fraction (alpha=0.30-0.40 instead of
   0.20), use a conservative finite-population correction, or switch to a Wilson-style
   bound on the positive rate per stratum (block-level Wilson + sum).

## Guardrail

- This is a Monte Carlo simulation on KNOWN ground truth, NOT a formal theorem.
- Even if coverage were valid, it would only apply to dataset3's specific distribution
  (40/347, 27 clusters). Cross-video validation is needed.
- Do NOT claim "ACCE provides a valid recall certificate" from these results.
- The certificate mechanism needs redesign before it can be included in the paper.

## Outputs

- `tables/stage14_certificate_coverage.csv` (full per-B-per-delta results)
