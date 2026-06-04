# SUPG Query Benchmark Report

## 1. Purpose

Use the real SUPG framework (`refe_repos/supg`) to measure query-time cost on the real video data. Compares brute-force oracle scan against SUPG's precision/recall selectors to show how adaptive selection reduces oracle calls.

**This is NOT ARC/G-ARC performance.** It only shows what the original SUPG algorithm achieves on this video's proxy/oracle table.

## 2. Setup

| Item | Value |
|------|-------|
| CSV | `video_supg_k5.csv` (SUPG format: id, label, proxy_score) |
| N (frames) | 1775 |
| Positive (K=5) | 615 (34.65%) |
| Oracle model | YOLOv8x (pseudo-oracle, NOT human ground truth) |
| Oracle fps | 44.9 (measured on RTX 2080 Ti) |
| Brute-force baseline | 39.53s (oracle on all 1775 frames) |
| Trials per config | 50 |

## 3. SUPG Selectors Tested

| Selector | Type | Description |
|----------|------|-------------|
| RecallSelector (sqrt importance) | rt | Theoretically correct importance sampling for recall |
| RecallSelector (uniform) | rt | Uniform sampling for recall |
| PrecisionSelector (importance) | pt | Importance sampling for precision (main SUPG method) |
| NaiveRecallSelector | rt | Naive rank-based recall selector |
| NaivePrecisionSelector | pt | Naive rank-based precision selector |

## 4. Results

### Budget ratio = 5% (budget = 88 samples)

| Selector | Time | Selected | Oracle cost | Total | Speedup | Precision |
|----------|------|----------|-------------|-------|---------|-----------|
| RecallSelector (sqrt) | 1.7ms | 1775 | 39.53s | 39.53s | **1.0×** | 0.346 |
| RecallSelector (uniform) | 1.6ms | 1775 | 39.53s | 39.53s | **1.0×** | 0.346 |
| **PrecisionSelector (imp)** | **1.1ms** | **49** | **1.08s** | **1.08s** | **36.4×** | **0.992** |
| NaiveRecallSelector | 1.5ms | 1233 | 27.47s | 27.47s | **1.4×** | 0.454 |
| NaivePrecisionSelector | 1.5ms | 1037 | 23.09s | 23.09s | **1.7×** | 0.513 |

### Budget ratio = 10% (budget = 177 samples)

| Selector | Time | Selected | Oracle cost | Total | Speedup | Precision |
|----------|------|----------|-------------|-------|---------|-----------|
| RecallSelector (sqrt) | 1.8ms | 1775 | 39.53s | 39.53s | **1.0×** | 0.346 |
| RecallSelector (uniform) | 1.7ms | 1775 | 39.53s | 39.53s | **1.0×** | 0.346 |
| **PrecisionSelector (imp)** | **1.4ms** | **220** | **4.90s** | **4.90s** | **8.1×** | **0.882** |
| NaiveRecallSelector | 1.7ms | 1227 | 27.32s | 27.32s | **1.4×** | 0.455 |
| NaivePrecisionSelector | 1.8ms | 1055 | 23.50s | 23.50s | **1.7×** | 0.505 |

### Budget ratio = 20% (budget = 355 samples)

| Selector | Time | Selected | Oracle cost | Total | Speedup | Precision |
|----------|------|----------|-------------|-------|---------|-----------|
| RecallSelector (sqrt) | 2.2ms | 1753 | 39.04s | 39.04s | **1.0×** | 0.348 |
| RecallSelector (uniform) | 2.1ms | 1746 | 38.89s | 38.90s | **1.0×** | 0.348 |
| **PrecisionSelector (imp)** | **1.9ms** | **584** | **13.00s** | **13.00s** | **3.0×** | **0.720** |
| NaiveRecallSelector | 2.3ms | 1229 | 27.37s | 27.38s | **1.4×** | 0.458 |
| NaivePrecisionSelector | 2.5ms | 1063 | 23.68s | 23.68s | **1.7×** | 0.509 |

## 5. Key Findings

### PrecisionSelector (importance) is the standout

| Budget | Selected | Oracle calls saved | Speedup | Precision |
|--------|----------|--------------------|---------|-----------|
| 5% | 49 / 1775 | 97.2% | **36.4×** | 99.2% |
| 10% | 220 / 1775 | 87.6% | **8.1×** | 88.2% |
| 20% | 584 / 1775 | 67.1% | **3.0×** | 72.0% |

The SUPG PrecisionSelector with importance sampling achieves dramatic speedups by:
1. Using proxy scores to rank frames
2. Sampling strategically (sqrt importance weights)
3. Applying concentration bounds to find a precision threshold
4. Selecting only frames above that threshold for oracle evaluation

### RecallSelector is conservative

Both RecallSelector variants select nearly all frames (1746–1775 out of 1775), resulting in no speedup. This is because the recall constraint (min_recall=0.9) is hard to satisfy with selective oracle calls when the positive rate is high (34.65%).

### Naive selectors are moderate

NaiveRecallSelector and NaivePrecisionSelector save 30–40% of oracle calls (1.4–1.7× speedup) but with lower precision than the importance-based selector.

### Selector overhead is negligible

All selector times are 1–2.5ms — negligible compared to oracle inference (39.5s for full scan). The speedup comes entirely from reducing oracle calls.

## 6. Query-Time Cost Model

```
Brute-force:  oracle_time = N / oracle_fps = 1775 / 44.9 = 39.53s

SUPG query:   selector_time + (selected_frames / oracle_fps)
            = ~1.5ms + selected × 0.022s

PrecisionSelector @ 5%:  1.1ms + 49 × 0.022s  = 1.08s  → 36.4× speedup
PrecisionSelector @ 10%: 1.4ms + 220 × 0.022s = 4.90s  → 8.1× speedup
PrecisionSelector @ 20%: 1.9ms + 584 × 0.022s = 13.00s → 3.0× speedup
```

## 7. Interpretation

The SUPG PrecisionSelector on this real video achieves **8–36× speedup** over brute-force oracle evaluation while maintaining **72–99% precision**. This means:

- At 5% budget: only 49 frames need oracle calls, and 99% of those are true positives.
- At 10% budget: 220 frames need oracle calls, 88% precision.
- The selector itself takes ~1ms — all savings come from avoiding oracle on non-selected frames.

**This validates the core G-ARC motivation:** if a cheap proxy can pre-rank frames, an adaptive selector can dramatically reduce the number of expensive oracle calls needed.

## 8. Limitations

1. **Oracle is YOLOv8x pseudo-oracle**, not human ground truth. With a human oracle (much slower per call), speedups would be even more dramatic.
2. **Single K value (K=5).** Different K thresholds would change positive rate and selector behavior.
3. **No ARC/G-ARC.** This is the original SUPG algorithm, not the G-ARC gradient-based extension.
4. **Single video.** Results may vary with different videos, resolutions, and traffic densities.
5. **No batching.** Oracle calls are sequential. Batched inference could change absolute times.
6. **RecallSelector ineffective.** With 34.65% positive rate, recall-oriented selectors can't reduce oracle calls much. Lower positive rate scenes would show different behavior.
7. **SUPG uses proxy_score as continuous ranking.** The quality of this ranking (proxy vs oracle correlation) directly affects selector performance.
