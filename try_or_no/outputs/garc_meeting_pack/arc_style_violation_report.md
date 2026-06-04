# ARC-style Recall Violation Smoke

## 1. Purpose

This is a **surrogate motivation experiment**, not an ARC reproduction.
The goal is to test whether a confidence-like candidate quality metric can be high
while actual clip recall remains low.

If such a violation exists, it supports the statement:
> "Candidate-side confidence does not necessarily certify clip-level recall."

This result motivates the need for a recall-certification layer (G-ARC),
but does not prove ARC violates recall.

---

## 2. Data Found

- **Dataset**: UA-DETRAC continuous frame table (`outputs/real_mvp/uadetrac_frame_table.csv`)
- **Frames**: 83,756 across 60 videos
- **Columns used**: `vehicle_count_gt` (oracle count), `proxy_score` (0–1 confidence score)
- **Oracle positive rate**:
  - K=20: 8.6% (7,234 frames)
  - K=25: 3.1% (2,637 frames)
- **True clips** (maximal consecutive positive runs ≥ τ):
  - K=20, τ=20: 35 true clips
  - K=20, τ=30: 28 true clips
  - K=25, τ=20: 13 true clips
  - K=25, τ=30: 11 true clips
- **Proxy score distribution**: mean=0.606, p90=0.800, p95=0.849, p99=0.907

---

## 3. Methods

All methods are simple baselines. `arc_style_surrogate` is explicitly **not** ARC.

1. **full_oracle** — Oracle labels for all frames. Upper bound reference. oracle_ratio=1.0.

2. **uniform_sampling_stitch** — Sample `budget_ratio × N` frames uniformly. Oracle labels on sampled frames only; unsampled frames marked negative. Stitch predicted positives into clips.

3. **fixed_proxy_threshold_stitch** — Use `proxy_score ≥ threshold` to mark positive frames. No oracle used (oracle_ratio=0). Thresholds: p90=0.800, p95=0.849, p99=0.907, p99.5=0.923.

4. **supg_style_frame_selection_stitch** — SURROGATE, not SUPG. Importance-sampled oracle frames (50% proxy-biased, 50% uniform). Calibrate proxy threshold from oracle samples targeting frame recall γ=0.9. Return all frames above threshold, stitch into clips.

5. **arc_style_surrogate** — SURROGATE, not ARC.
   - *Candidate generation*: proxy_score ≥ threshold, merge runs with gap ≤ τ/3.
   - *Refinement*: 80% oracle budget inside candidates (boundary-biased), 20% outside.
   - *Confidence*: fraction of oracle samples inside candidates that are positive. Measures candidate quality (precision-like). **Does not estimate missed true clips outside candidates.**

---

## 4. Results

Full results: `arc_style_violation_smoke.csv` (592 rows).

### Overall Violation Count (arc_style_surrogate)

- Total arc_style_surrogate rows: **144**
- Rows with reported_confidence ≥ 0.8 and actual_clip_recall < 0.8: **90** (62.5%)
- Rows with reported_confidence ≥ 0.9 and actual_clip_recall < 0.8: **90** (all high-confidence violations also have conf ≥ 0.9)
- Rows with violation_0.8 = True (actual_clip_recall < 0.8): **114** (79.2%)

### Violations by Proxy Threshold

| Proxy threshold | Total rows | Rows with conf ≥ 0.8 and recall < 0.8 | Violation rate |
|-----------------|-----------|----------------------------------------|---------------|
| p90             | 36        | 0                                      | 0%            |
| p95             | 36        | 18                                     | 50%           |
| p99             | 36        | 36                                     | 100%          |
| p99.5           | 36        | 36                                     | 100%          |

At p90, the proxy has ~90% frame-level recall, so candidates cover most true clips and recall is moderate. At p95 and above, the proxy recall drops sharply, creating a wide gap between candidate-side confidence and clip-level recall.

### Representative Violation Rows

| K  | tau | proxy | reported_confidence | actual_clip_recall |
| -- | --: | ----- | ------------------: | -----------------: |
| 20 |  20 | p99   |               1.000 |              0.000 |
| 20 |  20 | p95   |               0.975 |              0.314 |
| 25 |  20 | p99.5 |               0.996 |              0.154 |
| 25 |  30 | p99.5 |               0.995 |              0.091 |

### Additional High-Confidence Zero-Recall Rows

Many rows show reported_confidence = 1.000 with actual_clip_recall = 0.000:

| K  | tau | proxy | budget | reported_confidence | actual_clip_recall |
| -- | --: | ----- | -----: | ------------------: | -----------------: |
| 20 |  20 | p99   |   0.05 |               1.000 |              0.000 |
| 20 |  20 | p99   |   0.10 |               1.000 |              0.000 |
| 20 |  20 | p99   |   0.20 |               1.000 |              0.000 |
| 20 |  30 | p99   |   0.05 |               1.000 |              0.000 |
| 20 |  30 | p99   |   0.10 |               1.000 |              0.000 |
| 20 |  30 | p99.5 |   0.05 |               1.000 |              0.000 |
| 20 |  30 | p99.5 |   0.10 |               1.000 |              0.000 |
| 20 |  30 | p99.5 |   0.20 |               1.000 |              0.000 |

These rows represent the strongest violation pattern: the candidate-side confidence reports maximum confidence while no true clips are recalled at all.

### Reference: Other Methods

| method | typical recall (K=20, τ=20) | typical oracle_ratio |
|--------|---------------------------|---------------------|
| full_oracle | 1.00 | 1.00 |
| uniform_sampling_stitch | 0.00 | 0.05–0.20 |
| fixed_proxy_threshold_stitch (p90) | 0.83–1.00 | 0.00 |
| fixed_proxy_threshold_stitch (p99) | 0.00 | 0.00 |
| supg_style_frame_selection_stitch | 0.00–0.46 | 0.05–0.20 |

The `full_oracle` method always achieves recall=1.0. The `fixed_proxy_threshold_stitch` with p90 achieves high recall because the proxy at that threshold has 90% frame-level coverage. But at p99, both proxy-based methods fail — the key difference is that `arc_style_surrogate` still reports high confidence.

---

## 5. Row Count Audit

### Expected vs Actual

**Naive Cartesian product:**
5 methods × 4 proxy_thresholds × 2 K × 2 tau × 3 budgets × 3 seeds = **720**

**Actual CSV rows: 592**

**Difference: 128 rows**

### Explanation

The discrepancy is caused by `full_oracle`, which does not depend on budget or seed (it uses all oracle labels). The script runs `full_oracle` only once per (K, tau, proxy_threshold) combination, at budget=0.05 and seed=0.

| Method | Rows | Per-config count | Explanation |
|--------|------|-----------------|-------------|
| full_oracle | 16 | 2K × 2tau × 4proxy × 1budget × 1seed | Runs once per (K, tau, proxy) |
| uniform_sampling_stitch | 144 | 2K × 2tau × 4proxy × 3budgets × 3seeds | Full sweep |
| fixed_proxy_threshold_stitch | 144 | 2K × 2tau × 4proxy × 3budgets × 3seeds | Full sweep |
| supg_style_frame_selection_stitch | 144 | 2K × 2tau × 4proxy × 3budgets × 3seeds | Full sweep |
| arc_style_surrogate | 144 | 2K × 2tau × 4proxy × 3budgets × 3seeds | Full sweep |
| **Total** | **592** | | |

**Missing rows:** 720 - 592 = 128, which equals 4 × (144 - 16) = 4 × 128. Wait, that's not right.

Let me recalculate: full_oracle should have 144 rows in the naive product but only has 16. So 144 - 16 = 128 missing rows. This accounts for the entire discrepancy.

The reason is correct: full_oracle is a deterministic upper bound that does not vary by budget or seed, so running it for all 9 (budget, seed) combinations would be redundant. The script intentionally runs it only once per (K, tau, proxy_threshold).

### No Failed Runs

No configurations were skipped due to errors. No runs failed. The 592 rows are complete for the intended design.

---

## 6. Interpretation

This surrogate experiment **supports** the hypothesis that candidate-side confidence
does not necessarily certify clip-level recall.

In the observed violations:
- `reported_confidence` ranges from 0.95 to 1.00
- `actual_clip_recall` ranges from 0.00 to 0.31

The gap arises because the confidence metric measures **candidate quality** (are the
returned candidates pointing at real things?) but not **candidate coverage** (did we
find all the real things?). When the proxy has high precision but low recall, the
candidates that exist are excellent, but most true clips are never even considered.

**This is NOT a claim that ARC fails.** ARC's actual confidence mechanism may address
this gap. This experiment only shows that a natural candidate-side confidence estimator
has a structural blind spot: it certifies what the candidates contain, but not what
the candidates miss.

---

## 7. Limitations

1. **Not ARC reproduction.** This uses simple baselines and a proxy score, not ARC's
   candidate generation, confidence estimation, or refinement algorithms.

2. **Proxy/oracle may be pseudo labels.** The `vehicle_count_gt` and `proxy_score`
   columns come from a previous feasibility study. Their relationship to true oracle
   labels is not independently verified.

3. **Data may be too easy or too small.** 83,756 frames across 60 videos is a limited
   test. The proxy score is well-calibrated (high precision at moderate thresholds),
   which makes violations easy to construct by choosing extreme thresholds. Real-world
   proxies may behave differently.

4. **Surrogate confidence is approximate.** The reported_confidence is a frame-level
   precision estimate inside candidates, not a calibrated clip-level confidence.
   A real system might use a different confidence estimator.

5. **Clip recall depends on many factors.** IoU threshold (θ=0.5), minimum clip
   length (τ), gap merging strategy, and boundary refinement all affect results.
   Different parameter choices could change the violation pattern.

6. **Threshold choice is post-hoc.** The proxy thresholds (p95, p99, p99.5) were
   chosen after examining the proxy score distribution to find regimes where
   violations occur. A real system would calibrate thresholds from data.

7. **Results only motivate further validation.** This experiment defines the
   validation protocol and shows the structural gap exists under surrogate conditions.
   It does not prove the gap exists under real ARC conditions.

---

## 8. Next Step

1. **Implement a closer ARC-style surrogate** with (a) learned candidate generation,
   (b) calibrated confidence with coverage awareness, and (c) proper SUPG-style
   frame selection. Or obtain ARC code.

2. **Test on additional datasets** (nuScenes, BDD100K) to confirm the violation
   pattern generalizes beyond UA-DETRAC.

3. **Implement G-ARC verification layer** as the proposed solution: after ARC-style
   candidate generation, audit non-candidate regions with oracle samples to estimate
   missed clips and derive a clip recall lower bound.

---

## Final Consistency Check

1. ✅ This experiment is not an ARC reproduction. (Stated in §1, §3, §6, §7.)
2. ✅ The confidence metric is candidate-side / precision-like. (Stated in §3, §6.)
3. ✅ The confidence metric does not estimate missed true clips outside candidates. (Stated in §3, §6.)
4. ✅ The result supports a recall-certification layer, but does not prove ARC violates recall. (Stated in §6.)
5. ✅ G-ARC remains a proposed direction. (Stated in §8.)

---

## Reproducibility

```bash
python outputs/garc_meeting_pack/run_arc_style_violation_smoke.py
```

Output: `outputs/garc_meeting_pack/arc_style_violation_smoke.csv`
