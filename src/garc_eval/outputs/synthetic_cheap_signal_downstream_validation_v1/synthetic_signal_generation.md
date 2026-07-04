# Synthetic Signal Generation

Synthetic scores are candidate-level, label-derived diagnostic interventions. They use `y = TP_iou_0_3`, where TP means matching a true interval event at IoU >= 0.3. These scores are not non-leak cheap signals and must not be reported as real retrieval performance.

- Synthetic seeds: `0..19` (smoke-scale 20 seeds because full 100-seed CILS grid is high runtime).
- Random baseline repeats: `100`.
- Normal-score construction: positive scores are shifted by `sqrt(2) * Phi^-1(target_auc)` with unit Gaussian noise.
- Current real signal: normalized existing `active_score`, no label access.
- Oracle signal: `TP_iou_0_3 + tiny deterministic noise`, diagnostic upper bound only.
- Off-target AUC rows beyond +/-0.03: `0`.

Quality preview:

| synthetic_signal_name | target_auc | empirical_auc_iou_0_3 | empirical_ap_iou_0_3 | empirical_auc_iou_0_5 | empirical_ap_iou_0_5 | seed | pos_count | neg_count | score_mean_pos | score_mean_neg | score_std_pos | score_std_neg | diagnostic_label_derived | off_target_auc |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| current_real_signal | nan | 0.712618 | 0.181748 | 0.69147 | 0.0689983 | -1 | 1177 | 10762 | 0.725589 | 0.559158 | 0.175824 | 0.229303 | False | False |
| oracle_signal | 1 | 1 | 1 | 0.970979 | 0.435601 | -1 | 1177 | 10762 | 1 | 4.92837e-10 | 2.76074e-10 | 2.89148e-10 | True | False |
| random_signal | 0.5 | 0.49581 | 0.101502 | 0.503134 | 0.0389321 | 0 | 1177 | 10762 | 0.0106949 | 0.0134432 | 1.03199 | 0.995875 | False | False |
| random_signal | 0.5 | 0.499217 | 0.0991897 | 0.497112 | 0.0378938 | 1 | 1177 | 10762 | -0.0104659 | -0.0043016 | 1.00788 | 1.00075 | False | False |
| random_signal | 0.5 | 0.492508 | 0.0952818 | 0.498944 | 0.0362848 | 2 | 1177 | 10762 | -0.018822 | 0.0146654 | 0.974075 | 0.996498 | False | False |
| random_signal | 0.5 | 0.499744 | 0.100664 | 0.498352 | 0.0396344 | 3 | 1177 | 10762 | -0.012875 | -0.00649941 | 1.01884 | 0.988288 | False | False |
| random_signal | 0.5 | 0.50417 | 0.101551 | 0.487204 | 0.0360204 | 4 | 1177 | 10762 | 0.0118411 | -0.00409905 | 1.01272 | 0.992317 | False | False |
| random_signal | 0.5 | 0.499134 | 0.0996829 | 0.488527 | 0.0382277 | 5 | 1177 | 10762 | -0.00656016 | -0.00771312 | 1.01805 | 1.00791 | False | False |
| random_signal | 0.5 | 0.496137 | 0.0963264 | 0.48505 | 0.034578 | 6 | 1177 | 10762 | -0.011655 | -0.000490901 | 0.956458 | 0.995715 | False | False |
| random_signal | 0.5 | 0.489385 | 0.0961872 | 0.493888 | 0.035079 | 7 | 1177 | 10762 | -0.028561 | 0.0130412 | 0.999663 | 0.989343 | False | False |
| random_signal | 0.5 | 0.485369 | 0.0949705 | 0.465888 | 0.0323042 | 8 | 1177 | 10762 | -0.0276872 | 0.0169235 | 0.988717 | 1.00325 | False | False |
| random_signal | 0.5 | 0.508627 | 0.0996592 | 0.507216 | 0.037586 | 9 | 1177 | 10762 | 0.0316966 | 0.0012169 | 0.968381 | 1.01119 | False | False |
| random_signal | 0.5 | 0.488022 | 0.099111 | 0.484806 | 0.037392 | 10 | 1177 | 10762 | -0.0313351 | -0.00307736 | 1.01139 | 0.99568 | False | False |
| random_signal | 0.5 | 0.502665 | 0.10214 | 0.523048 | 0.0396381 | 11 | 1177 | 10762 | 0.00637376 | -0.00758468 | 1.01446 | 0.98795 | False | False |
| random_signal | 0.5 | 0.50874 | 0.102968 | 0.529223 | 0.0418985 | 12 | 1177 | 10762 | 0.041247 | 0.00803045 | 1.01516 | 1.00229 | False | False |
| random_signal | 0.5 | 0.497262 | 0.0981697 | 0.506433 | 0.0376822 | 13 | 1177 | 10762 | -0.00375487 | 0.0138127 | 1.01844 | 1.00563 | False | False |
| random_signal | 0.5 | 0.499554 | 0.100335 | 0.512963 | 0.0405073 | 14 | 1177 | 10762 | 0.00993129 | 0.00745956 | 1.01506 | 1.00041 | False | False |
| random_signal | 0.5 | 0.484075 | 0.0932916 | 0.490704 | 0.0361818 | 15 | 1177 | 10762 | -0.0339443 | 0.0139005 | 0.956602 | 0.998248 | False | False |
| random_signal | 0.5 | 0.50562 | 0.101252 | 0.500622 | 0.0379732 | 16 | 1177 | 10762 | 0.00530657 | -0.0173598 | 1.00738 | 1.00599 | False | False |
| random_signal | 0.5 | 0.511658 | 0.104132 | 0.494906 | 0.0370166 | 17 | 1177 | 10762 | 0.0434242 | 0.00538598 | 1.02369 | 0.996333 | False | False |
| random_signal | 0.5 | 0.503751 | 0.10037 | 0.50708 | 0.038474 | 18 | 1177 | 10762 | 0.0106503 | -0.00929553 | 0.979958 | 0.993685 | False | False |
| random_signal | 0.5 | 0.495131 | 0.097393 | 0.503297 | 0.0366957 | 19 | 1177 | 10762 | -0.0206939 | 0.00197045 | 0.994882 | 1.00091 | False | False |
| synthetic_auc_0_60 | 0.6 | 0.598469 | 0.137977 | 0.607337 | 0.0542274 | 0 | 1177 | 10762 | 0.365049 | 0.00874457 | 0.995988 | 1.00129 | True | False |
| synthetic_auc_0_60 | 0.6 | 0.604367 | 0.136859 | 0.59382 | 0.0539405 | 1 | 1177 | 10762 | 0.364392 | 0.00733666 | 0.983266 | 0.99598 | True | False |
| synthetic_auc_0_60 | 0.6 | 0.590493 | 0.136351 | 0.583038 | 0.0528378 | 2 | 1177 | 10762 | 0.323411 | 0.00261965 | 1.0166 | 0.991336 | True | False |
| synthetic_auc_0_60 | 0.6 | 0.611623 | 0.138511 | 0.611693 | 0.0528296 | 3 | 1177 | 10762 | 0.409137 | 0.0119342 | 0.981163 | 1.01834 | True | False |
| synthetic_auc_0_60 | 0.6 | 0.597934 | 0.134729 | 0.6135 | 0.0555151 | 4 | 1177 | 10762 | 0.349034 | 0.00924242 | 0.990284 | 0.996632 | True | False |
| synthetic_auc_0_60 | 0.6 | 0.594567 | 0.132505 | 0.613663 | 0.0542576 | 5 | 1177 | 10762 | 0.325581 | -0.00135843 | 0.990444 | 1.0023 | True | False |
| synthetic_auc_0_60 | 0.6 | 0.582915 | 0.128834 | 0.580996 | 0.0473758 | 6 | 1177 | 10762 | 0.316638 | 0.0143932 | 0.962516 | 1.00014 | True | False |
| synthetic_auc_0_60 | 0.6 | 0.613954 | 0.149017 | 0.59095 | 0.0545262 | 7 | 1177 | 10762 | 0.401878 | -0.0119596 | 0.990823 | 0.991727 | True | False |
