# Feature Informativeness (within top bin)

**Diagnostic only.**

AUC > 0.5 means feature positively correlates with TP; AUC < 0.5 means negative.

| feature | AUC | AP | spearman | TP median | FP median | direction |
| --- | --- | --- | --- | --- | --- | --- |
| active_score | 0.4401 | 0.2436 | 0.0638 | 0.6768 | 0.6981 | TP_lower |
| max_score | 0.4401 | 0.2436 | 0.0638 | 0.6768 | 0.6981 | TP_lower |
| mean_score | 0.4868 | 0.2330 | -0.0012 | 0.5041 | 0.4937 | TP_higher |
| score_persistence | 0.3099 | 0.2796 | 0.0589 | 0.5000 | 0.5000 | equal |
| boundary_quality | 0.5273 | 0.2079 | -0.0573 | 0.1047 | 0.1173 | TP_lower |
| boundary_left_drop | 0.5977 | 0.1799 | -0.1746 | 0.0348 | 0.1132 | TP_lower |
| boundary_right_drop | 0.3609 | 0.2955 | 0.1669 | 0.1282 | 0.0685 | TP_higher |
| signal_disagreement | 0.5537 | 0.2093 | -0.0910 | 0.1801 | 0.1992 | TP_lower |
| duration | 0.3944 | 0.2380 | -0.0638 | 12.0000 | 12.0000 | equal |
| num_units | 0.3944 | 0.2380 | -0.0638 | 6.0000 | 6.0000 | equal |
| p_answer | 0.3151 | 0.2847 | nan | 0.6667 | 0.6667 | equal |
