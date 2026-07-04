# Synthetic Cheap Signal Downstream Validation V1

## Purpose

This controlled intervention asks whether downstream CILS / calibration / selector mechanics can convert a cheap signal with controlled TP/FP separability into high-precision interval retrieval.

## Diagnostic-Only Label Use

Synthetic scores use `TP_iou_0_3`, reconstructed from true interval events only, as the positive label. This is intentionally label-derived and diagnostic. It is not real non-leak cheap-signal performance and must not be used as a retrieval claim.

## Reference Scope

- True interval events: `6`
- Reference gate: **FAIL**
- Main TP excludes point-anchor-only matches.
- All conclusions are diagnostic because true interval events are fewer than 20.
- Git status limitation: unavailable due to dubious-ownership protection; no global Git config was changed.

## Synthetic Signal Quality

| synthetic_signal_name | mean_target_auc | mean_empirical_auc | off_target_rate | seeds |
| --- | --- | --- | --- | --- |
| random_signal | 0.5 | 0.498329 | 0 | 20 |
| synthetic_auc_0_60 | 0.6 | 0.598155 | 0 | 20 |
| synthetic_auc_0_70 | 0.7 | 0.698275 | 0 | 20 |
| current_real_signal | nan | 0.712618 | 0 | 1 |
| synthetic_auc_0_75 | 0.75 | 0.752175 | 0 | 20 |
| synthetic_auc_0_80 | 0.8 | 0.80117 | 0 | 20 |
| synthetic_auc_0_85 | 0.85 | 0.850888 | 0 | 20 |
| synthetic_auc_0_90 | 0.9 | 0.89985 | 0 | 20 |
| synthetic_auc_0_95 | 0.95 | 0.95013 | 0 | 20 |
| oracle_signal | 1 | 1 | 0 | 1 |

## CILS Signal-Quality Response

| synthetic_signal_name | mean_auc | max_precision | max_recall | nonempty_rate |
| --- | --- | --- | --- | --- |
| synthetic_auc_0_60 | 0.598155 | 0.583333 | 1 | 0.2625 |
| synthetic_auc_0_70 | 0.698275 | 0.666667 | 1 | 0.4975 |
| current_real_signal | 0.712618 | 0.153846 | 0.333333 | 0.05 |
| synthetic_auc_0_75 | 0.752175 | 0.666667 | 1 | 0.6025 |
| synthetic_auc_0_80 | 0.80117 | 0.666667 | 1 | 0.6425 |
| synthetic_auc_0_85 | 0.850888 | 0.75 | 1 | 0.695 |
| synthetic_auc_0_90 | 0.89985 | 0.909091 | 1 | 0.7175 |
| synthetic_auc_0_95 | 0.95013 | 1 | 1 | 0.7525 |
| oracle_signal | 1 | 0.727273 | 1 | 1 |

## Answers

1. Purpose: validate downstream mechanism under controlled synthetic separability.
2. Labels used: `TP_iou_0_3` true-interval-only candidate labels reconstructed from `reference_events.csv`.
3. Diagnostic only: synthetic and oracle signals use evaluation labels and are label-derived.
4. Target AUCs: see `synthetic_signal_quality.csv`; off-target rows are explicitly marked.
5. Monotonicity: see plots and CILS summary; monotonicity is assessed diagnostically on a six-event interval reference.
6. Minimum CILS signal quality for precision >= 0.8 with nonzero recall: `synthetic_auc_0_90`; empirical AUC `0.9002718429187817`; AP `0.5917406873803235`; budget `160`; tau `0.5`.
7. Minimum CILS signal quality for precision >= 0.9 with nonzero recall: `synthetic_auc_0_90`; empirical AUC `0.9006878097942712`; AP `0.6074892444368949`; budget `160`; tau `0.9`.
8. CILS value-add over simple synthetic top-k: **CILS_NEUTRAL**. Best CILS recall at precision>=0.8: `1`; best synthetic top-k recall at precision>=0.8: `1`.
9. Strong/oracle-like signal failure check: see oracle rows in metrics; if oracle rows succeed, the selector is not absolutely blocked, but value-add remains separate.
10. Current real-signal failure interpretation: more consistent with weak/non-discriminative cheap signal if synthetic/oracle signal succeeds; otherwise downstream selector remains suspect.
11. Small reference limitation: **yes**, append `INCONCLUSIVE_DUE_TO_SMALL_REFERENCE`.
12. Recommended next action: **compare CILS against simple top-k if CILS lacks value-add**.

## Final Decision

`DOWNSTREAM_WEAK_OR_NOT_VALUE_ADDING + INCONCLUSIVE_DUE_TO_SMALL_REFERENCE`

## Limitations

- Synthetic scores are label-derived.
- Only 20 synthetic seeds were used for signal generation because the full 100-seed CILS grid is high runtime; random baseline uses 100 repeats.
- Main true interval reference has only six events.
- No model, proposal generation, production CILS, or default calibration code was modified.
