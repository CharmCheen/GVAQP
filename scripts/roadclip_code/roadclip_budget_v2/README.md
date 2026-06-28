# Roadclip Budget V2

This experiment rebuilds the semantic clip-query acceleration benchmark from source videos instead of continuing to tune the old 102-clip smoke set.

The old `kinematic_proxy` run is retained as a pipeline smoke test and conservative VLM prompt calibration set. Human audit showed that it includes pre-road, closed-area, low-speed maneuvering, and too few effective road-driving events.

## Goal

Build a cleaner and larger road-driving clip pool:

```text
source videos
-> road-driving segment filtering
-> candidate clips
-> YOLO proxy scores
-> conservative Qwen3-VL pseudo labels
-> budget simulation and policy sweep
-> acceleration report
-> human audit package
```

VLM labels are pseudo-GT for budget allocation analysis. They are not human ground truth.

## Run Full Pipeline

```bash
cd /qiuyeqing/llama_prl/G-ARC/test_vlm
bash experiments/roadclip_budget_v2/run_roadclip_budget_v2.sh
```

The runner uses full mode by default. It performs a small scene-filter and VLM-label smoke check first, then continues to full processing.

Smoke-only mode:

```bash
bash experiments/roadclip_budget_v2/run_roadclip_budget_v2.sh smoke
```

## Outputs

All outputs are written under:

```text
/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/roadclip_budget_v2
```

Key files:

- `video_inventory.csv`
- `road_segments.csv`
- `road_segment_filter_report.md`
- `clips.csv`
- `tracks.csv`
- `proxy_scores.csv`
- `proxy_scoring_report.md`
- `vlm_labels_conservative.csv`
- `vlm_label_report.md`
- `budget_curve.csv`
- `budget_report.md`
- `budget_policy_sweep.csv`
- `budget_policy_sweep_report.md`
- `budget_curve.png`
- `final_acceleration_report.md`
- `roadclip_v2_audit_package.tar.gz`

## Audit

Download or inspect:

```text
/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/roadclip_budget_v2/roadclip_v2_audit_package.tar.gz
```

The package contains `audit_manifest.csv`, `index.html`, `README_AUDIT.md`, and selected clips. Fill:

- `human_label`: `1` true ego-relevant risk/path conflict, `0` not ego-relevant risk, `-1` uncertain.
- `human_event_type`
- `human_reason`
- `human_confidence`
- `error_type`

After human audit, use the manifest to calibrate VLM pseudo-label precision/recall and decide whether to expand to more videos.

## Human Audit Analysis

Prefer keeping the original manifest unchanged and writing the filled copy to:

```text
/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/roadclip_budget_v2/audit_package/audit_manifest_labeled.csv
```

The analyzer also checks `audit_manifest.csv` if no labeled copy exists.

Required human columns:

- `human_label`: `1` = true ego-relevant risk / path conflict, `0` = not ego-relevant risk, `-1` = uncertain.
- `human_event_type`: suggested values include `cut_in`, `crossing`, `sudden_braking`, `lane_conflict`, `close_approach`, `normal_following`, `dense_traffic_only`, `roadside_static`, `far_vehicle`, `ambiguous`, `none`, `other`.
- `human_reason`: short explanation.
- `human_confidence`: `low`, `medium`, or `high`.
- `error_type`: use `correct`, a VLM false-positive/false-negative category, `human_uncertain`, or `other`.

Run:

```bash
cd /qiuyeqing/llama_prl/G-ARC/test_vlm
python experiments/roadclip_budget_v2/08_analyze_human_audit.py --config experiments/roadclip_budget_v2/config.yaml
```

If no valid `human_label` values are present, the script writes `TODO_human_audit.md` and exits without error.

Outputs:

- `human_audit_analysis.md`
- `human_audit_confusion.csv`
- `human_audit_errors.csv`

Audit statuses:

- `AUDIT_PASS`: enough labeled clips, VLM precision is high, and there is no large high-score false-negative cluster.
- `AUDIT_WEAK`: VLM precision is marginal or false positives concentrate in broad normal-driving categories.
- `AUDIT_FAIL`: VLM precision is low or many human positives were missed by the conservative VLM.
- `AUDIT_INCOMPLETE`: labels are missing or too few clips are audited.

## VLM-As-Oracle Expanded Benchmark

This mode treats the conservative Qwen3-VL labels as the oracle target and asks whether cheap proxy allocation can approximate a full VLM scan with fewer VLM calls. It is not a human-GT traffic-risk benchmark.

Run:

```bash
cd /qiuyeqing/llama_prl/G-ARC/test_vlm
bash experiments/roadclip_budget_v2/run_vlm_oracle_expanded.sh
```

The expanded run writes to a subdirectory so the original 500-clip outputs are not overwritten:

```text
/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded
```

The expanded config targets 1000 clips from the existing road-driving segments. It reuses the already filtered `road_segments.csv`, then runs clip cutting, YOLO proxy scoring, conservative VLM labeling, and VLM-as-oracle budget evaluation.

Main policies:

- `random`
- `uniform_time`
- `top_count`
- `top_naive`
- `temporal_nms_count`
- `proxy_then_expansion_count`
- `adaptive_count_nms_expand`
- `top_learned_logreg`
- `top_learned_rf`

`adaptive_count_nms_expand` first selects diverse `score_count` anchors with temporal NMS. If an anchor is VLM-positive, it spends follow-up calls on nearby clips; otherwise it continues to the next anchor.

Learned proxy scores are trained from existing proxy/track features using segment-level GroupKFold out-of-fold predictions, so clips from the same segment do not leak across train and test folds.

Key outputs:

- `proxy_scores_with_learned.csv`
- `vlm_oracle_budget_curve.csv`
- `target_recall_cost_saving.csv`
- `vlm_oracle_budget_curve.png`
- `final_vlm_oracle_acceleration_report.md`

## Interpretation

The final report declares one of:

- `PASS_PRELIMINARY_ACCELERATION`
- `FAIL_NO_ACCELERATION`
- `BLOCKED_INSUFFICIENT_DATA`
- `BLOCKED_VLM_OR_PROXY_FAILURE`

Passing means the clip pool is large enough, conservative positive rate is reasonable, positive events are sufficient, and at least one non-random allocation policy beats random by a meaningful margin at low budget.
