# ABae BDD100K Real-Frame Smoke Report


## Allocation Modes

- **ABae-paper** (default): T_k ∝ sqrt(p_hat_k * sigma_hat_k). Faithful to ABae Algorithm 1.
- **ABae-full_variance**: w_k = n_k * sqrt(p_k*sigma_k^2 + p_k*(1-p_k)*mu_k^2). Exploratory variant.
- **Uniform**: baseline random sampling.


## Data Source

- supg_source: `garc_eval/outputs/bdd100k_smoke/supg_source.csv`
- oracle_scores: `garc_eval/outputs/bdd100k_smoke/oracle_scores.parquet`
- proxy_scores: `garc_eval/outputs/bdd100k_smoke/proxy_scores.parquet`
- **YOLO rerun: NO** (using cached data only)


## Query

- predicate: count_car(frame) >= 13
- N: 10000
- positive rate: 0.0992 (992 / 10000)
- statistic_value source: oracle_count


## Exact Answers

- AVG(oracle_count | label=1): 15.2026
- COUNT(label=1): 992


## Experiment Parameters

- budget: 1000
- num_strata: 13
- stage1_per_stratum: 20
- trials: 30
- bootstrap_trials: 300
- alpha: 0.05


## Results

| Method | AVG abs_err | AVG rel_err | AVG CI width | AVG coverage | COUNT abs_err | COUNT rel_err | COUNT CI width | COUNT coverage |
|--------|-------------|-------------|--------------|-------------|---------------|---------------|----------------|----------------|
| Uniform | 0.1662 | 0.0109 | 0.9348 | 96.67% | 74.9 | 0.0755 | 374.6 | 96.67% |
| ABae-paper | 0.1569 | 0.0103 | 0.6092 | 93.33% | 80.3 | 0.0810 | 246.8 | 80.00% |
| ABae-full_variance | 0.1266 | 0.0083 | 0.5709 | 100.00% | 78.1 | 0.0788 | 164.0 | 56.67% |

## Qualitative Assessment (ABae-paper vs Uniform)

- ABae-paper AVG CI width < Uniform: True (0.6092 vs 0.9348)
- ABae-paper COUNT CI width < Uniform: True (246.8 vs 374.6)
- **ABae-paper improves over uniform sampling** on this benchmark.


## ABae-paper vs ABae-full_variance

- paper AVG CI width: 0.6092, full_variance: 0.5709
- paper COUNT CI width: 246.8, full_variance: 164.0
- paper AVG coverage: 93.33%, full_variance: 100.00%
- paper COUNT coverage: 80.00%, full_variance: 56.67%


## COUNT CI Coverage (100 trials)

| Method | AVG coverage | COUNT coverage |
|--------|-------------|----------------|
| Uniform | 97.00% | 97.00% |
| ABae-paper | 97.00% | 89.00% |
| ABae-full_variance | 97.00% | 70.00% |

**Warning**: COUNT bootstrap CIs with ABae-paper are mildly anti-conservative (89% vs target 95%). AVG CIs are well-calibrated. ABae-full_variance has worse COUNT coverage (70%). See `abae_bdd100k_count_coverage/` for detailed diagnostic.

## Limitations

- BDD100K is an image-level road-scene benchmark, not a temporal clip benchmark.
- The cached oracle is YOLOv8x pseudo-oracle, not human ground truth.
- ABae is for aggregation with expensive predicates, not selection or clip queries.
- statistic_value source (oracle_count) is cached oracle-derived for offline reproduction; ABae sampling simulates oracle access by reading cached labels/counts only for sampled records.
- refe_repos/abae not found; implementation based on paper description only.
- COUNT bootstrap CI may be anti-conservative with stratified sampling (89% coverage for ABae-paper).
- ABae-paper is faithful to ABae Algorithm 1. ABae-full_variance is an exploratory variant.

---
Generated: 2026-05-20T08:21:34.751045
