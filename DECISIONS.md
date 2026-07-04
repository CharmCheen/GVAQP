# Decisions

## 2026-07-02

- Initialized SQ-CRAQ loop state files because the requested root state files were absent.
- Treat Phase A/B as artifact stabilization, not as a new experiment stage.
- Keep all current cheap-signal v2 metrics labeled `6_event_reference` and diagnostic-only.
- Do not treat `auc_best_direction` / `precision_at20_best_direction` as a deployed selector.
- Do not use `probe_set_v1` until it is annotated, and never use it for tuning or repair decisions.
- Do not claim full 66-minute coverage from the current fallback-derived probe set.
- Static probe annotation index is acceptable because it only links existing media and does not add labels, scores, or model inference.

## 2026-07-03

- Use local Qwen3-VL-32B outputs as the current `probe_set_v1_vlm_oracle_reference`; these labels are VLM-oracle-relative, not human ground truth.
- User accepted proceeding without manual spotcheck before the first probe_set_v1 signal evaluation.
- Probe_set_v1 signal evaluation is allowed only as a small VLM-oracle-relative diagnostic over the feature-covered probes; do not use "true recall" or "ground truth recall."
- Because probe_set_v1 shows weak statistical power and only 20/25 probes have cheap_signal_v2 scores, the next recommended step is Phase 3 minimal end-to-end selector smoke rather than probe_v2 expansion.
- Ran Phase 3 minimal selector/budget smoke from existing CSV artifacts only; no VLM, YOLO, API, or GPU training was run.
- Treat the Phase 3 selector smoke as `diagnostic_design_target_smoke`, not validation. The result is negative for current deterministic cheap-signal selectors, so the next AQP step is selector/return-set redesign rather than a stronger claim.
