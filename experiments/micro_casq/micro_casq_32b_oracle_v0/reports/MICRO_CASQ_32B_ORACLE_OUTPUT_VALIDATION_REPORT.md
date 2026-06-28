# Micro-CASQ 32B Oracle Output Validation Report

Generated: `2026-06-22T15:17:02Z`

Validation checks oracle-relative output schema and accounting. It does not rewrite labels or event boundaries.

| check | passed | detail |
| --- | --- | --- |
| every_selected_materializable_sample_accounted_for | True | selected=153 results=153 |
| no_non_materializable_samples_processed | True | extra=0 |
| every_row_has_raw_output_or_explicit_not_run | True | 153 |
| successful_parses_have_allowed_labels | True |  |
| successful_parses_have_allowed_boundary_status | True |  |
| positive_rows_have_boundaries_or_uncertain_truncated | True | 31 |
| negative_rows_have_null_boundaries | True | 112 |
| event_boundaries_within_clip_duration | True | 149 |
| old_labels_not_promoted_to_gold | True | old labels retained only as provenance columns |