# Cross-Video Strategy 7 Comparison

- Output timestamp: 2026-06-27T14:37:38Z
- Comparison mode: strict replication, because Phase 0 accepted realcartest for strict second-video validation.
- Dataset3 clean-pool and realcartest are not pooled because positive rate, proxy strength, and candidate universe differ.
- Dataset3 is lower-positive-rate/weaker-proxy in the project framing; realcartest has higher positive rate and stronger `object_count_mean`.
- Transfer conclusion: `STRATEGY7_TRANSFER_CONFIRMED` for the target missed-positive recovery mechanism. Realcartest has positive S7-vs-uniform-audit gaps at 7/7 budgets, mean gap 0.057524; dataset3 clean-pool had positive count-gap direction at 3/6 shared budgets in the existing audit table.

| metric | dataset3 | realcartest | note |
|---|---:|---:|---|
| comparison_mode | strict replication reference | strict validation | ACCEPT_REALCARTEST_FOR_STRICT_SECOND_VIDEO_VALIDATION |
| positive_rate | 0.11527377521613832 | 0.23558897243107768 | dataset3 full canonical rate vs realcartest full V13 anchor rate |
| object_count_mean_auc | 0.6272394136807817 | 0.7564178583885595 | proxy ranking strength |
| L3_P20 | 0.2 | 0.8 | dataset3 clean pool if available; realcartest full universe |
| L3_R20 | 0.142857 | 0.1702127659574468 | dataset3 clean pool if available; realcartest full universe |
| Strategy7_vs_uniform_audit_gap_mean | 1.008000 missed-positive-count gap (3/6 positive budgets) | 0.057524428945442775 | dataset3 uses count gap from clean-pool audit; realcartest uses recovery-rate gap; compare direction, not units |
| GLM_positive_or_uncertain_enrichment | see post_transition_strategy7_audit_v1 | 1.8820754716981134 | Qwen evaluation-only enrichment |
| Strategy7_effect_transfers | confirmed in dataset3 clean-pool audit | positive: 7/7 budget gaps, mean recovery gap 0.057524 | transfer assessed by realcartest S7 vs uniform-audit L3-missed recovery gap |

## Interpretation

- Realcartest is a harder transfer test for Strategy 7 in one sense because `object_count_mean` is already strong at P@20=0.800, so pure L3 remains hard to beat on overall recall at small budgets.
- The Strategy 7 mechanism still transfers for the intended target: recovering positives that L3 misses. This supports a GLM/proxy disagreement audit as an AQP-side budget-allocation mechanism, not as a new detector claim.
