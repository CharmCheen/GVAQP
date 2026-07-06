# Low-Budget Diagnosis, Tuning, and Re-Validation for LATE-AQP

This directory contains the complete workflow for diagnosing the B=10/20 low-budget failure of Frozen-LATE-AQP-v1, tuning the audit schedule, and re-validating the selected Frozen-LATE-AQP-v2 configuration.

## Workflow

1. **Diagnosis** (no GPU): `budget_allocation_diagnosis.py` → `budget_allocation_diagnosis.md`
2. **Data availability** (no GPU): `data_availability_report.py` → `data_availability_report.md`
3. **One-time labeling** (GPU): `label_videos.py` → `new_labels/`, `labeling_cost_report.md`
4. **Tuning** (no GPU): `run_low_budget_replay.py` → `tuning_results.csv`
5. **Refreeze**: `frozen_v2_config.md`
6. **Final validation** (no GPU): `run_low_budget_replay.py` → `final_validation_results.csv`, `final_validation_report.md`

## Key findings

- Diagnosis: at B=10/20 Ours actually spends a *smaller* share of budget on audit than at B=40. The failure is therefore not "audit consumes too much" but rather a cold-start / trigger-starvation problem: too few outside-envelope positives are found to seed repair expansions.
- Because the original `realcartest.mp4` is no longer present in the workspace, additional realcartest footage could not be labeled. The only newly labeled video was `realcartest_5k.mp4`.
- Tuning on `realcartest_5k` did not reproduce the original low-budget failure (all variants achieved 100% long-event recall at B=10/20). `cold_start_fallback` was selected because it improved B=5 recall/precision without hurting B=10/20.
- Final validation on the unused existing interval `realcartest_3830_3920` showed no degradation versus v1.

## Deliverables

- `budget_allocation_diagnosis.md`
- `data_availability_report.md`
- `labeling_cost_report.md`
- `frozen_v2_config.md`
- `final_validation_report.md`
- `tuning_results.csv`
- `final_validation_results.csv`
- `new_labels/center10_vlm_oracle_events_realcartest_5k.csv` and supporting files

## Caution

The tuning/final-validation split is constrained by data availability. Both segments come from the only usable labeled source (`realcartest_5k` for tuning, existing `realcartest` tail for final validation). The original low-budget failure on the main `realcartest` cross-segment validation could not be directly re-tested because that footage is no longer available.
