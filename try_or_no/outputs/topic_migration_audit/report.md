# Research Topic Migration Audit: Final Report

## 1. Is the current query-impact-aware predictive execution direction the best topic?

**No.** The current direction (Query-Impact-Aware Predictive Execution) has preliminary evidence but is not the strongest topic:

- The advantage on UA-DETRAC 2D is small (0.103 F1) and parameter-sensitive
- The factorial ablation shows propagation dominates allocation (5x effect size), suggesting allocation tricks have limited impact
- The method has not been tested on real 3D data (nuScenes)
- The DB venue fit is moderate — more application-specific than general

**G-ARC (Clip-Level Guaranteed AQP) is stronger** because:
- It fills a genuine gap in the literature (no existing work provides clip-level high-probability guarantees)
- It has the strongest synthetic evidence (clip degradation 5-20x larger than frame, stable across 240 combinations)
- It has the best DB venue fit (natural extension of SUPG/ABae)
- It has clear theoretical contribution (extending guarantees from frame to clip)

## 2. Is it better than G-ARC / clip-level guaranteed AQP?

**No.** G-ARC is stronger on all criteria except data readiness:

| Criterion | G-ARC | Query-Impact-Aware |
|-----------|-------|-------------------|
| Novelty | 8/10 | 6/10 |
| Evidence strength | Strong synthetic | Weak real (small advantage) |
| DB venue fit | Strong (VLDB/SIGMOD) | Moderate |
| Theoretical depth | High (guarantee design) | Low (engineering) |
| Risk | Moderate | High |

## 3. Is it too close to Spatialyze / Seiden / ARC?

**No for G-ARC.** G-ARC is clearly distinct:
- ARC provides confidence estimation, not high-probability guarantees
- Spatialyze handles geospatial queries, not ego-relative geometry
- Seiden is an architecture paper, not an algorithmic contribution
- None provide clip-level guarantees with oracle budget constraints

**Partially for Query-Impact-Aware.** The predictive execution idea is more novel but the geometry-aware aspect overlaps with autonomous driving perception literature.

## 4. Is it too much like tracking rather than query processing?

**No for G-ARC.** G-ARC is fundamentally a query processing problem: given a clip query with budget constraints, return clips with quality guarantees. The tracking aspect (predicting target states) is a means to an end, not the contribution.

**Partially for Query-Impact-Aware.** The predictive execution direction does resemble tracking (predicting target states over time). The contribution must be clearly framed as query processing, not tracking.

## 5. What must be proven next to make it a credible paper?

**For G-ARC (main recommendation):**
1. Formal clip-level guarantee definition: Pr[Clip-Recall >= gamma] >= 1-delta
2. Algorithm design extending SUPG's importance sampling to clips
3. Real-data validation on nuScenes (clip-level guarantee violation rates)
4. Demonstration that guarantees are non-trivial (simple baselines violate them)
5. Comparison with ARC's confidence-based approach

**For Query-Impact-Aware (backup):**
1. Implement query-impact-aware triggering on nuScenes real 3D data
2. Show robust advantage across queries and parameters
3. Ablation of each component (boundary, staleness, disagreement)
4. Demonstrate that geometry-aware prediction beats generic temporal prediction

## 6. What is the shortest path to a publishable topic?

**G-ARC has the shortest path:**

1. **Formalize the guarantee** (1-2 weeks): Define clip-level recall guarantee, extend SUPG's sampling bounds to clips
2. **Implement the algorithm** (2-3 weeks): Importance sampling for clips, conservative threshold selection
3. **Validate on synthetic data** (1 week): Use existing smoke/factorial/hard_synthetic infrastructure
4. **Validate on nuScenes** (1-2 weeks): Use existing query table and baseline infrastructure
5. **Write the paper** (2-3 weeks): Novelty is clear, evidence is strong

**Total: ~8-12 weeks to submission-ready paper**

For Query-Impact-Aware, the path is longer because the method must be designed, implemented, and shown to work on real 3D data — and the advantage must be robust enough to constitute a paper.

## 7. What should we tell the advisor as the current proposed topic?

**Proposed topic:** Clip-Level Guaranteed Approximate Query Processing for Relevant Clips in Video Repositories (G-ARC)

**One-paragraph pitch:**
We propose G-ARC, a framework for answering relevant clip queries over large-scale video repositories with high-probability guarantees. Existing AQP methods (SUPG, ABae) provide frame-level guarantees, but clip-level queries introduce temporal dependencies and boundary uncertainty that break frame-level assumptions. Our synthetic experiments show that clip-level degradation is 5-20x larger than frame-level degradation, stable across 240 parameter combinations. We extend SUPG's importance sampling framework to handle clip semantics, providing guarantees of the form Pr[Clip-Recall >= gamma] >= 1-delta under oracle budget constraints. We validate on both synthetic data and real driving video data (nuScenes), demonstrating that clip-level guarantees are non-trivially achievable and that simple baselines (fixed-rate, uniform) violate them under realistic conditions.

**Key differentiators from existing work:**
- ARC (SIGIR 2025): confidence estimation, not high-probability guarantees
- SUPG (PVLDB 2020): frame-level only, clips are not i.i.d.
- ABae (PVLDB 2021): aggregation, not selection/clip queries

**Venue:** VLDB or SIGMOD (database systems / AQP)

---

## Final Judgment

**MIGRATE TO G-ARC / CLIP GUARANTEE**

The current query-impact-aware predictive execution direction has weak evidence (small advantage, parameter-sensitive, not tested on real 3D data). G-ARC has stronger evidence (synthetic degradation confirmed), a clearer gap in the literature (no clip-level guarantees exist), and a better fit for database venues.

The migration is justified because:
1. G-ARC addresses a genuine gap (clip-level guarantees)
2. G-ARC has stronger evidence (5-20x degradation, stable across 240 combinations)
3. G-ARC has better DB venue fit
4. G-ARC has a clearer theoretical contribution
5. The existing synthetic infrastructure (smoke, factorial, hard_synthetic, audit) directly supports G-ARC
6. The nuScenes real 3D pipeline can be reused for G-ARC validation

**The query-impact-aware direction should be kept as a backup** — it could be combined with G-ARC as "geometry-aware clip-level guaranteed AQP" if the nuScenes experiments show meaningful advantage.
