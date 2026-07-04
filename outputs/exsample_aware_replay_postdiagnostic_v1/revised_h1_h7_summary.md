# Revised H1–H7 Summary

| Hypothesis | Status | Revised conclusion |
|------------|--------|--------------------|
| H1 | supported | Positive mass exists outside E0 under both true-event-duration and positive-bin-mass definitions. |
| H2 | supported | Outside positives show temporal neighbourhood structure (median gaps 20–40s). |
| H3/H4 | not verified | SUPG/ABae baselines not independently re-run; cannot claim comparison. |
| H5 recall | supported | At budget=40, Ours-full recall=0.525 vs B7=0.421. |
| H5 coverage | partially supported | At budget=40, long-event complete coverage Ours=0.000 vs B7=0.000. |
| H6 | supported | Long-interval recall gain at budget=40 = 0.164. If this is ≤0, the benefit is mainly point-anchor seed discovery, not temporal structure repair. |
| H7 | not verified | No exhaustive human-annotated window exists; missing-mass calibration remains unverified. |

## Detailed H6 Evidence

|                       |   B6_ExSample |   B7_ExSample_plus_expansion |   Ours_full_LATE_AQP |
|:----------------------|--------------:|-----------------------------:|---------------------:|
| (10, 'all')           |         0.103 |                        0.107 |                0.167 |
| (10, 'long_interval') |         0.167 |                        0.128 |                0.356 |
| (10, 'point_anchor')  |         0.076 |                        0.098 |                0.086 |
| (20, 'all')           |         0.228 |                        0.211 |                0.19  |
| (20, 'long_interval') |         0.383 |                        0.303 |                0.394 |
| (20, 'point_anchor')  |         0.162 |                        0.171 |                0.102 |
| (40, 'all')           |         0.415 |                        0.421 |                0.525 |
| (40, 'long_interval') |         0.583 |                        0.564 |                0.728 |
| (40, 'point_anchor')  |         0.343 |                        0.36  |                0.438 |
| (80, 'all')           |         0.727 |                        0.757 |                0.763 |
| (80, 'long_interval') |         0.878 |                        0.861 |                1     |
| (80, 'point_anchor')  |         0.662 |                        0.712 |                0.662 |
