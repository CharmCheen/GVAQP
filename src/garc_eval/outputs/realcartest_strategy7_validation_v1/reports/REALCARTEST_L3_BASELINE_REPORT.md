# Realcartest L3 Baseline Report

- Output timestamp: 2026-06-27T12:37:51Z
- Candidate universe: 399 anchors.
- Existing V13.8 positives: 94; negatives: 305.
- Realcartest positive rate: 0.235589 (94/399).
- `object_count_mean` AUC: 0.756418.
- Dataset3 clean-pool positive rate is not directly comparable to this full realcartest anchor universe.

## Policy Boundary

- `L3_object_count_mean` sorts by `object_count_mean` descending with timestamp/anchor-id tie breaks; no labels are used.
- `L3_temporal_maxmin` first forms a top `2B` cheap-proxy candidate pool, then greedily maximizes timestamp spread; no labels are used.
- `uniform_random` uses 500 fixed seeds and no labels.

## L3 Object Count Curve

| B | selected positives | precision | anchor recall | event recall | L3-missed positives |
|---:|---:|---:|---:|---:|---:|
| 20 | 16.000 | 0.800000 | 0.170213 | 0.137255 | 78.000 |
| 20 | 16.000 | 0.800000 | 0.170213 | 0.137255 | 78.000 |
| 30 | 22.000 | 0.733333 | 0.234043 | 0.176471 | 72.000 |
| 30 | 22.000 | 0.733333 | 0.234043 | 0.176471 | 72.000 |
| 40 | 27.000 | 0.675000 | 0.287234 | 0.215686 | 67.000 |
| 40 | 27.000 | 0.675000 | 0.287234 | 0.215686 | 67.000 |
| 60 | 39.000 | 0.650000 | 0.414894 | 0.333333 | 55.000 |
| 60 | 39.000 | 0.650000 | 0.414894 | 0.333333 | 55.000 |
| 80 | 50.000 | 0.625000 | 0.531915 | 0.411765 | 44.000 |
| 80 | 50.000 | 0.625000 | 0.531915 | 0.411765 | 44.000 |
| 100 | 53.000 | 0.530000 | 0.563830 | 0.450980 | 41.000 |
| 100 | 53.000 | 0.530000 | 0.563830 | 0.450980 | 41.000 |
| 150 | 62.000 | 0.413333 | 0.659574 | 0.568627 | 32.000 |
| 150 | 62.000 | 0.413333 | 0.659574 | 0.568627 | 32.000 |
