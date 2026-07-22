# Protocol Confirmation

## Inputs

- Frame/unit CSV: `outputs/real_video_protocol_pilot_v1/frame_scores_adapter_ready.csv`
- Reference segments CSV: `outputs/real_video_protocol_pilot_v1/reference_segments_adapter_ready.csv`
- Units: 120
- Reference events: 20
- Video ids: realcartest

All methods in this comparison read the same `frame_scores_adapter_ready.csv` and are evaluated against the same `reference_segments_adapter_ready.csv`.

## Metric Protocol

- Primary metric: `event_detection@overlap_any`.
- Sensitivity rules: `overlap_min_seconds_1.0`, `iou_0.1`, `iou_0.3`, `iou_0.5`.
- Strict boundary IoU@0.5 is retained only as `strict_boundary_iou_0.5`; it is a boundary diagnostic, not the main event-discovery metric.
- Boundary quality fields include `matched_mean_iou`, `all_reference_best_iou_mean`, start/end error, coverage, and overcoverage.
- `overlap_any` means event detection by temporal intersection. It must not be interpreted as precise boundary localization.

## Upper Bounds

The metric repair report established that oracle-positive evidence-core upper bound has `overlap_any` recall/F1 = 1.0/1.0 for this pilot universe. Reference-closure is diagnostic only because it uses reference boundaries and is not a baseline.
