# SQ-CRAQ Handoff

## Current Safe State

Phase A/B artifacts exist and have been reviewed in `outputs/FINAL_REVIEW.md`.

No new VLM, YOLO, API, or GPU inference should run unless explicitly authorized.

## Ready For Human Work

- `/qiuyeqing/llama_prl/G-ARC/outputs/probe_set_v1/vlm_human_agreement_spotcheck.csv`
- `outputs/probe_set_v1/probe_set_vlm_oracle_labels.csv`
- `outputs/probe_set_v1/probe_media/clips/`
- `outputs/probe_set_v1/probe_media/centers/`
- `outputs/probe_set_v1/probe_media/sheets/`

## Ready For No-Compute Follow-Up

- Analyze Phase 3 selector smoke failure cases and redesign the selector/return-set objective. No new VLM, YOLO, or GPU training is needed.

## Completed Agent Loop Items

- T001: Registered Phase A/B artifacts and review findings in `outputs/agent_loop_v1/round2_phase_ab_registration.md`.
- T002: Built static probe annotation package at `outputs/probe_set_v1/annotation_package/index.html`.
- T003: Audited probe/feature coverage at `outputs/cheap_signal_v2/probe_feature_coverage_audit.md`.
- T004: Prepared round-5 decision handoff at `outputs/agent_loop_v1/HANDOFF_ROUND5.md`.
- T006: Completed pre-annotation design check, generated `outputs/probe_set_v1/probe_set_human_labels_template.csv`, created `sq_craq_agent_loop_v1/phase1_reference_probe/design_check/design_note.md`, and added `outputs/probe_set_v1/annotation_package/ANNOTATION_GUIDE.md`.
- T005: Local Qwen3-VL-32B oracle labels were produced for all 25 probes after a 5-probe smoke test; 25/25 parse_status=ok; VLM oracle positives are 7/25.
- T008: Pending decision after spotcheck: whether to launch `probe_set_v2` expansion with the same VLM oracle prompt at 50-80 probes.
- T009: Completed Phase 3 minimal selector smoke at `outputs/agent_loop_v1/phase3_selector_smoke_v1/`. It produced budgeted returned interval sets, but the diagnostic result is negative: deterministic cheap-signal selectors did not beat 50-seed uniform random at B=40 event_recall_iou_0_3.
- T010: Pending next design step: redesign AQP selector and return-set objective using the Phase 3 smoke failure cases.

## Current Blocker

No current blocker for the next no-new-VLM step.

User accepted the Qwen3-VL oracle labels as the current frozen reference without requiring the 12-row spotcheck before proceeding.

`outputs/probe_set_v1/probe_set_vlm_oracle_labels.csv` is VLM-oracle-relative, not human ground truth. Future metrics must say "relative to VLM oracle judgment" and must not use "true recall" or "ground truth recall."

`outputs/agent_loop_v1/probe_eval_after_vlm_oracle/` contains the completed small probe signal evaluation. The key caution is that only 20/25 probes have cheap_signal_v2 scores; all 7 VLM-oracle positives happen to be in the scored 20.

`outputs/agent_loop_v1/phase3_selector_smoke_v1/` contains the first executable AQP selector/budget loop. It should be treated as diagnostic_design_target_smoke, not validation. At B=40, uniform random averaged 0.153 event_recall_iou_0_3 across 50 seeds; the best deterministic cheap-signal selector reached 0.050.

## Requires Explicit Authorization

- Any additional VLM/API labeling beyond the completed `probe_set_v1` Qwen3-VL oracle run.
- Any new YOLO or GPU inference.
- Extending feature extraction over additional video time.
- Any full replay or selector integration that uses labels beyond diagnostic evaluation.
