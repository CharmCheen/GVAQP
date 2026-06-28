# Cascade Strategy Report — GLM-4.1V in AQP Budget Allocation

**Date**: 2026-06-27
**Candidate pool**: 123-sample pilot (subset of dataset3 347-anchor full table)
**N = 123** (122 valid after excluding 1 parse error)
**Reference oracle**: Qwen3-VL-32B (canonical dataset3 is_positive)
**GLM model**: GLM-4.1V-9B with BEST_glm_final.md (frozen prompt)
**Seeds**: 500 per (strategy, B) combination
**Budget points**: B = 30, 40, 60, 80, 100 (B=150 excluded: B > N=123)

---

## 1. Strategy Definitions

| # | Strategy | Description |
|---|----------|-------------|
| 1 | L3_baseline | Top-B by proxy score (object_count_mean/score_fusion_geometry_motion) |
| 2 | GLM_positive_only | Only GLM-positive anchors → Qwen (truncate to B by confidence if needed) |
| 3 | GLM_pos_uncertain | GLM-positive + uncertain → Qwen (truncate to B) |
| 4 | GLM_pos_unc_plus_L3_neg | GLM pos+unc first; remaining budget to L3 top-negative |
| 5 | GLM_pos_unc_plus_disagreement | GLM pos+unc first; remaining budget to GLM/proxy disagreement regions |
| 6 | L3_plus_uniform_audit | 70% L3 exploitation + 30% uniform random audit |
| 7 | L3_plus_GLM_disagreement_audit | 70% L3 exploitation + 30% GLM/proxy disagreement audit |

**Truncation rule**: When GLM positive+uncertain count exceeds B, truncate by GLM confidence descending. Truncated counts recorded.

---

## 2. Anchor-Level Recall Comparison

| Strategy | B=30 | B=40 | B=60 | B=80 | B=100 |
|----------|------|------|------|------|-------|
| 1. L3_baseline | 12.5% | 15.0% | 32.5% | 62.5% | 82.5% |
| 2. GLM_positive_only | **50.0%** | **60.0%** | 60.0% | 60.0% | 60.0% |
| 4. GLM+L3_neg | **50.0%** | **60.0%** | **67.5%** | **77.5%** | **87.5%** |
| 5. GLM+disagreement | **50.0%** | **60.0%** | **67.5%** | **77.5%** | **87.5%** |
| 6. L3+uniform_audit | 17.9% | 23.6% | 34.0% | 54.4% | 77.0% |
| 7. L3+GLM_disag_audit | 22.5% | 27.5% | 47.5% | **77.5%** | **87.5%** |

**Key observations**:
- GLM-based strategies (2,4,5) **crush L3 baseline at small budgets**: +37.5pp at B=30, +45pp at B=40
- GLM caps at 60% recall ceiling — 16/40 Qwen-positives are in GLM negative and cannot be recovered by GLM alone
- Strategy 4 (GLM + L3_neg) breaks the 60% ceiling by exploring GLM-negative anchors via proxy ranking
- Strategy 5 (disagreement) = Strategy 4 — disagreement-based selection adds no value over simple L3 ranking
- GLM disagreement audit (Strategy 7) beats uniform audit (Strategy 6) by **+13.5pp at B=60**, +23pp at B=80

---

## 3. Event-Cluster Recall

| Strategy | B=30 | B=40 | B=60 | B=80 | B=100 |
|----------|------|------|------|------|-------|
| 1. L3_baseline | 18.5% | 22.2% | 44.4% | 66.7% | 81.5% |
| 2. GLM_positive_only | 51.9% | 63.0% | 63.0% | 63.0% | 63.0% |
| 4. GLM+L3_neg | 51.9% | 63.0% | 70.4% | 81.5% | 88.9% |
| 7. L3+GLM_disag_audit | 29.6% | 33.3% | 55.6% | 81.5% | 88.9% |

GLM-based strategies provide higher cluster recall at all budget levels. The advantage is strongest at small budgets.

---

## 4. Singleton Recall

| Strategy | B=30 | B=40 | B=60 | B=80 | B=100 |
|----------|------|------|------|------|-------|
| 1. L3_baseline | 19.0% | 23.8% | 38.1% | 61.9% | 81.0% |
| 2. GLM_positive_only | 47.6% | 57.1% | 57.1% | 57.1% | 57.1% |
| 4. GLM+L3_neg | 47.6% | 57.1% | 66.7% | 76.2% | 85.7% |

GLM improves singleton recall by 28-33pp at small budgets compared to L3 baseline. This addresses the "low-proxy singleton" problem — GLM can identify positive singletons that proxy misses.

---

## 5. GLM False-Negative Loss

| Strategy | B=30 | B=40 | B=60 | B=80 | B=100 |
|----------|------|------|------|------|-------|
| 2/3/4/5 (GLM-based) | 16.0 | 16.0 | 13.0 | 9.0 | 5.0 |
| 1. L3_baseline | 13.0 | 12.0 | 9.0 | 6.0 | 2.0 |

GLM-based strategies permanently lose 16 Qwen-positives at small budgets because they're in GLM negative. Strategy 4/5 recovers some at larger budgets via L3 neg exploration.

---

## 6. Cost Model

| Strategy | B | GLM calls | Qwen calls | Serial wall (s) | 2-GPU wall (s) | 4-GPU wall (s) |
|----------|---|-----------|------------|-----------------|----------------|----------------|
| 1. L3_baseline | 30 | 0 | 30 | 360 | 360 | 360 |
| 1. L3_baseline | 100 | 0 | 100 | 1200 | 1200 | 1200 |
| 4. GLM+L3_neg | 30 | 123 | 30 | 3287 | 1824 | 1092 |
| 4. GLM+L3_neg | 100 | 123 | 100 | 4127 | 2664 | 1932 |
| 7. L3+GLM_disag | 30 | 123 | 30 | 3287 | 1824 | 1092 |
| 7. L3+GLM_disag | 100 | 123 | 100 | 4127 | 2664 | 1932 |

GLM-based strategies add ~123 GLM calls (avg 23.8s each = 2927s serial, 732s with 4 GPUs) but can dramatically reduce the number of Qwen calls needed for equivalent recall. At B=30, GLM achieves 50% recall with 30 Qwen calls vs L3 baseline's 12.5% recall. To match GLM's B=40 recall (60%) with L3 alone requires B≈80 (62.5% recall, 80 Qwen calls).

**Parallel GLM with 4 GPUs**: 732s for pre-screening 123 anchors.

---

## 7. Phase 3 Decision

**DECISION: USE_GLM_AS_BOOSTER**

**Rationale**:
- GLM positive bin has 61.5% Qwen-positive rate (3.3x the base rate of 32.5%)
- GLM-based selection achieves 50-60% recall at B=30-40 vs L3's 12.5-15% (+37.5-45pp gain)
- Strategy 4 (GLM priority boost + L3 exploration of negative region) reaches 67.5% recall at B=60, breaking GLM's 60% ceiling
- GLM disagreement audit (Strategy 7) beats uniform audit by 13.5pp at B=60, providing an effective audit mechanism
- **Critical limitation**: GLM negative contains 40% of Qwen-positives (16/40). GLM cannot serve as a reject filter. GLM must be used as a priority booster, not a gate.
- **Disagreement signal**: Strategy 5 = Strategy 4, meaning GLM/proxy disagreement does not enrich beyond simple L3 ranking of GLM-negative anchors. The value comes from GLM's own enrichment, not from disagreement patterns.
- **Wall-clock**: GLM pre-screening adds significant cost but provides dramatic recall gains at small Qwen budgets. With parallel GLM inference (4 GPUs), pre-screening overhead is ~12 min.

**What this decision means for AQP execution**:
- When budget B is small (30-60), send GLM-positive anchors to Qwen first, then fill remaining budget with proxy-ranked GLM-negative anchors (Strategy 4)
- Do NOT discard GLM-negative anchors — they contain 40% of Qwen-positives
- GLM provides a "cheap enrichment layer" that boosts positive yield per Qwen call from ~17% to ~62% at small budgets
- This is a **static priority boost mechanism**, not a new AQP algorithmic contribution (see task scope note)

---

## 8. Limitations

1. Single video (dataset3), 123-anchor pilot subset of 347-anchor full dataset3
2. GLM generates 0 uncertain labels — no triage tier available
3. GLM 40% false-negative rate is measured against Qwen reference, not human ground truth
4. Cost model uses estimated latencies; parallel GLM not empirically measured
5. Cascade replay is deterministic for non-audit strategies (L3 rank is fixed, GLM labels are fixed) — std=0 for strategies 1-5 and 7 at most budgets
6. B=150 excluded: exceeds candidate pool size N=123
7. Results are N=123 specific; do not directly compare with dataset3 347-anchor or realcartest 399-anchor L3/L4 curves

---

*Generated on 2026-06-27. N=123 candidate pool (123-sample pilot).*

---

## CORRECTION PATCH (2026-06-27)

### A. Tuning Set Overlap → `OVERLAP_MATERIAL_RESULT_INVALID`

All 23 unique anchors from the GLM + Qwen prompt tuning sets are present in this 123-pilot (18.7% of evaluation pool). Overlap is enriched in Qwen-positives (52.2% vs 32.5% base). All absolute recall/precision/recall-lift numbers are **upper bounds potentially inflated by tuning set familiarity**.

Sensitivity check (N=100 clean, excl. overlap):
- GLM positive bin rate: 61.5% → 57.1% (−4.4pp)
- GLM recall: 60.0% → 57.1% (−2.9pp)
- GLM precision: 61.5% → 57.1% (−4.4pp)

Directional finding (GLM > L3) survives; absolute numbers should carry inflation caveat.

### B. "3.3x" Calculation Error (line 107)

**Incorrect**: "3.3x the base rate of 32.5%"

**Corrected**: GLM positive bin Qwen-pos rate (61.5%) / base rate (32.5%) = **1.89x enrichment over base**. The "3.3x" was a computational error; no valid derivation produces this value. The 4.10x figure in the cost section (GLM pos bin precision / L3 B=40 precision) is valid but refers to a different comparison (GLM vs L3 yield, not GLM vs base rate).

### C. "positive yield per Qwen call from ~17% to ~62%" (line 118)

The 17% is approximately L3 baseline precision at B≈50 (interpolated). At B=30, L3 precision = 16.7%, GLM = 61.5% → 3.68x improvement. The 62% should be qualified as "upper bound, possibly inflated by tuning overlap" post-correction.

See `CORRECTIONS.md` for full audit.
