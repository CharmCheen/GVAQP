# Problem Formulations for G-ARC

## Formulation A: Clip-Level Recall Guarantee (Primary)

### Formal Query Definition

```sql
SELECT relevant_clips
FROM video_repository
WHERE duration >= tau
  AND predicate(frame) = TRUE
CLIP RECALL TARGET gamma_r        -- e.g., 0.90
WITH PROBABILITY 1 - delta        -- e.g., 0.95
ORACLE LIMIT B                    -- e.g., 5000 frames
USING proxy_model
IOU THRESHOLD theta               -- e.g., 0.5
```

### Input Data Model
- Video V with T frames: V = {f_1, ..., f_T}
- Proxy model P: frame -> [0, 1] (cheap, noisy)
- Oracle O: frame -> {0, 1} (expensive, ground truth)
- Oracle budget B: max number of oracle calls

### Output Definition
- Set of predicted clips C_tilde = {[s_i, e_i] : s_i <= e_i, e_i - s_i + 1 >= tau}
- Each clip is a contiguous interval of frames where predicate holds

### Quality Target
- Clip-level recall: CR(C_tilde) = |{C in C* : exists C_tilde_i s.t. IoU(C, C_tilde_i) >= theta}| / |C*|
- Where C* is the set of ground-truth relevant clips

### Oracle Budget Model
- Hard constraint: total oracle calls <= B
- B is specified by the user as a fraction of total frames or absolute count

### Guarantee
- **Pr[CR(C_tilde) >= gamma_r] >= 1 - delta**
- Over the randomness of the sampling strategy

### Strongest Baseline
- ARC (proxy pruning + MAB sampling + label propagation, no guarantee)
- SUPG-style frame selection applied naively to clips (guaranteed to fail)
- Fixed-rate oracle sampling with nearest-neighbor reconstruction

### Feasibility
- **High.** The guarantee formulation is natural. The main challenge is designing an estimator for clip-level recall that accounts for temporal dependence. Existing tools (Hoeffding, conformal prediction) may be adapted.
- Existing synthetic infrastructure can validate the guarantee violation rate.
- nuScenes real 3D data can validate on real driving scenes.

### Risk
- **Medium.** The theoretical challenge is real but tractable. The main risk is that the guarantee may be too conservative (requires too many oracle calls) to be practical.

---

## Formulation B: Segment-Aware Sampling with Recall Lower Bound

### Formal Query Definition

Instead of sampling individual frames, sample temporal windows/segments and estimate clip-level recall from segment-level observations.

```
Input: Video V, proxy P, oracle O, budget B, window size W, stride S
Output: Set of clips C_tilde with estimated recall lower bound R_lb
Goal: R_lb <= CR(C_tilde) with probability >= 1 - delta
```

### Input Data Model
- Same as Formulation A, plus window size W and stride S parameters

### Output Definition
- Set of predicted clips C_tilde
- Estimated recall lower bound R_lb (conservative estimate of true recall)

### Quality Target
- R_lb is a valid lower bound: Pr[R_lb <= CR(C_tilde)] >= 1 - delta
- Maximize |C_tilde| subject to the guarantee

### Oracle Budget Model
- Budget B is allocated across windows, not individual frames
- Each window costs 1 oracle call (or proportional to window size)

### Guarantee
- **Pr[R_lb <= CR(C_tilde)] >= 1 - delta**
- The lower bound is valid with high probability

### Strongest Baseline
- Frame-level SUPG applied to each window independently
- Uniform window sampling

### Feasibility
- **Medium.** Window-level sampling reduces the problem to a smaller number of correlated samples. The challenge is accounting for within-window correlation and cross-window dependence.
- May be easier to prove guarantees for window-level quantities than frame-level.

### Risk
- **Medium-high.** The window abstraction may lose important boundary information. If a clip boundary falls within a window, the window-level oracle may not capture it precisely.

---

## Formulation C: Boundary-Aware Refinement with Guarantee

### Formal Query Definition

Use oracle calls specifically to refine uncertain clip boundaries, reducing mIoU and boundary error risk.

```
Input: Candidate clips C_0 (from proxy), oracle O, budget B
Output: Refined clips C_tilde with boundary guarantee
Goal: Pr[max boundary error <= epsilon] >= 1 - delta
```

### Input Data Model
- Initial candidate clips C_0 from proxy pruning (e.g., ARC-style)
- Oracle O for boundary refinement
- Budget B for oracle calls

### Output Definition
- Refined clips C_tilde with tighter boundaries
- Boundary error: max(|s_i - s_i*|, |e_i - e_i*|) for matched clips

### Quality Target
- Boundary error bounded: Pr[max boundary error <= epsilon] >= 1 - delta
- Or: Pr[mIoU >= gamma] >= 1 - delta

### Oracle Budget Model
- Budget B allocated to boundary-critical frames (frames near candidate boundaries)
- Interior frames assumed correct (not sampled)

### Guarantee
- **Pr[max boundary error <= epsilon] >= 1 - delta**
- Or: **Pr[mIoU >= gamma] >= 1 - delta**

### Strongest Baseline
- Uniform frame sampling + nearest-neighbor reconstruction
- ARC with full oracle refinement

### Feasibility
- **Medium.** The boundary-focused allocation is intuitive. The challenge is formalizing the relationship between boundary oracle density and mIoU guarantee.
- May require assumptions about boundary smoothness or transition rates.

### Risk
- **Medium.** If clip boundaries are very noisy (rapid transitions), the guarantee may require oracle calls at nearly every frame. The guarantee may be too conservative in practice.

---

## Formulation D: Conservative Clip Retrieval with Guaranteed Recall

### Formal Query Definition

Return a superset of relevant clips with guaranteed recall lower bound, while controlling precision empirically.

```
Input: Video V, proxy P, oracle O, budget B, recall target gamma
Output: Set of candidate clips C_tilde (superset)
Goal: Pr[CR(C_tilde) >= gamma] >= 1 - delta AND minimize |C_tilde|
```

### Input Data Model
- Same as Formulation A

### Output Definition
- Superset of relevant clips (conservative: may include false positives)
- Minimize the number of returned clips subject to recall guarantee

### Quality Target
- Clip-level recall guaranteed: Pr[CR(C_tilde) >= gamma] >= 1 - delta
- Clip-level precision optimized (not guaranteed): minimize false positives

### Oracle Budget Model
- Hard constraint: total oracle calls <= B

### Guarantee
- **Pr[CR(C_tilde) >= gamma] >= 1 - delta**
- Precision is empirical (not guaranteed)

### Strongest Baseline
- Return all frames as clips (perfect recall, terrible precision)
- SUPG frame-level selection + clip construction

### Feasibility
- **High.** This is the most conservative formulation. The recall guarantee is the primary objective, and precision is optimized separately.
- Closest to SUPG's recall-target formulation.
- Easier to prove guarantees because we only need to bound false negatives, not false positives.

### Risk
- **Low-medium.** The guarantee is achievable. The risk is that the method may return too many clips (low precision) to achieve high recall, making it impractical.

---

## Recommendation

**Formulation A (Clip-Level Recall Guarantee) is the primary target.** It is the most natural extension of SUPG to clips, provides the strongest contribution, and has the clearest novelty.

**Formulation D (Conservative Clip Retrieval) is the safest fallback.** If proving Formulation A's guarantee is too hard, Formulation D is easier (only recall guarantee, no precision guarantee) and still provides a meaningful contribution.

**Formulation C (Boundary-Aware Refinement) can be a component** of Formulation A, not a standalone formulation.

**Formulation B (Segment-Aware Sampling) is an alternative** if frame-level sampling proves too difficult to analyze theoretically.
