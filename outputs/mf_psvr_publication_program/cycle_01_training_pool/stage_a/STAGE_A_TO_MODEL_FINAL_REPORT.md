# MF-PSVR Stage A to model final report

## Mandatory result block

```text
CANDIDATE_EXTRACTION_STATUS = PASS
PROVIDER_VIDEOS_COMPLETED = 603
UNIT_SCORE_ROWS = 5308
CANDIDATE_EXTRACTION_GPU_SECONDS = 939.6513740459993

STAGE_A_STATE = STAGE_A_FAIL_ACQUIRE_LICENSED_QUERY_ENRICHED_SOURCE
STAGE_A_ORACLE_EXECUTION_STATE = COMPLETE_COMMIT
STAGE_A_DEFAULT_FROZEN_VERIFY = FAIL
STAGE_A_ROUNDTRIP_FROZEN_VERIFY = VERIFIED_COMPLETE_COMMIT
STAGE_A_PHYSICAL_ATTEMPTS = 96
STAGE_A_ACCEPTED_DURABLE_CALLS = 96
STAGE_A_UNCERTAIN_CALLS = 0
STAGE_A_PARSE_FAILURES = 0
STAGE_A_Q1_POSITIVES = 10
STAGE_A_Q2_POSITIVES = 14
STAGE_A_Q1_EVENT_GROUPS = 10
STAGE_A_Q2_EVENT_GROUPS = 14
STAGE_A_TOTAL_PHYSICAL_COST_SECONDS = 2129.1209635050755
STAGE_A_SUPPORT_DECISION = STOP_ACQUIRE_LICENSED_QUERY_ENRICHED_SOURCE

TRAINING_SEMANTIC_SAMPLES = 192
TRAINING_SOURCE_DATASETS = 1
TRAINING_SOURCE_SESSIONS = 91

BEST_AGGREGATED_MODEL = M0_LOGISTIC
BEST_AGGREGATED_LOSO_AUPRC = 0.555469
BEST_AGGREGATED_MACRO_QUERY_AUPRC = 0.496673
BEST_TEMPORAL_REFINER = TCN_TEMPORAL
BEST_TEMPORAL_REFINER_LOSO_AUPRC = 0.335634
BEST_TEMPORAL_REFINER_MACRO_QUERY_AUPRC = 0.382338
BEST_MODEL_BRIER = 0.113147
BEST_MODEL_ECE = 0.110862

RAW_YOLO_AUPRC = 0.176400
SHUFFLED_LABEL_AUPRC = 0.142245
ID_ONLY_AUPRC = 0.111111
SELECTION_STRATUM_ONLY_AUPRC = 0.197388
ANCHOR_ID_ONLY_AUPRC = 0.133199

QUERY_CONDITIONING_SIGNAL = NO_CLEAR_EXPLICIT_QUERY_GAIN
TEMPORAL_REFINEMENT_SIGNAL = NO_CLEAR_GAIN
MODEL_READY_FOR_PHYSICAL_PILOT = NO
FINAL_CALIBRATOR_STATUS = UNSUPPORTED_ONE_POSITIVE_NOT_DEPLOYABLE
FINAL_CALIBRATOR_DEPLOYABLE = NO
MODELING_ANALYSIS_STATUS = EXPLORATORY_NOT_PREREGISTERED_OR_CRYPTOGRAPHICALLY_BLINDED

BEST_MODEL_PATH = outputs/mf_psvr_publication_program/cycle_01_training_pool/stage_a/modeling/models/M0_LOGISTIC.joblib
BEST_MODEL_SHA256 = 42907ae140160cf91dcf30d6aba967fcc8ed241ad171c1dd98b1df62f8f853de
NEXT_RESEARCH_STAGE = ADD_SECOND_QUERY_ALIGNED_SOURCE_DATASET_AND_REPEAT_STAGE_A_MODEL_AUDIT
NEXT_EXACT_COMMAND = python scripts/run_mf_psvr_stage_a_modeling.py verify
```

## Strongest supported conclusion

At least one exploratory evidence screen failed; Stage A does not justify physical-method execution. The best aggregate representation is `M0_LOGISTIC` and the best temporal representation is `TCN_TEMPORAL`. Their pooled exact development-LOSO AUPRC values are 0.555469 and 0.335634; their macro-query AUPRC values are 0.496673 and 0.382338. The representation selected without using `pool_audit` is `M0_LOGISTIC`. Pooled lift is not treated as a uniform learned refinement because Q1/Q2 behavior and nuisance controls differ materially.

## Decisive evidence

- Candidate extraction independently reconciled all 603 frozen providers and 5308 query-unit rows.
- Oracle accounting reconciled 96 STARTED attempts, 96 durable accepted calls, 0 uncertain calls, and 0 retained parse failures.
- The oracle execution finalized a `COMPLETE_COMMIT`. The default frozen verify command reproducibly fails because pandas' default CSV parser changes one textual runtime float before an exact-equality check. The hash-frozen verifier reaches `VERIFIED_COMPLETE_COMMIT` when only its module-local CSV float parser is switched to round-trip mode; the bound exception audit status is `PASS_WITH_RECORDED_FROZEN_VERIFIER_DEFECT`.
- Main model results are pooled predictions from exact leave-one-provider-session-out fits on development roles. No random row split or source/session identity feature is used by an effective model.
- The fixed `pool_audit` role was arithmetically excluded from fitting and model selection, then evaluated separately. The full dataset was available locally; this was not a cryptographic blind.
- The modeling protocol is exploratory, not preregistered: 70 human-readable raw oracle envelopes already existed when it was fixed. The physical oracle protocol remains separately frozen before calls.
- The strongest identity-only, selection-stratum-only, and anchor-only development AUPRC values are 0.111111, 0.197388, and 0.133199. The 32 fold-specific shuffled-label runs have mean 0.142245 and empirical 95th percentile 0.237679; 32 repetitions are a noisy diagnostic, not a formal significance test.
- A paired provider-session bootstrap conditional on the fixed OOF predictions estimates selected-minus-raw pooled AUPRC at 0.379070 (descriptive 95% interval 0.150389 to 0.595345) and macro-query AUPRC at 0.032889 (-0.094248 to 0.153035). These intervals do not cover dataset-to-dataset transport uncertainty.

## Exploratory aggregate-feature associations

The aggregate schema retained 61 of 72 candidates in a label-free full-rank basis. Raw numeric witness class is excluded. The following are coefficient-magnitude or LightGBM-gain associations, not independently identified feature effects or causal effects:

- `temporal_bbox_height_mean`: 1.187590 (absolute_standardized_coefficient)
- `track_front_region_occupancy_normalized`: 1.145775 (absolute_standardized_coefficient)
- `track_track_persistence_normalized`: 1.084090 (absolute_standardized_coefficient)
- `temporal_bbox_area_last`: 1.022296 (absolute_standardized_coefficient)
- `temporal_front_region_occupancy_last`: 0.959814 (absolute_standardized_coefficient)
- `temporal_delta_center_y_per_second_max`: 0.929431 (absolute_standardized_coefficient)
- `class_is_pedestrian`: 0.926316 (absolute_standardized_coefficient)
- `track_observations`: 0.924078 (absolute_standardized_coefficient)
- `witness_observation_fraction`: 0.919567 (absolute_standardized_coefficient)
- `temporal_active_query_track_count_max`: 0.764733 (absolute_standardized_coefficient)

These entries are hypothesis generators only. Even after algebraic redundancy pruning, regularization, correlation, and the small positive count make individual attribution unstable.

## Temporal refinement

The temporal-minus-aggregate development LOSO AUPRC difference is -0.219835, classified as `NO_CLEAR_GAIN` by a post-hoc descriptive 0.02 rule that was absent from the modeling protocol. Its paired provider-session bootstrap interval is -0.420047 to 0.048728; this is conditional on fixed OOF predictions. Per-query temporal-minus-aggregate AUPRC deltas are Q1 +0.042168, Q2 -0.270837, so direction and magnitude must be inspected rather than inferred from the pooled value. Both temporal models are causal, query-conditioned, have hidden width 32, use fixed trajectories only, and do not train an RGB backbone or YOLO. At the primary budget of 16 physical VERIFY calls, query probabilities are aggregated by maximum and a call is positive if either query is positive; `M0_LOGISTIC` recovers 7/15 development-positive calls (precision 0.4375, recall 0.4667). Semantic-opportunity top-k metrics are separately named in the metric table.

## Q1 versus Q2 learnability

- Q1: development n=72, positives=7, selected/raw AUPRC=0.167680/0.118055; fixed-audit selected/raw AUPRC=0.411111/0.327778, selected ECE=0.160823.
- Q2: development n=72, positives=9, selected/raw AUPRC=0.825665/0.809513; fixed-audit selected/raw AUPRC=1.000000/0.926667, selected ECE=0.112741.

Explicit query-column ablation of the selected aggregate model (`M0_LOGISTIC` versus `M0_NO_EXPLICIT_QUERY`) changes development AUPRC by -0.001286. This is classified as `NO_CLEAR_EXPLICIT_QUERY_GAIN` by the same post-hoc descriptive rule. Caveat: The ablation removes explicit query-code/interaction columns, but raw scores and witness construction remain query-specific.

## Calibration limitation

The final calibration role contains 1 positive and 27 negative binary rows; Q1/Q2 contribute 1/0 positives. Status is `UNSUPPORTED_ONE_POSITIVE_NOT_DEPLOYABLE`. Serialized M1/TCN/GRU Platt maps reproduce this exploratory run only and are not deployable calibrators.

## Worst provider-session result

For `M0_LOGISTIC`, the highest development-fold Brier source/session is `nexar_collision_prediction/nexar:00590.mp4` with n=2, positives=2, Brier=0.930917, and AUPRC=NA. Per-session AUPRC is intentionally undefined for one-class folds; Brier is used to identify the worst fold without inventing a ranking metric.

## Main competing explanation and unresolved uncertainty

Enriched stratum sampling and a single dataset family can inflate apparent discrimination without cross-dataset transport. Leave-one-dataset-out is unidentifiable until another source dataset is labeled. The frozen support gate failed specifically because the calibration role had only 1 Q1 positive and 0 Q2 positives, even though overall support existence passed for both queries. The data still lack a second source dataset, natural-prevalence sampling, and enough independent positive event groups for narrow source-specific claims. Unit outcomes also cannot be interpreted as verified witness-track labels.

## Decision and next action

The exploratory readiness decision is `NOT_READY_FOR_PHYSICAL_PILOT`. Independently, the frozen semantic support state is `STAGE_A_FAIL_ACQUIRE_LICENSED_QUERY_ENRICHED_SOURCE` because the oracle support decision is `STOP_ACQUIRE_LICENSED_QUERY_ENRICHED_SOURCE`. Acquire a second source dataset under the same frozen label semantics before physical-pilot execution. The observation that would trigger rejection or revision is: Reverse or revise this exploratory assessment if independent audit finds group leakage, audit-role fitting, unstable group-bootstrap deltas, or a below-control per-query audit result.

This run stops before any V0/V1 physical-method matrix. The exact next command above only re-verifies the completed Stage-A modeling handoff; it does not authorize or execute a physical pilot.
