# Oracle Replay Isolation Audit

## Full-VLM reference files

- `experiments/v13/v13_8_full_oracle/tables/center10_vlm_oracle_events.csv` (non-dev segments)
- `src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/reference_events.csv` (dev segment)

These files contain full-VLM labels, event IDs, and event intervals.

## Modules that may read full-VLM labels

- `oracle_adapter` (this experiment): returns only the label for a requested unit/interval.
- `final evaluator` (this experiment): reads full reference after method completion.
- Existing B6/B7 implementations use per-bin `event_id` to count discovered events per chunk; this is flagged as a risk.

## Method classification

| Method | Uses event_id in selection? | strict_replay | posthoc_eval | Notes |
|--------|-----------------------------|---------------|--------------|-------|
| B6 | Yes | No | Yes | Algorithmic use of event_id violates strict isolation.
| B7 | Yes | No | Yes | Same as B6.
| B6-core | Yes (inherited from B6) | No | Yes | Core/Halo release is strict, but upstream B6 is not.
| B7-core | Yes (inherited from B7) | No | Yes | Same as B6-core.
| LATE-AQP-core | No | Yes | No | Selection uses only per-bin labels and prior scores; event_id is only used in final evaluation/diagnosis.

## Label leakage risk

- **B6/B7**: risk exists because `event_id` is used to update per-chunk discovery counts. In a true limited-oracle setting, the oracle would not return event_id.
- **LATE-AQP-core**: low risk; selection decisions are based on label (positive/negative) and prior score.

## Conclusion

Main conclusions for LATE-AQP-core are reported under `strict_replay`. Results for B6/B7/B6-core/B7-core are reported under `posthoc_eval` because their selection logic accesses event_id.
