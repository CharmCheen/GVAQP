# Calibration Label Alignment Report

Default calibration label: `answer_iou_0_3`.

`discovery_positive` is recorded in oracle samples for diagnostics only and is not used as `oracle_label`.

Sensitivity labels available in `interval_labels_v2_clean.csv`: `answer_iou_0_5`, `answer_overlap_purity`.

| budget | policy | calls_ok | positive_rate | brier | ece | auc |
| --- | --- | --- | --- | --- | --- | --- |
| 5 | decision_aware_simple | True | 0 | 0.0917366 | 0.0433952 | 0.503276 |
| 5 | quota_stratified | True | 0.128 | 0.126156 | 0.162633 | 0.599533 |
| 5 | top_score | True | 0 | 0.0917231 | 0.0430163 | 0.5 |
| 5 | uncertainty_stratified | True | 0.232 | 0.169835 | 0.25532 | 0.583561 |
| 5 | uniform | True | 0.108 | 0.143819 | 0.205584 | 0.519531 |
| 10 | decision_aware_simple | True | 0 | 0.0890323 | 0.0148184 | 0.524938 |
| 10 | quota_stratified | True | 0.107 | 0.127696 | 0.178408 | 0.545345 |
| 10 | top_score | True | 0 | 0.0901452 | 0.0165075 | 0.5 |
| 10 | uncertainty_stratified | True | 0.168 | 0.145184 | 0.204996 | 0.555866 |
| 10 | uniform | True | 0.103 | 0.137074 | 0.192989 | 0.542721 |
| 20 | decision_aware_simple | True | 0.05 | 0.0890804 | 0.00575819 | 0.523677 |
| 20 | quota_stratified | True | 0.089 | 0.110981 | 0.130319 | 0.55911 |
| 20 | top_score | True | 0 | 0.0937008 | 0.058537 | 0.488004 |
| 20 | uncertainty_stratified | True | 0.132 | 0.124927 | 0.165129 | 0.579485 |
| 20 | uniform | True | 0.106 | 0.121413 | 0.152981 | 0.568443 |
| 40 | decision_aware_simple | True | 0.125 | 0.0913235 | 0.0453871 | 0.514336 |
| 40 | quota_stratified | True | 0.09675 | 0.0980384 | 0.0792211 | 0.587674 |
| 40 | top_score | True | 0.05 | 0.0910476 | 0.0286385 | 0.501495 |
| 40 | uncertainty_stratified | True | 0.12325 | 0.102341 | 0.0990563 | 0.583973 |
| 40 | uniform | True | 0.0975 | 0.105712 | 0.107573 | 0.599044 |
| 80 | decision_aware_simple | True | 0.15 | 0.0939498 | 0.0602082 | 0.47226 |
| 80 | quota_stratified | True | 0.093125 | 0.0934201 | 0.0628092 | 0.630305 |
| 80 | top_score | True | 0.1 | 0.0893108 | 0.015475 | 0.532038 |
| 80 | uncertainty_stratified | True | 0.09 | 0.0936528 | 0.0453689 | 0.588953 |
| 80 | uniform | True | 0.098625 | 0.103256 | 0.102133 | 0.6191 |
