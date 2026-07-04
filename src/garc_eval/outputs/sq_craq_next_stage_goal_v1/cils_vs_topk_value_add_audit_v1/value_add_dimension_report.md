# Value-Add Dimension Report

| dimension | cils_advantage | evidence_value | evidence |
| --- | --- | --- | --- |
| recall_gain | False | 0 | best CILS minus best baseline recall at precision>=0.8 |
| precision_control | False | 0 | CILS only reaches high precision at AUC about 0.90; top-k also reaches same region |
| duplicate_suppression | False | 0.364066 | no stable CILS-specific duplicate advantage established |
| duration_control | False | 1009 | duration-penalized top-k directly controls duration without calibration budget |
| background_duration_control | False | 0.4506 | no independent CILS gain shown |
| seed_stability | False | 5 | small reference and few successful CILS rows |
| oracle_budget_efficiency | False | 0 | top-k uses no calibration oracle budget; CILS does |
