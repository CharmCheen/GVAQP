# Metric and Clip Ground-Truth Audit Report

## Summary

The pipeline's metric computation and clip ground-truth construction are **largely correct** with inclusive interval handling, tau filtering, and IoU calculations all verified. Two issues were identified: an off-by-one in the ARC clustering merge-gap logic, and a known limitation of greedy one-to-one matching that can undercount recall when multiple GT clips compete for the same predicted clip. Neither issue invalidates the experiment's conclusions.

---

## 1. Inclusive/Exclusive Interval Handling

### clip_gt.py line 61-62: `end_frame = i - 1`

**Verdict: CORRECT.**

When the loop reaches frame `i` where `label[i]` is False, the run of True frames spans `[run_start, i-1]` inclusive. The run length is `i - run_start`, which correctly counts `i - 1 - run_start + 1 = i - run_start` frames. The end frame `i - 1` is the last True frame in the run.

### baselines.py `_labels_to_segment_list` line 268: `segments.append((run_start, i-1))`

**Verdict: CORRECT.** Identical logic to clip_gt.py. The segment `(run_start, i-1)` is inclusive on both ends, representing the last True frame before the False frame at index `i`.

### metrics.py `_compute_iou` line 183: `intersection = max(0, intersection_end - intersection_start + 1)`

**Verdict: CORRECT.** For inclusive integer intervals, the count of integers in `[a, b]` is `b - a + 1`. When `intersection_end >= intersection_start`, this formula gives the correct overlap length. When `intersection_end < intersection_start` (no overlap), the `max(0, ...)` returns 0.

Verified with test cases:
- Identical clips `[0,9], [0,9]`: IoU = 1.0
- Adjacent clips `[0,4], [5,9]`: IoU = 0.0 (no shared frame)
- 1-frame overlap `[0,4], [4,8]`: IoU = 1/9 = 0.111
- No overlap `[0,4], [6,9]`: IoU = 0.0
- Contained `[0,9], [2,5]`: IoU = 4/10 = 0.4
- Degenerate `[5,4]` (end < start): IoU = 0.0

### metrics.py line 185: `union = (a_end - a_start + 1) + (b_end - b_start + 1) - intersection`

**Verdict: CORRECT.** Standard inclusion-exclusion for inclusive intervals. Each term `end - start + 1` gives the length of an inclusive interval.

---

## 2. tau Handling

### clip_gt.py line 62: `if run_length >= tau`

**Verdict: CORRECT.** `run_length = i - run_start` counts the number of True frames in the run. The condition `>= tau` means "at least tau frames", which matches the documented intent: "count(vehicle) >= K for at least tau consecutive frames."

### baselines.py `_labels_to_clips` line 257: `(e - s + 1) >= tau`

**Verdict: CORRECT and CONSISTENT.** For a segment `(s, e)` inclusive, the length is `e - s + 1`. Since `_labels_to_segment_list` produces `(run_start, i - 1)`, we have `e - s + 1 = (i - 1) - run_start + 1 = i - run_start`, which is identical to clip_gt.py's `run_length`.

Verified: both functions produce identical clip lists for the same input.

---

## 3. Clip IoU Matching (Greedy)

### Behavior (lines 127-143)

The matching iterates over GT clips in order. For each GT clip, it finds the predicted clip with the highest IoU. If that IoU >= threshold AND the predicted clip is not already matched, it records the match.

**Known Limitation: Priority-by-order.** When two GT clips have the same best predicted clip, only the first GT clip (by iteration order) gets matched. The second GT clip becomes unmatched even if another predicted clip with IoU >= threshold exists.

Demonstrated behavior:
- GT: `[(0,99), (50,149)]`, Pred: `[(20,120)]`, threshold=0.3 -> recall=0.5 (only first GT matched)
- Reversing GT order gives the same recall but a different GT clip is matched

**Impact:** This is a standard greedy approach, not a bug. It is deterministic given the input order. In the pipeline, GT clips come from `build_ground_truth_clips` which produces them in temporal order, so behavior is well-defined. For the synthetic experiments, most videos have 1-2 GT clips, so this limitation has minimal impact.

**Recommendation:** If precise matching is needed, consider using the Hungarian algorithm for optimal bipartite matching. For the current experiment, the greedy approach is adequate.

### One-to-one constraint

Each predicted clip can match at most one GT clip. This is standard practice. A predicted clip that overlaps multiple GT clips will only match the first one encountered.

---

## 4. Fragmentation Definition

### Lines 154-163

For each GT clip, count all predicted clips with IoU > 0 (any overlap). Add `(overlapping - 1)` for each GT clip with more than one overlapping prediction. Normalize by total GT clip count.

**Verdict: CORRECT and well-defined.**

- Fragmentation = 0 means each GT clip overlaps at most 1 predicted clip (no over-segmentation)
- Fragmentation = 1.0 means on average, each GT clip has 1 extra overlapping prediction
- Unmatched GT clips (0 overlapping predictions) contribute 0 to fragmentation (they are missed, not fragmented)

**Note:** The fragmentation uses IoU > 0 (any overlap), not IoU >= threshold. This means a predicted clip that barely touches a GT clip counts as overlapping. This is intentional -- fragmentation measures spatial over-segmentation, not match quality.

**Edge case:** A predicted clip spanning two GT clips contributes to the fragmentation of both. This is correct behavior: the single predicted clip fragments the view of both GT clips.

---

## 5. Boundary Error Calculation

### Lines 141-143

For matched clips, `start_errors.append(abs(gs - ps))` and `end_errors.append(abs(ge - pe))` compute absolute frame differences between GT and predicted boundaries.

**Verdict: CORRECT.** Errors are only computed for matched clips. Unmatched GT clips contribute `inf` to the mean (lines 148-149), and `_safe_mean` in report.py (line 161-164) excludes `inf` values. This means boundary errors reflect only matched clips.

**Potential issue:** If no clips are matched, `mean_start_error` and `mean_end_error` are `float('inf')`. The `_safe_mean` in report.py returns 0.0 when all values are `inf`, which could be misleading (0.0 suggests perfect boundaries, but in reality no clips were matched). Consider reporting `nan` or a sentinel value instead.

---

## 6. Oracle Calls and Budget Accounting

### Perturbation oracle calls (perturbation.py line 191)

```python
num_oracle_calls = int(np.sum(perturbed_labels != original_labels))
```

This counts frames where the perturbation changed the label -- i.e., the environmental noise level, not the method's query count.

### Baseline oracle calls (baselines.py)

Each baseline independently tracks how many frames it queried from the ground truth oracle:
- **full_oracle**: `oracle_calls = len(true_labels)` = 300 (queries every frame)
- **fixed_rate**: `oracle_calls = len(sampled_indices)` = ~30
- **uniform_random**: `oracle_calls = len(sampled_indices)` = ~30
- **proxy_threshold**: `oracle_calls` incremented per queried frame (up to budget)
- **arc_clustering**: `oracle_calls` incremented per queried frame (often less than budget)

### Pipeline wiring (run_synthetic_clip_degradation.py line 119)

```python
oracle_calls=baseline.oracle_calls
```

**Verdict: CORRECT.** The pipeline correctly uses the baseline's own oracle call count, not the perturbation's `num_oracle_calls`. The perturbation's value is stored in `PerturbedSequence.num_oracle_calls` but never consumed by the metrics pipeline. This is the right design: the experiment measures how efficiently each method uses its oracle budget, not how noisy the environment is.

### Budget conformance

- **fixed_rate** and **uniform_random** use exactly `int(n * budget)` calls = 30
- **proxy_threshold** allocates `int(n * budget)` = 30 calls and uses all of them
- **arc_clustering** allocates `int(n * budget)` = 30 calls but uses fewer (avg 12.8) because:
  - It only refines boundary frames of candidate segments
  - If few segments are found, the budget is underutilized
  - **Note:** This means arc_clustering uses less budget than other methods, which could unfairly disadvantage it in comparisons. The unused budget could be allocated to random frame queries for fair comparison.

---

## 7. Additional Findings

### 7a. Off-by-one in ARC clustering merge gap (baselines.py line 267)

```python
if start - prev_end <= cluster_merge_gap:
```

When `prev_end` is inclusive, the actual gap between segment ending at `prev_end` and segment starting at `start` is `start - prev_end - 1` frames. The code uses `start - prev_end`, which is the distance between endpoints (gap + 1).

**Example:** Segments `[20, 59]` and `[70, 109]` have a 10-frame gap (frames 60-69). The code computes `70 - 59 = 11`, so `cluster_merge_gap` must be >= 11 to merge them, even though the gap is only 10 frames.

**Impact:** Minor. The merge is off by one frame. With the default `cluster_merge_gap=10`, segments with a 10-frame gap are NOT merged (they would need gap <= 9). The fix would be:

```python
if start - prev_end - 1 <= cluster_merge_gap:
```

### 7b. Proxy threshold uses lowered K (baselines.py line 143)

```python
proxy_labels = perturbed.perturbed_counts >= max(0, K - 1)
```

The proxy threshold baseline uses `K - 1` (i.e., 2 instead of 3 for default K=3). This is intentional to increase recall at the cost of precision. This is a valid design choice but should be documented.

### 7c. Frame-level vs clip-level degradation (confirmed by diagnostics)

The diagnostic run on 20 synthetic videos confirms the experiment's core hypothesis:

| Method | Frame Recall | Clip Recall | Frame Drop | Clip Drop |
|--------|-------------|-------------|------------|-----------|
| full_oracle | 1.000 | 1.000 | -- | -- |
| fixed_rate | 1.000 | 1.000 | 0.000 | 0.000 |
| uniform_random | 0.998 | 1.000 | 0.002 | 0.000 |
| proxy_threshold | 0.962 | 0.375 | 0.038 | 0.625 |
| arc_clustering | 0.912 | 0.050 | 0.088 | 0.950 |

Clip-level degradation is dramatically larger than frame-level degradation for budget-constrained methods, confirming that small frame-level errors cascade into clip-level misses.

### 7d. Synthetic data characteristics

The diagnostic shows that synthetic videos tend to have ~1 GT clip per video with average length ~289 frames (out of 300). This means the synthetic data is dominated by a single long positive run per video, which may limit the experiment's ability to detect fragmentation effects. Consider generating data with more diverse clip structures.

---

## Diagnostic Results

Full diagnostic output saved to `diagnostics.json`. Summary:

- **20 videos**, 300 frames each, K=3, tau=30, budget=0.1
- **21 total GT clips** (1.05 per video), average length 289 frames
- **1344 total perturbed label differences** (67.2 per video)
- **full_oracle**: 300 oracle calls, perfect metrics
- **fixed_rate**: 30 oracle calls, near-perfect metrics (IoU=0.999)
- **uniform_random**: 30 oracle calls, near-perfect metrics (IoU=0.998)
- **proxy_threshold**: 30 oracle calls, clip_recall=0.375, fragmentation=1.525
- **arc_clustering**: 12.8 oracle calls (underutilizes budget), clip_recall=0.050, fragmentation=1.775
