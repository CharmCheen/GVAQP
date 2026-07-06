# Data Availability Report

## Search scope

Searched for existing `reference_events.csv` / `full_reference_units.csv` / `*vlm_oracle_events.csv` files under the repository root.

## Existing O_ref files

| File | Video | Events | Time coverage | Notes |
|------|-------|--------|---------------|-------|
| `experiments/v13/v13_8_full_oracle/tables/center10_vlm_oracle_events.csv` | realcartest | 51 | 10.0–3920.7 | Primary whole-video VLM-oracle labels |
| `src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/reference_events.csv` | realcartest | 20 | 2030.0–3110.7 | Dev-segment reference |
| `src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_label_aligned/reference_events.csv` | realcartest | 20 | 2030.0–3110.7 | Dev-segment reference |
| `src/garc_eval/outputs/clean_interval_aqp_full_reference_v1/reference_events.csv` | realcartest | 20 | 2030.0–3110.7 | Dev-segment reference |

## Already-used intervals

| Video | Start | End | Role |
|-------|-------|-----|------|
| realcartest | 2000.0 | 3200.0 | dev (cross-segment validation) |
| realcartest | 0.0 | 1570.0 | unseen high (cross-segment validation) |
| realcartest | 1630.0 | 2000.0 | unseen low (cross-segment validation) |
| realcartest | 3200.0 | 3830.0 | unseen medium (cross-segment validation) |

## Unused intervals inside existing labels

| Start | End | Duration | Positive-bin density | Long events | Point events | Usable for tuning? | Usable for final validation? | Notes |
|-------|-----|----------|----------------------|-------------|--------------|--------------------|------------------------------|-------|
| 1570.0 | 1630.0 | 60.0 | 0.0% | 0 | 0 | No | No | Within realcartest labels |
| 3830.0 | 3920.7 | 90.7 | 22.2% | 1 | 1 | No | No | Within realcartest labels |

## Intervals outside existing labels

| Video | Available labels | Notes |
|-------|------------------|-------|
| realcartest (after ~3920 s) | No | Center10 labels end near 3920 s; video continues but no O_ref exists. |
| realcartest_5k | No | Video exists but no VEPC reference events found. |
| test | No | Video exists but no VEPC reference events found. |

## Conclusion

No usable interval inside existing labels satisfies the requirements for both tuning and final validation. **Step 3 (one-time labeling) is required.**

Recommended labeling plan:
- For tuning: choose a low-density interval within or beyond current labels, ideally <15% positive-bin density and containing long-interval events.
- For final validation: choose a disjoint interval, preferably on a different video source, with non-overlapping time bounds.
- Because no second labeled video exists, the final-validation interval will have to be a non-overlapping portion of `realcartest` unless new labels are generated for `realcartest_5k` or `test`.
