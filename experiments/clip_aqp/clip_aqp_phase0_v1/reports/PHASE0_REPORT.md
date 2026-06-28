# Phase 0 Report: Clip-level AQP Guarantee Feasibility

## 1. Goal

Validate whether clip-level approximate selection with recall certificates is viable under strict sample-splitting and oracle-relative reporting constraints. This Phase 0 run uses existing local data only, does not train models, does not run large-scale VLM inference, and does not download datasets.

## 2. Existing Data Inventory

- audited files: 269
- clean event-boundary files detected in strict audit: 177
- selected local unit source: `test_vlm/focused_validation_outputs/04_temporal_concentration/positive_timeline.csv`
- selected oracle label source: existing conservative VLM pseudo-oracle labels folded into the focused validation timeline
- score source: `proxy_score` derived from existing `score_count`; no fallback-score aggregate is used.

## 3. Unified Phase0 Table

- units: 1000
- oracle-positive units: 61
- pseudo-events: 29
- has clean event boundaries: False

Because clean event boundaries are absent in the unit table, pseudo-events are formed by merging adjacent oracle-positive units. All event recall and certificate quantities below are oracle-relative and pseudo-event based.

## 4. Experiment A: SUPG/window-level + Stitch

Window-level thresholding was calibrated on sampled records, applied to all units, stitched into returned intervals, and evaluated against pseudo-events.

| gamma | delta | theta | trials | GVR | mean_window_recall | mean_clip_event_recall | mean_selected_fraction |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0.8 | 0.05 | 0.3 | 100 | 1 | 0.8121 | 0.2824 | 0.2866 |
| 0.8 | 0.05 | 0.5 | 100 | 1 | 0.8007 | 0.1959 | 0.2673 |
| 0.8 | 0.1 | 0.3 | 100 | 1 | 0.8092 | 0.2872 | 0.2746 |
| 0.8 | 0.1 | 0.5 | 100 | 1 | 0.8139 | 0.1748 | 0.2917 |
| 0.9 | 0.05 | 0.3 | 100 | 1 | 0.8762 | 0.1969 | 0.4241 |
| 0.9 | 0.05 | 0.5 | 100 | 1 | 0.8733 | 0.12 | 0.3982 |
| 0.9 | 0.1 | 0.3 | 100 | 1 | 0.8723 | 0.2072 | 0.4006 |
| 0.9 | 0.1 | 0.5 | 100 | 1 | 0.8902 | 0.09655 | 0.4439 |

Result: SUPG/window-level + stitch has clip-level GVR above delta in at least one configured condition.

## 5. Experiment B1: No-repair Block/Event Audit

Returned clips were fixed before certification samples were drawn. Certificate computation rejected any non-certification, design, or repair rows. Event ownership used midpoint-to-block assignment; padding and provenance fields are persisted in the output CSV.

| block_size_seconds | gamma | delta | trials | mean_true_recall | mean_LCB_recall_O | coverage | GVR | mean_tightness | mean_cost |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 0.8 | 0.05 | 200 | 0.2586 | 0 | 1 | 0 | 0.2586 | 139 |
| 10 | 0.8 | 0.1 | 200 | 0.2586 | 0.001236 | 1 | 0 | 0.2574 | 139 |
| 10 | 0.9 | 0.05 | 200 | 0.2586 | 0 | 1 | 0 | 0.2586 | 139 |
| 10 | 0.9 | 0.1 | 200 | 0.2586 | 0 | 1 | 0 | 0.2586 | 139 |
| 15 | 0.8 | 0.05 | 200 | 0.2586 | 0 | 1 | 0 | 0.2586 | 96 |
| 15 | 0.8 | 0.1 | 200 | 0.2586 | 0.0003774 | 1 | 0 | 0.2582 | 96 |
| 15 | 0.9 | 0.05 | 200 | 0.2586 | 0 | 1 | 0 | 0.2586 | 96 |
| 15 | 0.9 | 0.1 | 200 | 0.2586 | 0 | 1 | 0 | 0.2586 | 96 |
| 30 | 0.8 | 0.05 | 200 | 0.2586 | 0 | 1 | 0 | 0.2586 | 49 |
| 30 | 0.8 | 0.1 | 200 | 0.2586 | 0 | 1 | 0 | 0.2586 | 49 |
| 30 | 0.9 | 0.05 | 200 | 0.2586 | 0 | 1 | 0 | 0.2586 | 49 |
| 30 | 0.9 | 0.1 | 200 | 0.2586 | 0 | 1 | 0 | 0.2586 | 49 |

Result: no-repair audit coverage=1.000; mean LCB=0.000; cost below full block scan=True.

## 6. Experiment B2: Repair + Fresh Certification

Status: SKIPPED_B1_NOT_CONSERVATIVE_NONVACUOUS. Diagnostic and certification samples are kept disjoint when the stage runs; final certificate rows carry `sample_split=certification`, `used_for_design=false`, and `used_for_repair=false`.

## 7. Experiment C: Oracle Stability

Configured stability thresholds were written to `config/oracle_stability_thresholds.json` and are reported side by side with measured values.

| label_source_pair | num_comparable_clips | agreement_rate | flip_rate | abstain_rate | stable_min_agreement_rate | stable_max_flip_rate | stability_classification |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 8b_raw_vs_masked | 67 | 0.8209 | 0.1791 | 0 | 0.85 | 0.1 | ambiguous |
| 32b_raw_vs_masked | 67 | 0.791 | 0.209 | 0 | 0.85 | 0.1 | unstable |

Current oracle labels are not stable enough for human-truth guarantee; only oracle-relative certification is currently defensible.

## 8. Findings

- Existing local data can support a Phase 0 pseudo-event smoke validation, but it does not contain clean human-adjudicated event boundaries.
- SUPG/window-level stitching failure observed: True.
- No-repair block audit conservative coverage observed: True.
- No-repair LCB non-vacuous by the configured mean-LCB check: False.
- Mean certification cost below full block scan: True.

## 9. Limitations

- Event boundaries are pseudo-derived from adjacent oracle-positive windows; they are not clean oracle-localized or human-adjudicated boundaries.
- The oracle is a VLM-defined pseudo-oracle and may be prompt/model sensitive.
- The candidate generator is intentionally simple and existing-score based; Phase 0 does not optimize proxy design.
- Confidence bounds are finite-population approximations for feasibility validation, not a final G-ARC theorem.

## 10. Next Action

Acquire or construct a small clean event-boundary set before making a GO/NO-GO claim about real clip-level event guarantees. Candidate datasets to audit without immediate download are DoTA, DADA-2000/LOTVS-DADA, and Nexar dashcam collision prediction.

## 11. Final Decision

FINAL_DECISION: NO_GO
