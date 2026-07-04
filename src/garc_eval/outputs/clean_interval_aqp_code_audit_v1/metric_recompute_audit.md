# Metric Recompute Audit

Verdict: **PASS**

| metric | recomputed | v2 | source | abs_diff |
| --- | --- | --- | --- | --- |
| lattice_oracle_upper_bound_iou_0_3 | 0.55 | 0.55 | proposal_upper_bound_report | 0 |
| lattice_oracle_upper_bound_iou_0_5 | 0.3 | 0.3 | proposal_upper_bound_report | 0 |
| best_proposal_family_iou_0_3 | 0.5 | 0.5 | proposal_quality max | 0 |
| any_overlap_event_recall | 1 | 1 | proposal_quality max | 0 |
| center_hit_event_recall | 1 | 1 | proposal_quality max | 0 |
| main_CILS_max_recall_iou_0_3 | 0 | 0 | selected_intervals empty | 0 |

Selected intervals file rows: `0`. Because it is empty, the independent selected-set recomputation proves the reported CILS main recall of 0.0, but cannot validate non-empty per-trial selection behavior.
