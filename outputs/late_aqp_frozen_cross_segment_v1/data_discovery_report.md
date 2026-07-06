# Data Discovery Report — Frozen Cross-Segment Validation

## Search scope
`BASE_SEARCH_ROOT = /qiuyeqing/llama_prl/G-ARC`

## What was searched
- Existing VLM-oracle labels for `Visible Ego-Path Conflict (VEPC)`
- `full_reference_units.csv` and `reference_events.csv`
- `clean_interval` / `interval_reference` / `full_reference` / `no_leak` outputs
- Prior scores (`cheap_signals_per_unit.csv`, `proxy_scores.csv`)
- `cheap_signal_v2` / roadclip proxy outputs
- `event_id` / event interval definitions
- Atomic temporal units (10 s atomic grids)
- Previously generated replay outputs (`outputs/exsample_aware_replay/`, `outputs/late_aqp_algorithm_v3_oracle_relative/`)

## Key files discovered

| File | Role | Coverage |
|------|------|----------|
| `experiments/v13/v13_8_full_oracle/tables/center10_vlm_oracle_events.csv` | **Primary O_ref for whole video** | realcartest, 0–3920 s, 52 VEPC events, `qwen3_vl_32b_v13_6_prompt` |
| `src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/reference_events.csv` | Dev-segment O_ref | realcartest, 2000–3200 s, 20 events |
| `src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/full_reference_units.csv` | Dev dense 2 s labels | realcartest, 2000–3200 s |
| `outputs/exsample_aware_replay/atomic_grid_10s.csv` | Dev 10 s atomic grid with prior scores | realcartest, 2000–3200 s |
| `experiments/roadclip_budget_v2/roadclip_budget_v2/proxy_scores.csv` | Prior scores for all realcartest segments | seg001–seg008 + realcartest_5k + test |
| `experiments/roadclip_budget_v2/roadclip_budget_v2/video_inventory.csv` | Video metadata | realcartest 3987 s, realcartest_5k 208 s, test 43 s |
| `experiments/roadclip_budget_v2/roadclip_budget_v2/road_segments.csv` | Road-segment definitions | 12 segments |

## Candidate segment audit

| segment_id | time_start | time_end | duration | bin_size | bins | pos_bins | density | events | long | point | has_prior | has_event_id | has_event_intervals | is_dev | usable | notes |
|------------|------------|----------|----------|----------|------|----------|---------|--------|------|-------|-----------|--------------|---------------------|--------|--------|-------|
| realcartest_0_1570 | 0.0 | 1570.0 | 1570.0 | 10 s | 157 | 44 | 28.0 % | 20 | 8 | 12 | yes | yes | yes | no | yes | Full seg001; high density; unseen |
| realcartest_1630_2000 | 1630.0 | 2000.0 | 370.0 | 10 s | 37 | 2 | 5.4 % | 2 | 0 | 2 | yes | yes | yes | no | yes | Pre-dev portion of seg003; lowest-density unseen window; only point anchors |
| realcartest_2000_3200 | 2000.0 | 3200.0 | 1200.0 | 10 s | 120 | 32 | 26.7 % | 20 | 6 | 14 | yes | yes | yes | yes | yes (dev) | Existing development segment |
| realcartest_2250_2610 | 2250.0 | 2610.0 | 360.0 | 10 s | 36 | 10 | 27.8 % | 7 | 2 | 5 | yes | yes | yes | partial | no | Overlaps dev 2000–3200 |
| realcartest_2650_3200 | 2650.0 | 3200.0 | 550.0 | 10 s | 55 | 16 | 29.1 % | 9 | 4 | 5 | yes | yes | yes | partial | no | Overlaps dev |
| realcartest_3200_3830 | 3200.0 | 3830.0 | 630.0 | 10 s | 63 | 13 | 20.6 % | 7 | 4 | 3 | yes | yes | yes | no | yes | Unseen tail of seg005; medium density |
| realcartest_3840_3890 | 3840.0 | 3890.0 | 50.0 | 10 s | 5 | 0 | 0.0 % | 0 | 0 | 0 | yes | yes | yes | no | no | Too short, no events |
| realcartest_5k_seg001 | 0.0 | 30.0 | 30.0 | 10 s | 3 | — | — | — | — | — | yes | no | no | no | no | Different video, no VEPC reference events |
| test_seg001 | 0.0 | 40.0 | 40.0 | 40.0 | 4 | — | — | — | — | — | yes | no | no | no | no | Different video, no VEPC reference events |

## Current dev segment
`realcartest_2000_3200` is the existing development segment. It is included only as a reference/calibration segment; the validation conclusions must be drawn from the unseen segments.

## Unseen candidate segments selected
1. `realcartest_0_1570` — high-density unseen window.
2. `realcartest_1630_2000` — lowest-density unseen window (note: only point-anchor events).
3. `realcartest_3200_3830` — medium-density unseen window.

## Gaps / limitations
- No true low-density unseen segment (< 5 % positive-bin density) with long-interval events exists in the available VLM-oracle labels. The lowest-density usable window (`realcartest_1630_2000`) is ≈ 5.4 % and contains only point-anchor events.
- Prior scores for the dev segment come from `cheap_signals_per_unit.csv`/`primary_signal_score`; prior scores for unseen segments come from `proxy_scores.csv`/`score_count`. The two scales differ, but only within-segment rankings are used for `top20` selection. This is documented in `frozen_config.yaml`.
- No human ground-truth labels exist; all metrics are oracle-relative to the existing VLM labels.

## Conclusion
Three unseen segments with replay-compatible labels and prior scores were found. Validation can proceed, but the low-density window is weaker than ideal and will be flagged in the final report.
