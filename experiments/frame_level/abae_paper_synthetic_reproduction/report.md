# ABae Synthetic Smoke Report


## Allocation Modes

- **ABae-paper** (default): T_k ∝ sqrt(p_hat_k * sigma_hat_k). Faithful to ABae Algorithm 1.
- **ABae-full_variance**: w_k = n_k * sqrt(p_k*sigma_k^2 + p_k*(1-p_k)*mu_k^2). Exploratory variant.
- **Uniform**: baseline random sampling.


## Data Generation Parameters

- N: 100000
- proxy_score ~ Beta(2, 5)
- label_prob = sigmoid(10*(proxy_score - 0.55))
- statistic_value = proxy_score + N(0, 0.1)
- positive_rate: 0.1355
- seed: 42


## Exact Answers

- AVG(statistic_value | label=1): 0.478490
- COUNT(label=1): 13554


## Experiment Parameters

- num_strata: 10
- trials: 30
- bootstrap_trials: 300
- alpha: 0.05


## Budget=500 (stage1_per_stratum=20)

| Method | AVG abs_err | AVG rel_err | AVG CI width | AVG coverage | COUNT abs_err | COUNT rel_err | COUNT CI width | COUNT coverage |
|--------|-------------|-------------|--------------|-------------|---------------|---------------|----------------|----------------|
| Uniform | 0.0173 | 0.0362 | 0.0821 | 96.67% | 1112.8 | 0.0821 | 5991.0 | 96.67% |
| ABae-paper | 0.0160 | 0.0335 | 0.0724 | 93.33% | 1106.2 | 0.0816 | 4393.8 | 93.33% |
| ABae-full_variance | 0.0118 | 0.0247 | 0.0707 | 96.67% | 910.2 | 0.0672 | 4236.0 | 90.00% |

## Budget=1000 (stage1_per_stratum=20)

| Method | AVG abs_err | AVG rel_err | AVG CI width | AVG coverage | COUNT abs_err | COUNT rel_err | COUNT CI width | COUNT coverage |
|--------|-------------|-------------|--------------|-------------|---------------|---------------|----------------|----------------|
| Uniform | 0.0122 | 0.0254 | 0.0589 | 100.00% | 726.9 | 0.0536 | 4164.7 | 96.67% |
| ABae-paper | 0.0216 | 0.0452 | 0.0594 | 63.33% | 1122.7 | 0.0828 | 3435.6 | 80.00% |
| ABae-full_variance | 0.0104 | 0.0218 | 0.0540 | 86.67% | 797.4 | 0.0588 | 3092.8 | 83.33% |

## Budget=2000 (stage1_per_stratum=30)

| Method | AVG abs_err | AVG rel_err | AVG CI width | AVG coverage | COUNT abs_err | COUNT rel_err | COUNT CI width | COUNT coverage |
|--------|-------------|-------------|--------------|-------------|---------------|---------------|----------------|----------------|
| Uniform | 0.0087 | 0.0182 | 0.0415 | 93.33% | 544.7 | 0.0402 | 2965.2 | 96.67% |
| ABae-paper | 0.0160 | 0.0335 | 0.0426 | 66.67% | 899.3 | 0.0664 | 2365.4 | 63.33% |
| ABae-full_variance | 0.0077 | 0.0161 | 0.0390 | 96.67% | 459.9 | 0.0339 | 2241.1 | 93.33% |

## Budget=5000 (stage1_per_stratum=75)

| Method | AVG abs_err | AVG rel_err | AVG CI width | AVG coverage | COUNT abs_err | COUNT rel_err | COUNT CI width | COUNT coverage |
|--------|-------------|-------------|--------------|-------------|---------------|---------------|----------------|----------------|
| Uniform | 0.0052 | 0.0109 | 0.0265 | 100.00% | 350.7 | 0.0259 | 1847.1 | 96.67% |
| ABae-paper | 0.0074 | 0.0154 | 0.0262 | 86.67% | 420.0 | 0.0310 | 1443.7 | 86.67% |
| ABae-full_variance | 0.0061 | 0.0128 | 0.0258 | 86.67% | 332.6 | 0.0245 | 1480.4 | 90.00% |

## Budget=10000 (stage1_per_stratum=150)

| Method | AVG abs_err | AVG rel_err | AVG CI width | AVG coverage | COUNT abs_err | COUNT rel_err | COUNT CI width | COUNT coverage |
|--------|-------------|-------------|--------------|-------------|---------------|---------------|----------------|----------------|
| Uniform | 0.0043 | 0.0090 | 0.0187 | 90.00% | 284.0 | 0.0210 | 1334.5 | 100.00% |
| ABae-paper | 0.0041 | 0.0086 | 0.0169 | 83.33% | 214.9 | 0.0159 | 1006.8 | 90.00% |
| ABae-full_variance | 0.0044 | 0.0092 | 0.0183 | 93.33% | 207.6 | 0.0153 | 1029.5 | 90.00% |

## Qualitative Assessment (ABae-paper vs Uniform)

### Budget=500
- ABae-paper AVG CI width < Uniform: True (0.0724 vs 0.0821)
- ABae-paper COUNT CI width < Uniform: True (4393.8 vs 5991.0)
- **Result**: ABae-paper improves over uniform sampling as expected.

### Budget=1000
- ABae-paper AVG CI width < Uniform: False (0.0594 vs 0.0589)
- ABae-paper COUNT CI width < Uniform: True (3435.6 vs 4164.7)
- **Result**: ABae-paper partially improves over uniform sampling.

### Budget=2000
- ABae-paper AVG CI width < Uniform: False (0.0426 vs 0.0415)
- ABae-paper COUNT CI width < Uniform: True (2365.4 vs 2965.2)
- **Result**: ABae-paper partially improves over uniform sampling.

### Budget=5000
- ABae-paper AVG CI width < Uniform: True (0.0262 vs 0.0265)
- ABae-paper COUNT CI width < Uniform: True (1443.7 vs 1847.1)
- **Result**: ABae-paper improves over uniform sampling as expected.

### Budget=10000
- ABae-paper AVG CI width < Uniform: True (0.0169 vs 0.0187)
- ABae-paper COUNT CI width < Uniform: True (1006.8 vs 1334.5)
- **Result**: ABae-paper improves over uniform sampling as expected.


## ABae-paper vs ABae-full_variance

### Budget=500
- paper AVG CI width: 0.0724, full_variance: 0.0707
- paper COUNT CI width: 4393.8, full_variance: 4236.0
- paper AVG coverage: 93.33%, full_variance: 96.67%
- paper COUNT coverage: 93.33%, full_variance: 90.00%

### Budget=1000
- paper AVG CI width: 0.0594, full_variance: 0.0540
- paper COUNT CI width: 3435.6, full_variance: 3092.8
- paper AVG coverage: 63.33%, full_variance: 86.67%
- paper COUNT coverage: 80.00%, full_variance: 83.33%

### Budget=2000
- paper AVG CI width: 0.0426, full_variance: 0.0390
- paper COUNT CI width: 2365.4, full_variance: 2241.1
- paper AVG coverage: 66.67%, full_variance: 96.67%
- paper COUNT coverage: 63.33%, full_variance: 93.33%

### Budget=5000
- paper AVG CI width: 0.0262, full_variance: 0.0258
- paper COUNT CI width: 1443.7, full_variance: 1480.4
- paper AVG coverage: 86.67%, full_variance: 86.67%
- paper COUNT coverage: 86.67%, full_variance: 90.00%

### Budget=10000
- paper AVG CI width: 0.0169, full_variance: 0.0183
- paper COUNT CI width: 1006.8, full_variance: 1029.5
- paper AVG coverage: 83.33%, full_variance: 93.33%
- paper COUNT coverage: 90.00%, full_variance: 90.00%


## COUNT Coverage Warnings

- **WARNING**: ABae-paper at budget=500: COUNT coverage = 93.33% < 95%. CI is anti-conservative (too narrow). Interpret COUNT CI with caution.
- **WARNING**: ABae-full_variance at budget=500: COUNT coverage = 90.00% < 95%. CI is anti-conservative (too narrow). Interpret COUNT CI with caution.
- **WARNING**: ABae-paper at budget=1000: COUNT coverage = 80.00% < 95%. CI is anti-conservative (too narrow). Interpret COUNT CI with caution.
- **WARNING**: ABae-full_variance at budget=1000: COUNT coverage = 83.33% < 95%. CI is anti-conservative (too narrow). Interpret COUNT CI with caution.
- **WARNING**: ABae-paper at budget=2000: COUNT coverage = 63.33% < 95%. CI is anti-conservative (too narrow). Interpret COUNT CI with caution.
- **WARNING**: ABae-full_variance at budget=2000: COUNT coverage = 93.33% < 95%. CI is anti-conservative (too narrow). Interpret COUNT CI with caution.
- **WARNING**: ABae-paper at budget=5000: COUNT coverage = 86.67% < 95%. CI is anti-conservative (too narrow). Interpret COUNT CI with caution.
- **WARNING**: ABae-full_variance at budget=5000: COUNT coverage = 90.00% < 95%. CI is anti-conservative (too narrow). Interpret COUNT CI with caution.
- **WARNING**: ABae-paper at budget=10000: COUNT coverage = 90.00% < 95%. CI is anti-conservative (too narrow). Interpret COUNT CI with caution.
- **WARNING**: ABae-full_variance at budget=10000: COUNT coverage = 90.00% < 95%. CI is anti-conservative (too narrow). Interpret COUNT CI with caution.

**Note**: Percentile bootstrap CI for COUNT can be anti-conservative with stratified sampling, especially when allocation is non-uniform. The paper mode (T_k ∝ sqrt(p_hat_k * sigma_hat_k)) allocates more samples to high-positive strata, which reduces CI width but can under-estimate between-stratum variability in bootstrap.


---
Generated: 2026-05-20T09:37:14.763533
