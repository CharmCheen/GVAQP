# Lattice Construction Report

Intervals generated from cheap signals only: 1220.

Methods implemented: fixed_window, threshold_merge, peak_expand, valley_split, multi_signal_union.

Feature-only lattice for selection: `interval_lattice_features_only.csv`.

Evaluation-labelled lattice: `interval_lattice.csv`.

Leakage control: interval generation consumes only `cheap_signals_per_unit.csv`; reference labels are
joined afterward by `evaluate_intervals` for diagnostics and oracle replay.

| method | number_of_intervals | avg_duration | median_duration | positive_interval_rate | mean_positive_unit_fraction |
| --- | --- | --- | --- | --- | --- |
| fixed_window | 505 | 15.695 | 10 | 0.0891089 | 0.133465 |
| multi_signal_union | 81 | 6.66667 | 4 | 0.0493827 | 0.110085 |
| peak_expand | 186 | 20.3871 | 22 | 0.193548 | 0.239783 |
| threshold_merge | 354 | 8.85876 | 6 | 0.0762712 | 0.130789 |
| valley_split | 94 | 14.1489 | 6 | 0.0638298 | 0.109663 |
