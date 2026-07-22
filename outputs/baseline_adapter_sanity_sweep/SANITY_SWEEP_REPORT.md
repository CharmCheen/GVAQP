# Baseline Adapter Sanity Sweep Report

## Scope

This is a lightweight CSV replay sanity sweep only. No model, GPU, VLM, YOLO, training, data download, baseline algorithm change, or original baseline source modification was used.

Inputs:

- `outputs/baseline_adapter_dryrun/frame_scores_adapter_ready.csv`
- `outputs/baseline_adapter_dryrun/reference_segments_adapter_ready.csv`
- `refe_repos/adapter/`

Generated outputs:

- `outputs/baseline_adapter_dryrun/METRIC_DEFINITION_AUDIT.md`
- `outputs/baseline_adapter_dryrun/proxy_reference_alignment.csv`
- `outputs/baseline_adapter_dryrun/ALIGNMENT_SANITY.md`
- `outputs/baseline_adapter_sanity_sweep/arc_threshold_sweep_metrics.csv`
- `outputs/baseline_adapter_sanity_sweep/merge_sensitivity_metrics.csv`
- `outputs/baseline_adapter_sanity_sweep/oracle_upper_bound_metrics.csv`

## Metric Definition Audit

`refe_repos/adapter/common.py` currently computes:

- `mean_iou`: mean IoU over greedily matched prediction/reference pairs only. It is not an all-reference best-IoU average.
- Greedy matching: candidate pairs with IoU >= threshold are sorted by descending IoU and accepted only if both the prediction and reference are still unmatched, so matching is one-to-one.
- `duplicate_rate`: unmatched predictions that overlap an already matched reference at IoU >= threshold divided by number of predictions.

Recommendation: keep existing results unchanged, but for formal reports either document `mean_iou` as matched-pair mean IoU or add a separate `mean_reference_best_iou` field.

## Proxy / Reference Alignment

Proxy distribution summary:

| group                       |   count |   proxy_min |   proxy_p10 |   proxy_p25 |   proxy_median |   proxy_mean |   proxy_p75 |   proxy_p90 |   proxy_max |   oracle_positive_units |
|:----------------------------|--------:|------------:|------------:|------------:|---------------:|-------------:|------------:|------------:|------------:|------------------------:|
| all_units                   |     600 |      0.0264 |      0.1136 |      0.1645 |         0.232  |       0.239  |      0.3088 |      0.3688 |      0.5206 |                      80 |
| oracle_positive_units       |      80 |      0.1058 |      0.206  |      0.2456 |         0.2999 |       0.306  |      0.3619 |      0.4243 |      0.4972 |                      80 |
| oracle_negative_units       |     520 |      0.0264 |      0.1098 |      0.153  |         0.2184 |       0.2287 |      0.2922 |      0.3564 |      0.5206 |                       0 |
| not_reference_covered_units |     520 |      0.0264 |      0.1098 |      0.153  |         0.2184 |       0.2287 |      0.2922 |      0.3564 |      0.5206 |                       0 |

Top-k proxy coverage:

|   top_k |   oracle_positive_units_in_top_k |   oracle_positive_unit_recall |   reference_events_covered_any_overlap |   reference_event_recall_any_overlap |   min_proxy_in_top_k |   mean_proxy_in_top_k |
|--------:|---------------------------------:|------------------------------:|---------------------------------------:|-------------------------------------:|---------------------:|----------------------:|
|       5 |                                2 |                        0.025  |                                      1 |                                 0.05 |               0.4804 |                0.4989 |
|      10 |                                5 |                        0.0625 |                                      2 |                                 0.1  |               0.4721 |                0.4869 |
|      20 |                                7 |                        0.0875 |                                      2 |                                 0.1  |               0.4311 |                0.4702 |
|      50 |                               15 |                        0.1875 |                                      4 |                                 0.2  |               0.3814 |                0.4294 |
|     100 |                               28 |                        0.35   |                                      9 |                                 0.45 |               0.3408 |                0.3942 |
|     200 |                               47 |                        0.5875 |                                     11 |                                 0.55 |               0.2785 |                0.3513 |

Interpretation:

- The pseudo-positive/reference-covered units have higher proxy scores on average than negatives, but the separation is weak.
- Top-20 proxy units cover only 7/80 pseudo-positive units and 2/20 reference events.
- Top-100 proxy units cover 28/80 pseudo-positive units and 9/20 reference events.
- This supports proxy weakness as one reason for low low-budget baseline scores.

## ARC Threshold Sweep

Best successful ARC rows by F1:

| method         |   threshold |   budget |   num_segments |   recall |   precision |     f1 |   mean_iou |   oracle_calls |
|:---------------|------------:|---------:|---------------:|---------:|------------:|-------:|-----------:|---------------:|
| ARC-refinement |         0.2 |       50 |             45 |     0.1  |      0.0444 | 0.0615 |     0.6271 |             50 |
| ARC-refinement |         0.3 |       50 |             46 |     0.1  |      0.0435 | 0.0606 |     0.8298 |             50 |
| ARC-refinement |         0.2 |       20 |             46 |     0.1  |      0.0435 | 0.0606 |     0.6271 |             20 |
| ARC-refinement |         0.3 |       10 |             48 |     0.1  |      0.0417 | 0.0588 |     0.8298 |             10 |
| ARC-refinement |         0.3 |       20 |             48 |     0.1  |      0.0417 | 0.0588 |     0.8298 |             20 |
| ARC-refinement |         0.2 |       10 |             48 |     0.1  |      0.0417 | 0.0588 |     0.6271 |             10 |
| ARC-refinement |         0.3 |        5 |             49 |     0.1  |      0.0408 | 0.058  |     0.8298 |              5 |
| ARC-refinement |         0.2 |        5 |             52 |     0.1  |      0.0385 | 0.0556 |     0.6271 |              5 |
| ARC-proxy-only |         0.1 |        5 |             16 |     0.05 |      0.0625 | 0.0556 |     0.6522 |              0 |
| ARC-proxy-only |         0.1 |       10 |             16 |     0.05 |      0.0625 | 0.0556 |     0.6522 |              0 |

ARC failures:

| method         |   threshold |   budget | status   | error                                                                                                   |
|:---------------|------------:|---------:|:---------|:--------------------------------------------------------------------------------------------------------|
| ARC-refinement |         0.5 |       10 | failed   | 6, in <module>                                                                                          |
|                |             |          |          |     main()                                                                                              |
|                |             |          |          |   File "/qiuyeqing/llama_prl/G-ARC/refe_repos/adapter/arc_baseline/run.py", line 211, in main           |
|                |             |          |          |     outputs = run_refinement(df, args, reference_segments)                                              |
|                |             |          |          |   File "/qiuyeqing/llama_prl/G-ARC/refe_repos/adapter/arc_baseline/run.py", line 158, in run_refinement |
|                |             |          |          |     result = original_arc(                                                                              |
|                |             |          |          |   File "/qiuyeqing/llama_prl/G-ARC/refe_repos/ARC-main/arc/arc.py", line 73, in arc                     |
|                |             |          |          |     int((confidence-tau_confidence)*len(tau_cand_clips)))                                               |
|                |             |          |          | ValueError: cannot convert float NaN to integer                                                         |
| ARC-refinement |         0.5 |       20 | failed   | 6, in <module>                                                                                          |
|                |             |          |          |     main()                                                                                              |
|                |             |          |          |   File "/qiuyeqing/llama_prl/G-ARC/refe_repos/adapter/arc_baseline/run.py", line 211, in main           |
|                |             |          |          |     outputs = run_refinement(df, args, reference_segments)                                              |
|                |             |          |          |   File "/qiuyeqing/llama_prl/G-ARC/refe_repos/adapter/arc_baseline/run.py", line 158, in run_refinement |
|                |             |          |          |     result = original_arc(                                                                              |
|                |             |          |          |   File "/qiuyeqing/llama_prl/G-ARC/refe_repos/ARC-main/arc/arc.py", line 73, in arc                     |
|                |             |          |          |     int((confidence-tau_confidence)*len(tau_cand_clips)))                                               |
|                |             |          |          | ValueError: cannot convert float NaN to integer                                                         |
| ARC-refinement |         0.5 |       50 | failed   | 6, in <module>                                                                                          |
|                |             |          |          |     main()                                                                                              |
|                |             |          |          |   File "/qiuyeqing/llama_prl/G-ARC/refe_repos/adapter/arc_baseline/run.py", line 211, in main           |
|                |             |          |          |     outputs = run_refinement(df, args, reference_segments)                                              |
|                |             |          |          |   File "/qiuyeqing/llama_prl/G-ARC/refe_repos/adapter/arc_baseline/run.py", line 158, in run_refinement |
|                |             |          |          |     result = original_arc(                                                                              |
|                |             |          |          |   File "/qiuyeqing/llama_prl/G-ARC/refe_repos/ARC-main/arc/arc.py", line 73, in arc                     |
|                |             |          |          |     int((confidence-tau_confidence)*len(tau_cand_clips)))                                               |
|                |             |          |          | ValueError: cannot convert float NaN to integer                                                         |

Interpretation:

- `threshold=0.3` should be treated as a dry-run workaround, not a validated default.
- `threshold=0.2` and `threshold=0.3` gave similarly low ARC-refinement recall around 0.10 in this sweep.
- `threshold=0.1` gave the only nonzero ARC-proxy-only recall, but with very low precision.
- `threshold=0.5` was brittle for ARC-refinement at larger budgets because the original ARC refinement path hit an empty-candidate/confidence NaN case. This was recorded, not patched.

## Segment Merge Sensitivity

SUPG/ABae merge sensitivity summary across `max_gap_frames in {0,1,2,5}` and `min_len_frames in {1,2,5,10}`:

| method                    |   budget |   max_recall |   max_precision |   max_f1 |   max_num_segments |   max_selected_positive_units |   oracle_calls |
|:--------------------------|---------:|-------------:|----------------:|---------:|-------------------:|------------------------------:|---------------:|
| ABae-stratified-confirmed |        5 |            0 |               0 |        0 |                  0 |                             0 |              5 |
| ABae-stratified-confirmed |       10 |            0 |               0 |        0 |                  0 |                             0 |             10 |
| ABae-stratified-confirmed |       20 |            0 |               0 |        0 |                  1 |                             1 |             20 |
| SUPG-RT-confirmed-only    |        5 |            0 |               0 |        0 |                  0 |                             0 |              5 |
| SUPG-RT-confirmed-only    |       10 |            0 |               0 |        0 |                  2 |                             2 |             10 |
| SUPG-RT-confirmed-only    |       20 |            0 |               0 |        0 |                  4 |                             4 |             20 |

Interpretation:

- The tested merge settings did not recover nonzero recall/F1 for SUPG-RT-confirmed-only or ABae-stratified-confirmed at budgets 5, 10, and 20.
- The selected confirmed positives were sparse at these budgets, so changing merge parameters alone does not explain the low scores.

## Oracle-Positive Unit Upper Bound

This upper bound uses `oracle_label == 1` directly to form a pseudo-positive unit mask, then applies the same unit-to-segment conversion and IoU evaluation. It is not a baseline.

Unique upper-bound metric rows across the merge sweep:

|   max_gap_frames |   min_len_frames |   num_segments |   recall |   precision |   f1 |   mean_iou |   oracle_calls |
|-----------------:|-----------------:|---------------:|---------:|------------:|-----:|-----------:|---------------:|
|                0 |                1 |             20 |      0.3 |         0.3 |  0.3 |      0.922 |            600 |

Interpretation:

- The oracle-positive-unit upper bound reaches only recall/F1 0.30 against the reference segments at IoU >= 0.5.
- Since even direct pseudo-positive units only match 6/20 references under the current conversion/evaluation protocol, low baseline scores are not only a proxy issue.
- This indicates a reference/unit/merge/IoU protocol alignment problem that must be resolved before formal comparison.

## Answers To Required Questions

### Is low score mainly proxy weakness or reference/merge/IoU protocol issue?

Both are present. The proxy is weak for low-budget selection, as top-k coverage is low. However, the stronger blocker is protocol alignment: the oracle-positive-unit upper bound is only recall/F1 0.30, which means the current unit-to-segment/reference/IoU setup cannot support reliable formal comparison even with direct pseudo-positive units.

### Is ARC threshold 0.3 a workaround or reasonable default?

It is only a dry-run workaround. The sweep does not justify it as a formal default. Threshold 0.2 and 0.3 behave similarly for ARC-refinement, threshold 0.1 is better for proxy-only recall but worse for precision, and threshold 0.5 is brittle in the original ARC refinement path.

### Does `mean_iou` need renaming or an added field?

Yes for clarity. Existing `mean_iou` is matched-pair mean IoU. Do not rewrite old results, but formal tables should either rename it to `mean_matched_iou` or add `mean_reference_best_iou` as a separate field.

### Is the oracle-positive-unit upper bound high enough?

No. Recall/F1 0.30 is too low for treating this adapter-ready data and reference setup as a reliable benchmark protocol.

### Can this enter formal comparison with the target method?

No. The current dry-run is useful as an integration check, but it should not be used as a formal benchmark yet. First resolve the reference/unit/merge/IoU alignment issue, then rerun the upper-bound sanity check. A reasonable gate is that the oracle-positive-unit upper bound should recover most reference events before comparing methods.

## Next Manual Checks

- Verify whether `reference_segments_adapter_ready.csv` uses the same temporal coordinate convention as `frame_scores_adapter_ready.csv`.
- Confirm whether unit-level positives represent whole events, event centers, sampled evidence points, or partial overlaps.
- Decide whether evaluation should compare unit-derived segments to reference event spans directly, or use an event-level expansion/aggregation policy outside these baseline adapters.
- Document the selected IoU threshold and segment conversion rule before formal benchmark runs.
