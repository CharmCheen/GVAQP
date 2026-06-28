# Nexar-200 Derived-Boundary CASQ Benchmark Report

## 1. Goal

Build a metadata-only Nexar benchmark with about 200 positive derived-boundary events and 200 normal videos, then rerun Phase 0-style SUPG stitch and no-repair block/event audit validation. No VLM, training, perception stack, full dataset download, or original-boundary fabrication is used.

## 2. Dataset and Metadata Source

- Positive metadata: `/qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/hf_metadata_probe/train/positive/metadata.csv`
- Negative metadata: `/qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar/hf_metadata_probe/train/negative/metadata.csv`
- Positive metadata rows: `750`
- Negative metadata rows: `750`
- Selected positive rows: `200`
- Selected normal rows: `200`
- Videos downloaded: `False`

## 3. Boundary Derivation Rule

For positives with `time_of_alert` and `time_of_event`, CASQ uses:

`event_start = time_of_alert`

`event_end = time_of_event`

`boundary_source = derived_from_alert_time_to_event_moment`

`boundary_confidence = medium`

These are derived precursor intervals, not original human event_start/event_end annotations.

## 4. CASQ Event Conversion

| metric | value |
| --- | --- |
| num_videos | 400 |
| num_positive_videos | 200 |
| num_normal_videos | 200 |
| usable_casq_events | 200 |
| event_duration_min | 0.0329999999999977 |
| event_duration_median | 1.4000000000000021 |
| event_duration_mean | 1.6031150000000003 |
| event_duration_max | 4.213000000000001 |
| event_duration_distribution | {'<=0.5s': 11, '0.5-1s': 39, '1-2s': 93, '2-5s': 57, '>5s': 0} |
| boundary_source_distribution | {'derived_from_alert_time_to_event_moment': 200} |
| boundary_confidence_distribution | {'medium': 200} |

## 5. CASQ Unit Construction

Units are fixed 5s, 10s, and 15s intervals. Tail fragments shorter than the configured unit length are dropped.

| metric | value |
| --- | --- |
| num_units | 4401 |
| event_overlap_units | 759 |
| background_units | 3642 |
| unit_durations | [5.0, 10.0, 15.0] |

## 6. Schema Validation

| check | passed | detail |
| --- | --- | --- |
| manifest_required_columns | True |  |
| event_required_columns | True |  |
| unit_required_columns | True |  |
| event_start_lt_event_end | True |  |
| event_duration_positive | True |  |
| event_midpoint_inside_interval | True |  |
| derived_boundaries_not_original_annotation | True |  |
| derived_boundaries_explicitly_marked | True |  |
| human_adjudicated_false | True |  |
| no_fabricated_boundaries | True |  |
| all_matched_event_ids_exist | True |  |
| normal_videos_have_no_casq_events | True |  |

Sanity checks:

| check | passed | recall | detail |
| --- | --- | --- | --- |
| oracle_event_clips_recall_theta_0.3 | True | 1.0 | exact derived event intervals used only to validate IoU evaluator |
| stitched_all_5s_units_recall_theta_0.3 | True | 0.0 | expected failure observed for short derived intervals; documents SUPG stitch failure mode, not evaluator failure |
| oracle_event_clips_recall_theta_0.5 | True | 1.0 | exact derived event intervals used only to validate IoU evaluator |
| stitched_all_5s_units_recall_theta_0.5 | True | 0.0 | expected failure observed for short derived intervals; documents SUPG stitch failure mode, not evaluator failure |

## 7. SUPG/window-level + Stitch Result

The SUPG-style run uses metadata-only hash-random 5s unit selection, independent of labels and event intervals. Because many Nexar alert-to-event intervals are much shorter than 5s, overlap does not imply high IoU recall.

| theta | gamma | selection_fraction | trials | mean_true_derived_recall | median_true_derived_recall | GVR | mean_selected_n | mean_stitched_clip_n |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.3 | 0.8 | 0.1 | 100 | 0.030899999999999987 | 0.03 | 1.0 | 240.0 | 219.54 |
| 0.3 | 0.8 | 0.2 | 100 | 0.05099999999999999 | 0.05 | 1.0 | 480.0 | 400.33 |
| 0.3 | 0.8 | 0.35 | 100 | 0.06255 | 0.06 | 1.0 | 840.0 | 596.03 |
| 0.3 | 0.8 | 0.5 | 100 | 0.054700000000000006 | 0.055 | 1.0 | 1200.0 | 700.87 |
| 0.3 | 0.8 | 1.0 | 100 | 0.0 | 0.0 | 1.0 | 2401.0 | 400.0 |

## 8. Block/Event Audit Result

The no-repair block/event audit freezes a metadata-only hash candidate set before certification sampling. It uses only certification samples and does not use diagnostic or repair reuse.

Reference condition for comparison: theta=0.3, gamma=0.8, delta=0.1, 10s blocks, sample_fraction=0.35.

| theta | gamma | delta | block_size_seconds | sample_fraction | trials | true_derived_recall | LCB_recall_mean | LCB_recall_median | LCB_recall_p10 | LCB_recall_p90 | GVR | coverage | tightness | fraction_vacuous | certificate_success_rate | cost_to_certificate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.3 | 0.8 | 0.1 | 10 | 0.35 | 100 | 0.06 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 | 0.0599999999999999 | 1.0 | 0.0 | 420.0 |

## 9. Comparison to Phase 0.6 Power Simulation

- Did Nexar-200 behave like the power simulation predicted? Partly. It reached 200 derived events, but the metadata-only hash candidate set has true derived recall `0.0600`, which is not the same operating point as the Phase 0.6 reference recall around 0.31.
- Is LCB_recall non-vacuous at around 200 events? Reference median LCB is `0.0000` with fraction vacuous `1.0000`.
- Does GVR remain <= delta? Reference GVR is `0.0000` against delta `0.1`; this is mostly because certificates do not succeed when LCB is far below gamma.
- Is the bound still too conservative for gamma=0.8/0.9? Yes. Reference certificate success rate is `0.0000`.
- Does this justify expanding to 500 events? Not as a main claim. It can be useful as a derived-boundary baseline, but the current metadata-only candidate and short derived intervals still make certification weak.
- Are derived boundaries too weak for main-paper claims? Yes; they are not original human intervals.

## 10. Limitations

- Boundaries are derived from alert/event timestamps, not original human interval annotations.
- Videos were not downloaded, so no visual/perception proxy is available.
- The candidate generator is a metadata-only hash/random baseline and should not be interpreted as a deployed retrieval method.
- The block audit validates the certificate machinery over derived boundaries; it does not establish human-truth driving-event recall.
- GVR can be zero when certificate success is also zero, so GVR alone is not evidence of usefulness.

## 11. Recommendation

Use Nexar-200 as a derived-boundary baseline and certificate plumbing benchmark only. For main research claims, prioritize original interval annotations or human-adjudicated CASQ boundaries. Expanding to 500 derived events is reasonable only after adding a non-label perception or metadata proxy that raises true derived recall without using event labels.

NEXAR_200_DECISION: METHOD_STILL_TOO_VACUOUS
