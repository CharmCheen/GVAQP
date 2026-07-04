# Exhaustive Subset Status

- **Existing exhaustive annotation subset**: not found in any searched path.
- **Generated template**: `outputs/exsample_aware_replay/exhaustive_subset_annotation_package/exhaustive_bins_template.csv`
- **Status**: pending human annotation.

## Template Contents
- Total bins in template: 54
- Windows: {'window_high_prior': 18, 'window_low_prior': 18, 'window_suspected_leakage': 18}

## Required Annotation Fields
- `label`: positive / negative / uncertain
- `event_id`: identifier for the event this bin belongs to (if positive)
- `event_t_start`, `event_t_end`: event boundaries
- `inside_E0_top10/top20/top30`: whether the bin falls inside the corresponding E0 envelope
- `notes`, `reviewer`: free-form notes and reviewer initials

## Calibration Metrics Blocked
The following metrics are marked **未验证 / pending human annotation** until this package is completed:
- estimated missing-mass error
- outside-envelope leakage calibration
- H7 (audit ledger calibration ability)
