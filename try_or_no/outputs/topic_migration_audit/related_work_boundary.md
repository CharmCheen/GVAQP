# Related Work Boundary Check

Based on local notes, reference repos, and the G-ARC Research Report. Paper PDFs are not locally available; conclusions are based on repo-level code and documented descriptions.

---

## Does SUPG only solve frame/record selection?

**YES.** SUPG (refe_repos/supg) operates on individual records (frames). Its `DFDataSource` loads a CSV with `id, label, proxy_score` — one row per record. The `RecallSelector` and `ImportancePrecisionSelector` return a *set of record IDs*, not temporal clips. There is no concept of temporal continuity, clip boundaries, or IoU-based hit semantics.

SUPG's guarantee is: Pr[Recall(R) >= gamma] >= 1-delta for the returned *set* of records. This is a frame-level guarantee, not a clip-level guarantee.

**Conclusion:** SUPG does not solve clip-level queries. G-ARC extends SUPG to clips.

---

## Does ABae mainly solve aggregation with expensive predicates?

**YES.** ABae (refe_repos/abae) solves `SELECT AVG(statistics) WHERE predicate` with expensive predicate evaluation. Its `Records` class takes `proxy_scores, statistics, predicates` — one row per record. The core algorithm allocates oracle budget across strata proportional to `sqrt(p_k) * sigma_k`.

ABae provides confidence intervals for the aggregation estimate, not selection guarantees. There is no clip concept.

**Conclusion:** ABae does not solve clip-level queries. Its aggregation framework could be extended to clip-level aggregation (e.g., AVG(duration) WHERE clip_satisfies_predicate), but this is not done.

---

## Does ARC already solve relevant clip query?

**PARTIALLY.** ARC (SIGIR 2025) is the closest existing work. According to the G-ARC Research Report:

- ARC solves relevant clip queries over large-scale video repositories
- ARC uses proxy pruning + time-domain clustering + adaptive progressive sampling (MAB-UCB) + label propagation
- ARC operates on clips (continuous frame sequences, variable length)

**However, ARC does NOT provide high-probability clip-level guarantees.** ARC's `Conf(C)` is a point estimate of confidence, not a formal guarantee like Pr[Clip-Recall >= gamma] >= 1-delta. The G-ARC report explicitly states: "没有 Pr[Clip-Recall ≥ γ] ≥ 1-δ 式的高概率保证；没有 oracle budget 约束下的 guarantee violation rate 控制"

**Conclusion:** ARC solves the clip query problem but without formal guarantees. G-ARC's contribution is the guarantee, not the clip query itself.

---

## Does ARC provide high-probability clip-level guarantee?

**NO.** ARC provides confidence estimation (Conf(C)) but not high-probability guarantees. The G-ARC report confirms this gap.

**Conclusion:** This is the core gap that G-ARC fills.

---

## Does ARC handle ego-relative geometry and predictive skipping?

**NO.** ARC is designed for general video queries (object detection, activity recognition) with proxy scores. It does not:
- Use ego-relative geometry (in_fov, within_30m, ego_front)
- Predict target states based on ego motion
- Skip oracle calls based on geometric prediction uncertainty

**Conclusion:** The geometry-aware predictive execution (Topic A) is distinct from ARC.

---

## Does Seiden-style temporal interpolation already cover our idea?

**NO.** Seiden (PVLDB 2023) revisits the oracle-proxy architecture in VDBMS but does not:
- Provide clip-level guarantees
- Handle ego-relative geometry
- Use predictive oracle skipping
- Define clip semantics

Seiden is primarily an architecture paper, not an algorithmic contribution.

**Conclusion:** Seiden does not cover our ideas.

---

## Does Spatialyze-style geospatial video query already cover our idea?

**NO.** Spatialyze handles geospatial video queries (find objects in geographic regions) but does not:
- Use ego-relative geometry (it uses absolute geographic coordinates)
- Provide clip-level guarantees
- Use predictive oracle skipping

**Conclusion:** Spatialyze does not cover our ideas.

---

## Summary Table

| Work | Frame Selection | Clip Query | Guarantees | Ego Geometry | Predictive Skipping |
|------|----------------|------------|------------|--------------|---------------------|
| SUPG | YES | NO | Frame-level | NO | NO |
| ABae | NO (aggregation) | NO | CI for aggregation | NO | NO |
| ARC | YES | YES | Confidence only | NO | Partial (MAB) |
| Seiden | YES | NO | NO | NO | NO |
| Spatialyze | YES | NO | NO | Absolute geo | NO |
| G-ARC (proposed) | YES | YES | Clip-level | Ego-relative | YES |

---

## Conclusion

There is a clear gap in the literature:
1. **No existing work provides clip-level high-probability guarantees** (G-ARC fills this)
2. **No existing work uses ego-relative geometry for predictive oracle skipping** (Topic A fills this)
3. **ARC is the closest but lacks guarantees and geometry-awareness**

The two proposed contributions (G-ARC and geometry-aware predictive execution) are complementary and could be combined into a single paper, or pursued separately.
