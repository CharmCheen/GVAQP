# Topic Recommendation

## Main Topic: B. Clip-Level Guaranteed AQP (G-ARC)

**Rationale:**
1. **Genuine gap confirmed.** No existing work provides high-probability clip-level guarantees. ARC provides confidence estimation but not Pr[Clip-Recall >= gamma] >= 1-delta.
2. **Strongest synthetic evidence.** Clip degradation is 5-20x larger than frame degradation (stable across 240 parameter combinations). This is a real, reproducible phenomenon.
3. **Clear theoretical contribution.** Extending SUPG's guarantees from frame-level to clip-level requires handling non-i.i.d. structure, IoU-based hit semantics, and boundary uncertainty. This is a tractable but meaningful theoretical challenge.
4. **Best DB venue fit.** G-ARC is a natural extension of SUPG (PVLDB 2020) and ABae (PVLDB 2021). The clip-level guarantee is a clear contribution for VLDB/SIGMOD.
5. **Builds on existing assets.** Synthetic experiments (smoke, factorial, hard_synthetic, audit) provide strong evidence. Real data pipeline (nuScenes) exists for validation.

**What must be proven next:**
- Formal guarantee definition and proof
- Real-data validation on nuScenes (clip-level guarantee violation rates)
- Demonstration that guarantees are non-trivial (not satisfied by simple baselines)

---

## Backup Topic: A. Query-Impact-Aware Predictive Execution

**Rationale:**
1. **Real 3D data available.** nuScenes pipeline is complete with ego pose, calibration, 3D boxes, and three ego-relative predicates.
2. **Preliminary advantage shown.** boundary_only_m10 beats fixed_rate by 0.103 F1 on UA-DETRAC 2D.
3. **Complementary to G-ARC.** Could be combined as "geometry-aware clip-level guaranteed AQP."

**Why it's backup, not main:**
1. **Advantage is small and parameter-sensitive.** 0.103 F1 improvement on UA-DETRAC; margin=20 fails.
2. **Factorial ablation suggests limited impact.** Propagation dominates allocation (5x), suggesting allocation tricks (including predictive skipping) have limited value.
3. **Weaker DB venue fit.** More application-specific (driving videos), less general contribution.
4. **Method not yet tested on real 3D data.** Only UA-DETRAC 2D results exist.

**What must be proven next:**
- Query-impact-aware triggering on nuScenes real 3D data
- Demonstration that geometry-aware prediction beats generic temporal prediction
- Robust advantage across queries and parameters

---

## Topic to Avoid: F. Uncertainty-Aware Relevant Clip Semantics

**Rationale:**
1. **Too complex for first paper.** Requires formal uncertainty quantification, soft clip boundaries, probabilistic tau satisfaction.
2. **No existing experiments.** No synthetic or real evidence supports this direction.
3. **Users may prefer hard boundaries.** Soft clip semantics may not be practically useful.
4. **High risk.** May not be publishable as a standalone contribution.

**Keep as future work** after G-ARC is published.

---

## Topic to Keep as Future Work: E. Anytime / Progressive Relevant Clip Query Processing

**Rationale:**
1. **Useful property but not core contribution.** Anytime behavior is an interface/API improvement, not algorithmic novelty.
2. **Can build on G-ARC.** Once G-ARC is solved, anytime extensions are straightforward.
3. **Not enough for standalone paper.** May be too incremental for VLDB/SIGMOD.

**Keep as follow-up** after G-ARC is published.

---

## Summary

| Recommendation | Topic | Rationale |
|----------------|-------|-----------|
| **Main** | B. G-ARC | Genuine gap, strongest evidence, best DB fit |
| **Backup** | A. Query-Impact-Aware | Real 3D data, small advantage, complementary |
| **Avoid** | F. Uncertainty-Aware | Too complex, no evidence, high risk |
| **Future** | E. Anytime | Useful but incremental, build on G-ARC |
