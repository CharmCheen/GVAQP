# Candidate Pool Quality Audit

Generated: `2026-06-22T13:50:09Z`

This is a metadata-only audit. It does not infer labels, create boundaries, or treat prior VLM/Nexar labels as gold truth.

## Core Counts

- Row count: `488314`
- Unique `video_id`: `6377`
- Unique `source_asset`: `268`
- Rows with non-empty `source_video_path`: `14367`
- Rows with existing `source_video_path`: `9416`
- Rows missing `source_video_path`: `473947`
- Valid start/end windows: `333635`
- Invalid start/end windows: `154679`

## Duration Distribution

| metric | value |
| --- | --- |
| duration_quantile_0 | 0.0329999999999977 |
| duration_quantile_0.05 | 1.2339999999999982 |
| duration_quantile_0.25 | 5.0 |
| duration_quantile_0.5 | 10.0 |
| duration_quantile_0.75 | 15.0 |
| duration_quantile_0.95 | 30.0 |
| duration_quantile_1 | 45.0 |

## Old Label Distribution, Top 15

| old_label | count |
| --- | --- |
| __MISSING__ | 477977 |
| normal | 4101 |
| positive | 2739 |
| no | 1648 |
| False | 939 |
| negative | 405 |
| yes | 240 |
| 0 | 143 |
| True | 61 |
| 1 | 47 |
| skipped_no_video_access | 5 |
| completed | 5 |
| skipped_no_local_model_assets | 1 |
| MISSING_INPUT | 1 |
| NOT_RUN_CPU_FALLBACK_INFEASIBLE | 1 |

## Candidate Source Distribution, Top 15

| candidate_source | count |
| --- | --- |
| block_audit_rows_v2 | 227200 |
| predicted_clips | 144906 |
| kinematic_proxy | 53816 |
| nexar_candidate_event_hits_v2 | 31104 |
| ground_truth_clips | 5931 |
| casq_units_nexar_200 | 4401 |
| proxy_scores | 2602 |
| gt_clips | 2010 |
| nexar_candidate_windows | 2000 |
| roadclip | 1746 |
| vlm_labels_conservative | 1622 |
| phase0_units | 1000 |
| casq_units_nexar_small | 550 |
| nexar_video_mapping_v2 | 400 |
| nexar_video_mapping | 400 |

## Provenance Flags

- `is_nexar_derived` true count: `44253`
- `is_vlm_derived` true count: `335467`
- `is_human_audited` true count: `68`
- `is_pseudo_boundary` true count: `1818`
- `is_external_label` true count: `44253`
- `recommended_for_adjudication` true count: `820`
