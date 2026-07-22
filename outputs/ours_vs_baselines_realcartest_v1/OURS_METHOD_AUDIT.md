# Ours Method Audit

## Located Code Or Outputs

Found a runnable historical method implementation named `Frozen-LATE-AQP-v1`:

- `outputs/late_aqp_frozen_cross_segment_v1/run_frozen_cross_segment.py`
- `outputs/late_aqp_frozen_cross_segment_v1/FINAL_REPORT.md`
- `outputs/late_aqp_frozen_cross_segment_v1/repair_trace_calls.csv`
- `outputs/late_aqp_frozen_cross_segment_v1/repair_trace_selected_intervals.csv`

No new model, VLM, YOLO, training, or proxy materialization is needed for this comparison. The wrapper in this directory replays the same budget logic on the current `realcartest_2000_3200` adapter-ready CSV and writes adapter-format `segments.csv` and `oracle_log.csv`.

## Method Identity Used Here

Comparison method name: `Ours-Frozen-LATE-AQP-v1`.

This is treated as the available Ours candidate in the repository. It is not relabeled as ARC, SUPG, or ABae. It is also not claimed to be a human-ground-truth system; all labels are pseudo-oracle labels from the existing CSV.

## Inputs

- `frame_idx`, `start_time`, `end_time`, `start_frame`, `end_frame` from the adapter-ready unit CSV.
- `proxy_score` as the cheap score. The wrapper aliases this to the historical `prior_score_max`.
- `oracle_label` only when a unit is selected by the budgeted call sequence.

## Output

Each run writes:

- `segments.csv`
- `oracle_log.csv`

The final comparison does not use legacy `audit_metrics.csv`; all methods are re-evaluated by the repaired event-detection protocol.

## Oracle Budget Use

The wrapper follows the historical Frozen-LATE-AQP-v1 phases:

- top-20-percent proxy envelope construction from proxy only;
- small inside/outside audit sample;
- optional repair expansion only if a queried outside unit is positive;
- remaining discovery calls by proxy rank.

`oracle_label` is read only for units already selected as budgeted calls. It is not used to pre-rank all units, construct the proxy envelope, tune thresholds, or repair to reference boundaries.

## Leakage Audit

- Reference segments are not used by Ours selection.
- Unqueried `oracle_label` values are not used by Ours selection.
- Boundary output is the merged selected unit boundaries, not post-hoc reference-aware boundary correction.
- Risk: the method is evaluated on pseudo-oracle/VLM-defined labels, not human ground truth. Claims must use pseudo-oracle language.

## Fairness Status

Fairly connectable to the current benchmark as a CSV replay method under the same unit grid, input CSV, budget list, and repaired metrics.
