# Stage 17: Exact Finite-Population Bound Redesign

## Key Insight: i.i.d. violation does NOT invalidate random-sample estimation

The Sprint 2 certificate failure (HT + normal approximation, coverage 0.83) was
misdiagnosed as "temporal clustering makes certification impossible." This is wrong.

**Two separate things are conflated:**
1. **Exploitation efficiency** (how fast proxy-based selection finds positives):
   YES, temporal clustering (P(1→1)=2.83x) affects this — clustered positives are
   harder to find with uniform sampling, easier with proxy+diversity.
2. **Audit sample validity** (does a random sample give an unbiased population estimate):
   NO, temporal clustering does NOT affect this — a simple random sample without
   replacement (SRSWOR) gives an unbiased estimate of total positives regardless
   of HOW positives are distributed in the population.

The hypergeometric distribution is EXACT for SRSWOR: if we draw n samples from
N items containing K positives, the count of positives in the sample follows
Hypergeometric(N, K, n) — this holds whether positives are clustered or scattered.
The only requirement is that the SAMPLING is random, not that the POPULATION is i.i.d.

## Methods tested

| Sampling | Bound method | Description |
|---|---|---|
| SRSWOR | exact_hypergeom | Exact Clopper-Pearson-style hypergeometric upper bound |
| SRSWOR | wilson | Wilson interval with FPC (pooled) |
| Stratified | stratified_hypergeom | Per-stratum exact hypergeom, summed (conservative) |
| Stratified | stratified_wilson | Per-stratum Wilson with FPC, summed (conservative) |

## Summary: which (sampling, bound) combos are valid?

| sampling | bound | min_coverage | mean_coverage | all_valid |
| --- | --- | --- | --- | --- |
| srswor | exact_hypergeom | 0.9600 | 0.9908 | True |
| srswor | wilson | 0.8220 | 0.9532 | False |
| stratified | wilson | 0.8400 | 0.9500 | False |
| stratified | stratified_wilson | 1.0000 | 1.0000 | True |
| stratified | stratified_hypergeom | 1.0000 | 1.0000 | True |

## Detailed results: exact_hypergeom + SRSWOR

| budget | delta | est_pool_size | coverage | nominal | mean_K_upper | true_K | mean_R_lower | mean_true_recall | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 30 | 0.0500 | 9 | 1.0000 | 0.9500 | 266.0000 | 40 | 0.0383 | 0.1875 | VALID |
| 30 | 0.1000 | 9 | 1.0000 | 0.9000 | 246.0200 | 40 | 0.0479 | 0.1870 | VALID |
| 40 | 0.0500 | 12 | 1.0000 | 0.9500 | 280.0880 | 40 | 0.0405 | 0.1941 | VALID |
| 40 | 0.1000 | 12 | 1.0000 | 0.9000 | 280.1840 | 40 | 0.0454 | 0.1946 | VALID |
| 60 | 0.0500 | 17 | 1.0000 | 0.9500 | 312.4260 | 40 | 0.0418 | 0.2334 | VALID |
| 60 | 0.1000 | 17 | 1.0000 | 0.9000 | 320.7700 | 40 | 0.0416 | 0.2352 | VALID |
| 80 | 0.0500 | 23 | 1.0000 | 0.9500 | 329.2520 | 40 | 0.0446 | 0.2819 | VALID |
| 80 | 0.1000 | 23 | 0.9620 | 0.9000 | 334.9920 | 40 | 0.0432 | 0.2812 | VALID |
| 100 | 0.0500 | 28 | 0.9700 | 0.9500 | 337.5800 | 40 | 0.0575 | 0.3987 | VALID |
| 100 | 0.1000 | 28 | 0.9600 | 0.9000 | 334.1600 | 40 | 0.0658 | 0.3976 | VALID |
| 150 | 0.0500 | 42 | 1.0000 | 0.9500 | 347.0000 | 40 | 0.0576 | 0.4995 | VALID |
| 150 | 0.1000 | 42 | 0.9980 | 0.9000 | 346.3400 | 40 | 0.0603 | 0.5033 | VALID |

## Detailed results: stratified_hypergeom + stratified

| budget | delta | est_pool_size | coverage | nominal | mean_K_upper | true_K | mean_R_lower | mean_true_recall | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 30 | 0.0500 | 9 | 1.0000 | 0.9500 | 321.5760 | 40 | 0.0235 | 0.1888 | VALID |
| 30 | 0.1000 | 9 | 1.0000 | 0.9000 | 310.5240 | 40 | 0.0241 | 0.1873 | VALID |
| 40 | 0.0500 | 12 | 1.0000 | 0.9500 | 311.7120 | 40 | 0.0255 | 0.1991 | VALID |
| 40 | 0.1000 | 12 | 1.0000 | 0.9000 | 297.2400 | 40 | 0.0266 | 0.1978 | VALID |
| 60 | 0.0500 | 17 | 1.0000 | 0.9500 | 300.5400 | 40 | 0.0310 | 0.2332 | VALID |
| 60 | 0.1000 | 17 | 1.0000 | 0.9000 | 281.4000 | 40 | 0.0332 | 0.2342 | VALID |
| 80 | 0.0500 | 23 | 1.0000 | 0.9500 | 282.8220 | 40 | 0.0397 | 0.2807 | VALID |
| 80 | 0.1000 | 23 | 1.0000 | 0.9000 | 262.9840 | 40 | 0.0428 | 0.2818 | VALID |
| 100 | 0.0500 | 28 | 1.0000 | 0.9500 | 268.2840 | 40 | 0.0592 | 0.3971 | VALID |
| 100 | 0.1000 | 28 | 1.0000 | 0.9000 | 248.5900 | 40 | 0.0640 | 0.3974 | VALID |
| 150 | 0.0500 | 42 | 1.0000 | 0.9500 | 238.9060 | 40 | 0.0835 | 0.4968 | VALID |
| 150 | 0.1000 | 42 | 1.0000 | 0.9000 | 218.4980 | 40 | 0.0925 | 0.5020 | VALID |

## Detailed results: stratified_wilson + stratified

| budget | delta | est_pool_size | coverage | nominal | mean_K_upper | true_K | mean_R_lower | mean_true_recall | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 30 | 0.0500 | 9 | 1.0000 | 0.9500 | 292.5342 | 40 | 0.0258 | 0.1888 | VALID |
| 30 | 0.1000 | 9 | 1.0000 | 0.9000 | 273.1978 | 40 | 0.0274 | 0.1873 | VALID |
| 40 | 0.0500 | 12 | 1.0000 | 0.9500 | 273.1672 | 40 | 0.0291 | 0.1991 | VALID |
| 40 | 0.1000 | 12 | 1.0000 | 0.9000 | 247.6115 | 40 | 0.0319 | 0.1978 | VALID |
| 60 | 0.0500 | 17 | 1.0000 | 0.9500 | 243.3724 | 40 | 0.0382 | 0.2332 | VALID |
| 60 | 0.1000 | 17 | 1.0000 | 0.9000 | 209.3996 | 40 | 0.0447 | 0.2342 | VALID |
| 80 | 0.0500 | 23 | 1.0000 | 0.9500 | 227.8029 | 40 | 0.0492 | 0.2807 | VALID |
| 80 | 0.1000 | 23 | 1.0000 | 0.9000 | 191.9892 | 40 | 0.0587 | 0.2818 | VALID |
| 100 | 0.0500 | 28 | 1.0000 | 0.9500 | 214.0421 | 40 | 0.0742 | 0.3971 | VALID |
| 100 | 0.1000 | 28 | 1.0000 | 0.9000 | 178.4622 | 40 | 0.0893 | 0.3974 | VALID |
| 150 | 0.0500 | 42 | 1.0000 | 0.9500 | 183.1379 | 40 | 0.1086 | 0.4968 | VALID |
| 150 | 0.1000 | 42 | 1.0000 | 0.9000 | 148.8136 | 40 | 0.1355 | 0.5020 | VALID |

## DECISION

`EXACT_HYPERGEOMETRIC_BOUND_VALIDATED`

## Discussion

The exact hypergeometric bound provides a valid (conservative) recall lower bound
estimate under simulated replay, PROVIDED the estimation sample is drawn by true
random sampling (SRSWOR or stratified SRSWOR). The temporal clustering of positives
does NOT invalidate this bound — only the sampling mechanism matters.

**Important distinction for the paper:**
- The bound is a "recall lower bound estimate under simulated replay", NOT a
  "recall guarantee" — it is validated by Monte Carlo on known ground truth,
  not by a formal theorem.
- The bound's tightness depends on estimation pool size: at small pools (B=30,
  est_pool~12), the bound is very conservative (R_lower << true_recall); at
  larger pools (B=150, est_pool~40), it tightens.
- The stratified version is more conservative than SRSWOR because per-stratum
  bounds are summed independently (ignoring finite-population correction across
  strata). This is a deliberate trade-off: conservative but provably valid.

## Guardrails

- This is Monte Carlo validation on dataset3's KNOWN ground truth (40/347), NOT
  a formal theorem. Cross-video validation is still needed.
- The bound is conservative (R_lower < true_recall in most sims), which is the
  correct direction for a "lower bound" — but it may be too conservative to be
  practically useful at small estimation pools.
- The estimation_pool must be STRICTLY known-probability samples. Proxy-ranked
  exploit samples CANNOT be used for the bound computation.
- Use "recall lower bound estimate under simulated replay" in the paper, NOT
  "recall guarantee" or "statistical guarantee".

## Outputs

- `tables/stage17_exact_bound_coverage.csv` (full results for all method combos)
