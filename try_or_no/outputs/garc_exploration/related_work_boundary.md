# Related Work Boundary Audit for G-ARC

Based on: local reference repos (supg, abae), G-ARC_Research_Report.md, topic_migration_audit, and existing experiment outputs. Paper PDFs are not locally available; conclusions rely on repo code and documented descriptions.

---

## 1. What does SUPG guarantee?

**Source:** `refe_repos/supg/` code + G-ARC_Research_Report

- **Scope:** Frame / record-level selection. `DFDataSource` loads CSV with `id, label, proxy_score` — one row per record. `RecallSelector.select()` returns a set of record IDs.
- **Guarantee type:** High-probability recall and precision targets.
  - Recall target: Pr[Recall(R) >= gamma] >= 1 - delta
  - Precision target: Pr[Precision(R) >= gamma] >= 1 - delta
- **Mechanism:** Importance sampling with sqrt(proxy) weights, Hoeffding-style confidence bounds on threshold selection, conservative threshold adjustment.
- **Can it directly apply to clips?** **NO.** Five fundamental obstacles:
  1. **Clips are not i.i.d.** Adjacent frames within a clip are correlated. SUPG's CLT/Hoeffding arguments assume independence.
  2. **Frame recall != clip recall.** 90% frame recall can yield 0% clip recall if boundary frames are missed (IoU drops below threshold).
  3. **Frame precision != clip precision.** A few wrong frames in a candidate clip can flip IoU from hit to miss.
  4. **Clip boundary uncertainty.** Boundary frames have inherent ambiguity that SUPG does not model.
  5. **Non-monotonic merge/split.** Adding an oracle-labeled frame can merge or split clips, violating the monotonicity assumption in threshold selection.

**Conclusion:** SUPG provides frame-level guarantees that do NOT transfer to clip-level. This is the core gap G-ARC fills.

---

## 2. What does ABae guarantee or estimate?

**Source:** `refe_repos/abae/` code + G-ARC_Research_Report

- **Scope:** Aggregation queries (AVG, SUM, COUNT) over records with expensive predicates.
- **Guarantee type:** Confidence intervals on the aggregation estimate. Uses bootstrap for CI computation.
- **Mechanism:** Proxy-based stratification, pilot sampling per stratum, optimal budget allocation proportional to sqrt(p_k * sigma_k), Horvitz-Thompson estimation.
- **Can it apply to relevant clip retrieval?** **NO.** Three obstacles:
  1. **Clip discovery is stochastic.** The number and boundaries of clips depend on oracle results. ABae assumes a fixed, enumerable dataset.
  2. **Temporal dependence.** Clips are not i.i.d.; ABae's stratified i.i.d. sampling does not apply.
  3. **Stochastic clip size.** Clip length depends on consecutive oracle results, making effective sample size a random variable.

**Conclusion:** ABae does not solve clip queries. Its aggregation framework could be extended to clip-level aggregation (e.g., AVG(duration) WHERE clip_satisfies_predicate), but this requires new theory.

---

## 3. What does ARC solve?

**Source:** G-ARC_Research_Report (SIGIR 2025, Yue Chen et al.)

ARC solves **relevant clip queries** over large-scale video repositories:
- **Proxy pruning:** Use cheap proxy model to score frames and prune unlikely candidates.
- **Time-domain clustering:** Group consecutive high-scoring frames into candidate clips.
- **Adaptive progressive sampling (MAB-UCB):** Use multi-armed bandit to prioritize which frames to label with the oracle.
- **Label propagation:** Propagate oracle labels to unlabeled frames within clips.
- **Confidence estimation:** Compute Conf(C) for each candidate clip as a point estimate of quality.

**What ARC does NOT provide:**
- No high-probability guarantee (no Pr[Clip-Recall >= gamma] >= 1-delta)
- No oracle budget constraint with controlled violation rate
- No formal relationship between confidence and guarantee

---

## 4. Does ARC provide true high-probability clip-level guarantee?

**NO.**

ARC's confidence Conf(C) is defined as:
```
Conf(C_tilde) = E_{C_tilde_i in C_tilde} [ P(exists C_j s.t. IoU >= theta) ]
```

This is an **expected precision point estimate**, not a high-probability guarantee.

Key differences from a true guarantee:
- Conf(C) = 0.92 does NOT mean "with 95% probability, clip-level precision >= 0.9"
- ARC does not control guarantee violation rate: Pr[Clip-Recall < gamma] is not bounded
- ARC's experiments show performance degradation when proxy reliability is biased (taipei-hires), confirming that confidence estimates are not robust guarantees
- ARC uses soft budget constraints, not hard oracle limits

**Conclusion:** ARC's confidence is fundamentally different from SUPG-style guarantees. This is the core gap.

---

## 5. Are ARC's confidence estimates equivalent to statistical guarantees?

**NO.** The distinction is:

| Property | ARC Confidence | SUPG-Style Guarantee |
|----------|---------------|---------------------|
| Type | Point estimate (E[Precision]) | Probabilistic bound (Pr[Quality >= gamma] >= 1-delta) |
| Controls violation rate? | No | Yes |
| Robust to proxy bias? | No (degrades on taipei-hires) | Yes (by construction) |
| Relationship to true quality | Expected value (may be biased) | Lower bound with failure probability |

---

## 6. Do Seiden / Spatialyze already solve clip-level guaranteed AQP?

**NO.**

**Seiden (PVLDB 2023):**
- Revisits oracle-proxy architecture in VDBMS
- Architecture/systems paper, not algorithmic
- No clip semantics, no guarantees, no temporal reasoning
- **Does not solve clip-level guaranteed AQP**

**Spatialyze:**
- Geospatial video queries over geographic regions
- Uses absolute coordinates, not ego-relative geometry
- No clip guarantees, no oracle budget constraints
- **Does not solve clip-level guaranteed AQP**

**ExSample (ICDE 2022):**
- MAB-based frame sampling for video search
- No clip concept, no guarantees
- Goal is finding K matching frames, not clip-level quality

**BARGAIN (SIGMOD 2026):**
- Upgrades SUPG's asymptotic guarantees to finite-sample (e-values, conformal p-values)
- Most relevant method reference for G-ARC
- But operates on i.i.d. text records, not temporal clips

---

## Summary

| Work | Frame Selection | Clip Query | High-Prob Guarantee | Oracle Budget | IoU Hit |
|------|:-:|:-:|:-:|:-:|:-:|
| SUPG | Yes | No | Yes (frame-level) | Yes | No |
| ABae | No (agg) | No | CI (aggregation) | Yes | No |
| ARC | Yes | Yes | **No** (confidence only) | Soft | Yes |
| Seiden | Yes | No | No | No | No |
| Spatialyze | Yes | No | No | No | No |
| BARGAIN | Yes | No | Yes (frame-level, finite-sample) | Yes | No |
| **G-ARC** | **Yes** | **Yes** | **Yes (clip-level)** | **Hard** | **Yes** |

**Genuine gap confirmed:** No existing work combines clip-level high-probability guarantees, IoU-based hit semantics, and oracle budget constraints.
