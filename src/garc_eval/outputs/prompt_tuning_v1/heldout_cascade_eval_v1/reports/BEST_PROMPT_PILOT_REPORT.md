# GLM-4.1V (BEST prompt) on 123-Sample Pilot — Held-Out Validation

**Date**: 2026-06-27
**GLM prompt**: BEST_glm_final.md (v1_lower_threshold, tuning F1=0.706 on GLM test set)
**Qwen reference**: canonical_dataset3_anchor_table is_positive column (Qwen3-VL-32B oracle labels)
**Status**: Held-out — GLM was NOT tuned on these samples. Qwen reference reused from canonical table.

---

## 1. Summary Metrics

| Metric | Value |
|--------|-------|
| Samples | 123 |
| Valid (GLM parsed) | 122 (99.2%) |
| Parse errors | 1 (0.8%) |
| Qwen reference positives | 40 |
| Qwen reference negatives | 83 |

## 2. Confusion Matrix (GLM vs Qwen Reference)

| GLM → / Qwen ↓ | positive | negative | uncertain | parse_error |
|-----------------|----------|----------|-----------|-------------|
| positive (40) | 24 | 16 | 0 | 0 |
| negative (83) | 15 | 67 | 0 | 1 |

## 3. A. Balanced / Hard-Set Metrics

| Metric | Value |
|--------|-------|
| GLM positive rate | 31.7% (39/123) |
| GLM negative rate | 67.5% (83/123) |
| GLM uncertain rate | 0.0% (0/123) |
| Recall (positive only) | 60.0% (24/40) |
| Precision (positive only) | 61.5% (24/39) |
| F1 (positive only) | 0.608 |
| False positive rate (on negatives) | 18.1% (15/83) |

## 4. B. AQP / Cascade-Relevant Metrics

| Metric | Value |
|--------|-------|
| GLM pos+unc recall of Qwen-pos | 60.0% (24/40) |
| Qwen-positives in GLM negative | 16 (40.0% of all positives) |
| GLM negative false-negative rate | 40.0% |
| Qwen positive rate in GLM positive bin | 61.5% (24/39) |
| Qwen positive rate in GLM uncertain bin | N/A (0 in bin) |
| Qwen positive rate in GLM negative bin | 19.3% (16/83) |

## 5. Latency and Cost

| Metric | Value |
|--------|-------|
| Avg latency | 23.8s |
| P50 latency | 19.9s |
| P95 latency | 51.1s |
| Avg output tokens | 562 |
| Hit max_tokens (2048) | 1 |
| Peak GPU memory | ~19.2 GB |

## 6. Event-Cluster Analysis

| Metric | Value |
|--------|-------|
| Event clusters | 27 |
| Singleton clusters | 21 |
| Cluster recall (GLM pos+unc) | 17/27 = 0.630 |
| Singleton recall | 12/21 = 0.571 |

## 7. Error Analysis

### GLM false negatives (16 Qwen-positives missed)
GLM negative contains 40% of all Qwen-positives. This is the single most critical finding — GLM cannot serve as a safe reject filter because discarding GLM negatives would lose nearly half of the oracle positives.

### GLM false positives (15 Qwen-negatives called positive)
FP rate on negatives is 18.1%. GLM positive rate (31.7%) is higher than Qwen positive rate (32.5%), suggesting GLM is not a strong precision booster either.

### Parse errors
1 parse error (anchor 0342) — GLM hit max_tokens=2048 with incomplete output.

### Comparison to tuning set
- Tuning F1: 0.706 (GLM test set, 15 samples)
- Held-out F1: 0.608 (123 samples)
- Tuning recall: 60% (6/10 positives)
- Held-out recall: 60% (24/40 positives)
- Recall is consistent; precision dropped from 85.7% to 61.5% (expected with more negatives)

## 8. Phase 2 Decision

**DECISION: GLM_DISAGREEMENT_SIGNAL_ONLY**

**Rationale**: GLM recall of Qwen-positives (60%) is too low for routing/rejection (GLM negative contains 40% of Qwen-positives). GLM precision (61.5%) is below the 70% threshold for booster-only use. However, GLM recall ≥ 50% and GLM positive bin has 61.5% Qwen positive rate (vs 32.5% base rate), indicating that GLM predictions carry signal — the disagreement between GLM and cheap proxy may enrich L3 missed positives.

GLM is NOT suitable as:
- A cascade reject filter (40% FN rate unacceptable)
- A standalone booster (precision not high enough)

GLM MAY have value as:
- A disagreement signal with cheap proxy to identify L3-missed positives
- An enrichment layer that triages GLM-positive anchors for higher priority

## 9. Limitations

1. Qwen reference is VLM-oracle, not human-adjudicated
2. Single video (dataset3), 123-anchor pilot is a subset of 347-anchor full dataset3
3. GLM zero uncertains — the current prompt produces only binary positive/negative outputs; no triage tier
4. GLM has `<think>` reasoning in 100% of outputs (~562 tokens of reasoning before label)
5. Tuning set (15 samples, 10 pos) was GLM-optimized, not Qwen-reference-optimized
6. GLM model generation flags warning: temperature flag ignored by transformers

---

*Generated on 2026-06-27*

---

## CORRECTION PATCH (2026-06-27) — Tuning Set Overlap

**Finding**: All 23 unique anchors from the GLM + Qwen prompt tuning sets are present in this 123-pilot. 18.7% of the evaluation pool overlaps with the samples used to select `BEST_glm_final.md` and `BEST_qwen_final.md`. The overlap is enriched in Qwen-positives (52.2% vs 32.5% base).

**Impact on Phase 2 metrics** (N=100 clean, excl. 23 overlap anchors):

| Metric | Original (N=123) | Clean (N=100) | Δ |
|--------|------------------|---------------|----|
| GLM positive bin Qwen-pos rate | 61.5% (24/39) | 57.1% (16/28) | −4.4pp |
| GLM recall | 60.0% (24/40) | 57.1% (16/28) | −2.9pp |
| GLM precision | 61.5% (24/39) | 57.1% (16/28) | −4.4pp |

**Verdict**: `OVERLAP_MATERIAL_RESULT_INVALID` — the absolute numbers above are upper bounds inflated by tuning set familiarity. Directional conclusions (GLM enriches positives beyond L3 proxy) remain valid but absolute recall/precision claims should carry an "upper bound, possibly inflated" caveat. See `CORRECTIONS.md` for full audit.
