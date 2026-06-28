# Nexar Candidate Feasibility v2 Report

## 1. Goal

Evaluate Phase 1 candidate feasibility v2 for clip-level approximate selection over Nexar-200 videos. The goal is not to train a stronger driving-event proxy; it is to test whether local candidate generators can produce returned clips that are usable for Nexar-derived-boundary-relative recall and certificate simulation.

## 2. Protocol Reference

Authority: `CASQ_CODEX_BRIEF_V12_1.md`, especially Sections 23 and 26-31.

Protocol type: Phase 1+ candidate feasibility v2.

Claim scope: Nexar-200 only, derived boundary.

## 3. Hardware and Runtime Environment

- GPU: NVIDIA H20-3e
- YOLOv8n local path: `/qiuyeqing/llama_prl/G-ARC/models/yolo/yolov8n.pt`
- VLM audit hardware: NVIDIA H20-3e, imported from v1 without rerun.

Candidate runtimes:

| candidate_name | runtime_seconds | frames_processed | videos_processed | notes |
| --- | --- | --- | --- | --- |
| fixed_sliding_window | 0.00330138 | 0 | 384 |  |
| random_window | 0.0536637 | 0 | 384 |  |
| motion_energy | 156.434 | 768 | 384 |  |
| yolo_count_proxy | 0 | 0 | 0 | NOT_RUN_CPU_FALLBACK_INFEASIBLE |

## 4. Input Data and Readability

- manifest rows: 400
- events rows: 200
- repair readable rows: 392
- positive readable rows: 200
- normal readable rows: 192
- balanced readable rows: 384
- candidate_dev videos: 192
- heldout_report videos: 192

Tables:

- `tables/nexar_video_mapping_v2.csv`
- `tables/nexar_video_readability_v2.csv`
- `tables/nexar_candidate_subset_full_readable.csv`
- `tables/nexar_candidate_subset_balanced_readable.csv`

## 5. External Label to Predicate Mapping

Mapping: LOOSE_APPROXIMATION / AUDIT_UNRELIABLE.

Nexar-derived labels are not equivalent to O_enter_ego_path_v0.

All candidate/certificate conclusions are Nexar-derived-boundary-relative and single-dataset scoped.

## 6. Bounded 32B Oracle / VLM Micro-Audit

The bounded VLM micro-audit was executed under the v1 directory and imported into v2 without rerunning.

- planned / completed calls: 100 / 100
- near_label: 50
- random_negative: 50
- max calls per video: 2
- clip length: 5 seconds
- model: Qwen3-VL-32B-Instruct
- GPU: NVIDIA H20-3e
- peak memory allocated: 63.243GiB
- peak memory reserved: 63.568GiB
- positive agreement: 0.160
- random-negative estimated miss rate: 0.020
- abstain rate: 0.000
- EXTERNAL_LABEL_AUDIT_RESULT: UNRELIABLE

## 7. Design / Report Split

Selection protocol: HELD_OUT_REPORT.

Candidate hyperparameters were selected on candidate_dev videos. Final selected-configuration metrics below are computed on heldout_report videos.

Selected heldout configurations:

| candidate_name | theta | budget_type | budget_value | merge_gap | true_derived_recall | returned_duration_fraction | event_hit_count | event_total_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fixed_sliding_window | 0.3 | top_k_per_video | 1 | 0 | 0 | 0.0132181 | 0 | 96 |
| fixed_sliding_window | 0.5 | top_k_per_video | 1 | 0 | 0 | 0.0132181 | 0 | 96 |
| motion_energy | 0.3 | top_k_per_video | 1 | 0 | 0 | 0.0132181 | 0 | 96 |
| motion_energy | 0.5 | top_k_per_video | 1 | 0 | 0 | 0.0132181 | 0 | 96 |
| random_window | 0.3 | top_duration_fraction | 0.5 | 0 | 0.489583 | 0.50697 | 47 | 96 |
| random_window | 0.5 | top_duration_fraction | 0.5 | 0 | 0.197917 | 0.50697 | 19 | 96 |

## 8. Candidate Generators

Generated candidates:

- fixed_sliding_window
- random_window
- motion_energy

YOLO count proxy status:

| candidate_name | status | local_model_available | ultralytics_available | reason | how_to_enable |
| --- | --- | --- | --- | --- | --- |
| yolo_count_proxy | NOT_RUN_CPU_FALLBACK_INFEASIBLE | True | True | A smoke attempt did not attach as a visible GPU compute process and ran as slow CPU-heavy inference; full YOLO scoring was not run to avoid an infeasible CPU fallback. | Set CASQ_RUN_SLOW_YOLO=1 and rerun if full YOLO scoring is explicitly authorized despite runtime. |

Candidate generation did not use `event_start`, `event_end`, `event_moment`, `alert_time`, or derived boundary fields. Those fields were used only for evaluation and certificate simulation after returned clips were frozen.

## 9. Candidate Evaluation Results

Recall values are Nexar-derived-boundary-relative recall.

Best heldout grid rows by candidate, shown for context only:

| candidate_name | theta | budget_type | budget_value | merge_gap | true_derived_recall | returned_duration_fraction | event_hit_count | event_total_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| random_window | 0.3 | top_duration_fraction | 0.5 | 0 | 0.489583 | 0.50697 | 47 | 96 |
| fixed_sliding_window | 0.3 | top_duration_fraction | 0.5 | 0 | 0.0104167 | 0.50697 | 1 | 96 |
| motion_energy | 0.3 | top_duration_fraction | 0.5 | 2.5 | 0.0104167 | 0.50697 | 1 | 96 |

Full table: `tables/nexar_candidate_eval_results_v2.csv`.

## 10. Representation-Based Candidate Status

| candidate_name | status | reason | claim_limitation |
| --- | --- | --- | --- |
| representation_based_candidate | REPRESENTATION_CANDIDATE_NOT_AVAILABLE | No local CLIP/SigLIP package or local representation embedding assets were available; no download approved. | Cheap handcrafted candidate results cannot be generalized to candidate generation overall. |

REPRESENTATION_CANDIDATE_NOT_AVAILABLE.

Cheap handcrafted candidate findings must not be generalized to candidate generation overall.

## 11. Certificate Simulation

Certificate simulation was run only for selected heldout configurations with true_derived_recall >= 0.5.

Top certificate rows:

_empty_

Full tables:

- `tables/nexar_candidate_certificate_results_v2.csv`
- `tables/nexar_candidate_certificate_block_rows_v2.csv`
- `tables/certificate_formula_synthetic_test_v2.csv`

Synthetic formula invariant test:

| test_name | M_hat_O | Y_hat_O | pre_fix_UCB_M_O | fixed_UCB_M_O | fixed_LCB_Y_O | pre_fix_passes_ucb_invariant | fixed_passes_ucb_invariant | fixed_passes_lcb_invariant |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pre_fix_cap_ucb_by_lcb_known_failure | 40 | 20 | 12 | 55 | 12 | False | True | True |

## 12. Selectivity Stratification

No subtype/severity field is available in the current Nexar-derived labels.

Pooled recall should not be interpreted as uniform performance across event severities.

See `reports/SELECTIVITY_STRATIFICATION_REPORT.md`.

## 13. Leakage and Invariant Checks

- sample_split == certification enforced in certificate computation
- used_for_design == false enforced in certificate computation
- used_for_repair == false enforced in certificate computation
- row-level block audit table persisted
- UCB_M_O >= M_hat_O - 1e-9 enforced
- LCB_Y_O <= Y_hat_O + 1e-9 enforced
- event-boundary fields excluded from candidate generation
- video-level candidate_dev / heldout_report split used

## 14. Figures

- `figures/recall_vs_budget_by_candidate_v2.png`
- `figures/returned_duration_vs_recall_v2.png`
- `figures/runtime_vs_recall_v2.png`
- `figures/certificate_success_by_candidate_v2.png`
- `figures/lcb_by_candidate_v2.png`

## 15. Findings

The v2 run is interpretable only as Nexar-200 derived-boundary candidate feasibility. The imported VLM audit shows that Nexar positives do not reliably match O_enter_ego_path_v0, so these results cannot support O_enter_ego_path_v0 oracle-relative claims.

## 16. Limitations

- External labels are LOOSE_APPROXIMATION / AUDIT_UNRELIABLE.
- Boundaries are derived from alert time to event moment, not native human event boundaries.
- Heldout certificate sample size is smaller than the Phase 0.6 power-simulation regime associated with consistently non-vacuous certificates.
- Representation-based candidate was unavailable locally.

## 17. Next Action

Build a small VLM/human-adjudicated O_enter_ego_path_v0 benchmark or add a local representation-based candidate before making broader candidate-generation claims.

## 18. Final Decision

NEXAR_CANDIDATE_DECISION: CANDIDATE_STILL_TOO_WEAK (Nexar-200 only, derived boundary)
