# Oracle Replay Isolation Audit - dataset3

## Method classification

| method | selection uses event_id | strict_replay_or_posthoc |
|--------|-------------------------|---------------------------|
| B6 | yes | posthoc_eval |
| B7 | yes | posthoc_eval |
| B6-core | yes (via B6) | posthoc_eval |
| B7-core | yes (via B7) | posthoc_eval |
| LATE-AQP-core | no | strict_replay |

## Label-leakage risk

- B6/B7 use per-bin `event_id` for adaptive chunk counting, which is a leakage risk.
- LATE-AQP-core selects bins using only `prior_score_max` and oracle feedback from queried bins.
- The oracle adapter exposes only the label of the requested unit/interval, never the full reference.
