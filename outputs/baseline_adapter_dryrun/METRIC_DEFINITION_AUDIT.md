# Metric Definition Audit

Source audited: `refe_repos/adapter/common.py`.

## Temporal IoU

`temporal_iou(a_start, a_end, b_start, b_end)` uses inclusive integer endpoints:

```text
intersection = max(0, min(a_end,b_end) - max(a_start,b_start) + 1)
union = max(a_end,b_end) - min(a_start,b_start) + 1
IoU = intersection / union
```

## Greedy Matching

`evaluate_segments` builds all prediction/reference pairs within the same `video_id` whose IoU is at least `config.iou_threshold`. It sorts pairs descending by `(iou, pred_idx, ref_idx)` and greedily accepts a pair only if neither the prediction nor reference has already been matched.

Conclusion: matching is one-to-one, but greedy, not Hungarian/global-optimal.

## mean_iou

`mean_iou` is the arithmetic mean over the accepted greedy matched pairs only:

```text
mean_iou = mean(matched_ious)
```

It is not the mean of each reference segment's best IoU over all predictions, and it is not averaged over unmatched references.

README/FINAL_REPORT currently state this matched-pairs interpretation, so no result rewrite is needed.

## duplicate_rate

After greedy matching, `duplicate_rate` counts predictions that were not matched but still have an IoU-threshold-qualified pair to a reference that has already been matched:

```text
duplicate_rate = len(duplicate_preds) / len(predictions)
```

This is a redundant-prediction rate relative to already matched references, not a general overlap or NMS duplicate metric.

## Audit Action

No metric implementation was changed. Existing dry-run metrics remain as originally computed.
