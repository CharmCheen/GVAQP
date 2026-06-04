# G-ARC Recommendation Memo

## 1. Is G-ARC currently the best main topic?

**Yes.** Among the directions explored:
- Moving-camera / query-impact-aware: small advantage (0.103 F1), parameter-sensitive, not tested on real 3D
- Synthetic clip degradation: strong evidence but not a paper topic by itself
- G-ARC: genuine gap (no clip-level guarantees), strong synthetic evidence (5-20x degradation), best DB venue fit

G-ARC is the only direction with a clear, defensible novelty claim and existing evidence to support it.

## 2. What is the strongest version of the topic?

**Clip-Level Recall Guarantee with IoU-Based Hit Semantics:**

```
Given video V, proxy P, oracle O, budget B, target recall gamma, failure probability delta, IoU threshold theta:
Return clips C_tilde such that Pr[CR(C_tilde) >= gamma] >= 1 - delta
Where CR = clip-level recall with IoU >= theta
```

This is the strongest because:
- It directly extends SUPG's guarantee to clips (natural DB contribution)
- It addresses the genuine gap (ARC has confidence, not guarantees)
- It has a clear formal statement that reviewers can evaluate
- The synthetic evidence (5-20x degradation) directly motivates why frame-level guarantees are insufficient

## 3. What is the safest fallback if guarantee is too hard?

**Clip-Aware AQP without formal guarantee:**

If proving Pr[Clip-Recall >= gamma] >= 1 - delta is too hard, fall back to:
- Empirical clip-level quality metrics (clip recall, mIoU, boundary error)
- Budget-quality curves showing clip-level quality vs oracle budget
- Demonstration that frame-level AQP methods fail at clip level
- A practical algorithm that improves clip-level quality over baselines

This is still a meaningful contribution (no existing work systematically studies clip-level AQP quality), but lacks the theoretical punch of a formal guarantee.

**Title:** "Clip-Aware Approximate Query Processing for Relevant Clips in Video Repositories"

## 4. What is the shortest path to a publishable result?

**8-12 weeks to submission-ready paper:**

| Phase | Duration | Output |
|-------|----------|--------|
| Guarantee formalization | 1-2 weeks | Formal definition, proof sketch |
| Algorithm implementation | 2-3 weeks | Working G-ARC prototype |
| Synthetic validation | 1 week | Guarantee violation rates on synthetic data |
| Real validation (nuScenes) | 1-2 weeks | Guarantee violation rates on real 3D data |
| Paper writing | 2-3 weeks | Full paper draft |

**Critical path item:** The guarantee formalization. If this takes longer than 2 weeks, the project timeline extends.

## 5. What should be discussed with the advisor?

1. **Topic selection:** Present G-ARC as the main topic, with the evidence inventory and related work boundary as justification.

2. **Risk acknowledgment:** The main risk is that the guarantee may be too conservative (requires too many oracle calls) or too hard to prove. The fallback is clip-aware AQP without formal guarantee.

3. **Venue choice:** VLDB or SIGMOD. The clip-level guarantee is a database query processing contribution, not a CV contribution.

4. **Timeline:** 8-12 weeks to submission. Critical dependency on guarantee formalization (Week 1-2).

5. **Data:** nuScenes mini is available and the pipeline is built. No new data downloads needed for the first validation round.

6. **What to NOT do:** Do not continue moving-camera method development. Do not pursue uncertainty-aware semantics (too complex for first paper). Do not pursue anytime/progressive (too incremental).

## 6. What should be done next by coding agents?

**Immediate (this week):**

1. Implement the simplest possible G-ARC algorithm:
   - SUPG-style frame-level importance sampling
   - Nearest-neighbor clip reconstruction
   - Hoeffding-style clip recall lower bound
   - Conservative threshold selection

2. Run on existing synthetic data (smoke_test infrastructure):
   - 100 videos, K=3, tau=30, budget=0.1
   - Measure guarantee violation rate over 5 seeds
   - Compare with uniform, fixed-rate, proxy-threshold baselines

3. Run on nuScenes mini:
   - Use existing query table and baseline infrastructure
   - Measure guarantee violation rate for in_fov, within_30m, ego_front
   - Compare with existing baselines (fixed_rate_k2/k5/k10, linear_interp, const_vel)

**Next week:**

4. Ablation: vary gamma, delta, tau, budget
5. Hard synthetic validation
6. UA-DETRAC validation
7. Compile results and draft paper outline

## 7. What should not be done next?

1. **Do not implement moving-camera methods.** The migration audit recommended G-ARC as main topic. Stop query-impact-aware development.

2. **Do not download new datasets.** nuScenes mini and UA-DETRAC are sufficient for the first validation round.

3. **Do not pursue uncertainty-aware semantics.** Too complex for first paper. Keep as future work.

4. **Do not pursue anytime/progressive.** Too incremental. Keep as follow-up after G-ARC.

5. **Do not overclaim.** The synthetic evidence is strong but not sufficient for a paper. Real-data validation (nuScenes) is required.

6. **Do not spend too long on theory.** If the guarantee formalization takes > 2 weeks, pivot to the fallback (clip-aware AQP without formal guarantee).

---

## Final Judgment

**LOCK G-ARC AS MAIN TOPIC**

Reasons:
1. Genuine gap confirmed (no clip-level high-probability guarantees exist)
2. Strongest existing evidence (5-20x synthetic degradation, audit-validated)
3. Best DB venue fit (VLDB/SIGMOD)
4. Clear formal statement possible (Pr[Clip-Recall >= gamma] >= 1 - delta)
5. Real 3D data pipeline ready (nuScenes mini)
6. Fallback exists if guarantee is too hard (clip-aware AQP without guarantee)

The topic is locked. The next action is implementation and validation, not further exploration.
