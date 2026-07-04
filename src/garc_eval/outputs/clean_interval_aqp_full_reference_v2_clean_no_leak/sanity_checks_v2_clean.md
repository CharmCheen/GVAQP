# Sanity Checks V2

- feature_only_has_no_label_columns: PASS (detail=[])
- calibration_uses_answer_label: PASS (detail=['answer_iou_0_3'])
- sample_count_never_exceeds_budget: PASS (detail=)
- quota_policy_present: PASS (detail=)
- stress_best_noisy_random_not_identical: PASS (detail=[{'stress_test': 'best_proxy', 'recall': 0.048, 'precision': 1.0}, {'stress_test': 'low_density_blindspot_proxy', 'recall': 0.0, 'precision': nan}, {'stress_test': 'noisy_proxy', 'recall': 0.002, 'precision': 0.2}, {'stress_test': 'partial_inverted_proxy', 'recall': 0.0, 'precision': nan}, {'stress_test': 'random_proxy', 'recall': 0.0, 'precision': 0.0}])
- random_not_stably_close_to_best: PASS (detail={'best_proxy': 0.048, 'low_density_blindspot_proxy': 0.0, 'noisy_proxy': 0.002, 'partial_inverted_proxy': 0.0, 'random_proxy': 0.0})
- duration_inflation_control: PASS (detail=0.0)
