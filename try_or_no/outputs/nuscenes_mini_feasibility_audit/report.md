# Sanity Audit Report

## 1. Why was naive_oracle ClipF1 only 0.808?

**Aggregation bug.** The `aggregate_metrics` function averaged clip metrics over ALL instances, including 166 instances that had no GT clips. For these instances, `evaluate_instance` returned clip_f1=0, which dragged the mean down.

For `within_30m, tau=3`:
- 699 instances have GT clips → naive_oracle clip_f1 = 1.0000
- 166 instances have NO GT clips → clip_f1 = 0.0000 (incorrectly penalized)
- 46 instances skipped (n < tau)
- Mean over all: 699/865 × 1.0 + 166/865 × 0.0 = 0.808

## 2. Was it a metric bug, filtering mismatch, clip construction mismatch, or expected behavior?

**Metric bug in aggregation.** Specifically:

- **Clip construction**: Correct. GT clips and naive clips are 100% identical (verified: 0 mismatches across all queries and tau values).
- **Filtering**: Correct. Both use the same data, same instance grouping, same ordering, same label column, same tau.
- **IoU matching**: Correct. For instances with clips, naive_oracle predicted clips exactly match GT clips with IoU=1.0.
- **Aggregation**: **BUG.** Instances with 0 GT clips + 0 predicted clips returned clip_f1=0 instead of 1.0. A method that correctly predicts "no clips" when there are no clips should score perfectly.

## 3. After fixing, what is the corrected naive_oracle score?

**naive_oracle ClipF1 = 1.0000** for all queries and all tau values.

Fix: In `evaluate_instance`, when both GT clips and predicted clips are empty, return clip_f1=1.0 instead of 0.0.

Corrected results (averaged over 5 seeds):

| Query | tau | naive_oracle ClipF1 | fixed_rate_k2 | fixed_rate_k5 | fixed_rate_k10 | linear_interp |
|-------|-----|---------------------|---------------|---------------|----------------|---------------|
| in_fov | 2 | 1.000 | 0.960 | 0.950 | 0.856 | 0.947 |
| in_fov | 3 | 1.000 | 0.999 | 0.901 | 0.850 | 0.921 |
| in_fov | 5 | 1.000 | 0.997 | 0.806 | 0.784 | 0.902 |
| within_30m | 2 | 1.000 | 0.989 | 0.941 | 0.807 | 0.976 |
| within_30m | 3 | 1.000 | 0.990 | 0.936 | 0.810 | 0.973 |
| within_30m | 5 | 1.000 | 0.987 | 0.924 | 0.828 | 0.950 |
| ego_front | 2 | 1.000 | 0.989 | 0.966 | 0.879 | 0.962 |
| ego_front | 3 | 1.000 | 0.992 | 0.953 | 0.880 | 0.948 |
| ego_front | 5 | 1.000 | 0.998 | 0.923 | 0.872 | 0.934 |

## 4. Are previous baseline results still valid?

**No.** The previous baseline results from `build_clips_and_baselines_v2.py` had the same aggregation bug. All methods were equally affected (they all got 0 for instances with no clips), so the *relative* ranking was approximately correct, but the absolute numbers were wrong.

The corrected results in `recomputed_baseline_metrics.csv` are valid.

## 5. Can we now proceed to implement query-impact-aware triggering?

**Yes.** The evaluation is now correct:

- naive_oracle = 1.0 (verified)
- Baselines show meaningful degradation with sparser oracle (fixed_rate_k10: 0.81-0.88)
- The data pipeline (query table → clips → evaluation) is consistent
- The task is non-trivial: even fixed_rate_k2 (51% oracle) drops to 0.96-0.99

## Summary

| Question | Answer |
|----------|--------|
| Why was naive_oracle ClipF1 only 0.808? | Aggregation bug: instances with 0 clips penalized as 0 instead of 1.0 |
| What was it? | Metric bug in aggregation (not filtering, not clip construction) |
| Corrected naive_oracle score | **1.0000** for all queries and tau |
| Previous results valid? | No — recomputed with fix |
| Can we proceed? | **Yes** |
