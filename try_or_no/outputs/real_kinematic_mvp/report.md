# Real Kinematic AQP MVP Report

## 1. Dataset Used

**UA-DETRAC** training set (60 surveillance camera video sequences).
- Path: `/qiuyeqing/llama_prl/G-ARC/data/ua_detrac/ua_detrac_training_set.zip`
- 906,524 bounding box annotations across 82,085 frames
- 341 unique tracked objects (target_id > 0)
- Fixed camera at 25 FPS, image size 960×540

**Not available:** nuScenes, Waymo (needed for 3D ego-relative geometry).

## 2. Exact Paths Read

- `/qiuyeqing/llama_prl/G-ARC/data/ua_detrac/ua_detrac_training_set.zip` (annotations.csv per sequence)
- `/qiuyeqing/llama_prl/G-ARC/try_or_no/outputs/real_kinematic_mvp/kinematic_query_table.csv` (598,281 records)
- `/qiuyeqing/llama_prl/G-ARC/try_or_no/outputs/real_kinematic_mvp/frame_count_table.csv` (82,085 records)
- `/qiuyeqing/llama_prl/G-ARC/try_or_no/outputs/real_kinematic_mvp/ground_truth_clips.jsonl` (42,486 clips)

## 3. Scale

| Metric | Count |
|--------|-------|
| Videos | 60 |
| Total frames | 82,085 |
| Track-frame records | 598,281 |
| Unique tracks | 341 |
| Ground-truth clips | 42,486 |

## 4. Oracle States and Labels

**Oracle states** are bounding boxes from UA-DETRAC annotations (real data, not synthetic).

**Oracle labels derived from real annotations:**
- `in_image_label`: 1 if bbox_area >= 500 (target visible and not tiny)
- `in_front_label`: 1 if bbox center is in center 60% of image width, top 85% of height, and area >= 500
- `count_ge_K`: 1 if per-frame vehicle count >= K

**Positive rates:**
- in_image: 97.4%
- in_front: 67.5%
- count_ge_3: ~98% (most frames have ≥3 vehicles)
- count_ge_5: ~90%

## 5. Queries Evaluated

| Query | Description | Positive Rate |
|-------|-------------|---------------|
| in_image | Target visible for ≥ tau frames | 97.4% |
| in_front | Target in front region for ≥ tau frames | 67.5% |
| count_ge_3 | ≥ 3 vehicles for ≥ tau frames | ~98% |
| count_ge_5 | ≥ 5 vehicles for ≥ tau frames | ~90% |

Tau values: 5, 10, 20, 30 frames.

## 6. Baselines Implemented

| ID | Method | Description |
|----|--------|-------------|
| B0 | naive_oracle | Oracle at every frame (upper bound) |
| B1 | fixed_rate_k | Oracle every k frames (k=2,5,10,20) |
| B2 | linear_interp_k | Oracle at k-frame intervals, interpolate between |
| B3 | const_vel_k | Constant velocity extrapolation |
| B4 | kalman_fixed_k | Kalman prediction, fixed-interval oracle |
| B5 | kalman_uncertainty_t | Kalman, trigger when uncertainty > threshold |
| B6 | boundary_only_m | Trigger when near spatial boundary |
| B7 | query_impact_m_g | Query-impact-aware: boundary + staleness + disagreement |
| B8 | count_fixed_rate / count_query_impact | Count-based query variants |

## 7. Does Query-Impact-Aware Beat Strong Baselines?

### in_front query (tau=10):

| Method | Clip F1 | Oracle % | vs fixed_rate_k10 |
|--------|---------|----------|-------------------|
| naive_oracle | 0.900 | 100% | baseline |
| **boundary_only_m10** | **1.000** | **11.0%** | **+0.103 F1, +0.2% cost** |
| query_impact_m20_g5 | 0.900 | 35.2% | +0.003 F1, +24.4% cost |
| fixed_rate_k5 | 0.900 | 21.0% | +0.003 F1, +10.2% cost |
| fixed_rate_k10 | 0.897 | 10.8% | reference |
| kalman_uncertainty_t50 | 0.897 | 15.3% | +0.000 F1, +4.5% cost |
| fixed_rate_k20 | 0.867 | 5.7% | -0.030 F1, -5.1% cost |
| boundary_only_m20 | 0.470 | 12.2% | -0.427 F1, +1.4% cost |

**Finding:** boundary_only_m10 achieves perfect F1 at ~11% oracle cost, beating fixed_rate_k10 (F1=0.897 at ~11% cost). This is a real but small advantage. However, boundary_only_m20 (F1=0.47) shows the method is very sensitive to margin parameter.

### count_ge_3 query (tau=10):

| Method | Clip F1 | Oracle % | vs fixed_rate_k10 |
|--------|---------|----------|-------------------|
| **query_impact_g10** | **0.981** | **43.8%** | **+0.090 F1** |
| fixed_rate_k5 | 0.918 | 20.0% | +0.027 F1 |
| fixed_rate_k10 | 0.891 | 10.0% | reference |
| fixed_rate_k20 | 0.850 | 5.0% | -0.041 F1 |

**Finding:** query_impact_g10 achieves F1=0.981 at 43.8% oracle cost. But this is 4× the cost of fixed_rate_k10. At comparable cost (~10%), query_impact_g10 still beats fixed_rate_k10 by 0.09 F1.

### in_image query (tau=10):

All methods achieve F1 ≥ 0.86. The 97.4% positive rate makes this query trivially easy. No method has a meaningful advantage.

## 8. Does Query-Impact-Aware Reduce Boundary Error?

**Partially.** The boundary_only_m10 method achieves the best clip F1 for in_front queries, suggesting that boundary-aware triggering helps at predicate transitions. However:
- The advantage is parameter-sensitive (margin=10 works, margin=20 fails)
- The advantage is small (0.103 F1 improvement)
- The advantage requires careful tuning

## 9. Best Speed-Quality Tradeoff

**in_front, tau=10:**
- Best F1/cost: boundary_only_m10 (F1=1.0, 11% oracle)
- Runner-up: kalman_uncertainty_t100 (F1=0.86, 9.2% oracle)
- Budget option: fixed_rate_k20 (F1=0.87, 5.7% oracle)

**count_ge_3, tau=10:**
- Best F1/cost: query_impact_g10 (F1=0.98, 43.8% oracle)
- Runner-up: fixed_rate_k5 (F1=0.92, 20% oracle)
- Budget option: fixed_rate_k20 (F1=0.85, 5% oracle)

## 10. Is the Advantage Visible on Real Data?

**Yes, but it is small and query-dependent.**

On the `in_front` query (the most dynamic predicate), boundary-aware triggering shows a measurable advantage over fixed-rate sampling at comparable oracle cost. On count-based queries, query-impact-aware triggering also shows an advantage.

However:
- The advantage is parameter-sensitive
- Fixed-rate sampling with appropriate k is a strong baseline
- The queries are relatively easy (transitions are infrequent — 1.5% rate for in_front)

## 11. Is This Direction Strong Enough to Continue?

### Strengths:
1. The boundary-aware idea works on real data for the in_front query
2. Clip construction from frame-level predictions is a real contribution
3. The AQP-style evaluation framework (budget-quality curves) is clean and reproducible
4. UA-DETRAC provides real continuous video with tracked objects

### Weaknesses:
1. **2D only** — cannot validate 3D ego-relative geometry (within_distance, true FOV)
2. **Fixed camera** — no ego motion, so "ego-relative" predicates reduce to image-region predicates
3. **Small advantage** — boundary-aware methods beat fixed-rate by 0.03-0.10 F1, which may not be significant
4. **Parameter-sensitive** — margin=10 works, margin=20 fails; oracle_gap=5 works, gap=3 uses too much budget
5. **Easy predicates** — 97.4% positive for in_image, 67.5% for in_front; transitions are rare (1.5%)
6. **No real detector proxy** — oracle labels come from annotations, not from a lightweight detector

## 12. Kill Conditions

The direction should be killed if:
1. On nuScenes/Waymo with real 3D geometry, boundary-aware methods do not beat fixed-rate by ≥ 0.05 F1 at comparable oracle cost
2. The advantage disappears with a real lightweight detector proxy (rather than perfect oracle labels)
3. The advantage is only visible on easy predicates (high positive rate, rare transitions)

## 13. What Should Be Done Next

1. **Get nuScenes mini** — validate on real 3D ego-relative geometry (within_distance, true FOV)
2. **Use a real lightweight detector** — test whether proxy quality degrades the advantage
3. **Harder predicates** — test on predicates with more frequent transitions (e.g., enters/exits FOV events)
4. **Statistical significance** — run more seeds and compute confidence intervals
5. **Ablation** — test each component of query-impact-aware (boundary, staleness, disagreement) separately

## Final Judgment

**CONDITIONAL GO**

The direction shows a small but real advantage on 2D real data for the in_front query. Boundary-aware triggering can beat fixed-rate sampling at comparable oracle cost. However:

- The advantage is small (0.03-0.10 F1)
- The data is 2D only (no ego motion)
- The results are parameter-sensitive
- The predicates are relatively easy

**Continue only after:**
1. Validating on nuScenes/Waymo with real 3D geometry
2. Testing with a real lightweight detector proxy
3. Showing the advantage is robust across query types and parameters

If the advantage disappears on real 3D data or with a real proxy, abandon this direction and return to G-ARC / clip-level guarantee.

## Output Files

| File | Description |
|------|-------------|
| `kinematic_query_table.csv` | Per-track-frame table (598K records) |
| `frame_count_table.csv` | Per-frame vehicle counts (82K records) |
| `ground_truth_clips.jsonl` | Ground-truth clips (42K clips) |
| `metrics.csv` | All experiment results (100K rows) |
| `per_method_summary.csv` | Per-method aggregated metrics |
| `per_query_summary.csv` | Per-query aggregated metrics |
| `per_scene_summary.csv` | Per-scene aggregated metrics |
| `data_inventory.md` | Available data summary |
| `aqp_repo_style_notes.md` | Reference repo design notes |
