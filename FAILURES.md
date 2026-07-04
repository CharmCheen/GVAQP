# Failures And Warnings

## Active Warnings

- `try_or_no/videos/realcartest.mp4` is absent; current probe media uses fallback `data/realcam/long_video_data/long_video_dataset3.mp4`.
- Current `probe_set_v1` covers local `[0.0, 1462.930499]`, not full 66-minute realcartest.
- Current cheap-signal features cover local `[0, 1200]`; 5 probe intervals start after local 1200s.
- `auc_best_direction` chooses best direction post hoc for diagnostics and must not be treated as selector tuning.
- `git status` is blocked by Git dubious-ownership protection in this environment.
- `probe_set_v1` signal evaluation is limited to 20/25 probes because current cheap-signal features cover local `[0,1200]`; probes 21-25 remain unscored by cheap_signal_v2.
- Probe metrics are VLM-oracle-relative, not human-ground-truth metrics.
- Phase 3 selector smoke is negative for the current deterministic cheap-signal selectors: at B=40, uniform_random averaged 0.153 event_recall_iou_0_3 across 50 seeds, while the best deterministic selector reached 0.050.
- `overlap_group_id` in `interval_features_with_signal_v2.csv` is a single global value, so it is not usable as a return-set diversity cap in the current smoke; the script disables that cap and uses time-IoU NMS.

## No Current FAIL

No blocking FAIL condition was found in `outputs/FINAL_REVIEW.md`.

## Resolved Execution Issues

- Round 3 annotation package generation had three transient script errors:
  - f-string expression syntax in HTML assembly;
  - absolute versus relative path handling;
  - shell quoting around f-string dictionary access.
- All three were fixed in the same round; final validation passed with 25 manifest rows, 25 HTML probe sections, and zero missing media references.

## Coverage Audit Detail

- `outputs/cheap_signal_v2/probe_feature_coverage_audit.md` confirms 20 probes fully covered by current cheap-signal feature tables and 5 probes with no coverage.
- A small probe metric pass now exists at `outputs/agent_loop_v1/probe_eval_after_vlm_oracle/`, but it is limited to the feature-covered 20-probe scope and must not be treated as a full 25-probe signal validation.
- `outputs/agent_loop_v1/phase3_selector_smoke_v1/` now contains the first executable selector/budget smoke. It produced returned interval sets but does not support selector replacement.
