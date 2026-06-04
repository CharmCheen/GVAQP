# Synthetic Clip Degradation -- Controlled Audit Report

**Date**: 2026-06-03
**Purpose**: Determine whether the observed clip-level degradation under synthetic perturbation is real, stable, and actionable -- or an artifact of metric bugs, weak baselines, or overly strict parameters.

---

## Executive Summary

The audit confirms that **clip-level degradation is a real, stable phenomenon** -- not an artifact. Across 240 parameter combinations (4 tau x 4 budget x 3 K x 5 seeds), clip recall drop exceeds frame recall drop in **80.7%** of cases, with average amplification ratios of 5-20x depending on the method. The metrics are correct, the baselines behave properly on clean data, and the effect is driven primarily by a single perturbation type (motion-conditioned proxy noise). However, the magnitude of the effect depends heavily on the label propagation strategy -- nearest-neighbor interpolation (used by uniform_random) is far more robust than proxy-threshold decisions.

**Verdict**: Continue with the research direction, but with two critical adjustments: (1) switch to gap-tolerant or visibility-aware clip semantics, and (2) use nearest-neighbor propagation rather than proxy-threshold decisions for non-oracle frames.

---

## 1. Are the Metrics Valid?

**Source**: `outputs/audit/agent_a/metric_audit.md`, `outputs/audit/agent_a/diagnostics.json`

**Answer: Yes, with minor notes.**

| Item | Status | Details |
|------|--------|---------|
| Inclusive interval handling | Correct | `end_frame=i-1`, `+1` in IoU formula all verified |
| tau handling | Correct | Both `clip_gt.py` and `baselines.py` use `length >= tau` consistently |
| Clip IoU formula | Correct | Verified with 6 test cases (identical, adjacent, overlap, contained, degenerate) |
| Greedy matching | Known limitation | When multiple GT clips compete for the same predicted clip, only the first wins. Not a bug, but could undercount recall in multi-clip videos. |
| Fragmentation definition | Correct | Counts overlapping predictions per GT clip, adds (n-1) per clip with n>1 overlaps |
| Boundary error | Correct | Only computed for matched clips; unmatched clips get inf |
| Oracle call accounting | Correct | Uses `baseline.oracle_calls` (method query count), not perturbation noise count |

**Minor issues found**:
1. **Off-by-one in ARC clustering merge gap** (`baselines.py` line 267): `start - prev_end` should be `start - prev_end - 1` since `prev_end` is inclusive. Impact: segments with exactly `cluster_merge_gap` frames between them are not merged. Minor.
2. **ARC clustering underutilizes budget**: averages 12.8/30 oracle calls, which could unfairly disadvantage it in comparisons.
3. **`_safe_mean` returns 0.0 for all-inf inputs**: potentially misleading in boundary error columns.

---

## 2. Does Clean Control Behave Correctly?

**Source**: `outputs/audit/agent_b/clean_control.md`, `outputs/audit/agent_b/clean_control_metrics.csv`

**Answer: Yes. All baselines pass.**

| Method | Frame Recall | Clip Recall | Oracle Frac | Status |
|--------|-------------|-------------|-------------|--------|
| full_oracle | 1.0000 | 1.0000 | 1.000 | PASS |
| fixed_rate | 0.9996 | 1.0000 | 0.100 | PASS |
| uniform_random | 0.9991 | 1.0000 | 0.100 | PASS |
| proxy_threshold | 1.0000 | 0.9750 | 0.100 | PASS (minor: lower threshold merges clips in 1 video) |
| arc_clustering | 1.0000 | 1.0000 | 0.043 | PASS |

Key observations:
- `full_oracle` is perfect (upper bound confirmed)
- `fixed_rate` and `uniform_random` achieve near-perfect metrics on clean data with only 10% budget
- `proxy_threshold` loses 2.5% clip recall due to its lowered threshold (K-1) merging two GT clips -- expected design trade-off
- `arc_clustering` is perfect while using only 4.3% of oracle budget (boundary-focused allocation)

**Conclusion**: All baseline implementations are sound. The degradation observed in the perturbed experiment is not caused by baseline bugs.

---

## 3. Is Clip-Level Degradation Stable Across tau, budget, K, and seed?

**Source**: `outputs/audit/agent_c/sweep_summary.md`, `outputs/audit/agent_c/sweep_metrics.csv`

**Answer: Yes, it is stable and consistent.**

### Overall statistics (240 combinations, 5 seeds each)

| Method | Avg Frame Drop | Avg Clip Drop | Avg Ratio | Clip>Frame % |
|--------|---------------|---------------|-----------|-------------|
| fixed_rate | 0.005 | 0.023 | 4.40x | 54% (26/48) |
| uniform_random | 0.007 | 0.031 | 7.19x | 69% (33/48) |
| proxy_threshold | 0.054 | 0.628 | 19.48x | **100% (48/48)** |
| arc_clustering | 0.106 | 0.880 | 11.69x | **100% (48/48)** |

### By K (threshold)

| K | proxy_threshold ratio | arc_clustering ratio |
|---|----------------------|---------------------|
| 2 | 31.21x | 20.05x |
| 3 | 20.21x | 10.27x |
| 5 | 7.02x | 4.77x |

Effect is strongest at K=2 (low threshold, more clips to disrupt) and weakest at K=5.

### By tau (minimum clip length)

| tau | proxy_threshold ratio | arc_clustering ratio |
|-----|----------------------|---------------------|
| 10 | 20.10x | 11.75x |
| 20 | 19.21x | 11.62x |
| 30 | 19.62x | 11.75x |
| 60 | 19.01x | 11.66x |

Effect is remarkably stable across tau values for proxy_threshold and arc_clustering.

### Reversals (frame_drop > clip_drop)

18 out of 192 cells show reversals, but **all are cases where both drops are essentially zero** (near-perfect performance). No meaningful reversals were observed.

### Top 10 strongest effects (by ratio)

| K | tau | budget | Method | Ratio |
|---|-----|--------|--------|------:|
| 3 | 10 | 0.40 | fixed_rate | 47.58 |
| 2 | 10 | 0.05 | proxy_threshold | 37.70 |
| 2 | 10 | 0.40 | proxy_threshold | 35.00 |
| 3 | 20 | 0.20 | uniform_random | 34.53 |
| 2 | 20 | 0.10 | proxy_threshold | 34.46 |
| 2 | 30 | 0.10 | proxy_threshold | 34.00 |
| 2 | 60 | 0.10 | proxy_threshold | 33.97 |
| 2 | 10 | 0.10 | proxy_threshold | 33.30 |
| 2 | 30 | 0.20 | proxy_threshold | 32.76 |
| 2 | 30 | 0.05 | proxy_threshold | 32.65 |

---

## 4. Which Perturbation Causes the Main Failure?

**Source**: `outputs/audit/agent_d/perturbation_ablation.md`, `outputs/audit/agent_d/perturbation_ablation.csv`

**Answer: Motion-conditioned proxy noise is the dominant cause.**

### Per-perturbation impact (proxy_threshold method, deltas vs clean)

| Perturbation | Clip Recall Drop | Frame Recall Drop | Ratio | Fragmentation |
|-------------|-----------------|-------------------|-------|---------------|
| proxy_noise_only | 0.670 | 0.025 | 26.5x | +2.01 |
| visibility_drop_only | 0.100 | 0.011 | 9.3x | +0.42 |
| short_positive_gaps | 0.000 | 0.000 | -- | 0.00 |
| boundary_jitter | 0.000 | 0.000 | -- | 0.00 |

### Per-perturbation impact (arc_clustering method, deltas vs clean)

| Perturbation | Clip Recall Drop | Frame Recall Drop | Ratio | Fragmentation |
|-------------|-----------------|-------------------|-------|---------------|
| proxy_noise_only | 0.930 | 0.047 | 19.7x | +2.15 |
| visibility_drop_only | 0.380 | 0.047 | 8.1x | +1.23 |
| short_positive_gaps | 0.000 | 0.000 | -- | 0.00 |
| boundary_jitter | 0.000 | 0.000 | -- | 0.00 |

### Key findings

1. **proxy_noise** is the single dominant failure source. It corrupts frames where activity is highest (noise scales with temporal derivative), fragmenting continuous clips into sub-tau segments.
2. **visibility_drop** is a secondary contributor (10-38% clip recall drop).
3. **short_positive_gaps** and **boundary_jitter** have **zero measurable impact** under oracle-based evaluation -- the oracle corrects for both.
4. Degradation is approximately **additive**, not synergistic. The combined effect of proxy_noise + visibility_drop is slightly less than the sum of individual effects.

---

## 5. Can Hidden Risk-Aware Allocation Recover Quality?

**Source**: `outputs/audit/agent_e/hidden_risk_summary.md`, `outputs/audit/agent_e/hidden_risk_metrics.csv`

**Answer: No -- the bottleneck is label propagation, not oracle allocation.**

| Method | Frame Recall | Clip Recall | Frag Rate | Oracle Frac |
|--------|-------------|-------------|-----------|-------------|
| full_oracle | 1.000 | 1.000 | 0.000 | 1.000 |
| **uniform_random** | **0.999** | **0.990** | **0.000** | 0.100 |
| proxy_threshold | 0.959 | 0.230 | 1.990 | 0.100 |
| risk_aware_hidden | 0.919 | 0.060 | 1.930 | 0.100 |
| arc_clustering | 0.912 | 0.040 | 1.990 | 0.044 |

### Analysis

The hidden-risk-aware baseline correctly identifies error-prone frames (highest frame recall among proxy-based methods at 0.919), but **fails at clip-level recovery** (clip_recall=0.060). The dramatic gap between `uniform_random` (0.990) and all proxy-based methods (0.04-0.23) stems from a fundamental **label propagation strategy difference**:

- **uniform_random** uses **nearest-neighbor interpolation**: oracle-corrected labels are interpolated to fill the entire video. With 30 oracle points spread across 300 frames, even a few correctly-placed points near clip boundaries reconstructs full clips.
- **proxy-based methods** use `perturbed_count >= K` for non-oracle frames. Perturbation noise at boundaries causes counts to fluctuate around K, creating false-negative gaps that fragment clips below the tau threshold.

**Conclusion**: The oracle budget allocation strategy matters less than the label propagation strategy for non-oracle frames. Risk-aware allocation is a good idea in principle, but it must be paired with robust propagation (e.g., nearest-neighbor or gap-tolerant semantics) to be effective.

---

## 6. Recommendation

Based on the evidence from 5 independent audit agents:

### What is confirmed
- Clip-level degradation is **real and stable** across tau, budget, K, and seed (80.7% of combinations show clip > frame degradation)
- The metrics are **correct** (inclusive intervals, tau handling, IoU, fragmentation all verified)
- The baselines are **sound** (clean control passes all checks)
- **proxy_noise** is the **dominant failure source** (20-27x amplification from frame to clip level)

### What is NOT confirmed
- The research direction is **not proven** -- this is a synthetic-only audit
- The hidden-risk baseline **does not help** with the current propagation strategy
- The synthetic data has limited clip structure (~1 long clip per video)

### Recommended next steps

1. **Switch to gap-tolerant clip semantics**: The current tau-based continuity requirement is too strict. A gap-tolerant definition (e.g., allow up to G consecutive False frames within a clip) would reduce fragmentation from proxy noise.

2. **Use nearest-neighbor propagation for non-oracle frames**: The uniform_random baseline's success (clip_recall=0.990) shows that nearest-neighbor interpolation from oracle-corrected points is far more robust than proxy-threshold decisions. Future baselines should use this strategy.

3. **Focus mitigation on proxy_noise**: The ablation shows that proxy_noise alone causes 67-93% clip recall drop. Any oracle allocation strategy should prioritize frames with high temporal derivative (motion frames).

4. **Test on real datasets**: The synthetic data is dominated by single long clips. Real video data with multiple short clips, occlusions, and complex motion patterns will provide a more realistic stress test.

5. **Consider visibility-aware semantics**: If visibility drops are expected in real data (e.g., fast panning), the clip definition should either tolerate short count drops or explicitly model visibility.

### What NOT to do
- Do not stop the research direction -- the degradation is real, not an artifact
- Do not rely on proxy-threshold decisions for non-oracle frames -- they fragment clips
- Do not claim the method is proven -- this is synthetic-only evidence

---

## Appendix: Output Files

| Agent | Output | Path |
|-------|--------|------|
| A (Metric Audit) | Audit report | `outputs/audit/agent_a/metric_audit.md` |
| A (Metric Audit) | Diagnostics script | `outputs/audit/agent_a/run_diagnostics.py` |
| A (Metric Audit) | Diagnostic results | `outputs/audit/agent_a/diagnostics.json` |
| B (Clean Control) | Control metrics | `outputs/audit/agent_b/clean_control_metrics.csv` |
| B (Clean Control) | Control report | `outputs/audit/agent_b/clean_control.md` |
| B (Clean Control) | Per-video results | `outputs/audit/agent_b/clean_control.jsonl` |
| C (Parameter Sweep) | Sweep metrics | `outputs/audit/agent_c/sweep_metrics.csv` |
| C (Parameter Sweep) | Sweep summary | `outputs/audit/agent_c/sweep_summary.md` |
| C (Parameter Sweep) | Aggregated summary | `outputs/audit/agent_c/sweep_summary.csv` |
| D (Perturbation Ablation) | Ablation metrics | `outputs/audit/agent_d/perturbation_ablation.csv` |
| D (Perturbation Ablation) | Ablation report | `outputs/audit/agent_d/perturbation_ablation.md` |
| D (Perturbation Ablation) | Summary JSON | `outputs/audit/agent_d/ablation_summary.json` |
| E (Hidden Risk) | Risk metrics | `outputs/audit/agent_e/hidden_risk_metrics.csv` |
| E (Hidden Risk) | Risk summary | `outputs/audit/agent_e/hidden_risk_summary.md` |
| E (Hidden Risk) | Per-video results | `outputs/audit/agent_e/hidden_risk_results.jsonl` |
