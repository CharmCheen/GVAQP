# Stage 21: Stratified Hypergeometric Bound with Bonferroni Correction

## Setup

Stratified exact hypergeometric bound with Bonferroni confidence budget allocation:
- L = 12 time blocks (300s each)
- delta_h = delta / L per stratum (Bonferroni)
- Two allocation strategies:
  - **Proportional** (deployable): audit samples allocated by N_h (stratum size), no oracle info
  - **Neyman** (diagnostic only): audit samples allocated by N_h * sqrt(p_h*(1-p_h)) using TRUE p_h

Monte Carlo: 500 sims per (B, delta, allocation). delta=0.05 and 0.10.
Comparison vs Stage 17 non-stratified stratified_hypergeom (same sampling, same delta).

## Results: Proportional allocation (DEPLOYABLE)

| budget | delta | est_pool_size | coverage | nominal | mean_R_lower | mean_K_upper | true_K | mean_recall | s17_R_lower | R_lower_improvement | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 30 | 0.0500 | 8 | 1.0000 | 0.9500 | 0.0186 | 337.4360 | 40 | 0.2298 | 0.0235 | -0.0048 | VALID |
| 30 | 0.1000 | 8 | 1.0000 | 0.9000 | 0.0188 | 334.5360 | 40 | 0.2291 | 0.0241 | -0.0053 | VALID |
| 40 | 0.0500 | 10 | 1.0000 | 0.9500 | 0.0204 | 334.6920 | 40 | 0.2376 | 0.0255 | -0.0052 | VALID |
| 40 | 0.1000 | 10 | 1.0000 | 0.9000 | 0.0205 | 330.8400 | 40 | 0.2361 | 0.0266 | -0.0061 | VALID |
| 60 | 0.0500 | 15 | 1.0000 | 0.9500 | 0.0273 | 329.9120 | 40 | 0.2840 | 0.0310 | -0.0037 | VALID |
| 60 | 0.1000 | 15 | 1.0000 | 0.9000 | 0.0279 | 325.4260 | 40 | 0.2856 | 0.0332 | -0.0053 | VALID |
| 80 | 0.0500 | 19 | 1.0000 | 0.9500 | 0.0372 | 325.7640 | 40 | 0.3939 | 0.0397 | -0.0025 | VALID |
| 80 | 0.1000 | 19 | 1.0000 | 0.9000 | 0.0376 | 320.1980 | 40 | 0.3907 | 0.0428 | -0.0052 | VALID |
| 100 | 0.0500 | 24 | 1.0000 | 0.9500 | 0.0537 | 317.3140 | 40 | 0.5341 | 0.0592 | -0.0056 | VALID |
| 100 | 0.1000 | 24 | 1.0000 | 0.9000 | 0.0548 | 309.5720 | 40 | 0.5336 | 0.0640 | -0.0093 | VALID |
| 150 | 0.0500 | 36 | 1.0000 | 0.9500 | 0.0685 | 296.4400 | 40 | 0.6318 | 0.0835 | -0.0150 | VALID |
| 150 | 0.1000 | 36 | 1.0000 | 0.9000 | 0.0714 | 287.3820 | 40 | 0.6375 | 0.0925 | -0.0211 | VALID |

## Results: Neyman allocation (DIAGNOSTIC ONLY, oracle-informed)

| budget | delta | est_pool_size | coverage | nominal | mean_R_lower | mean_K_upper | true_K | mean_recall | s17_R_lower | R_lower_improvement | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 30 | 0.0500 | 8 | 1.0000 | 0.9500 | 0.0186 | 337.4360 | 40 | 0.2298 | 0.0235 | -0.0048 | VALID |
| 30 | 0.1000 | 8 | 1.0000 | 0.9000 | 0.0188 | 334.5360 | 40 | 0.2291 | 0.0241 | -0.0053 | VALID |
| 40 | 0.0500 | 10 | 1.0000 | 0.9500 | 0.0204 | 334.6920 | 40 | 0.2376 | 0.0255 | -0.0052 | VALID |
| 40 | 0.1000 | 10 | 1.0000 | 0.9000 | 0.0205 | 330.8400 | 40 | 0.2361 | 0.0266 | -0.0061 | VALID |
| 60 | 0.0500 | 15 | 1.0000 | 0.9500 | 0.0273 | 329.9120 | 40 | 0.2840 | 0.0310 | -0.0037 | VALID |
| 60 | 0.1000 | 15 | 1.0000 | 0.9000 | 0.0279 | 325.4260 | 40 | 0.2856 | 0.0332 | -0.0053 | VALID |
| 80 | 0.0500 | 19 | 1.0000 | 0.9500 | 0.0380 | 326.5220 | 40 | 0.3949 | 0.0397 | -0.0017 | VALID |
| 80 | 0.1000 | 19 | 1.0000 | 0.9000 | 0.0387 | 320.9660 | 40 | 0.3952 | 0.0428 | -0.0041 | VALID |
| 100 | 0.0500 | 24 | 1.0000 | 0.9500 | 0.0541 | 318.0200 | 40 | 0.5304 | 0.0592 | -0.0051 | VALID |
| 100 | 0.1000 | 24 | 1.0000 | 0.9000 | 0.0554 | 310.3120 | 40 | 0.5292 | 0.0640 | -0.0086 | VALID |
| 150 | 0.0500 | 36 | 1.0000 | 0.9500 | 0.0688 | 303.3600 | 40 | 0.6389 | 0.0835 | -0.0147 | VALID |
| 150 | 0.1000 | 36 | 1.0000 | 0.9000 | 0.0708 | 293.7980 | 40 | 0.6372 | 0.0925 | -0.0217 | VALID |

## Coverage check

Proportional: all valid = True
Neyman: all valid = True

Both allocations achieve coverage = 1.0 at all budgets and deltas (with Bonferroni
correction). The Bonferroni correction (delta_h = delta/L = delta/12) makes the
per-stratum bounds very conservative, which is why coverage is 1.0.

## R_lower tightness comparison (vs Stage 17)

### Proportional (deployable)
Mean R_lower improvement vs Stage 17: -0.0074

### Neyman (diagnostic)
Mean R_lower improvement vs Stage 17: -0.0072

The Neyman allocation (which uses oracle p_h to optimize sample allocation) provides
a tighter bound than proportional, as expected. The proportional allocation is the
deployable version.

## B=80 missed cluster check (structural gap from Stage 20)

### proportional at B=80, delta=0.05
Clusters missed >50% of sims: 17
| cluster_id | miss_freq | allocation |
| --- | --- | --- |
| 13 | 0.9840 | proportional |
| 14 | 0.9740 | proportional |
| 21 | 0.9740 | proportional |
| 12 | 0.9720 | proportional |
| 11 | 0.9700 | proportional |
| 17 | 0.9680 | proportional |
| 0 | 0.9660 | proportional |
| 2 | 0.9660 | proportional |
| 15 | 0.9660 | proportional |
| 25 | 0.9660 | proportional |

### neyman at B=80, delta=0.05
Clusters missed >50% of sims: 17
| cluster_id | miss_freq | allocation |
| --- | --- | --- |
| 26 | 1.0000 | neyman |
| 14 | 0.9740 | neyman |
| 21 | 0.9740 | neyman |
| 15 | 0.9720 | neyman |
| 25 | 0.9680 | neyman |
| 0 | 0.9660 | neyman |
| 2 | 0.9660 | neyman |
| 12 | 0.9660 | neyman |
| 1 | 0.9640 | neyman |
| 16 | 0.9640 | neyman |

## DECISION

`STRATIFIED_BOUND_NO_MEANINGFUL_GAIN`

## Interpretation

The stratified bound with Bonferroni correction maintains valid coverage
(1.0 >= nominal) but does NOT provide a meaningfully tighter R_lower than the
non-stratified version (mean improvement = -0.0074).

This is because the Bonferroni correction (delta_h = delta/12) makes each
per-stratum bound very conservative. With 12 strata and delta=0.05, each
stratum gets delta_h = 0.00417, which is extremely small, leading to
very wide per-stratum bounds that sum to a total bound similar to or wider
than the non-stratified version.

The Neyman allocation (oracle-informed) shows no meaningful improvement either,
indicating that the bottleneck is the Bonferroni correction itself, not the
allocation strategy.

**Possible fix (future work)**: replace Bonferroni with a less conservative
joint correction (e.g., Simes correction, or exact multivariate hypergeometric
joint distribution). This is left for future work as it requires more complex
implementation.

## B=80 structural gap

The B=80 structural cluster gap (Stage 20) is NOT addressed by stratification.
The missed clusters are low-proxy-score singletons spread across multiple blocks.
Stratification forces audit coverage in each block, but the audit samples are
random within blocks and do not specifically target the missed clusters' anchors.

## Guardrails

- Proportional allocation is the ONLY deployable version. Neyman uses true p_h
  (oracle-informed) and is diagnostic only.
- Coverage is validated by Monte Carlo on known ground truth (dataset3, 40/347),
  NOT by formal theorem.
- R_lower is a "recall lower bound estimate under simulated replay", NOT a
  formal theorem statement.
- The Bonferroni correction is conservative; less conservative joint corrections
  (Simes, exact joint hypergeometric) could tighten the bound but are left for
  future work.

## Outputs

- `tables/stage21_stratified_bound_results.csv`
- `tables/stage21_b80_missed_clusters_proportional.csv`
- `tables/stage21_b80_missed_clusters_neyman.csv`
- `replay/stage21_mc_selection_traces.csv`
