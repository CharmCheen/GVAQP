# TODO: Human Audit Labels Needed

Status: AUDIT_INCOMPLETE

Reason: audit_manifest_labeled.csv not found

Please copy:

```text
/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/roadclip_budget_v2/audit_package/audit_manifest.csv
```

to:

```text
/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/roadclip_budget_v2/audit_package/audit_manifest_labeled.csv
```

Then fill these columns:

- `human_label`: `1` = true ego-relevant risk / path conflict; `0` = not ego-relevant risk; `-1` = uncertain.
- `human_event_type`: one of `cut_in, crossing, sudden_braking, lane_conflict, close_approach, normal_following, dense_traffic_only, roadside_static, far_vehicle, ambiguous, none, other`.
- `human_reason`: short explanation for the human decision.
- `human_confidence`: `low`, `medium`, or `high`.
- `error_type`: one of `correct, vlm_false_positive_normal_following, vlm_false_positive_dense_traffic, vlm_false_positive_roadside_static, vlm_false_positive_far_vehicle, vlm_false_positive_ambiguous, vlm_false_negative_cut_in, vlm_false_negative_crossing, vlm_false_negative_close_approach, human_uncertain, other`.

After labeling, run:

```bash
cd /qiuyeqing/llama_prl/G-ARC/test_vlm
python experiments/roadclip_budget_v2/08_analyze_human_audit.py --config experiments/roadclip_budget_v2/config.yaml
```

This script does not call VLM, rerun YOLO, or modify pseudo labels.
