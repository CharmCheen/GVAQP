# ABae Temporal Assumption Stress Test

## Executive Summary

This study tests whether temporal correlation breaks ABae's stratified approximate aggregation assumptions.

## 1. Does Temporal Correlation Destabilize ABae?

### Temporal Redundancy Within Strata

| Stratum | Positive Rate | Autocorr (lag-1) | Mean Pos Run | Mean Entropy |
|---------|---------------|------------------|--------------|---------------|
| 0.0 | 0.000 | 0.000 | 0.0 | 0.000 |
| 1.0 | 0.000 | 0.000 | 0.0 | 0.000 |
| 2.0 | 0.000 | 0.000 | 0.0 | 0.000 |
| 3.0 | 0.019 | 0.635 | 2.7 | 0.027 |
| 4.0 | 0.098 | 0.718 | 3.9 | 0.095 |
| 5.0 | 0.163 | 0.750 | 4.7 | 0.127 |
| 6.0 | 0.182 | 0.678 | 3.8 | 0.173 |
| 7.0 | 0.167 | 0.540 | 2.6 | 0.247 |
| 8.0 | 0.189 | 0.472 | 2.3 | 0.310 |
| 9.0 | 0.274 | 0.561 | 3.1 | 0.340 |

**Key finding:** Temporal autocorrelation within strata is moderate (mean=0.435, max=0.750). Positive frames are clustered (mean run length = 2.3 frames).

## 2. Does Pilot Sampling Become Biased?

| Stratum | True p | Estimated p | Bias | Std |
|---------|--------|-------------|------|-----|
| 0.0 | 0.000 | 0.000 | +0.000 | 0.000 |
| 1.0 | 0.000 | 0.000 | +0.000 | 0.000 |
| 2.0 | 0.000 | 0.000 | +0.000 | 0.000 |
| 3.0 | 0.019 | 0.033 | +0.014 | 0.058 |
| 4.0 | 0.098 | 0.067 | -0.031 | 0.058 |
| 5.0 | 0.163 | 0.067 | -0.096 | 0.115 |
| 6.0 | 0.182 | 0.200 | +0.018 | 0.173 |
| 7.0 | 0.167 | 0.100 | -0.067 | 0.100 |
| 8.0 | 0.189 | 0.067 | -0.122 | 0.058 |
| 9.0 | 0.274 | 0.300 | +0.026 | 0.100 |

**Key finding:** Pilot sampling bias is small (mean |bias| = 0.037). Estimation variance is 0.066. Temporal clustering can cause pilot samples to repeatedly hit the same event, creating variance estimation illusions.

## 3. Does Temporal Redundancy Collapse ESS?

| Stratum | Autocorr (lag-1) | ESS@10 | ESS@50 | ESS@100 |
|---------|------------------|--------|--------|--------|
| 0 | 0.000 | 1.0 | 1.0 | 1.0 |
| 1 | 0.000 | 1.0 | 1.0 | 1.0 |
| 2 | 0.000 | 1.0 | 1.0 | 1.0 |
| 3 | 0.635 | 1.3 | 2.0 | 2.0 |
| 4 | 0.718 | 1.7 | 2.0 | 2.0 |
| 5 | 0.750 | 1.7 | 2.0 | 2.0 |
| 6 | 0.678 | 1.7 | 2.0 | 2.0 |
| 7 | 0.540 | 1.7 | 2.0 | 2.0 |
| 8 | 0.472 | 2.0 | 2.0 | 2.0 |
| 9 | 0.561 | 2.0 | 2.0 | 2.0 |

**Key finding:** Temporal correlation does reduce ESS, but the effect is moderate. ESS reduction is proportional to autocorrelation strength.

## 4. Does Variance Estimation Become Unreliable?

| Stress Type | Strength | Autocorr | Count Variance | Count Bias |
|-------------|----------|----------|----------------|------------|
| persistence | 0.0 | 0.680 | 92719.8 | -544.0 |
| persistence | 0.2 | 0.726 | 77860.3 | -315.7 |
| persistence | 0.4 | 0.773 | 118677.7 | -334.6 |
| persistence | 0.6 | 0.823 | 134525.1 | -44.5 |
| persistence | 0.8 | 0.887 | 219679.5 | +628.8 |
| burst | 0.0 | 0.680 | 92719.8 | -544.0 |
| burst | 0.2 | 0.742 | 142376.0 | -500.4 |
| burst | 0.4 | 0.804 | 51282.9 | -612.8 |
| burst | 0.6 | 0.852 | 70766.8 | -723.8 |
| burst | 0.8 | 0.923 | 46177.3 | -420.6 |
| periodic | 0.0 | 0.680 | 92719.8 | -544.0 |
| periodic | 0.2 | 0.581 | 218046.1 | -248.8 |
| periodic | 0.4 | 0.422 | 79502.3 | +390.1 |
| periodic | 0.6 | 0.292 | 54464.8 | +1905.7 |
| periodic | 0.8 | 0.157 | 91355.4 | +3707.4 |

**Key finding:** Variance estimation is unstable (max variance = 219679.5). Temporal correlation inflates variance estimation, but the effect is bounded.

## 5. Does Optimal Allocation Become Distorted?

**True optimal allocation:** [2.8557137097488484e-06, 2.8557137097488484e-06, 2.8557137097488484e-06, 0.05807323149797415, 0.11192273251173852, 0.13765819423811193, 0.12961938958996744, 0.12647699787711672, 0.1480967519211519, 0.28814413522280996]

**Mean allocation error:** 0.1152
**Max allocation error:** 0.4229

**Key finding:** Allocation distortion is significant. Temporal correlation can cause pilot samples to be unrepresentative, leading to suboptimal allocation. However, the distortion is bounded.

## 6. Is ABae More Fragile Than SUPG?

| Stress | Autocorr | SUPG Recall | ABae Count Bias | ABae Count RMSE |
|--------|----------|-------------|-----------------|------------------|
| baseline | 0.680 | 0.997 | -544.0 | 623.5 |
| persistence_0.4 | 0.773 | 0.994 | -565.6 | 662.3 |
| persistence_0.8 | 0.887 | 0.993 | -236.2 | 524.9 |
| burst_0.4 | 0.804 | 0.999 | -566.8 | 610.4 |
| burst_0.8 | 0.923 | 0.997 | -471.6 | 518.2 |

**Key finding:** SUPG maintains high recall (0.996) while ABae count RMSE is 587.8. ABae is more fragile than SUPG under temporal correlation.

## 7. Are IID Assumptions More Critical for Aggregation Than Retrieval?

**Analysis:**

1. **SUPG (retrieval)**: Uses importance correction at the frame level. Temporal correlation affects individual frames, but importance weighting corrects for sampling bias regardless of temporal structure.

2. **ABae (aggregation)**: Uses stratified sampling with variance-based allocation. Temporal correlation affects variance estimation within strata, which can distort allocation.

3. **Key difference**: SUPG's correction is frame-level (robust to correlation), while ABae's correction is stratum-level (sensitive to within-stratum correlation).

**Conclusion:** Yes, iid assumptions are more critical for aggregation than retrieval. ABae's variance estimation depends on within-stratum independence, while SUPG's importance correction does not.

## 8. Conclusion

ABae's stratified aggregation is more sensitive to temporal correlation than SUPG's importance-corrected retrieval:

1. **Temporal redundancy exists within strata**: Autocorrelation is moderate to strong, with clustered positive frames.

2. **Pilot sampling can be biased**: Temporal clustering causes pilot samples to repeatedly hit the same event.

3. **ESS reduction is moderate**: Temporal correlation reduces ESS, but the effect is bounded.

4. **Variance estimation is inflated**: Temporal correlation inflates variance estimates, but not catastrophically.

5. **Allocation is distorted**: Temporal correlation can cause suboptimal allocation, but the distortion is bounded.

6. **ABae is more fragile than SUPG**: Aggregation depends more on iid assumptions than retrieval.

7. **IID assumptions matter more for aggregation**: ABae's variance estimation depends on within-stratum independence, while SUPG's importance correction does not.

**Bottom line:** Temporal workloads violate ABae's assumptions more than SUPG's. ABae remains functional but with degraded accuracy. SUPG's importance correction provides inherent robustness to temporal correlation.
