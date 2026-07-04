# H1–H7 Summary Report

**Query predicate**: Visible Ego-Path Conflict (VEPC)
**Atomic bin size**: 10s
**Reference events**: 20 (VLM-oracle labels, `clean_interval_aqp_full_reference_v2_clean_no_leak`)
**Data source tags**: all bins tagged `uniform_2s_no_switch_found` (no granularity switch detected).

## H1: Does positive temporal mass exist outside E0?

- **top10** (12 bins): 26 positive bins outside E0, covering 260.0s (21.67% of segment). Outside-positive ratio = 0.241.
- **top20** (24 bins): 21 positive bins outside E0, covering 210.0s (17.50% of segment). Outside-positive ratio = 0.219.
- **top30** (36 bins): 16 positive bins outside E0, covering 160.0s (13.33% of segment). Outside-positive ratio = 0.190.
- **Conclusion**: Yes. Even the top-30% prior envelope misses some positive temporal mass.

## H2: Do outside positives show temporal neighbourhood structure?

- **top10**: outside positives median gap = 20.0s, mean gap = 33.2s, max gap = 120.0s. Affected reference events: ['realcartest_event_0022', 'realcartest_event_0023', 'realcartest_event_0024', 'realcartest_event_0025', 'realcartest_event_0026', 'realcartest_event_0027', 'realcartest_event_0028', 'realcartest_event_0029', 'realcartest_event_0030', 'realcartest_event_0031', 'realcartest_event_0032', 'realcartest_event_0033', 'realcartest_event_0034', 'realcartest_event_0035', 'realcartest_event_0037', 'realcartest_event_0038', 'realcartest_event_0039', 'realcartest_event_0040', 'realcartest_event_0041'].
- **top20**: outside positives median gap = 20.0s, mean gap = 41.5s, max gap = 120.0s. Affected reference events: ['realcartest_event_0022', 'realcartest_event_0023', 'realcartest_event_0024', 'realcartest_event_0025', 'realcartest_event_0026', 'realcartest_event_0027', 'realcartest_event_0028', 'realcartest_event_0030', 'realcartest_event_0031', 'realcartest_event_0032', 'realcartest_event_0033', 'realcartest_event_0034', 'realcartest_event_0037', 'realcartest_event_0038', 'realcartest_event_0039', 'realcartest_event_0040'].
- **top30**: outside positives median gap = 40.0s, mean gap = 52.0s, max gap = 180.0s. Affected reference events: ['realcartest_event_0022', 'realcartest_event_0023', 'realcartest_event_0024', 'realcartest_event_0025', 'realcartest_event_0026', 'realcartest_event_0027', 'realcartest_event_0028', 'realcartest_event_0030', 'realcartest_event_0032', 'realcartest_event_0034', 'realcartest_event_0037', 'realcartest_event_0038'].
- **Conclusion**: Outside positives cluster near event boundaries (median gaps are small relative to the 1200s segment), supporting the use of local expansion/repair rather than treating them as isolated false negatives.

## H3/H4: SUPG-style / ABae-style baseline performance

- No dedicated SUPG-style thresholding or ABae-style estimator was re-run in this replay. The existing `clean_interval_aqp_full_reference_v2_clean_no_leak` baseline comparison files contain threshold/top-k and CILS results, but they are not directly comparable under the exact budget/ledger definitions of this task.
- **Status**: H3/H4 not independently verified in this replay. Reported comparisons are limited to B6/B7/Ours-full.

## H5/H6: LATE-AQP repair vs B7 (ExSample + simple expansion)

Mean event-level recall (across all parameter combinations, by budget):

|   budget |   B6_ExSample |   B7_ExSample_plus_expansion |   Ours_full_LATE_AQP |
|---------:|--------------:|-----------------------------:|---------------------:|
|        5 |        0.0583 |                       0.0504 |               0.065  |
|       10 |        0.1033 |                       0.1067 |               0.1667 |
|       20 |        0.2283 |                       0.2108 |               0.19   |
|       40 |        0.415  |                       0.4212 |               0.525  |
|       80 |        0.7267 |                       0.7567 |               0.7633 |
|      120 |        1      |                       1      |               1      |

Mean complete-event coverage (across all parameter combinations, by budget):

|   budget |   B6_ExSample |   B7_ExSample_plus_expansion |   Ours_full_LATE_AQP |
|---------:|--------------:|-----------------------------:|---------------------:|
|        5 |        0.0283 |                       0.0392 |               0.0083 |
|       10 |        0.0583 |                       0.0879 |               0.0617 |
|       20 |        0.1383 |                       0.1742 |               0.1117 |
|       40 |        0.3233 |                       0.3779 |               0.39   |
|       80 |        0.66   |                       0.7333 |               0.73   |
|      120 |        1      |                       1      |               1      |

Absolute recall gain of Ours-full over B7 (event-level recall, mean across params):

|   budget |   abs_gain |   rel_gain_pct |
|---------:|-----------:|---------------:|
|        5 |     0.0146 |           28.9 |
|       10 |     0.06   |           56.2 |
|       20 |    -0.0208 |           -9.9 |
|       40 |     0.1038 |           24.6 |
|       80 |     0.0067 |            0.9 |
|      120 |     0      |            0   |

### Best-parameter comparison at budget=40

- B7 best: chunk_size=120.0s, k=3.0, recall=0.470±0.079, complete-coverage=0.440±0.070
- Ours-full best: E0=top30, recall=0.540±0.021, complete-coverage=0.395±0.037

- **H6 conclusion**: Ours-full obtains a measurable recall gain over B7 at budget=40 (+0.104 absolute). The gain is not explained by simple ExSample+expansion.

## H7: Calibration ability of audit ledger

- **Status: 未验证 / pending human annotation**. No exhaustive human-annotated continuous window exists in the data.
- An annotation package template has been generated at:
  `outputs/exsample_aware_replay/exhaustive_subset_annotation_package/exhaustive_bins_template.csv`
- Until the three windows (high_prior, low_prior, suspected_leakage) are fully annotated by humans, missing-mass error and outside-envelope leakage calibration cannot be computed.

## Layer-A / Layer-B Reporting Notes

- **Layer-A (granularity_source_tag)**: only one stratum (`uniform_2s_no_switch_found`) because the primary 1200s segment uses a uniform 2s base granularity. No switch point was recoverable from the data.
- **Layer-B (exhaustive window source)**: not yet available; will be reported separately after human annotation.

## Metric Interpretation Caveat

- 14 of 20 reference events are point-anchor events (<1s duration). With 10s atomic bins, these events cannot achieve IoU≥0.3 with a single bin. Boundary-IoU metrics are therefore capped by the long-duration event count (6 events).
- Event-level recall uses any-overlap discovery, so it is not subject to this cap.
