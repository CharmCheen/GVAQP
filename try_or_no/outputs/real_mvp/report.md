# Real-Data AQP MVP Report

## 1. Dataset Used

**Primary:** BDD100K validation set (10,000 images with object detection annotations).
- Path: `/qiuyeqing/llama_prl/G-ARC/data/bdd100k/bdd100k/bdd100k.csv`
- 186,033 object annotations across 10,000 images
- Vehicle classes: car, truck, bus, motorcycle, bicycle, rider, train, trailer, other vehicle

**Secondary:** UA-DETRAC training set (60 video sequences, 83,756 frames).
- Path: `/qiuyeqing/llama_prl/G-ARC/data/ua_detrac/ua_detrac_training_set.zip`
- Used for clip-level experiments (each sequence = one clip)

## 2. Data Scale

| Dataset | Videos | Frames/Records | Annotations |
|---------|--------|---------------|-------------|
| BDD100K | — (independent images) | 10,000 | 186,033 objects |
| UA-DETRAC | 60 sequences | 83,756 frames | Per-frame bounding boxes |

## 3. Oracle Label Derivation

**Query:** `label = 1[count(vehicle) >= K]`

For each image/frame:
1. Count all objects belonging to vehicle classes (car, truck, bus, motorcycle, bicycle, rider, train, trailer, other vehicle)
2. Set `label = 1` if count >= K, else 0

**K=3 results:** 9,486/10,000 images are positive (94.86% positive rate)

**Alternative K values tested:**
| K | Positive Rate |
|---|--------------|
| 3 | 94.86% |
| 10 | 54.83% |
| 15 | 27.65% |
| 20 | 10.04% |

## 4. Proxy Score Derivation

**The proxy is SYNTHETIC over real labels.** It is NOT a real model proxy.

Method:
1. Start with ground-truth vehicle counts
2. Multiply by detection_rate=0.70 (simulating missed detections)
3. Add Gaussian noise with std=2.0
4. Clamp to >= 0
5. Normalize via log1p + min-max to [0, 1]

This simulates a noisy detector that misses ~30% of vehicles and has count noise. The proxy correlates with the ground truth but has substantial noise.

**Why synthetic?** We do not have a precomputed lightweight detector output for BDD100K. Building one would require running a detector, which violates the constraint of not running heavy pipelines.

## 5. SUPG-Style Results

### 5.1 Baselines (K=3, 5% budget)

| Method | Recall | Precision | Set Size |
|--------|--------|-----------|----------|
| Uniform | 0.050 | 0.946 | 500 |
| Proxy Threshold | 0.053 | 1.000 | 500 |
| Importance Sampling | 0.050 | 0.975 | 488 |
| Defensive Mixture | 0.050 | 0.963 | 488 |

All baselines achieve recall proportional to budget (~5% at 5% budget). Precision is high because 94.86% of items are positive.

### 5.2 SUPG Methods (K=3)

| Method | Budget | Recall | Precision | Set Size | Violation Rate |
|--------|--------|--------|-----------|----------|---------------|
| SUPG Recall (target=0.9) | 1% | 1.000 | 0.949 | 10,000 | 0% |
| SUPG Recall (target=0.9) | 5% | 0.970 | 0.969 | 9,507 | 0% |
| SUPG Recall (target=0.9) | 10% | 0.950 | 0.979 | 9,204 | 0% |
| SUPG Precision (target=0.8) | 1% | 0.921 | 0.984 | 8,879 | 0% |
| SUPG Precision (target=0.8) | 5% | 0.930 | 0.983 | 8,969 | 0% |
| SUPG Precision (target=0.8) | 10% | 0.931 | 0.984 | 8,976 | 0% |

**Key observation:** With K=3, the 94.86% positive rate makes this trivially easy. SUPG methods return ~90% of the dataset to guarantee targets. The returned set size is not meaningfully smaller than the full dataset.

### 5.3 K-Sweep Results (5% budget)

| K | Method | Recall | Precision | Set Size | Violation |
|---|--------|--------|-----------|----------|-----------|
| 3 | uniform | 0.050 | 0.951 | 500 | 100% |
| 3 | supg_recall | 0.789 | 0.992 | 7,553 | 80% |
| 10 | uniform | 0.051 | 0.556 | 500 | 100% |
| 10 | supg_recall | 0.590 | 0.855 | 3,742 | 80% |
| 15 | uniform | 0.049 | 0.273 | 500 | 100% |
| 15 | supg_recall | 0.662 | 0.741 | 2,770 | 60% |
| 20 | uniform | 0.049 | 0.099 | 500 | 100% |
| 20 | supg_recall | 0.501 | 0.680 | 728 | 100% |

**Observations:**
- The synthetic proxy helps: proxy_threshold achieves 100% precision at all K values
- SUPG recall methods have high variance across seeds (std up to 0.37)
- At K=20 (10% positive), the proxy quality degrades significantly
- The proxy's usefulness diminishes as the positive rate drops

## 6. ABae-Style Results

Query: `SELECT AVG(vehicle_count_gt) FROM frames WHERE vehicle_count >= K`

Exact answer (K=3): 11.63

| Budget | Uniform MSE | Stratified MSE | Uniform MAE | Stratified MAE |
|--------|------------|----------------|-------------|----------------|
| 1% | 0.271 | 0.179 | 0.314 | 0.224 |
| 2% | 0.063 | 0.112 | 0.203 | 0.144 |
| 5% | 0.020 | 0.042 | 0.123 | 0.117 |
| 10% | 0.013 | 0.017 | 0.069 | 0.104 |
| 20% | 0.011 | 0.003 | 0.095 | 0.085 |

**Observation:** At low budgets, stratified (ABae-style) has lower MAE than uniform. At higher budgets, the advantage diminishes. The MSE results are mixed — stratified doesn't always win on MSE.

## 7. Clip-Level Results

Built 5,931 pseudo-clips (tau=30 frames) from BDD100K frame groups. 5,730 clips are positive.

| Method | Budget | Clip Recall | Clip Precision | Mean IoU |
|--------|--------|-------------|----------------|----------|
| Uniform | 10% | 0.155 | 0.975 | 0.636 |
| Proxy Threshold | 10% | 0.156 | 1.000 | 0.664 |
| Importance | 10% | 0.152 | 0.983 | 0.636 |
| Uniform | 20% | 0.290 | 0.975 | 0.686 |
| Proxy Threshold | 20% | 0.299 | 1.000 | 0.714 |

**Observation:** Clip recall is low (~15% at 10% budget) because frame-level sampling covers only a fraction of each clip. Mean IoU is moderate (~0.64) for frames that are hit. The pseudo-clip construction from independent BDD100K frames is a limitation.

## 8. Does Frame-Level AQP Translate to Clip-Level Quality?

**Partially.** Frame-level precision translates well (clip precision > 0.97). However, frame-level recall does NOT translate to clip recall — even at 20% budget, clip recall is only ~30%. This is because:
1. Clips require coverage of *contiguous* frames, not just any frames
2. Random frame sampling is spatially uniform, not temporally clustered
3. BDD100K frames are independent (not sequential), so pseudo-clips are artificial

**This is a genuine finding:** frame-to-clip reconstruction is a significant challenge that AQP methods must address.

## 9. Limitations

1. **Synthetic proxy:** The proxy score is synthetic (subsampled gt + noise), not a real model proxy. Any claim about "proxy quality" is about this specific synthetic proxy, not about real detector proxies.

2. **Extreme class imbalance (K=3):** 94.86% positive rate makes the selection task trivial. The more interesting case is K=10-20.

3. **Independent frames:** BDD100K images are independent, not sequential. Clip construction is artificial.

4. **Small UA-DETRAC:** Only 60 sequences, all with high vehicle density. Not representative.

5. **No real detector proxy:** We have no lightweight model output to serve as a genuine proxy.

## 10. Which Issue Appears Most Important?

Based on this MVP, the issues in priority order:

1. **Frame-to-clip reconstruction** — This is the biggest gap. Frame-level AQP does not translate to clip-level quality. Even with perfect frame selection, clip recall is poor because random sampling doesn't cover contiguous segments. This is the core challenge for video AQP.

2. **Frame-level proxy quality** — The synthetic proxy works for K=3 but degrades at K=20. A real detector proxy would likely be better, but proxy quality is a genuine concern for rare predicates.

3. **Oracle budget allocation** — SUPG/ABae-style allocation works for aggregation but is overkill for selection when the positive rate is high. For rare predicates (K=20), allocation matters more.

4. **Clip-level guarantees** — No existing method provides clip-level guarantees. This is an open problem.

5. **Kinematic prediction** — Not tested here (no ego-pose data). Could help with temporal coverage.

## 11. What Should Be Tested Next?

Based on this MVP, I recommend:

1. **Robust clip reconstruction** — Develop methods that explicitly model temporal contiguity. Key question: can we get clip-level recall from frame-level budget by exploiting temporal structure?

2. **Real proxy on a smaller dataset** — Run a lightweight detector (e.g., YOLOv5-nano) on UA-DETRAC to get a real proxy, then re-run experiments. This would validate whether the synthetic-proxy findings hold with real proxies.

3. **G-ARC / clip-level guarantee** — Formalize the clip-level guarantee problem. Key question: what budget is needed to guarantee clip-level recall >= R with probability >= 1-delta?

4. **Kinematic-AQP on real ego-pose data** — If KITTI or nuScenes ego-pose data becomes available, test whether motion prediction helps with temporal allocation.

**Recommendation:** Do NOT stop this branch. The frame-to-clip gap is a real finding that motivates further work. But do NOT claim the direction is proven — this MVP shows the problem exists, not that we have a solution.

## Output Files

| File | Description |
|------|-------------|
| `frame_query_table.csv` | BDD100K frame-level table (10K records) |
| `supg_style_metrics.csv` | SUPG-style selection results |
| `abae_style_metrics.csv` | ABae-style aggregation results |
| `clip_metrics.csv` | Clip-level evaluation results |
| `k_sweep_metrics.csv` | Results across K=3,10,15,20 |
| `ground_truth_clips.csv` | Pseudo-clip ground truth |
| `uadetrac_frame_table.csv` | UA-DETRAC frame table (83K records) |
| `uadetrac_clip_table.csv` | UA-DETRAC clip table (60 clips) |
| `repo_notes.md` | Reference repo analysis |
| `data_inventory.md` | Available data summary |
