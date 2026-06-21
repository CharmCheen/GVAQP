# Phase 0 Repair v1 Report

This repair reruns only the corrected no-repair block/event audit and report generation on existing Phase 0 data. It does not collect new data, call VLMs, or start Phase 1 system building.

## Root Cause and Fix

The original `UCB_M_O` was capped by `LCB_Y_O`, which could push an upper confidence bound below the missed-event point estimate. The repaired formula removes that cap and enforces `UCB_M_O >= M_hat_O - epsilon` and `LCB_Y_O <= Y_hat_O + epsilon` with `epsilon = 1e-9`.

Synthetic formula test:

| formula | Y_hat_O | M_hat_O | LCB_Y_O | UCB_M_O | invariant_passes |
| --- | --- | --- | --- | --- | --- |
| pre_fix | 3750 | 3375 | 1350 | 1350 | False |
| fixed | 3750 | 3375 | 1350 | 5535 | True |

## Corrected No-repair Block/Event Audit

| theta | block_size_seconds | gamma | delta | trials | mean_true_recall | mean_LCB_recall_O | max_LCB_recall_O | coverage | GVR | mean_tightness | mean_cost | invariant_UCB | invariant_LCB |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.3 | 10 | 0.8 | 0.05 | 100 | 0.3103 | 0 | 0 | 1 | 0 | 0.3103 | 139 | True | True |
| 0.3 | 10 | 0.8 | 0.1 | 100 | 0.3103 | 0.002472 | 0.2472 | 1 | 0 | 0.3079 | 139 | True | True |
| 0.3 | 10 | 0.9 | 0.05 | 100 | 0.3103 | 0 | 0 | 1 | 0 | 0.3103 | 139 | True | True |
| 0.3 | 10 | 0.9 | 0.1 | 100 | 0.3103 | 0 | 0 | 1 | 0 | 0.3103 | 139 | True | True |
| 0.3 | 15 | 0.8 | 0.05 | 100 | 0.3103 | 0 | 0 | 1 | 0 | 0.3103 | 96 | True | True |
| 0.3 | 15 | 0.8 | 0.1 | 100 | 0.3103 | 0.0007548 | 0.07548 | 1 | 0 | 0.3096 | 96 | True | True |
| 0.3 | 15 | 0.9 | 0.05 | 100 | 0.3103 | 0 | 0 | 1 | 0 | 0.3103 | 96 | True | True |
| 0.3 | 15 | 0.9 | 0.1 | 100 | 0.3103 | 0 | 0 | 1 | 0 | 0.3103 | 96 | True | True |
| 0.3 | 30 | 0.8 | 0.05 | 100 | 0.3103 | 0 | 0 | 1 | 0 | 0.3103 | 49 | True | True |
| 0.3 | 30 | 0.8 | 0.1 | 100 | 0.3103 | 0 | 0 | 1 | 0 | 0.3103 | 49 | True | True |
| 0.3 | 30 | 0.9 | 0.05 | 100 | 0.3103 | 0 | 0 | 1 | 0 | 0.3103 | 49 | True | True |
| 0.3 | 30 | 0.9 | 0.1 | 100 | 0.3103 | 0 | 0 | 1 | 0 | 0.3103 | 49 | True | True |
| 0.5 | 10 | 0.8 | 0.05 | 100 | 0.2069 | 0 | 0 | 1 | 0 | 0.2069 | 139 | True | True |
| 0.5 | 10 | 0.8 | 0.1 | 100 | 0.2069 | 0 | 0 | 1 | 0 | 0.2069 | 139 | True | True |
| 0.5 | 10 | 0.9 | 0.05 | 100 | 0.2069 | 0 | 0 | 1 | 0 | 0.2069 | 139 | True | True |
| 0.5 | 10 | 0.9 | 0.1 | 100 | 0.2069 | 0 | 0 | 1 | 0 | 0.2069 | 139 | True | True |
| 0.5 | 15 | 0.8 | 0.05 | 100 | 0.2069 | 0 | 0 | 1 | 0 | 0.2069 | 96 | True | True |
| 0.5 | 15 | 0.8 | 0.1 | 100 | 0.2069 | 0 | 0 | 1 | 0 | 0.2069 | 96 | True | True |
| 0.5 | 15 | 0.9 | 0.05 | 100 | 0.2069 | 0 | 0 | 1 | 0 | 0.2069 | 96 | True | True |
| 0.5 | 15 | 0.9 | 0.1 | 100 | 0.2069 | 0 | 0 | 1 | 0 | 0.2069 | 96 | True | True |
| 0.5 | 30 | 0.8 | 0.05 | 100 | 0.2069 | 0 | 0 | 1 | 0 | 0.2069 | 49 | True | True |
| 0.5 | 30 | 0.8 | 0.1 | 100 | 0.2069 | 0 | 0 | 1 | 0 | 0.2069 | 49 | True | True |
| 0.5 | 30 | 0.9 | 0.05 | 100 | 0.2069 | 0 | 0 | 1 | 0 | 0.2069 | 49 | True | True |
| 0.5 | 30 | 0.9 | 0.1 | 100 | 0.2069 | 0 | 0 | 1 | 0 | 0.2069 | 49 | True | True |

- per-block rows persisted: `227200`
- per-block recomputation check passed: `True`
- bound invariants passed: `True`
- total pseudo-events / certification target events: `29`

Sample size insufficient for robust GVR estimation; results indicate direction only and must not be treated as sufficient evidence for GO/NO_GO.

## Oracle Configuration Identification

| oracle_source_values_in_phase0_units | certification_oracle_label_table | model_size | raw_or_masked | prompt_variant | inference_from_existing_logs |
| --- | --- | --- | --- | --- | --- |
| conservative_vlm_pseudo_oracle | /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded/vlm_labels_conservative.csv | not_recorded_in_phase0_units | not_recorded_in_phase0_units | conservative_vlm_pseudo_oracle | Phase0 units record only conservative_vlm_pseudo_oracle; exact model size and raw/masked setting are not persisted in Phase0 outputs. |

| comparison_name | stability_classification | agreement_rate | flip_rate | matches_certification_oracle | implication |
| --- | --- | --- | --- | --- | --- |
| 8b_raw_vs_masked | ambiguous | 0.8209 | 0.1791 | False | No direct match: Phase 0 did not persist enough oracle metadata to map this comparison to the exact Y_i^O/M_i^O oracle. |
| 32b_raw_vs_masked | unstable | 0.791 | 0.209 | False | No direct match: Phase 0 did not persist enough oracle metadata to map this comparison to the exact Y_i^O/M_i^O oracle. |

Exact model-size and raw/masked metadata were not persisted in Phase 0 outputs. No existing Stage 4 comparison can be confirmed as the exact certification oracle configuration from current logs/tables alone. A prepared stability-check placeholder was written but not run.

## Does the Original NO_GO Change?

The original formula defect is fixed, but this repaired run remains underpowered because the benchmark still has only 29 pseudo-events. The fixed LCBs remain below the target recall settings, and the result should not be promoted to a clean GO/NO_GO claim.

REPAIR_DECISION: UNDERPOWERED_NO_CLEAN_GO_NO_GO

## Human Review Note

Read `reports/ROOT_CAUSE.md` and this report directly. Spot-check at least one row of `tables/block_audit_rows_v2.csv` against the formula before deciding what Phase 0's real verdict is.