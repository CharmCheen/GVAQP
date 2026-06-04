# Perturbation Ablation Study

## Configuration

- **Videos**: 50 synthetic sequences (seed=42)
- **Frames per video**: 300
- **K (min vehicles)**: 3
- **tau (min clip length)**: 30 frames
- **Oracle budget**: 10% (30 frames per video)
- **Perturbation configs tested**: clean, proxy_noise_only, short_positive_gaps_only, boundary_jitter_only, visibility_drop_only, all_perturbations
- **Baseline methods**: full_oracle, fixed_rate, uniform_random, proxy_threshold, arc_clustering

## Method Behavior Summary

The `full_oracle`, `fixed_rate`, and `uniform_random` methods query the ground-truth oracle directly (they read `original_labels`, not `perturbed_labels`). These methods are therefore invariant to perturbation type, which is confirmed by the data: all three show identical metrics across every ablation config. The interesting degradation occurs in `proxy_threshold` and `arc_clustering`, which operate on the perturbed proxy signals.

## Per-Perturbation Impact Table

The table below shows metrics for the two affected methods. All values are means over 50 videos.

### proxy_threshold method

| Perturbation Config   | Frame Recall | Clip Recall | mIoU   | Frag Rate | Start Err | End Err |
|-----------------------|-------------|-------------|--------|-----------|-----------|---------|
| clean                 | 1.000       | 0.980       | 0.980  | 0.00      | 0.0       | 5.7     |
| proxy_noise_only      | 0.975       | 0.310       | 0.239  | 2.01      | 23.4      | 46.5    |
| short_positive_gaps   | 1.000       | 0.980       | 0.980  | 0.00      | 0.0       | 5.7     |
| boundary_jitter_only  | 1.000       | 0.980       | 0.980  | 0.00      | 0.0       | 5.7     |
| visibility_drop_only  | 0.989       | 0.880       | 0.820  | 0.42      | 1.0       | 24.4    |
| all_perturbations     | 0.959       | 0.230       | 0.159  | 1.99      | 17.5      | 76.0    |

### arc_clustering method

| Perturbation Config   | Frame Recall | Clip Recall | mIoU   | Frag Rate | Start Err | End Err |
|-----------------------|-------------|-------------|--------|-----------|-----------|---------|
| clean                 | 1.000       | 1.000       | 1.000  | 0.00      | 0.0       | 0.0     |
| proxy_noise_only      | 0.953       | 0.070       | 0.060  | 2.15      | 14.0      | 37.8    |
| short_positive_gaps   | 1.000       | 1.000       | 1.000  | 0.00      | 0.0       | 0.0     |
| boundary_jitter_only  | 1.000       | 1.000       | 1.000  | 0.00      | 0.0       | 0.0     |
| visibility_drop_only  | 0.953       | 0.620       | 0.493  | 1.23      | 29.4      | 29.6    |
| all_perturbations     | 0.912       | 0.040       | 0.031  | 1.99      | 11.5      | 26.5    |

## Deltas Relative to Clean Baseline

### proxy_threshold

| Perturbation Config   | Clip Recall Drop | Frame Recall Drop | mIoU Drop | Frag Increase | Clip/Frame Drop Ratio |
|-----------------------|-----------------|-------------------|-----------|---------------|----------------------|
| proxy_noise_only      | 0.670           | 0.025             | 0.742     | 2.01          | 26.5x                |
| short_positive_gaps   | 0.000           | 0.000             | 0.000     | 0.00          | --                   |
| boundary_jitter_only  | 0.000           | 0.000             | 0.000     | 0.00          | --                   |
| visibility_drop_only  | 0.100           | 0.011             | 0.161     | 0.42          | 9.3x                 |
| all_perturbations     | 0.750           | 0.041             | 0.822     | 1.99          | 18.4x                |

### arc_clustering

| Perturbation Config   | Clip Recall Drop | Frame Recall Drop | mIoU Drop | Frag Increase | Clip/Frame Drop Ratio |
|-----------------------|-----------------|-------------------|-----------|---------------|----------------------|
| proxy_noise_only      | 0.930           | 0.047             | 0.940     | 2.15          | 19.7x                |
| short_positive_gaps   | 0.000           | 0.000             | 0.000     | 0.00          | --                   |
| boundary_jitter_only  | 0.000           | 0.000             | 0.000     | 0.00          | --                   |
| visibility_drop_only  | 0.380           | 0.047             | 0.507     | 1.23          | 8.1x                 |
| all_perturbations     | 0.960           | 0.088             | 0.969     | 1.99          | 10.9x                |

## Analysis: Which Perturbation Causes the Largest Degradation?

### 1. Largest clip-level degradation: proxy_noise

**Motion-conditioned proxy noise** is by far the dominant source of clip-level failure. For both `proxy_threshold` and `arc_clustering`, it produces:

- **proxy_threshold**: clip_recall drops from 0.98 to 0.31 (drop = 0.67), fragmentation jumps from 0 to 2.01
- **arc_clustering**: clip_recall drops from 1.00 to 0.07 (drop = 0.93), fragmentation jumps from 0 to 2.15

This perturbation adds Gaussian noise scaled by the local temporal derivative (motion proxy). The noise magnitude is proportional to frame-to-frame count changes, meaning it corrupts the very frames where activity is highest -- precisely the frames that matter most for clip detection. The result is that the proxy threshold is crossed in the wrong direction at critical moments, fragmenting what should be continuous clips into many short segments.

### 2. Largest frame-vs-clip gap: proxy_noise

The clip-to-frame drop ratio for proxy_noise is extremely high:

- **proxy_threshold**: 26.5x (clip_recall_drop=0.67 vs frame_recall_drop=0.025)
- **arc_clustering**: 19.7x (clip_recall_drop=0.93 vs frame_recall_drop=0.047)

A 2.5% frame-level error cascades into a 67-93% clip-level failure. This confirms the core hypothesis: perturbation compounds disproportionately at the clip level. The mechanism is clear -- even a small fraction of misclassified frames, when they occur within otherwise positive runs, is enough to break the continuity requirement (tau=30) and fragment or destroy clips entirely.

### 3. Secondary contributor: visibility_drop

Visibility drops cause moderate degradation:

- **proxy_threshold**: clip_recall drops by 0.10 (to 0.88), fragmentation increases by 0.42
- **arc_clustering**: clip_recall drops by 0.38 (to 0.62), fragmentation increases by 1.23

Visibility drops reduce vehicle counts by 70% (scale=0.3) for 10-frame segments. This pushes counts below the K=3 threshold in frames that are genuinely active, creating false-negative gaps. For arc_clustering the impact is notably larger than for proxy_threshold, because arc_clustering relies entirely on the proxy to identify candidate segments -- if the proxy count drops below K, the segment is never proposed as a candidate at all.

### 4. Zero-impact perturbations: short_positive_gaps and boundary_jitter

Both `short_positive_gaps` and `boundary_jitter` produce **zero measurable degradation** against the clean baseline for every method tested. This is because:

- **short_positive_gaps**: Operates in label space (flipping True to False for 1-5 frames). The proxy_threshold method uses count-based thresholds, not label gaps, so it is unaffected. The arc_clustering method also uses count thresholds for candidate detection and then queries the oracle for boundary refinement -- the oracle is always correct.
- **boundary_jitter**: Requires `boundary_clips` to be passed in and only modifies labels near clip boundaries. The perturbation effect is small (jitter_std=3 frames on boundaries that are already imprecise in the proxy), and the oracle-based methods correct for it.

In a real system where the oracle is not available (i.e., where methods must use perturbed labels as ground truth), these perturbations would likely matter more. But under the current experimental setup where the oracle is queried for sampled frames, they are harmless.

## Single vs. Multiple Perturbation Interaction

The `all_perturbations` config (default PerturbationConfig) shows degradation that is approximately additive with respect to the two active perturbations (proxy_noise and visibility_drop):

| Method          | proxy_noise drop | visibility_drop drop | Sum   | all_perturbations drop |
|-----------------|-----------------|---------------------|-------|----------------------|
| proxy_threshold | 0.670           | 0.100               | 0.770 | 0.750                |
| arc_clustering  | 0.930           | 0.380               | 1.310 | 0.960 (capped at 1)  |

For `proxy_threshold`, the combined drop (0.75) is slightly less than the sum of individual drops (0.77), suggesting mild negative interaction -- the visibility drop sometimes shifts counts in the same direction as noise, so they do not fully compound.

For `arc_clustering`, the sum exceeds 1.0 but the actual drop is capped at 0.96, indicating near-total failure from the combination. The interaction here is that visibility drops create false-negative gaps that, combined with proxy noise, make it nearly impossible for the clustering algorithm to form correct candidate segments.

**Conclusion**: The degradation is primarily driven by a single perturbation type (proxy_noise), with a secondary contribution from visibility_drop. There is no evidence of strong synergistic interaction between perturbation types -- the combined effect is approximately additive. The two zero-impact perturbations (short_positive_gaps, boundary_jitter) contribute nothing to degradation under the current oracle-based evaluation framework.

## Key Takeaway

**Motion-conditioned proxy noise (proxy_noise_std=1.5) is the single perturbation responsible for nearly all clip-level degradation.** It causes a 2.5-4.7% frame-level error that cascades into 67-93% clip-level failure -- a 20-27x amplification factor. Any mitigation strategy should focus on this perturbation type first. The second priority is visibility drops (drop_prob=0.02), which cause a more modest but still meaningful 10-38% clip recall drop.
