# Segment Selection Report

## Goal
Document why each video segment was chosen for the frozen cross-segment validation.

## Selection Constraints
- Use only previously computed signals and existing VLM-oracle labels.
- Include the original dev segment (`realcartest_2000_3200`) as a calibration reference.
- Select 2–3 additional unseen segments spanning high, medium, and low event density.
- Do not use any part of the data to tune the frozen configuration.

## Selected Segments

| Segment | Role | Density label | Duration (s) | N events | N long | N point | Positive-bin density | Rationale |
|---------|------|---------------|--------------|----------|--------|---------|----------------------|-----------|
| realcartest_2000_3200 | calibration | dev | 1,200 | 20 | 6 | 14 | 26.7% | Original dev window; recomputed under frozen pipeline as sanity reference. |
| realcartest_0_1570 | unseen | high | 1,570 | 20 | 8 | 12 | 28.0% | Densest available unseen window; tests behavior when many long events are packed together. |
| realcartest_3200_3830 | unseen | medium | 630 | 7 | 4 | 3 | 20.6% | Medium density; covers the tail of the video not used in dev. |
| realcartest_1630_2000 | unseen | low | 370 | 2 | 0 | 2 | 5.4% | Lowest-density available window; only point-anchor events, so long-event recall is undefined/metric is event recall. |

## Data Sources
- Whole-video oracle labels: `experiments/v13/v13_8_full_oracle/tables/center10_vlm_oracle_events.csv`
- Unseen prior scores: `experiments/roadclip_budget_v2/roadclip_budget_v2/proxy_scores.csv`
- Dev atomic grid: `experiments/v13/v13_8_full_oracle/tables/atomic_grid_10s.csv`

## Known Limitations
- `realcartest_1630_2000` does not contain any long-interval events; long-event recall cannot be measured there.
- No available segment has a true <5% long-event density with long events, so the "low" condition is approximated by a point-anchor-only window.
- Segment boundaries were chosen to align with existing 10 s bins and to avoid overlapping with the dev window.
