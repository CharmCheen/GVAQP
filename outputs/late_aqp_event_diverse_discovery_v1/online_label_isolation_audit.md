# Online Label Isolation Audit

## Method classification

| method | uses event_id in selection | strict_replay_or_posthoc |
|--------|----------------------------|---------------------------|
| B6-core | yes | posthoc_eval |
| B7-core | yes | posthoc_eval |
| D3-norepair-core-chunk120 | no | strict_replay |
| D3-norepair-core-chunk30 | no | strict_replay |
| D3-norepair-core-chunk60 | no | strict_replay |
| LATE-D0-core | no | strict_replay |
| LATE-D1-core-radius10 | no | strict_replay |
| LATE-D1-core-radius20 | no | strict_replay |
| LATE-D1-core-radius30 | no | strict_replay |
| LATE-D2-core-q20-smass-rcenter | no | strict_replay |
| LATE-D2-core-q20-smass-rhighest | no | strict_replay |
| LATE-D2-core-q20-smax-rcenter | no | strict_replay |
| LATE-D2-core-q20-smax-rhighest | no | strict_replay |
| LATE-D2-core-q30-smass-rcenter | no | strict_replay |
| LATE-D2-core-q30-smass-rhighest | no | strict_replay |
| LATE-D2-core-q30-smax-rcenter | no | strict_replay |
| LATE-D2-core-q30-smax-rhighest | no | strict_replay |
| LATE-D2-core-q50-smass-rcenter | no | strict_replay |
| LATE-D2-core-q50-smass-rhighest | no | strict_replay |
| LATE-D2-core-q50-smax-rcenter | no | strict_replay |
| LATE-D2-core-q50-smax-rhighest | no | strict_replay |
| LATE-D3-core-chunk120 | no | strict_replay |
| LATE-D3-core-chunk30 | no | strict_replay |
| LATE-D3-core-chunk60 | no | strict_replay |

## Notes

- B6-core/B7-core inherit B6/B7's use of per-bin event_id for chunk-level singleton counting.
- All LATE-* and D3-norepair-core methods select bins using only prior scores and oracle labels (positive/negative), never event_id or GT intervals.
- Full-VLM references are only used for final evaluation.
