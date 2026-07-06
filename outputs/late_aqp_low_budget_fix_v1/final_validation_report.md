# Final Validation Report — Frozen-LATE-AQP-v2

**Selected v2 variant**: `cold_start_fallback` (tuned on `realcartest_5k_tuning`; validated on `realcartest_3830_3920_final`).

## Tuning-stage long-event recall (source: tuning segment labels)

| Budget | B6 | B7 | v1 | floor_a | floor_b | cold_start_fallback |
|--------|----|----|----|---------|---------|---------------------|
| 5 | 0.700 | 0.900 | 0.600 | 0.600 | 0.700 | 1.000 |
| 10 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| 20 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| 40 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| 80 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| 120 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## Final validation long-event recall (source: final validation segment labels)

| Budget | B6 | B7 | v1 | v2 |
|--------|----|----|----|----|
| 5 | 0.600 | 1.000 | 0.000 | 0.000 |
| 10 | 1.000 | 1.000 | 1.000 | 1.000 |
| 20 | 1.000 | 1.000 | 1.000 | 1.000 |
| 40 | 1.000 | 1.000 | 1.000 | 1.000 |
| 80 | 1.000 | 1.000 | 1.000 | 1.000 |
| 120 | 1.000 | 1.000 | 1.000 | 1.000 |

## Final validation precision (source: final validation segment labels)

| Budget | B6 | B7 | v1 | v2 |
|--------|----|----|----|----|
| 5 | 0.088 | 0.120 | 0.000 | 0.000 |
| 10 | 0.120 | 0.120 | 0.120 | 0.120 |
| 20 | 0.120 | 0.120 | 0.120 | 0.120 |
| 40 | 0.120 | 0.120 | 0.120 | 0.120 |
| 80 | 0.120 | 0.120 | 0.120 | 0.120 |
| 120 | 0.120 | 0.120 | 0.120 | 0.120 |

## Final validation selected duration (source: final validation segment labels)

| Budget | B6 | B7 | v1 | v2 |
|--------|----|----|----|----|
| 5 | 46.280 | 90.700 | 50.000 | 50.000 |
| 10 | 90.700 | 90.700 | 90.700 | 90.700 |
| 20 | 90.700 | 90.700 | 90.700 | 90.700 |
| 40 | 90.700 | 90.700 | 90.700 | 90.700 |
| 80 | 90.700 | 90.700 | 90.700 | 90.700 |
| 120 | 90.700 | 90.700 | 90.700 | 90.700 |

## Key comparisons

- B=10: v2 long recall 1.000 vs v1 1.000 (Δ 0.000); precision 0.120 vs v1 0.120 (Δ 0.000).
- B=20: v2 long recall 1.000 vs v1 1.000 (Δ 0.000); precision 0.120 vs v1 0.120 (Δ 0.000).
- B=40: v2 long recall 1.000 vs v1 1.000 (Δ 0.000); precision 0.120 vs v1 0.120 (Δ 0.000).
- B=80: v2 long recall 1.000 vs v1 1.000 (Δ 0.000); precision 0.120 vs v1 0.120 (Δ 0.000).

## Conclusion

Frozen-LATE-AQP-v2 does **not** consistently improve low-budget long-event recall on the final validation segment. The low-budget failure remains unresolved.

## Data provenance note

- Tuning data: `realcartest_5k_tuning` uses `newly_generated_this_task` labels.
- Final validation data: `realcartest_3830_3920_final` uses `existing_vlm_oracle` labels.
- `test` video could not be read by OpenCV, so no labels were generated for it.
- `realcartest.mp4` was no longer present in the workspace, so no additional realcartest footage beyond existing center10 labels could be labeled.
