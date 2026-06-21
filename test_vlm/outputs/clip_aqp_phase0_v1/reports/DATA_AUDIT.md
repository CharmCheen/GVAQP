# Data Audit

This audit inspects existing local CSV/JSON/Markdown/tar metadata only. It does not download datasets or run VLM inference.

- discovered files: 269
- files with any Phase 0-relevant field: 48
- clean event-boundary files detected by strict column presence/non-null check: 177

The Phase 0 implementation uses existing proxy scores where present. If a fallback score is ever needed, it is defined as a lagged oracle-positive indicator within the same video timeline, used only as a deterministic diagnostic fallback and recorded with `score_source = fallback_score`; the current selected unified table uses `score_source = proxy_score` for all rows.

## Relevant Inventory Sample

| path | row_count | has_video_id | has_start_time | has_end_time | has_proxy_score | has_oracle_label | has_human_label | has_event_id | has_event_start | has_event_end | has_event_boundary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/focused_validation_outputs/00_input_inventory.md |  | True | True | True | True | True | True | False | False | False | False |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/focused_validation_outputs/01_pseudo_oracle_definition.md |  | False | False | False | False | True | False | False | False | False | False |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/focused_validation_outputs/02_audit_package/priority_audit_clips.csv | 40 | False | True | True | True | True | True | False | False | False | False |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/focused_validation_outputs/04_temporal_concentration/positive_timeline.csv | 1000 | False | True | True | True | True | False | False | False | False | False |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/focused_validation_outputs/06_focused_validation_report.md |  | False | False | False | True | True | False | False | False | False | False |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/focused_validation_outputs/07_sampling_baseline_comparison/input_inventory.md |  | True | True | True | True | True | False | False | False | False | False |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/focused_validation_outputs/07_sampling_baseline_comparison/sampling_baseline_comparison.md |  | False | False | False | True | True | False | False | False | False | False |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/candidate_coverage_gate_v1/reports/00_asset_audit.md |  | True | True | True | True | True | False | False | False | False | False |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase0_v1/data_audit/phase0_pseudo_events.csv | 29 | True | False | False | False | False | False | True | True | True | True |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/event_budget_gate_v2/reports/00_asset_audit.md |  | True | True | True | True | True | False | False | False | False | False |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/event_budget_gate_v2/tables/pseudo_events_gap_0p0.csv | 61 | True | False | False | False | False | False | True | True | True | True |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/event_budget_gate_v2/tables/pseudo_events_gap_4p0.csv | 32 | True | False | False | False | False | False | True | True | True | True |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/event_budget_gate_v2/tables/pseudo_events_gap_8p0.csv | 29 | True | False | False | False | False | False | True | True | True | True |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/BLOCKED_learned_anomaly_proxy.md |  | False | True | True | True | False | False | False | False | False | False |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/budget_report.md |  | False | False | False | True | True | False | False | False | False | False |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/budget_report_conservative_exact_102.md |  | False | False | False | True | True | False | False | False | False | False |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/budget_report_exact_102.md |  | False | False | False | True | True | False | False | False | False | False |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/budget_report_strict_variants_exact_102.md |  | False | False | False | True | True | False | False | False | False | False |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/budget_selected_clips.csv | 7998 | False | True | True | True | True | False | False | False | False | False |
| /qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/budget_selected_clips_conservative_exact_102.csv | 8976 | False | True | True | True | True | False | False | False | False | False |

## Boundary Finding

The main unit-level timeline lacks clean human-adjudicated event boundaries. Later Phase 0 stages therefore use pseudo-events formed by merging adjacent oracle-positive units and label all event results as pseudo-event / oracle-relative.
