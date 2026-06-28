# Sprint 4 Input Manifest

## Dataset3 canonical table

- Path: `garc_eval/outputs/codex_recompute_proxy_budget_basa_v1/tables/canonical_dataset3_anchor_table.csv`
- Use: Stage20 B=80 diagnosis, Stage21 stratified replay, Stage22 dataset3 comparison.
- Labels: conservative VLM-defined replay labels, used only for evaluation and oracle-informed diagnostic upper-bound allocation.

## Realcartest labels

- Path: `test_vlm/outputs/v13_8_center10_full_oracle_reference_v1/tables/center10_full_oracle_labels.csv`
- Use: Stage22 realcartest backfill.
- Labels: Qwen3-VL-32B pseudo-oracle labels, not human ground truth.

## Realcartest proxy features

- Path: `test_vlm/outputs/v13_7_center10_multi_method_replay_v1/tables/center10_proxy_features.csv`
- Use: Stage22 available-feature audit.
- Limitation: per-class person/bicycle YOLO counts are not present; only total object counts and vehicle aggregates are available.

## Stage17 reference results

- Path: `garc_eval/outputs/glm52_sprint3_certificate_queryprior_v1/tables/stage17_exact_bound_coverage.csv`
- Use: Stage21 R_lower tightness comparison.

## Stage18 reference results

- Path: `garc_eval/outputs/glm52_sprint3_certificate_queryprior_v1/tables/stage18_budget_schedule.csv`
- Use: Stage19 relabel audit.
