# Proxy-Oracle Audit

Based on `full_center10_analysis.json` (proxy AUROCs, quartile rates, object distribution), `proxy_oracle_relation.csv` (347-row per-anchor analysis), `PROXY_ORACLE_RELATION_ANALYSIS.md`, and budget replay results.

---

## Q1: Can proxy score predict semantic event?

**Weakly and non-monotonically.** 

- Best fusion proxy AUROC = 0.624 (score_fusion_geometry_motion)
- motion_energy_mean = 0.607 (weak)
- score_fusion_yolo_motion = 0.586 (weak)
- score_fusion_ego_lateral = 0.574 (barely above random)
- **object_count_mean = 0.052** (anti-predictive — dense traffic predicts negative)
- **near_ego_vehicle_count_max = 0.014** (strongly anti-predictive)

**Critical:** The same proxy feature that was the best on realcartest (object_count_mean, AUC=0.738) is anti-predictive on dataset3 (AUC=0.052). This is workload-level instability.

## Q2: Is top-proxy better than uniform/random?

**Marginally yes, but the advantage shrinks with budget.**

| B | top_proxy recall | random recall | advantage |
|---|---|---|---|
| 10 | 7.5% | 3.1% | +4.4% |
| 20 | 10.0% | 6.0% | +4.0% |
| 40 | 15.0% | 12.2% | +2.8% |
| 80 | 25.0% | 23.7% | +1.3% |
| 150 | 47.5% | 43.9% | +3.6% |

At B=80, top-proxy advantage over random is only +1.3% — essentially random. A proxy with AUROC=0.624 in a top-k selection task barely beats random sampling.

## Q3: High-score negatives — proportion and types

**77 high-score negatives** (top quartile score but negative label):
- normal_following: 48 (dense traffic, no event)
- no_ego_path_interaction: 29 (objects visible but no ego-path entry)

These anchors waste oracle budget. Top-proxy selection allocates calls to these dense-traffic false alarms.

## Q4: Low-score positives — do they exist?

**Yes, 17/40 = 42.5% of positives have below-median proxy score.**

Examples from `proxy_oracle_relation.csv`:
- anchor_0128: score=-1.859, pedestrian at crosswalk (sparse traffic)
- anchor_0129: score=-2.023, pedestrian 
- anchor_0132: score=-0.975, vehicle
- anchor_0161: score=-1.401, pedestrian
- anchor_0164: score=-0.368, cyclist
- anchor_0173-0179: cluster of 7 low-score positives in 1500-1800s block

The proxy systematically misses events in sparse-traffic scenes (pedestrian crossings, cyclist maneuvers) because its dominant signal is object density.

## Q5: Proxy's main value

- **Stratification for non-monotonic selection:** Q3 (15.1%) > Q4 (11.2%) > Q2 (11.6%) > Q1 (8.1%). Stratified sampling across all quartiles beats top-proxy.
- **Coverage guidance:** Temporal grid with proxy-informed block selection beats pure score-based selection.
- **Exploitation at high budgets:** At B≥60, diversity_prefilter (proxy + temporal spread) achieves +30% over top-proxy.
- **Not:** Direct ranking, hard filtering, event detection.

## Q6: Proxy's main risk

- **Proxy-blind positives: 42.5% — a coverage failure for score-only methods**
- **Anti-predictive features:** object_count_mean and near_ego_vehicle_count_max actively mislead
- **Cross-video instability:** Same proxy has opposite direction on different videos
- **Non-monotonic quartile yield:** Q4 has lower positive rate than Q3

## Q7: Proxy's correct role in AQP

1. **Ranking signal:** WRONG. Proxy is too weak (AUROC=0.624) and non-monotonic.
2. **Stratification signal:** CORRECT. Proxy quartiles show meaningful yield variation (8-15%). Each quartile has non-trivial positive rate.
3. **Coverage signal:** CORRECT. Proxy can identify which time blocks may be event-rich, but coverage must be the dominant factor.
4. **Audit signal:** CORRECT. Proxy identifies which regions need auditing (low-score) because 42.5% of positives are there.
5. **Direct event detector:** WRONG. Proxy explicitly cannot replace the VLM oracle.

## Q8: How results support oracle resource saving

- Full scan: 347 calls × 12s = ~70 min GPU
- Best non-oracle at B=80: 80 calls × 12s = ~16 min → **77% oracle saving**
- At B=30: temporal_grid achieves 17.5% recall with 30 calls → **91% oracle saving**
- The saving is real but the recall is modest (~35% at B=80 for best method)

## Q9: How results refute naive top-proxy-only strategy

- At B=80: top_proxy (25%) ≈ random (23.7%) — no meaningful gain
- 42.5% proxy-blind positives — score-only misses nearly half
- Non-monotonic Q4 yield — top quartile is not the best quartile
- Conclusion: top-proxy-only is essentially random with extra compute

## Q10: Impact on AQP algorithm design

1. **Budget decomposition must include temporal coverage** — temporal_grid beats top_proxy at B=30
2. **Budget decomposition must include audit** — 42.5% proxy-blind positives must be found
3. **Proxy exploitation must be secondary** — Q3 > Q4 means rank-based selection is wrong
4. **Cluster-aware design is the key opportunity** — oracle-informed upper bound = 100% event recall at B=30 (vs best non-oracle 59% at B=80)
5. **Adaptive allocation is necessary** — event-rich blocks (36.7%) need more budget than event-sparse blocks (0%)
