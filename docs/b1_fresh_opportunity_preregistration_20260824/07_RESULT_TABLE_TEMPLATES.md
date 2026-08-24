# Frozen result templates

No experimental result has been generated. Every `TBD` must come from the
frozen execution package.

## Main comparison

| Policy | Scan-enabled | Mean anytime AUC ↑ | Median AUC ↑ | Recall@D10 ↑ | Recall@D20 ↑ | Recall@D40 ↑ | Failure rate ↓ |
|---|---:|---:|---:|---:|---:|---:|---:|
| DV_CHRONOLOGICAL | No | TBD | TBD | TBD | TBD | TBD | TBD |
| DV_TEMPORAL_BISECTION | No | TBD | TBD | TBD | TBD | TBD | TBD |
| SCAN_THEN_PROXY_GREEDY | Yes | TBD | TBD | TBD | TBD | TBD | TBD |
| FIXED_1S_1V | Yes | TBD | TBD | TBD | TBD | TBD | TBD |
| FIXED_1S_3V | Yes | TBD | TBD | TBD | TBD | TBD | TBD |
| FIXED_3S_1V | Yes | TBD | TBD | TBD | TBD | TBD | TBD |

## Gate table

| Gate quantity | Frozen threshold | Result | Pass? |
|---|---:|---:|---:|
| SCAN_FIXED_GAIN | >= 0.02 | TBD | TBD |
| Positive videos | >= 2/3 | TBD | TBD |
| Positive queries | >= 3/6 | TBD | TBD |
| Positive LOVO videos | >= 2/3 | TBD | TBD |
| Pooled LOVO_SELECTED_GAIN | >= 0.01 | TBD | TBD |
| Material-state prevalence | >= 0.10 on >=2/3 videos | TBD | TBD |
| Non-degenerate exposure | criterion 5 | TBD | TBD |

## Exposure and failure table

| Video | Empty-region fraction | Full-SCAN exposure recall | Candidates/non-empty region | Verifier disagreement | Zero-reference queries |
|---|---:|---:|---:|---:|---:|
| B1A_V1 | TBD | TBD | TBD | TBD | TBD |
| B1A_V2 | TBD | TBD | TBD | TBD | TBD |
| B1A_V3 | TBD | TBD | TBD | TBD | TBD |

## Workload-level table

One row per 3 videos × 6 queries × 6 policies. Required columns:
`video_id, query_id, policy_id, deadline_seconds, anytime_auc,
terminal_event_recall, committed_reference_events, scan_actions,
candidate_verify_actions, direct_verify_actions, failed_actions,
deadline_rejections, wallclock_seconds`.
