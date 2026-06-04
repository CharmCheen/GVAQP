# Filter Audit

## Filtering Consistency

GT clips and naive_oracle clips use **identical filtering**:
- Same data source: `real_3d_query_table.csv`
- Same instance grouping: by `instance_token`
- Same ordering: by `timestamp`
- Same label column: `within_30m_label` (or `in_fov_label`, `ego_front_label`)
- Same tau value
- Same `n < tau` skip condition
- Same clip construction function

## Result

**No filtering mismatch.** GT clips and naive clips are 100% identical for all queries and tau values.

## The Real Bug

The bug is in `aggregate_metrics`: it averages clip metrics over ALL instances, including 166 instances that have no GT clips. For these instances, `evaluate_instance` returns clip_f1=0, which drags down the mean.

For `within_30m, tau=3`:
- 699 instances have clips: naive_oracle clip_f1 = 1.0000
- 166 instances have no clips: clip_f1 = 0.0000 (incorrectly penalized)
- 46 instances skipped (n < tau)
- **Naive oracle should score 1.0, not 0.808**

## Fix

Exclude instances with 0 GT clips from the clip-level aggregation, or treat 0 GT + 0 predicted as a perfect score.
