# Baseline Adapter Real-CSV Dry-Run Report

## Scope

This dry-run used existing CSV artifacts only. No GPU, VLM, YOLO, model inference, training, data download, or baseline algorithm change was performed.

Adapter code used from:

```text
refe_repos/adapter
```

Output directory:

```text
outputs/baseline_adapter_dryrun
```

## Input CSV Search Result

Usable selected mini-universe:

- Frame/window units: `src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_label_aligned/base_units.csv`
- Existing cheap proxy signals: `src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_label_aligned/cheap_signals_per_unit.csv`
- Existing offline replay labels: `src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_label_aligned/full_reference_units.csv`
- Existing reference events: `src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_label_aligned/reference_events.csv`

Other candidates observed but not used:

- `experiments/frame_level/*/supg_source.csv`: already contains `id,label,proxy_score`, but lacks video/time fields and a matching reference segment file.
- `experiments/roadclip_budget_v2/roadclip_budget_v2/vlm_oracle_expanded/proxy_scores.csv` plus `vlm_labels_conservative.csv`: joinable by `clip_id`, but no unambiguous event-level reference segment CSV was selected for this dry-run.
- `outputs/late_aqp_low_budget_fix_v1/new_labels/*realcartest_5k*.csv`: usable small label/event files, but the selected clean interval universe has clearer unit/proxy/reference alignment.

## Adapter-Ready Files

Generated:

```text
outputs/baseline_adapter_dryrun/frame_scores_adapter_ready.csv
outputs/baseline_adapter_dryrun/reference_segments_adapter_ready.csv
outputs/baseline_adapter_dryrun/field_mapping_report.csv
outputs/baseline_adapter_dryrun/input_audit_summary.csv
```

Input audit summary:

```text
frame_source_rows=600
frame_source_videos=1
oracle_label_present=True
oracle_positive_rows=80
proxy_score_min=0.026383
proxy_score_max=0.520573
reference_segments_present=True
reference_segments=20
```

Field mapping:

| adapter_field         | source_file                                                                                         | source_field                                | transform                             |
|:----------------------|:----------------------------------------------------------------------------------------------------|:--------------------------------------------|:--------------------------------------|
| video_id              | src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_label_aligned/base_units.csv             | video_id                                    | as string                             |
| frame_idx             | src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_label_aligned/base_units.csv             | row order after video_id,t_start,t_end sort | 0-based integer unit index            |
| timestamp             | src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_label_aligned/base_units.csv             | t_start                                     | float                                 |
| proxy_score           | src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_label_aligned/cheap_signals_per_unit.csv | cheap_fused_score                           | clip to [0,1]; no new proxy generated |
| oracle_label          | src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_label_aligned/full_reference_units.csv   | label_event                                 | int(label_event > 0)                  |
| start_frame           | src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_label_aligned/base_units.csv             | t_start                                     | round(t_start * 10)                   |
| end_frame             | src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_label_aligned/base_units.csv             | t_end                                       | round(t_end * 10) - 1                 |
| start_time            | src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_label_aligned/base_units.csv             | t_start                                     | float                                 |
| end_time              | src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_label_aligned/base_units.csv             | t_end                                       | float                                 |
| reference.start_frame | src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_label_aligned/reference_events.csv       | t_start                                     | round(t_start * 10)                   |
| reference.end_frame   | src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_label_aligned/reference_events.csv       | t_end                                       | round(t_end * 10) - 1                 |

Notes:

- The dry-run record is a 2-second window/unit, not a raw decoded video frame.
- `proxy_score` uses existing `cheap_fused_score`, clipped to `[0,1]`; no new proxy was generated.
- `oracle_label` uses existing `label_event` from `full_reference_units.csv` and is converted to 0/1 for replay.
- Temporal IoU frame coordinates use decisecond ticks: `start_frame=round(t_start*10)`, `end_frame=round(t_end*10)-1`.

## Reference Segments

Reference segments were found and converted from:

```text
src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_label_aligned/reference_events.csv
```

Because `--reference-segments` was supplied to every run, `audit_metrics.csv` contains real recall/precision/F1 values under the VLM-defined pseudo-oracle reference for this mini-universe.

## Dry-Run Commands

Budgets:

```text
5,10,20
```

Methods run:

- `ARC-proxy-only`
- `ARC-refinement`
- `SUPG-RT-all-selected`
- `SUPG-RT-confirmed-only`
- `ABae-stratified-confirmed`

ARC dry-run threshold:

```text
0.3
```

Reason: with threshold `0.5`, one ARC-refinement run hit an original ARC edge case where all candidate clips became empty and confidence became NaN. This dry-run did not modify ARC logic; it used a less sparse proxy threshold to validate adapter interoperability.

## Combined Audit Metrics

Generated:

```text
outputs/baseline_adapter_dryrun/combined_audit_metrics.csv
```

| method                    |   budget |   num_segments |   segment_recall |   segment_precision |   segment_f1 |   mean_iou |   duplicate_rate |   oracle_calls |   proxy_calls |
|:--------------------------|---------:|---------------:|-----------------:|--------------------:|-------------:|-----------:|-----------------:|---------------:|--------------:|
| ABae-stratified-confirmed |        5 |              0 |              0   |           0         |    0         |    0       |                0 |              5 |           600 |
| ABae-stratified-confirmed |       10 |              0 |              0   |           0         |    0         |    0       |                0 |             10 |           600 |
| ABae-stratified-confirmed |       20 |              1 |              0   |           0         |    0         |    0       |                0 |             20 |           600 |
| ARC-proxy-only            |        5 |             50 |              0   |           0         |    0         |    0       |                0 |              0 |           600 |
| ARC-proxy-only            |       10 |             50 |              0   |           0         |    0         |    0       |                0 |              0 |           600 |
| ARC-proxy-only            |       20 |             50 |              0   |           0         |    0         |    0       |                0 |              0 |           600 |
| ARC-refinement            |        5 |             49 |              0.1 |           0.0408163 |    0.057971  |    0.82979 |                0 |              5 |           600 |
| ARC-refinement            |       10 |             48 |              0.1 |           0.0416667 |    0.0588235 |    0.82979 |                0 |             10 |           600 |
| ARC-refinement            |       20 |             48 |              0.1 |           0.0416667 |    0.0588235 |    0.82979 |                0 |             20 |           600 |
| SUPG-RT-all-selected      |        5 |              9 |              0   |           0         |    0         |    0       |                0 |              5 |           600 |
| SUPG-RT-all-selected      |       10 |              1 |              0   |           0         |    0         |    0       |                0 |             10 |           600 |
| SUPG-RT-all-selected      |       20 |              1 |              0   |           0         |    0         |    0       |                0 |             20 |           600 |
| SUPG-RT-confirmed-only    |        5 |              0 |              0   |           0         |    0         |    0       |                0 |              5 |           600 |
| SUPG-RT-confirmed-only    |       10 |              2 |              0   |           0         |    0         |    0       |                0 |             10 |           600 |
| SUPG-RT-confirmed-only    |       20 |              4 |              0   |           0         |    0         |    0       |                0 |             20 |           600 |

## Output Completeness And Budget Checks

Generated:

```text
outputs/baseline_adapter_dryrun/dryrun_output_checks.csv
```

| result_dir                                                 | method                    |   budget |   segments_rows |   oracle_log_rows_for_method |   oracle_calls | oracle_calls_le_budget   | files_ok   |
|:-----------------------------------------------------------|:--------------------------|---------:|----------------:|-----------------------------:|---------------:|:-------------------------|:-----------|
| outputs/baseline_adapter_dryrun/results/abae_b10           | ABae-stratified-confirmed |       10 |               0 |                           10 |             10 | True                     | True       |
| outputs/baseline_adapter_dryrun/results/abae_b20           | ABae-stratified-confirmed |       20 |               1 |                           20 |             20 | True                     | True       |
| outputs/baseline_adapter_dryrun/results/abae_b5            | ABae-stratified-confirmed |        5 |               0 |                            5 |              5 | True                     | True       |
| outputs/baseline_adapter_dryrun/results/arc_proxy_b10      | ARC-proxy-only            |       10 |              50 |                            0 |              0 | True                     | True       |
| outputs/baseline_adapter_dryrun/results/arc_proxy_b20      | ARC-proxy-only            |       20 |              50 |                            0 |              0 | True                     | True       |
| outputs/baseline_adapter_dryrun/results/arc_proxy_b5       | ARC-proxy-only            |        5 |              50 |                            0 |              0 | True                     | True       |
| outputs/baseline_adapter_dryrun/results/arc_refinement_b10 | ARC-refinement            |       10 |              48 |                           10 |             10 | True                     | True       |
| outputs/baseline_adapter_dryrun/results/arc_refinement_b20 | ARC-refinement            |       20 |              48 |                           20 |             20 | True                     | True       |
| outputs/baseline_adapter_dryrun/results/arc_refinement_b5  | ARC-refinement            |        5 |              49 |                            5 |              5 | True                     | True       |
| outputs/baseline_adapter_dryrun/results/supg_b10           | SUPG-RT-all-selected      |       10 |               1 |                           10 |             10 | True                     | True       |
| outputs/baseline_adapter_dryrun/results/supg_b10           | SUPG-RT-confirmed-only    |       10 |               2 |                           10 |             10 | True                     | True       |
| outputs/baseline_adapter_dryrun/results/supg_b20           | SUPG-RT-all-selected      |       20 |               1 |                           20 |             20 | True                     | True       |
| outputs/baseline_adapter_dryrun/results/supg_b20           | SUPG-RT-confirmed-only    |       20 |               4 |                           20 |             20 | True                     | True       |
| outputs/baseline_adapter_dryrun/results/supg_b5            | SUPG-RT-all-selected      |        5 |               9 |                            5 |              5 | True                     | True       |
| outputs/baseline_adapter_dryrun/results/supg_b5            | SUPG-RT-confirmed-only    |        5 |               0 |                            5 |              5 | True                     | True       |

Findings:

- Every result directory contains `segments.csv`, `oracle_log.csv`, and `audit_metrics.csv`.
- Every method/budget row has `oracle_calls <= budget`.
- `ARC-proxy-only` has `oracle_calls=0` for all budgets.
- SUPG emitted a runtime warning in one small-budget run from the upstream selector's recall-bound calculation, but still wrote complete output files and stayed within budget.

## Successful Baselines

All requested baselines succeeded on the selected adapter-ready input:

- `ARC-proxy-only`: success for budgets 5, 10, 20.
- `ARC-refinement`: success for budgets 5, 10, 20.
- `SUPG-RT-all-selected`: success for budgets 5, 10, 20.
- `SUPG-RT-confirmed-only`: success for budgets 5, 10, 20.
- `ABae-stratified-confirmed`: success for budgets 5, 10, 20.

## Metrics Interpretation

- Recall/precision/F1 are segment-level temporal IoU metrics using the adapter's greedy one-to-one matching.
- These numbers are VLM-defined pseudo-oracle-relative, not human ground truth.
- This is a small-budget dry-run for protocol validation, not a benchmark conclusion.

## Next Human Confirmation Needed

- Confirm that `cheap_fused_score` is the desired shared proxy column for baseline comparison; `primary_signal_score` is also available in the same source table.
- Confirm that decisecond tick conversion is acceptable for adapter `start_frame/end_frame` when the source units are 2-second windows.
- Confirm the ARC threshold for future comparisons. `0.3` was used only to avoid an original ARC empty-candidate edge case in dry-run.
- Confirm whether roadclip or frame-level `supg_source.csv` artifacts should be included in a later broader comparison after a matching reference segment source is selected.
- Confirm that VLM-defined pseudo-oracle labels are acceptable for this baseline comparison table and should not be described as human ground truth.
