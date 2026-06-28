# CORRECTIONS.md — Tuning/Pilot Overlap Audit & Report Correction Patch

**Date**: 2026-06-27
**Status**: `OVERLAP_MATERIAL_RESULT_INVALID` — corrective action required

---

## Task 1: Tuning Set vs 123-Pilot Overlap

### 1.1 Tuning sets identified

| Tuning set | File | N | Pos | Neg | Used to select |
|------------|------|---|-----|-----|----------------|
| GLM tuning | `test_sets/glm_test_small.csv` | 15 | 10 | 5 | `BEST_glm_final.md` (v1_lower_threshold, F1=0.706) |
| Qwen tuning | `test_sets/qwen_test_small.csv` | 10 | 2 | 8 | `BEST_qwen_final.md` (v3_two_step, F1=0.571) |
| Combined (union) | — | 23 | 12 | 11 | — |

Note: `glm_test_set.csv` (38 anchors, larger) was also found but `glm_test_small.csv` is the actual set used for prompt selection per PROMPT_TUNING_REPORT.md. The GLM v1-v3 raw_outputs directories contain exactly the 15 anchors from glm_test_small.csv (plus anchors 0187 and 0320 which are in glm_test_small but NOT in glm_test_set — confirming glm_test_small is NOT a subset of glm_test_set; they are disjoint or partially overlapping selection sets).

### 1.2 Overlap results

| Intersection | Count | % of 123-pilot | % of tuning |
|---|---|---|---|
| GLM tuning ∩ 123-pilot | 15/15 | 12.2% | 100.0% |
| Qwen tuning ∩ 123-pilot | 10/10 | 8.1% | 100.0% |
| **Combined ∩ 123-pilot** | **23/23** | **18.7%** | **100.0%** |

All 23 unique tuning anchors appear in the 123-pilot. ZERO tuning anchors are held-out from the pilot.

### 1.3 Positive enrichment in overlap

- Overlap Qwen-positive rate: **12/23 = 52.2%**
- 123-pilot base positive rate: 40/123 = 32.5%
- **Overlap is 1.6x enriched in Qwen-positives**

### 1.4 Individual overlap anchors in pilot

```
center10_anchor_0068: is_pos=True  glm_pred=negative [GLM]
center10_anchor_0075: is_pos=True  glm_pred=positive [Qwen]
center10_anchor_0129: is_pos=True  glm_pred=positive [GLM]
center10_anchor_0147: is_pos=False glm_pred=positive [Qwen]       ← Qwen tuning FN (GLM FP)
center10_anchor_0161: is_pos=True  glm_pred=positive [GLM]
center10_anchor_0171: is_pos=True  glm_pred=negative [GLM]        ← GLM tuning FN
center10_anchor_0172: is_pos=True  glm_pred=positive [GLM]
center10_anchor_0175: is_pos=True  glm_pred=positive [GLM]
center10_anchor_0182: is_pos=False glm_pred=negative [GLM]
center10_anchor_0183: is_pos=True  glm_pred=negative [GLM]        ← GLM tuning FN
center10_anchor_0187: is_pos=False glm_pred=negative [GLM]
center10_anchor_0213: is_pos=False glm_pred=positive [Qwen]       ← Qwen tuning FN (GLM FP)
center10_anchor_0227: is_pos=False glm_pred=negative [Qwen]
center10_anchor_0230: is_pos=False glm_pred=positive [GLM Qwen]   ← in BOTH tuning sets
center10_anchor_0246: is_pos=True  glm_pred=positive [GLM]
center10_anchor_0251: is_pos=False glm_pred=negative [Qwen]
center10_anchor_0254: is_pos=True  glm_pred=positive [GLM]
center10_anchor_0317: is_pos=True  glm_pred=negative [GLM]        ← GLM tuning FN
center10_anchor_0320: is_pos=False glm_pred=negative [GLM]
center10_anchor_0325: is_pos=True  glm_pred=positive [Qwen]
center10_anchor_0341: is_pos=False glm_pred=negative [GLM Qwen]   ← in BOTH tuning sets
center10_anchor_0342: is_pos=False glm_pred=parse_error [Qwen]
center10_anchor_0345: is_pos=False glm_pred=negative [Qwen]
```

Key: `[GLM]` = in GLM tuning set only, `[Qwen]` = in Qwen tuning set only, `[GLM Qwen]` = in both.

### 1.5 Sensitivity: Key metrics WITHOUT overlap

| Metric | With overlap (original) | Without overlap (N=100) | Δ |
|--------|------------------------|-------------------------|---|
| GLM positive bin Qwen-pos rate | 61.5% (24/39) | 57.1% (16/28) | −4.4pp |
| GLM recall of Qwen-positives | 60.0% (24/40) | 57.1% (16/28) | −2.9pp |
| GLM precision | 61.5% (24/39) | 57.1% (16/28) | −4.4pp |
| GLM F1 | 0.608 | ~0.571 | −0.037 |

### 1.6 Verdict

**`OVERLAP_MATERIAL_RESULT_INVALID`**

Diagnosis:
1. **18.7% > 10%** → MATERIAL by proportion criterion
2. **52.2% > 32.5%** → overlap enriched in Qwen-positives (confirms tuning bias)
3. **Δ = 4.4pp > 3pp** → sensitivity check shows substantive impact on positive bin rate

**Consequences for current conclusions:**
- The 61.5% GLM positive bin rate, 60% recall, +45pp recall lift, and all Phase 3 cascade numbers are inflated by prompt tuning overlap
- These metrics contain up to ~4.4pp of "familiarity bias" from the 23 training anchors
- They CANNOT be reported as pure held-out performance
- A proper held-out evaluation requires a genuinely disjoint test set (the current 123-pilot minus the 23 overlap anchors = N=100 clean pilot, but the task instructions say "不需要现在重新跑实验")

**What survives:**
- The **direction** of the boost (GLM > L3) is likely real — even without overlap, GLM positive bin rate is 57.1% vs L3's 15.0% at B=40
- The relative ranking of strategies is unchanged
- The **qualitative finding** that GLM enriches Qwen-positives beyond L3 proxy holds post-correction

**What must be caveated:**
- All absolute numbers (recall, precision, F1) should be reported as "upper bound (possibly inflated by tuning overlap)" until clean validation
- The 4.4pp sensitivity gap is the best estimate of overlap inflation
- The final decision label `USE_GLM_AS_BOOSTER` remains directionally correct but weaker post-correction

---

## Task 2: 3.3x Calculation Error

### Error location
`CASCADE_STRATEGY_REPORT.md` line 107:
> GLM positive bin has 61.5% Qwen-positive rate (3.3x the base rate of 32.5%)

### Correct calculation

| Metric | Value | Derivation |
|--------|-------|------------|
| GLM positive bin Qwen-pos rate | 61.5% | 24 TP / 39 in GLM positive bin |
| 123-pilot base rate | 32.5% | 40 pos / 123 total |
| **Enrichment over base** | **1.89x** | 61.5 / 32.5 |
| GLM pos bin rate / L3 B=40 precision | **4.10x** | 61.5 / 15.0 |
| GLM pos bin rate / L3 B=60 precision | **2.84x** | 61.5 / 21.7 |

The "3.3x" value does not correspond to any of these valid computations. It may have come from an erroneous intermediate step. The correct enrichment over base rate is **1.89x**.

### Additional error in same paragraph
Line 118 references "positive yield per Qwen call from ~17% to ~62%" — the 17% comes from L3 baseline precision at approximately B≈50 (interpolated). At small budgets the contrast is even larger (L3 B=30 precision = 16.7%, GLM = 61.5% → 3.68x).

### Correction applied
See appended correction block in CASCADE_STRATEGY_REPORT.md.

---

## Summary of Actions

| Action | Status |
|--------|--------|
| Tuning/pilot overlap computed | Done — 23/23 overlap anchors identified |
| Sensitivity recalc (N=100 clean) | Done — 4.4pp inflation confirmed |
| Verdict declared | `OVERLAP_MATERIAL_RESULT_INVALID` |
| 3.3x error identified and corrected | Done |
| Original reports preserved | Unchanged; corrections appended |

### Remaining risk
All Phase 2/3 numbers in BEST_PROMPT_PILOT_REPORT.md and CASCADE_STRATEGY_REPORT.md should be read with the caveat that 18.7% of the evaluation pool overlaps with prompt tuning. A genuinely held-out replication on a disjoint test set (e.g., a different video) is needed to confirm the absolute performance claims.

---

*Generated 2026-06-27. Script used: inline python3 pandas snippet in this audit session.*
