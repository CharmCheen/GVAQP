# Score Conditions

All synthetic and oracle signals are `DIAGNOSTIC_ONLY`; only `real_repaired_score` is non-label-derived and uses existing `active_score`.

| score_condition | source_signal_name | target_auc | mean_empirical_auc | mean_empirical_ap | seed_count | diagnostic_label_derived |
| --- | --- | --- | --- | --- | --- | --- |
| random_signal | random_signal | 0.5 | 0.498329 | 0.0992088 | 20 | False |
| synthetic_auc_0_70 | synthetic_auc_0_70 | 0.7 | 0.698275 | 0.216102 | 20 | True |
| real_repaired_score | current_real_signal | nan | 0.712618 | 0.181748 | 1 | False |
| synthetic_auc_0_80 | synthetic_auc_0_80 | 0.8 | 0.80117 | 0.355328 | 20 | True |
| synthetic_auc_0_85 | synthetic_auc_0_85 | 0.85 | 0.850888 | 0.462732 | 20 | True |
| synthetic_auc_0_90 | synthetic_auc_0_90 | 0.9 | 0.89985 | 0.596678 | 20 | True |
| synthetic_auc_0_95 | synthetic_auc_0_95 | 0.95 | 0.95013 | 0.766511 | 20 | True |
| oracle_signal | oracle_signal | 1 | 1 | 1 | 1 | True |
