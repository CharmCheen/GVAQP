# Data Granularity Report

The original `repair_trace_calls.csv` and `cross_segment_metrics.csv` from `late_aqp_frozen_cross_segment_v1` only store final per-trial aggregates and per-call action metadata; they do **not** contain cumulative long-event recall/precision after each oracle call.

To perform this diagnosis, we re-ran B6 and v2 in pure offline replay against the existing labeled grids and recorded, for every call index:

- selected bin and time interval
- prior score (for v2) / sampled chunk (for B6)
- oracle label and hit event id
- cumulative long-event recall and precision up to that call

This is the finest granularity supported by the existing data without generating new labels or oracle calls.
