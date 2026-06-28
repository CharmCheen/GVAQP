# Stage 4: Full-Reference AQP Structure Analysis

---

## 4.1 Selectivity

| time block | n anchors | positives | rate |
|---|---|---|---|
| 300-600s | 30 | 2 | 6.7% |
| 600-900s | 30 | 5 | 16.7% |
| 1200-1500s | 30 | 3 | 10.0% |
| 1500-1800s | 30 | 11 | **36.7%** |
| 1800-2100s | 30 | 4 | 13.3% |
| 2100-2400s | 30 | 3 | 10.0% |
| 2400-2700s | 30 | 4 | 13.3% |
| 2700-3000s | 30 | 4 | 13.3% |
| 3000-3300s | 30 | 3 | 10.0% |
| 3300-3600s | 17 | 1 | 5.9% |

**Selectivity is non-uniform.** The 1500-1800s block has 36.7% positive rate (event-rich), while 300-600s and 3300-3600s have ~6% (event-sparse). This means a uniform temporal grid will waste budget on sparse blocks and under-allocate to rich blocks.

**AQP implication:** Adaptive allocation that discovers event-rich blocks early and reallocates budget to them is necessary. This is the motivation for the CFA (Cluster-First Adaptive) algorithm.

**Comparison to realcartest:** realcartest V13.8 had 23.6% overall positive rate with less extreme block variation. dataset3 has 11.5% overall with a 36.7% peak block — more heterogeneous.

---

## 4.2 Temporal Correlation

| metric | value |
|---|---|
| P(1→1) | 0.325 |
| base rate | 0.115 |
| correlation ratio | 2.83× |
| transitions 1→1 | 13 |
| transitions 1→0 | 27 |
| transitions 0→1 | 27 |
| transitions 0→0 | 279 |

**Positive labels are 2.83× more likely to be followed by another positive than the base rate.** This confirms temporal clustering — positives cluster in event-rich segments.

**Comparison to realcartest:** realcartest had P(1→1)=0.457 vs base 0.236 (1.94×). dataset3 has 2.83× — stronger temporal clustering despite lower base rate.

**AQP implication:** The i.i.d. assumption in SUPG is violated 2.8×. Statistical guarantees must account for this correlation. Temporal NMS and cluster-aware selection are justified by this structure.

---

## 4.3 Positive Clusters

| metric | value |
|---|---|
| total clusters | 27 |
| singleton clusters | 18 (66.7%) |
| multi-anchor clusters | 9 (33.3%) |
| largest cluster | 9 anchors (0171-0179, 85s) |

**Cluster distribution:**
- 18 singletons (isolated positives) — these are the hardest to find with budgeted AQP
- 5 two-anchor clusters (15s each)
- 1 three-anchor cluster
- 1 nine-anchor cluster (the 1500-1800s event-rich block)

**Largest cluster (0171-0179):** 9 consecutive positive anchors spanning 85 seconds, mixed pedestrian=7/cyclist=2. This is a busy intersection with continuous crosswalk activity. Any method that hits one anchor in this cluster will likely hit the cluster — but the question is whether the method can afford to expand.

**Event stitching:** With 40 positive anchors forming 27 clusters, the stitching compression is 40→27 (1.48:1). On realcartest, 94 positives → 51 stitched events (1.84:1). The lower compression on dataset3 means more isolated events.

**AQP implication:** The 66.7% singleton rate means cluster expansion alone won't find all events. Coverage and audit are necessary for singletons.

---

## 4.4 Hard Negatives

| category | count | description |
|---|---|---|
| high_score + normal_following | 76 | dense traffic, high proxy score, no event |
| high_score + no_interaction | 56 | visible objects, high score, no ego-path entry |
| dense_traffic (above median count) | 87 | high object count, normal following |

**Hard negatives are the budget waste.** 77 high-score negatives (top quartile) consume oracle budget without yielding positives. 87 dense-traffic negatives show that object count is anti-predictive: more vehicles → normal following, not ego-path intrusion.

**AQP implication:** The 77 high-score negatives are the "proxy trap" — any score-based method wastes budget on them. The DCA algorithm's audit component is designed to escape this trap by examining low-score regions.
