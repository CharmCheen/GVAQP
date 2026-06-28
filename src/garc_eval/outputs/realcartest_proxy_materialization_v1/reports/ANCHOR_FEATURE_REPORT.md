# ANCHOR_FEATURE_REPORT.md - realcartest anchor proxy features

## Method

- Raw detections: YOLOv8n at 2 fps over realcartest.mp4.
- Anchor table: V13.7 center10 anchor grid, 399 anchors.
- Window definition: confirmed dataset3-compatible anchor_time +/- 5 s, 10 s center window.
- Aggregates are computed over processed sampled frames in the anchor window.

## Headline

| Key | Value |
|---|---:|
| anchor_total | 399 |
| anchor_timestamp_mapped | 399 |
| anchors_with_missing_or_warning | 0 |
| positive_labeled_anchors | 94 |
| negative_labeled_anchors | 305 |
| l3_required_fields_reproducible | YES |

## Frame Coverage

- Processed frames per anchor window: n=399, mean=19.987, std=0.305, min=14.000, p25=20.000, median=20.000, p75=20.000, max=21.000
- Sampled frames per anchor window: n=399, mean=19.987, std=0.305, min=14.000, p25=20.000, median=20.000, p75=20.000, max=21.000

## Proxy Distributions

- object_count_mean: n=399, mean=6.056, std=2.860, min=0.150, p25=3.950, median=5.650, p75=7.750, max=15.400
- vehicle_count_mean: n=399, mean=5.543, std=2.590, min=0.000, p25=3.575, median=5.400, p75=7.225, max=11.800
- person_count_mean: n=399, mean=0.332, std=0.675, min=0.000, p25=0.000, median=0.050, p75=0.300, max=5.800
- lateral_presence_mean: n=399, mean=0.858, std=0.242, min=0.000, p25=0.800, median=1.000, p75=1.000, max=1.000

## Missingness

- proxy_feature_warning counts: {'NONE': 399}

## Decision

Anchor-level proxy feature extraction is complete and L3 fields are computable.
