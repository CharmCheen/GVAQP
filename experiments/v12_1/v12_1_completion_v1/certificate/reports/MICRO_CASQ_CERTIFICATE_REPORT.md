# Micro-CASQ Certificate Report

A reserved-pool certificate simulation was run only after the benchmark and candidate gates passed. This is oracle-relative and not a human-truth safety certificate. No non-vacuous final certificate is claimed when the reserved certification pool is underpowered.

| candidate_generator | configuration | split | reserved_pool_n | selected_n | positive_event_count | event_hit_count | true_oracle_recall | LCB_recall | wilson_lcb_95 | wilson_ucb_95 | coverage | GVR | tightness | cost_to_certificate | negative_window_coverage | decision | reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fixed_temporal_coverage | top_fraction=0.75 | reserved_certification_pool | 47 | 35 | 7 | 6 | 0.8571428571428571 | 0.48686549668097 | 0.48686549668097 | 0.9743210440510252 | 0.6417910447761194 | 0.7446808510638298 | 0.4874555473700552 | 35 | 29 | MICRO_CASQ_CERTIFICATE_DECISION: UNDERPOWERED | reserved certification pool has fewer than 30 oracle positives |

MICRO_CASQ_CERTIFICATE_DECISION: UNDERPOWERED
