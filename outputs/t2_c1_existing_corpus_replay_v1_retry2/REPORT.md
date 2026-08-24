# T2-C1 Existing-Corpus Descriptive Replay

## Verdict

`C1_DESCRIPTIVE_ONLY`

- Workloads: 6 video-query cells from 3 videos and 2 queries
- Policy replays: 2880
- Mean DATB-minus-ExSample AUC: -0.040842
- Median DATB-minus-ExSample AUC: -0.039983
- Positive/equal/negative paired rows: 44/0/316
- Workloads with positive mean delta: 0/6
- Cached labels: {"not_relevant": 2430, "parse_failure": 4, "relevant": 515, "unknown": 1}

## Claim boundary

`DESCRIPTIVE_ONLY_LOW_INDEPENDENT_SAMPLE_SUPPORT_NO_HUMAN_EVENTS_NO_C3`

Every unit had a precomputed query-agnostic proxy candidate. Events are contiguous runs of cached VLM-relative positives, not independent human events.
