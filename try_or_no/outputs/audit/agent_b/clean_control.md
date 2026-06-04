# Clean Control Experiment Report

## Setup

- **Dataset**: 20 synthetic videos, seed=42, 300 frames each
- **Query**: K=3 (min vehicle count), tau=30 (min clip length in frames)
- **Perturbation**: Identity (all noise parameters set to 0.0)
- **Budget**: 0.1 (10% of frames) for non-oracle baselines

## Method Summary (mean across 20 videos)

| Method | Frame Recall | Frame Prec | Clip Recall | Clip Prec | Mean IoU | Frag Rate | Oracle Frac |
|--------|-------------|------------|-------------|-----------|----------|-----------|-------------|
| full_oracle | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 1.0000 |
| fixed_rate | 0.9996 | 0.9996 | 1.0000 | 1.0000 | 0.9994 | 0.0000 | 0.1000 |
| uniform_random | 0.9991 | 0.9974 | 1.0000 | 1.0000 | 0.9970 | 0.0000 | 0.1000 |
| proxy_threshold | 1.0000 | 0.9896 | 0.9750 | 1.0000 | 0.9679 | 0.0000 | 0.1000 |
| arc_clustering | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0430 |

## Analysis by Method

### full_oracle (PASS)

- frame_recall = 1.0000, clip_recall = 1.0000
- The upper-bound baseline correctly recovers all ground truth. It queries every frame (oracle_fraction=1.0) and uses the original labels directly. This confirms the ground truth construction and metric computation are correct.

### fixed_rate (PASS)

- frame_recall = 0.9996, clip_recall = 1.0000
- With a 10% budget (every 10th frame sampled), frame recall is very high on clean data. Forward-fill propagation works well because the label structure is smooth (activity bursts span many consecutive frames). The small frame_recall loss (0.04%) occurs at label transition boundaries where the sampled frame may not exactly align with the boundary.

### uniform_random (PASS)

- frame_recall = 0.9991, clip_recall = 1.0000
- Random sampling with 10% budget performs comparably to fixed-rate. Nearest-neighbor fill on clean data preserves most label structure. Slightly lower precision (0.9974 vs 0.9996) is expected since random sampling can miss tight boundaries more often than uniform stride.

### proxy_threshold (PASS with note)

- frame_recall = 1.0000, clip_recall = 0.9750
- On clean data, the perturbed proxy is identical to the original counts, so the proxy label (count >= K-1) matches the true label (count >= K) for most frames. The small clip_recall loss (2.5%) comes from 1 video (synthetic_006) where the proxy threshold baseline merged two ground-truth clips into one predicted clip, reducing clip_recall to 0.5 for that video. This is expected behavior: the lower threshold (K-1) can merge nearby segments. This is a design trade-off favoring recall at the cost of precision, not a bug.

### arc_clustering (PASS)

- frame_recall = 1.0000, clip_recall = 1.0000
- This baseline uses proxy-based clustering with boundary refinement. On clean data, proxy labels perfectly match true labels, so candidate segments are exact. The boundary refinement oracle budget (fraction of 10%) is sufficient to confirm boundaries. Oracle fraction is only 0.043 (4.3%), demonstrating the method's efficiency: it focuses budget on segment boundaries rather than querying all frames.

## Anomalies Found

No significant anomalies. All methods behave correctly:

1. No perturbation artifacts: The identity perturbation was verified -- perturbed_counts equal original_counts and perturbed_labels equal original_labels for all 20 videos (0 oracle calls from perturbation).

2. Minor expected variance: Videos synthetic_005 and synthetic_006 show slightly lower metrics for proxy_threshold due to its lower threshold (K-1) causing segment merging. This is an expected property of the algorithm, not a defect.

3. Budget compliance: All budgeted baselines correctly use approximately 10% of frames as oracle calls. arc_clustering uses less (4.3%) because it only spends budget on boundary refinement.

## Conclusion

**All baseline implementations are sound.** The clean control experiment confirms:

- The ground truth pipeline (synthetic generation, clip construction, metric computation) works correctly.
- The full_oracle upper bound is perfect as expected.
- Budget-constrained baselines (fixed_rate, uniform_random) achieve near-perfect performance on clean data with 10% budget, validating their forward-fill/nearest-neighbor propagation logic.
- Proxy-based baselines (proxy_threshold, arc_clustering) achieve near-perfect performance on clean data where proxy equals ground truth.
- The pipeline is ready for perturbation experiments. Any degradation observed under perturbation can be attributed to the perturbation itself, not baseline defects.
