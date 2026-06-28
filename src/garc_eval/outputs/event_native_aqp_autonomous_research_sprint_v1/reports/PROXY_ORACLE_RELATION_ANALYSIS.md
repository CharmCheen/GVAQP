# Proxy-Oracle Relationship Analysis

**Core question:** Can cheap proxy signals predict semantic event oracle labels? If not, what is the proxy's correct role in AQP?

---

## 1. Proxy Predictive Power (AUROC/AUPRC)

| proxy feature | AUROC | AUPRC | interpretation |
|---|---|---|---|
| score_fusion_geometry_motion | 0.624 | 0.169 | weak positive predictor |
| motion_energy_mean | 0.607 | 0.138 | weak positive predictor |
| score_fusion_yolo_motion | 0.586 | 0.128 | weak positive predictor |
| score_fusion_ego_lateral | 0.574 | 0.129 | barely above random |
| object_count_mean | 0.052 | 0.209 | **anti-predictive** (high count → negative) |
| near_ego_vehicle_count_max | 0.014 | 0.108 | **strongly anti-predictive** |

**Critical finding:** `object_count_mean` (the best single feature on realcartest, AUC=0.738) is **anti-predictive** on dataset3 (AUROC=0.052). Dense traffic (high object count) predicts NEGATIVE, not positive. This is because dataset3's positives are pedestrian/cyclist crossings in less dense traffic, while dense traffic is normal following.

**Cross-video proxy instability:** The same proxy feature has opposite predictive direction on two videos. This is a fundamental AQP finding: **proxy quality is workload-dependent, not fixed.** A budget allocation policy that assumes "high proxy score → high event probability" will fail on dataset3.

---

## 2. Proxy Quartile Positive Rate

| quartile | n | positives | rate |
|---|---|---|---|
| Q1 (low score) | 86 | 7 | 8.1% |
| Q2 | 86 | 10 | 11.6% |
| Q3 | 86 | 13 | 15.1% |
| Q4 (high score) | 89 | 10 | 11.2% |

**The positive rate is NOT monotonically increasing with proxy score.** Q3 has the highest rate (15.1%), but Q4 drops to 11.2% (below Q2). This means top-proxy selection (Q4) wastes budget on dense-traffic negatives while missing Q3 positives.

---

## 3. Top-k Positive Yield vs Random

| budget B | top_proxy positives | recall | random mean | random recall | advantage |
|---|---|---|---|---|---|
| 10 | 3 | 7.5% | 1.1 | 2.7% | +4.8% |
| 20 | 4 | 10.0% | 2.3 | 5.7% | +4.3% |
| 40 | 6 | 15.0% | 4.4 | 11.1% | +3.9% |
| 80 | 10 | 25.0% | 9.2 | 22.9% | +2.1% |
| 150 | 19 | 47.5% | 17.1 | 42.8% | +4.7% |

**Top-proxy advantage over random is marginal and shrinks at higher budgets.** At B=80, top-proxy recall (25%) is barely above random (22.9%). This is because the proxy AUROC is only 0.624 — weak signal that barely beats random.

**Comparison to realcartest:** On realcartest V13.9, top-proxy at B=40 had recall ~0.216 with AUC=0.738. On dataset3, top-proxy at B=40 has recall 0.15 with AUC=0.624. The weaker proxy makes top-proxy selection less effective.

---

## 4. High-Score Negatives (Proxy False Alarms)

77 high-score negatives (top quartile score, negative label):
- normal_following: 48 (dense traffic, no event)
- no_ego_path_interaction: 29 (objects visible but no ego-path entry)

**These are the budget-wasting anchors.** Top-proxy selection spends oracle calls on these 77 dense-traffic negatives, missing the 17 low-score positives.

---

## 5. Low-Score Positives (Proxy Misses)

17 positives have below-median proxy score. Examples:
- anchor 0128: score=-1.859, pedestrian (crosswalk in sparse traffic)
- anchor 0129: score=-2.023, pedestrian
- anchor 0132: score=-0.975, vehicle
- anchor 0161: score=-1.401, pedestrian
- anchor 0164: score=-0.368, cyclist

**These are the proxy-blind positives.** Any policy that only examines high-score anchors will miss these 17/40 = 42.5% of all positives. This is a severe coverage failure.

---

## 6. Proxy's Correct Role in AQP

Given these findings, the proxy's role is NOT direct ranking. The correct roles are:

1. **Candidate generation (weak):** Proxy can narrow the search space, but with AUROC=0.624, it misses 42.5% of positives. Using proxy as a hard filter would lose nearly half the events.

2. **Stratification (better):** Proxy can stratify anchors into score bands, but the non-monotonic quartile positive rate means each stratum has meaningful event probability. Stratified sampling across strata is better than top-proxy.

3. **Coverage control (best):** Proxy can identify "interesting" time blocks (not individual anchors), but temporal coverage is more important than score-based selection. The temporal grid method outperforms top-proxy at B=30.

4. **Audit sampling (complementary):** Low-score strata must be audited because 42.5% of positives are there. An audit-aware policy that reserves budget for low-score exploration is necessary.

5. **NOT direct ranking:** Top-proxy selection wastes budget on dense-traffic negatives and misses low-score positives. This is the core proxy-oracle mismatch.

---

## 7. Comparison to SUPG / ABae / ARC Proxy Usage

| system | proxy role | assumption | holds on dataset3? |
|---|---|---|---|
| SUPG | proxy filters for oracle call | proxy AUROC > 0.7 | NO (AUROC=0.624) |
| ABae | proxy strata for adaptive sampling | proxy stratifies by yield | PARTIALLY (non-monotonic) |
| ARC | proxy for adaptive reduction | proxy correlates with target | WEAKLY |
| Our approach | proxy for coverage + audit | proxy is weak, use for stratification not ranking | YES |

**Key distinction:** SUPG/ABae assume the proxy is a reasonably good ranker (AUROC > 0.7). Our setting has AUROC=0.624, where the proxy is barely better than random and anti-predictive for some features. This requires a different AQP design: coverage-first, not score-first.
