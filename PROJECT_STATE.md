# SQ-CRAQ Project State

Last updated: 2026-07-03

## Current Stage

Phase A/B artifact stabilization completed; probe_set_v1 VLM-oracle signal evaluation completed; Phase 3 minimal selector smoke completed with a negative diagnostic result.

The current loop state is initialized from existing outputs only:

- `outputs/probe_set_v1/`
- `outputs/cheap_signal_v2/`
- `outputs/FINAL_REVIEW.md`
- `src/garc_eval/experiments/sq_craq_v2_phase_ab/run_phase_ab.py`

## Active Constraints

- Do not run VLM, API, YOLO, or GPU inference without explicit authorization.
- Do not download datasets.
- Do not use `probe_set_v1` for tuning, threshold selection, selector choice, repair decisions, or candidate generation.
- Do not add formal guarantee fields or certificate logic.
- Do not make CILS the default selector.
- Current probe labels are VLM-oracle-relative, not human ground truth.

## Available Data

- `probe_set_v1`: 25 probes with clips, center frames, and contact sheets.
- `probe_set_v1_vlm_oracle_reference`: local Qwen3-VL-32B labels at `/qiuyeqing/llama_prl/G-ARC/outputs/probe_set_v1/probe_set_vlm_oracle_labels.csv`; 25/25 parsed, 7 oracle-positive (`true_interval` + `point_anchor`), 18 negative.
- `vlm_human_agreement_spotcheck`: 12-row random spotcheck table at `/qiuyeqing/llama_prl/G-ARC/outputs/probe_set_v1/vlm_human_agreement_spotcheck.csv`.
- `probe_set_v1_vlm_oracle_signal_eval`: small frozen signal evaluation at `/qiuyeqing/llama_prl/G-ARC/outputs/agent_loop_v1/probe_eval_after_vlm_oracle/`; scored scope is 20/25 probes because cheap_signal_v2 coverage ends at local 1200s.
- `phase3_selector_smoke_v1`: first executable AQP selector/budget loop at `/qiuyeqing/llama_prl/G-ARC/outputs/agent_loop_v1/phase3_selector_smoke_v1/`; uses existing interval features and reference events only.
- `cheap_signal_v2`: track-interaction and inside/outside contrast feature tables.
- `6_event_reference`: available for diagnostic within-bin metrics only.
- `expanded_reference`: present but empty.
- Probe_set_v1 signal evaluation has been run only as VLM-oracle-relative diagnostics over the feature-covered scope.

## Known Time Axis

- `try_or_no/videos/realcartest.mp4` is absent in this workspace.
- Probe media uses `data/realcam/long_video_data/long_video_dataset3.mp4`.
- `local_to_media_offset_seconds = 2000.0`.
- Fallback media duration is `3462.930499s`.
- Current `probe_set_v1` covers local `[0.0, 1462.930499]`, not the full historical 66-minute realcartest video.
- Current cheap-signal feature tables cover local `[0, 1200]`.

## Last Review Outcome

`outputs/FINAL_REVIEW.md` found no FAIL condition, but recorded warnings about fallback video coverage, feature coverage stopping at local 1200s, diagnostic-only metric direction choice, `__pycache__`, and Git dubious ownership.

## Agent Loop Progress

- Round 1: initialized missing loop state files.
- Round 2: registered Phase A/B artifacts and claim boundaries in `outputs/agent_loop_v1/round2_phase_ab_registration.md`.
- Round 3: built static `probe_set_v1` annotation package in `outputs/probe_set_v1/annotation_package/`.
- Round 4: audited probe/feature coverage in `outputs/cheap_signal_v2/probe_feature_coverage_audit.md`; 20 probes have full current feature coverage and 5 have none.
- Round 5: prepared decision handoff in `outputs/agent_loop_v1/HANDOFF_ROUND5.md`.
- Round 6: completed the pre-annotation design check, created `outputs/probe_set_v1/probe_set_human_labels_template.csv`, created `sq_craq_agent_loop_v1/phase1_reference_probe/design_check/design_note.md`, and added `outputs/probe_set_v1/annotation_package/ANNOTATION_GUIDE.md`.
- Round 7: ran local Qwen3-VL-32B VLM oracle labeling for `probe_set_v1` after a 5-probe smoke test; wrote `outputs/probe_set_v1/probe_set_vlm_oracle_labels.csv`, raw responses, and a 12-probe random human agreement spotcheck table.
- Round 8: user accepted VLM oracle labels as the current frozen reference without requiring spotcheck first; ran probe_set_v1 VLM-oracle-relative signal evaluation with 2000 probe-bootstrap resamples. Track-interaction representative features did not collapse; inside/outside representatives were weak/inconsistent on probe_v1.
- Round 9: implemented `scripts/phase3/run_minimal_selector_smoke.py`, documented AQP algorithm design v1, and ran the first cheap-signal -> selector -> NMS -> budgeted interval return-set smoke. The result is negative: at B=40, 50-seed uniform random mean event_recall_iou_0_3 was 0.153, while the best deterministic cheap-signal selector reached 0.050.

## Current Blocker

There is no current blocker for the next no-new-VLM step.

Recommended next step: redesign the AQP selector/return-set objective before making stronger AQP claims. Start from the failure cases in `outputs/agent_loop_v1/phase3_selector_smoke_v1/selected_intervals.csv` and `event_coverage.csv`; keep all results labeled by reference source and do not claim selector superiority.
