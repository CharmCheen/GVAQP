# Real Video Protocol Pilot Report

## 1. Scope

This was a small protocol pilot, not a formal benchmark. It used existing CSV artifacts only: no model training, no VLM/YOLO run, no data download, and no modification to ARC/SUPG/ABae source code or adapter algorithm logic.

Output directory: `outputs/real_video_protocol_pilot_v1`.

## 2. Selected Pilot Universe

Selected universe: `realcartest_2000_3200`.

| item | value |
|---|---:|
| duration_seconds | 1200 |
| unit_count | 120 |
| unit_duration_seconds | 10 |
| positive_units | 32 |
| reference_events | 20 |
| short_reference_events_lt_2s | 14 |
| proxy_column | `prior_score_max` |

Source files:

- `outputs/late_aqp_frozen_cross_segment_v1/grid_realcartest_2000_3200.csv`
- `outputs/late_aqp_frozen_cross_segment_v1/ref_events_realcartest_2000_3200.csv`

Important data caveat: the historical manifest source `/qiuyeqing/llama_prl/G-ARC/try_or_no/videos/realcartest.mp4` is missing on this server. This pilot validates the real-video-derived CSV replay protocol, not fresh video decoding. The available `dataset3` video has proxy and labels, but no reliable stitched reference boundary file suitable for this adapter evaluation was found.

## 3. Hardware Use

No GPU was used. This run was CSV materialization, reference-unit auditing, and lightweight adapter replay only.

## 4. Input / Output Protocol

Generated adapter inputs:

- `frame_scores_adapter_ready.csv`
- `reference_segments_adapter_ready.csv`

Field mapping is documented in `FIELD_MAPPING.md`.

Key mapping choices:

- `frame_idx` is the 10-second unit/bin index from `bin_idx`, not the raw video frame number.
- `timestamp` is the unit start time in seconds relative to the selected 20-minute window.
- `proxy_score` is `prior_score_max`, clipped to `[0,1]`; no new proxy was generated.
- `oracle_label` is `is_positive` converted to 0/1 for offline pseudo-oracle replay.
- `start_frame/end_frame` use relative decisecond ticks: `round(t_start * 10)` and `round(t_end * 10) - 1`.

## 5. Reference / Unit Alignment Result

Reference-unit audit outputs:

- `per_reference_coverage.csv`
- `positive_unit_attribution.csv`
- `oracle_upper_bound_by_threshold.csv`
- `REFERENCE_UNIT_PROTOCOL_AUDIT.md`

Coverage findings:

| check | value |
|---|---:|
| references_with_any_overlapping_unit | 20/20 |
| references_with_positive_unit | 20/20 |
| positive_units_outside_any_reference | 0/32 |
| references_hit_by_evidence_core_at_iou_0.5 | 6/20 |

Oracle upper bounds:

| upper_bound_type   |   iou_threshold |   num_segments |   segment_recall |   segment_precision |   segment_f1 |   mean_iou |   matched_pairs |
|:-------------------|----------------:|---------------:|-----------------:|--------------------:|-------------:|-----------:|----------------:|
| evidence-core      |             0.1 |             20 |              0.3 |                 0.3 |          0.3 |     0.6383 |               6 |
| reference-closure  |             0.1 |             20 |              1   |                 1   |          1   |     1      |              20 |
| evidence-core      |             0.2 |             20 |              0.3 |                 0.3 |          0.3 |     0.6383 |               6 |
| reference-closure  |             0.2 |             20 |              1   |                 1   |          1   |     1      |              20 |
| evidence-core      |             0.3 |             20 |              0.3 |                 0.3 |          0.3 |     0.6383 |               6 |
| reference-closure  |             0.3 |             20 |              1   |                 1   |          1   |     1      |              20 |
| evidence-core      |             0.4 |             20 |              0.3 |                 0.3 |          0.3 |     0.6383 |               6 |
| reference-closure  |             0.4 |             20 |              1   |                 1   |          1   |     1      |              20 |
| evidence-core      |             0.5 |             20 |              0.3 |                 0.3 |          0.3 |     0.6383 |               6 |
| reference-closure  |             0.5 |             20 |              1   |                 1   |          1   |     1      |              20 |

Interpretation:

- Oracle-positive units cover all reference events at overlap/detection level.
- Evidence-core segments only reach 0.30 recall/F1 at IoU=0.5 because many references are point-anchor or sub-2s events while units are 10s bins.
- Reference-closure diagnostic upper bound is 1.0 because every reference contains at least one positive unit. This confirms that detection evidence exists, but boundary-level IoU is not aligned with the current unit granularity.
- Current evaluation should be split into event detection recall and boundary quality before formal benchmark use.

## 6. Baseline Pilot Result

All requested methods and budgets ran successfully. These numbers are protocol smoke results, not benchmark conclusions.

Best score by method:

| method                    |   max_recall |   max_precision |   max_f1 |   max_oracle_calls |   runs |
|:--------------------------|-------------:|----------------:|---------:|-------------------:|-------:|
| ABae-stratified-confirmed |         0.15 |          0.5    |   0.1765 |                 50 |      4 |
| ARC-proxy-only            |         0    |          0      |   0      |                  0 |      4 |
| ARC-refinement            |         0    |          0      |   0      |                 50 |      4 |
| SUPG-RT-all-selected      |         0    |          0      |   0      |                 43 |      4 |
| SUPG-RT-confirmed-only    |         0.05 |          0.3333 |   0.087  |                 43 |      4 |

Combined baseline metrics:

| method                    |   budget |   num_segments |   segment_recall |   segment_precision |   segment_f1 |   mean_iou |   oracle_calls |
|:--------------------------|---------:|---------------:|-----------------:|--------------------:|-------------:|-----------:|---------------:|
| ARC-proxy-only            |        5 |             21 |             0    |              0      |       0      |     0      |              0 |
| ARC-refinement            |        5 |             21 |             0    |              0      |       0      |     0      |              5 |
| SUPG-RT-all-selected      |        5 |              1 |             0    |              0      |       0      |     0      |              5 |
| SUPG-RT-confirmed-only    |        5 |              2 |             0    |              0      |       0      |     0      |              5 |
| ABae-stratified-confirmed |        5 |              2 |             0.05 |              0.5    |       0.0909 |     0.9346 |              5 |
| ARC-proxy-only            |       10 |             21 |             0    |              0      |       0      |     0      |              0 |
| ARC-refinement            |       10 |             21 |             0    |              0      |       0      |     0      |             10 |
| SUPG-RT-all-selected      |       10 |              1 |             0    |              0      |       0      |     0      |              9 |
| SUPG-RT-confirmed-only    |       10 |              3 |             0.05 |              0.3333 |       0.087  |     0.9346 |              9 |
| ABae-stratified-confirmed |       10 |              5 |             0.1  |              0.4    |       0.16   |     0.9346 |             10 |
| ARC-proxy-only            |       20 |             21 |             0    |              0      |       0      |     0      |              0 |
| ARC-refinement            |       20 |             23 |             0    |              0      |       0      |     0      |             20 |
| SUPG-RT-all-selected      |       20 |              1 |             0    |              0      |       0      |     0      |             18 |
| SUPG-RT-confirmed-only    |       20 |              4 |             0.05 |              0.25   |       0.0833 |     0.9346 |             18 |
| ABae-stratified-confirmed |       20 |              6 |             0.05 |              0.1667 |       0.0769 |     0.9346 |             20 |
| ARC-proxy-only            |       50 |             21 |             0    |              0      |       0      |     0      |              0 |
| ARC-refinement            |       50 |             20 |             0    |              0      |       0      |     0      |             50 |
| SUPG-RT-all-selected      |       50 |              1 |             0    |              0      |       0      |     0      |             43 |
| SUPG-RT-confirmed-only    |       50 |              9 |             0.05 |              0.1111 |       0.069  |     0.9346 |             43 |
| ABae-stratified-confirmed |       50 |             14 |             0.15 |              0.2143 |       0.1765 |     0.9451 |             50 |

Output status:

- Successful adapter runs: 20/20
- Each run wrote `segments.csv`, `oracle_log.csv`, and `audit_metrics.csv`.
- SUPG stopped below requested budget for some budgets by selector logic; no oracle budget was exceeded.
- ARC-proxy-only used zero oracle calls for every budget.

## 7. Validation

Validation checks:

| status | count |
|---|---:|
| PASS | 136 |
| FAIL | 0 |

Checks covered CSV readability, `start_frame <= end_frame`, `oracle_calls <= budget`, ARC-proxy-only zero-oracle behavior, and nonempty metrics when reference segments are present.

## 8. Decision

Decision: `REPAIR_PROTOCOL_FIRST`.

Reason: adapter replay is closed-loop and all baselines emit the required CSVs, but the reference/unit/IoU protocol is not ready for formal benchmark interpretation. The evidence-core upper bound stays at 0.30 at IoU=0.5 while reference-closure reaches 1.0, which indicates a boundary granularity mismatch rather than only a method failure.

## 9. Next Steps

1. Decide whether formal evaluation should report detection recall separately from boundary quality.
2. Repair temporal granularity: either evaluate 10s units with overlap/detection metrics, or generate finer units/boundaries for IoU=0.5 segment evaluation.
3. Restore or locate the raw `realcartest.mp4` source if this universe will remain the formal baseline pilot source.
4. Alternatively, build reliable stitched reference events for `dataset3`, whose raw video is present, then rerun this pilot there.
