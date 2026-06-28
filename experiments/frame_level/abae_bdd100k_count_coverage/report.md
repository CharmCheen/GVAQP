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
- trials: 100
- bootstrap_trials: 300
- alpha: 0.05


## Results

| Method | AVG abs_err | AVG rel_err | AVG CI width | AVG coverage | COUNT abs_err | COUNT rel_err | COUNT CI width | COUNT coverage |
|--------|-------------|-------------|--------------|-------------|---------------|---------------|----------------|----------------|
| Uniform | 0.1932 | 0.0127 | 0.9341 | 97.00% | 66.4 | 0.0669 | 366.9 | 97.00% |
| ABae-paper | 0.1350 | 0.0089 | 0.6249 | 97.00% | 69.6 | 0.0702 | 268.6 | 89.00% |
| ABae-full_variance | 0.1242 | 0.0082 | 0.5818 | 97.00% | 66.6 | 0.0671 | 174.5 | 70.00% |

## Qualitative Assessment (ABae-paper vs Uniform)

- ABae-paper AVG CI width < Uniform: True (0.6249 vs 0.9341)
- ABae-paper COUNT CI width < Uniform: True (268.6 vs 366.9)
- **ABae-paper improves over uniform sampling** on this benchmark.


## ABae-paper vs ABae-full_variance

- paper AVG CI width: 0.6249, full_variance: 0.5818
- paper COUNT CI width: 268.6, full_variance: 174.5
- paper AVG coverage: 97.00%, full_variance: 97.00%
- paper COUNT coverage: 89.00%, full_variance: 70.00%


## Limitations

- BDD100K is an image-level road-scene benchmark, not a temporal clip benchmark.
- The cached oracle is YOLOv8x pseudo-oracle, not human ground truth.
- ABae is for aggregation with expensive predicates, not selection or clip queries.
- statistic_value source (oracle_count) is cached oracle-derived for offline reproduction; ABae sampling simulates oracle access by reading cached labels/counts only for sampled records.
- refe_repos/abae not found; implementation based on paper description only.
- COUNT bootstrap CI may be anti-conservative with stratified sampling.


---
Generated: 2026-05-20T08:43:15.142033
