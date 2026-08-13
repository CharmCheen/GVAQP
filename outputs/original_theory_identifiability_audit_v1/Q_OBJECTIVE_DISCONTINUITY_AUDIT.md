# Q objective discontinuity audit

Frozen Q is `0.5*terminal_event_recall + 0.5*anytime_event_recall_auc - 1[nonempty precision<0.8]`. At practical `delta=0.005`, original classes are `{'BENEFICIAL': 5, 'HARMFUL': 5, 'INDIFFERENT': 98}`. Two penalty-avoidance states contribute 96.6% of positive deviation value (2.0394/2.1113).

Offline sensitivity removes only the discontinuous `-1`, with no fitting or historical relabeling. Smooth classes become `{'BENEFICIAL': 5, 'HARMFUL': 4, 'INDIFFERENT': 99}`; original-versus-smooth delta Spearman is `0.899`. Per-state results are in `Q_OBJECTIVE_STATE_DIAGNOSTIC.csv`.

`ACTION_HEADROOM_STRUCTURE = MIXED`: positive gain magnitude is discontinuity-dominated, but practical class prevalence changes only from 5/5/98 to 5/4/99 and rank correlation remains high. The smooth recall/AUC component still contains structure. This diagnostic does not replace the frozen Q conclusion.
