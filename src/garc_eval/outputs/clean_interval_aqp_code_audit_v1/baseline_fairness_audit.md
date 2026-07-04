# Baseline Fairness Audit

Verdict: **WARNING**

| method | rows | budgets | taus | max_number_returned | mean_recall_iou_0_3 | is_upper_bound | uses_same_feature_file_for_non_upper_bound |
| --- | --- | --- | --- | --- | --- | --- | --- |
| arc_plus_uniform_outside_audit_simplified | 2500 | 5,10,20,40,80 | 0.5,0.6,0.7,0.8,0.9 | 80 | 0.08592 | False | True |
| arc_style_prune_refine_simplified | 2500 | 5,10,20,40,80 | 0.5,0.6,0.7,0.8,0.9 | 11 | 0.04 | False | True |
| cheap_signal_only | 2500 | 5,10,20,40,80 | 0.5,0.6,0.7,0.8,0.9 | 80 | 0.02 | False | True |
| dense_multiscale_oracle_upper_bound | 2500 | 5,10,20,40,80 | 0.5,0.6,0.7,0.8,0.9 | 80 | 0.18 | True | False |
| fixed_window_topk | 2500 | 5,10,20,40,80 | 0.5,0.6,0.7,0.8,0.9 | 80 | 0.05 | False | True |
| lattice_oracle_upper_bound | 2500 | 5,10,20,40,80 | 0.5,0.6,0.7,0.8,0.9 | 80 | 0.29 | True | False |
| oracle_confirmed_only | 2500 | 5,10,20,40,80 | 0.5,0.6,0.7,0.8,0.9 | 8 | 0.02 | False | True |
| supg_on_windows_simplified | 2500 | 5,10,20,40,80 | 0.5,0.6,0.7,0.8,0.9 | 76 | 0.01496 | False | True |
| threshold_merge_topk | 2500 | 5,10,20,40,80 | 0.5,0.6,0.7,0.8,0.9 | 80 | 0.05 | False | True |

The two oracle upper-bound baselines are explicitly named as upper bounds. Several simplified baselines use budgeted oracle replay labels for confirmation, which is acceptable only if reported as replay/simplified baselines rather than cheap production algorithms.
