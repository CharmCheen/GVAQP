# Metric Audit

## Issue Found

**Root cause: Aggregation includes instances with 0 clips**

For `within_30m, tau=3`:
- 865 total instances
- 699 instances have GT clips → naive_oracle clip_f1 = 1.0
- 166 instances have NO GT clips → clip_f1 = 0.0 (penalized)
- 46 instances skipped (n < tau)

Current code averages over all 865 instances: mean = 0.808
Correct behavior: average over 699 instances with clips: mean = 1.000

## IoU Matching Analysis

For instances with clips, IoU matching works correctly:
- naive_oracle predicted clips exactly match GT clips
- IoU = 1.0 for all matches
- All matches pass the 0.3 threshold

## Matching Logic

The one-to-many matching (greedy by IoU) is correct for naive_oracle since there's exactly one predicted clip per GT clip (they're identical).

## Fix

The `aggregate_metrics` function should either:
1. Only include instances with n_gt_clips > 0 in the mean, OR
2. Treat instances with 0 GT clips and 0 predicted clips as perfect (clip_f1 = 1.0)

Option 2 is more principled: if the ground truth says there are no clips, and the method correctly predicts no clips, that's a perfect prediction.
