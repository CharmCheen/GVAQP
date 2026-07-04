# Oracle-Relative Dense Calibration Plan

## Existing dense \( O_{\text{ref}} \) labels

A dense VLM-oracle labeling already exists:

- **Path**: `src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/full_reference_units.csv`
- **Granularity**: 2 s per unit
- **Coverage**: 600 units = 1200 s (100.0% of the 1200 s video)
- **Positive units**: 80
- **Negative units**: 520
- **Label column**: `label_event`
- **Oracle provider**: VLM-oracle (`qwen3_vl_32b_v13_6_prompt`)

Because these labels are already materialized, **no new oracle calls or human annotation are required** to evaluate oracle-relative calibration on the full video.

## Label schema

- `positive` (label_event == 1)
- `negative` (label_event == 0)
- Optional extended fields can be derived: `event_fraction_in_bin`, `event_t_start`, `event_t_end`.

## Proposed calibration windows

Even though the full video is labeled, we retain three conceptual windows for reporting consistency:

| window_id | criteria | approximate local time | purpose |
|-----------|----------|------------------------|---------|
| `window_high_prior` | bins with prior_score_max in top quartile | scattered | calibration on high-signal regions |
| `window_low_prior` | bins with prior_score_max in bottom quartile | scattered | calibration on low-signal regions |
| `window_suspected_leakage` | bins outside E0_top20 that are positive | scattered | measure candidate-envelope leakage |

## Oracle call manifest

Because the labels are already materialized, the manifest below is a **retrospective lookup plan**, not a request for new calls.

Fields:

- `window_id`
- `bin_id`
- `local_t_start`
- `local_t_end`
- `media_t_start`
- `media_t_end`
- `query_predicate` = "Visible Ego-Path Conflict (VEPC)"
- `oracle_provider` = "VLM-oracle qwen3_vl_32b_v13_6_prompt"
- `expected_label_schema` = positive / negative / uncertain
- `inside_E0_top10`
- `inside_E0_top20`
- `inside_E0_top30`
- `notes`

## Calibration metrics

- `estimated_positive_bin_mass`: fraction of bins predicted positive by the algorithm.
- `true_positive_bin_mass_under_O_ref`: actual fraction of positive bins under VLM-oracle labels.
- `estimated_missing_mass`: 1 - estimated positive mass.
- `true_missing_mass_under_O_ref`: 1 - true positive mass.
- `outside_leakage_estimate`: predicted positives outside E0.
- `outside_leakage_true_under_O_ref`: true positives outside E0.
- `calibration_error`: estimated mass - true mass.

## New oracle calls

`ALLOW_NEW_ORACLE_CALLS = False`.

If new oracle calls are later enabled, they should target the same 2 s units and reuse the VLM prompt already used for \( O_{\text{ref}} \).
No human annotation is required for oracle-relative calibration.

## Claims status

- We **can** say: a dense VLM-oracle labeling exists and enables oracle-relative calibration.
- We **cannot** say: calibration has been validated or that VLM-oracle labels equal human truth.
- We **cannot** say: missing-mass estimates are formally calibrated without executing the calibration evaluation.
