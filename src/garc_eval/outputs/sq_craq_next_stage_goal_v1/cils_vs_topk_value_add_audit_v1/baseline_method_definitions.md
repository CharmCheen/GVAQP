# Baseline Method Definitions

- `raw_topk`: sort by score descending and take k.
- `topk_nms`: sort by score descending and apply temporal IoU NMS.
- `duration_penalized_topk`: sort by normalized score minus a duration penalty.
- `topk_nms_duration_penalty`: duration-penalized score plus temporal NMS.
- `calibrated_threshold`: use existing smoke `p_answer` where available; diagnostic only.
- `CILS`: reused prior synthetic CILS metrics/predictions; no production selector modification.
