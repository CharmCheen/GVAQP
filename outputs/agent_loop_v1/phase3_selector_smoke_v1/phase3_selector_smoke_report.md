# Phase 3 Minimal AQP Selector Smoke

This is a diagnostic smoke test of the AQP algorithm loop: candidate lattice -> fixed selector scoring -> overlap-constrained return set -> event coverage metrics.

It used existing CSV artifacts only. It did not run VLM, YOLO, GPU training, API calls, threshold fitting, or probe-label tuning.

## Inputs

- Candidate/features: `outputs/cheap_signal_v2/tables/interval_features_with_signal_v2.csv`
- Reference events: `src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_label_aligned/reference_events.csv`
- Reference interpretation: `diagnostic_design_target_smoke`
- Budgets: `[5, 10, 20, 40]`
- NMS interval IoU threshold: `0.5`
- Overlap group cap enabled: `False`
- Uniform baseline seeds: `0..49`; non-random selectors are deterministic.

## Fixed Selector Definitions

- `uniform_random`: deterministic random score per seed.
- `existing_signal`: mean percentile rank of `motion_energy_mean:asc`.
- `track_interaction`: mean percentile rank of `track_mean_track_speed_mean:asc, track_mean_relative_speed_mean:asc`.
- `inside_outside`: mean percentile rank of `contrast_optical_flow_burst_z_max:asc, contrast_object_density_change_z_min:desc, contrast_optical_flow_burst_z_mean:asc`.
- `simple_fused`: mean of existing_signal, track_interaction, and inside_outside selector scores.

## Budget 40 Snapshot

| selector | event_recall_iou_0_3 | event_recall_iou_0_5 | interval_precision_iou_0_3 | returned_count | background_duration_ratio |
| --- | ---: | ---: | ---: | ---: | ---: |
| uniform_random | 0.153 | 0.069 | 0.098 | 40.0 | 0.843 |
| track_interaction | 0.050 | 0.000 | 0.050 | 40.0 | 0.825 |
| inside_outside | 0.050 | 0.000 | 0.025 | 40.0 | 0.678 |
| existing_signal | 0.000 | 0.000 | 0.000 | 40.0 | 0.992 |
| simple_fused | 0.000 | 0.000 | 0.000 | 40.0 | 0.926 |

## Observed Smoke Outcome

- At B=40, the uniform random baseline mean event recall at IoU@0.3 was `0.153` across 50 seeds.
- The best deterministic cheap-signal selector event recall at IoU@0.3 was `0.050`.
- In this smoke, the current fixed cheap-signal selectors did not convert signal-level diagnostics into better budgeted return-set coverage.
- This is a negative Phase 3 result and should drive selector/return-set redesign before any stronger AQP claim.

## Reading Rules

- These numbers show whether the AQP loop can produce budgeted interval sets from current cheap signals.
- They do not establish selector superiority because the reference scope is small and design-linked.
- Probe_set_v1 remains a separate VLM-oracle-relative signal diagnostic; it was not used to define these selectors.
- A production AQP variant should next replace greedy NMS with a declared weighted interval scheduling objective if the precision/overlap constraints need exact optimization.
