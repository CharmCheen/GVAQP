# Within-Bin Tie-Break Ablation — FINAL REPORT

**Diagnostic only.** Reference gate FAIL: 6 true interval events (< 20). All conclusions diagnostic.

## 1. Is there enough TP in the top p_answer bin?

| stat | value |
| --- | --- |
| bin size | 87 |
| TP (answer_iou_0_3=True) | 16 |
| FP | 71 |
| bin base precision | 0.1839 |
| oracle precision@20 | 0.8000 |

**Yes, the bin contains 16 TPs — enough that oracle precision@20 = 0.8000.** The TP supply is not the bottleneck.

## 2. Oracle precision@20 vs 0.8

Oracle precision@20 = **0.8000**. This reaches / exceeds 0.8 — the failure is purely a ranking problem, not a supply problem.

## 3. Why does current utility fail?

Current utility (`p_answer * value * boundary_quality`) precision@20 = **0.2000**, recall@20 = **0.3333**.

Within the bin, `p_answer` is constant (0.6667), so utility is driven by `value * boundary_quality`. Feature informativeness shows:

| feature | AUC | direction |
| --- | --- | --- |
| boundary_quality | 0.5273 | TP_lower |
| active_score | 0.4401 | TP_lower |
| score_persistence | 0.3099 | equal |

Current utility weights `boundary_quality` positively, but `boundary_quality` AUC = 0.5273 with direction TP_lower — **boundary_quality favors FP**, so weighting it positively pushes FPs to the top. This is a sign/combination problem.

## 4. Is there any non-oracle tie-break rule that beats current utility and random?

| rule | precision@20 | recall@20 | beats random p95 (0.3000)? |
| --- | --- | --- | --- |
| random mean | 0.1804 | - | - |
| current_utility_desc | 0.2000 | 0.3333 | False |
| best composite: inverse_boundary_quality_minus_duration | 0.3500 | 0.5000 | True |
| best single: boundary_drop_sum_asc | 0.3500 | - | True |

## 5. Best rule precision@20 / recall@20

Best composite rule: **inverse_boundary_quality_minus_duration** with precision@20 = **0.3500**, recall@20 = **0.5000**.

## 6. Is the best rule still far below 0.8?

Best precision@20 = 0.3500. YES — it is still far below 0.8 (gap = 0.4500).

## 7. Decision

**NEED_NEW_DISCRIMINATIVE_SIGNAL + INCONCLUSIVE_DUE_TO_SMALL_REFERENCE**

Evidence:
- oracle precision@20 = 0.8000 (reachable)
- best non-oracle precision@20 = 0.3500
- random p95 precision@20 = 0.3000
- best feature AUC = 0.5977 (boundary_left_drop, TP_lower)
- reference size = 6 interval events

## Recommended next action

Oracle ranking reaches 0.8 but no non-oracle rule does. Introduce a new cheap discriminative signal. Do not spend more time on calibration or utility weights.

## Limitations

- 6 true interval events — all conclusions diagnostic only.
- Single bin (p_answer=0.667) from a single (budget=80, seed=0) calibration.
- No label-trained features; composite rules are predefined non-learned formulas.
- Point-anchor events excluded from recall; they appear in precision label (answer_iou_0_3) only for the ~1.3% of candidates that match them.

## Reproducibility

Run: `bash src/garc_eval/experiments/within_bin_tiebreak_ablation_v1/run_all.sh`
Outputs in: `src/garc_eval/outputs/within_bin_tiebreak_ablation_v1/`
