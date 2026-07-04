# Clean V2 No-Leak Fix Report

## Executive Summary

- Feature-only leakage fixed: **yes**.
- Calibration Brier mismatch fixed: **yes**.
- Clean audit verdict: **WARNING**.
- Clean audit BLOCKER: **no**.
- Clean v2 Level 2 judgement: **Negative**.
- Recommendation: **proceed to `reference_duration_stratified_eval_v1` with documented baseline-fairness warnings**.

## What Changed

1. Created isolated clean experiment:
   - `src/garc_eval/experiments/clean_interval_aqp_full_reference_v2_clean_no_leak/`
   - `src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/`

2. Replaced blacklist/drop-based feature generation with a whitelist:
   - `FEATURES_ALLOWED_COLUMNS`
   - `LABEL_COLUMNS`
   - `interval_lattice_features_only.csv` is emitted from the candidate lattice before label joins, not from the joined label table.

3. Hardened no-leak execution:
   - `run_all.sh` fails if forbidden/reference-derived fields appear in `interval_lattice_features_only.csv`.
   - CILS, cheap-score baselines, threshold/top-k baselines, and stress variants read `interval_lattice_features_only.csv` for algorithm input.
   - Full labels are used only for `interval_labels_v2_clean.csv`, oracle replay lookup, upper-bound diagnostics, and final evaluation.

4. Fixed calibration metrics:
   - Calibration target remains `answer_iou_0_3`.
   - Brier is computed as `mean((p_hat - y)^2)`.
   - ECE uses fixed 5 bins.
   - Per-bin details are written to `calibration_bins_v2_clean.csv`.
   - Empty CILS return sets are represented as `observed_precision=NaN`, `precision_violation_rate=NaN`, and `empty_return_rate=1.0`, not as precision success.

## Verification

- Clean v2 command:
  `bash src/garc_eval/experiments/clean_interval_aqp_full_reference_v2_clean_no_leak/run_all.sh`
- Clean audit command:
  `bash src/garc_eval/experiments/clean_interval_aqp_code_audit_v2_clean_no_leak/run_audit.sh`

Clean audit result:

- Overall verdict: **WARNING**
- BLOCKER present: **no**
- Calibration Brier recompute max diff: **0.0**
- Lattice oracle upper bound IoU@0.3: **0.550**
- CILS max event recall IoU@0.3: **0.000**

## Required Answers

1. Feature-only leakage fixed: **yes**. Clean audit reports no forbidden/reference-derived fields in `interval_lattice_features_only.csv`.
2. Calibration Brier inconsistency fixed: **yes**. Independent recomputation matches exactly.
3. Clean audit verdict: **WARNING**.
4. Clean v2 lattice upper bound still near 0.55: **yes**, recomputed as **0.550**.
5. Clean v2 CILS max recall still 0: **yes**, max `event_recall_iou_0_3 = 0.000`.
6. v2 Negative trustworthy under clean no-leak setting: **yes**, as an artifact-level pseudo-oracle result with baseline-fairness warnings.
7. Enter `reference_duration_stratified_eval_v1`: **yes**, with documented warnings; no BLOCKER remains.

## Remaining Warnings

The clean audit still flags oracle-confirmed / ARC-style simplified baselines as requiring careful interpretation because they use budgeted answer labels during oracle replay or confirmation. They are acceptable as budgeted replay baselines, not as cheap production algorithms.
