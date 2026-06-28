# Codex Recompute BASA Final Report

## Executive Summary

The corrected no-new-VLM replay confirms the full oracle reference is usable, but it changes the proxy story. `object_count_mean` is the corrected strongest simple proxy on dataset3; GLM's anti-predictive object-count claim was caused by a broken AUROC implementation, not by data alignment.

## 1. GLM AUROC Bug Source

The canonical table has 347 aligned anchors, no duplicate join keys, and no missing proxy rows. The bug is therefore not join mismatch or filtering. The likely source is GLM's custom AUROC routine in `stage3_5_analysis_replay.py`, which over-counts pair contributions and reports misleading percent-scale values.

## 2. Corrected Proxy Ranking

- Best hindsight proxy: `person_count_max`.
- Corrected deployable proxy: `object_count_mean`.
- `object_count_mean` AUROC=0.627; it is genuinely useful on dataset3.
- `score_fusion_geometry_motion` AUROC=0.550; it remains weak and nonmonotone but is still useful for testing score-fusion budget decomposition.

## 3. Corrected Budget Replay

The strongest non-oracle method must be judged after adding object-count baselines. Best deployable average-rank method: `diversity_prefilter_object_count_mean`. At B=80, best deployable method is `diversity_prefilter_object_count_mean` with event recall 0.444 and anchor recall 0.350.

Score-fusion diversity prefilter remains a valid score-fusion-family result, but it is no longer enough to claim the overall best non-oracle method because object-count baselines are stronger.

## 4. Fixed DCA

Fixed DCA is now actually replayed. Its status should be read from `replay/budget_replay_corrected_summary.csv`; it is not automatically the main method unless it beats object-count and diversity baselines across B=30-80.

## 5. BASA

Best BASA at B=80: `BASA_mean_block600_m1_calibrated_best_proxy` with event recall 0.369. BASA uses sampled oracle outcomes during selection, so it is a deployable adaptive replay method, not a hindsight upper bound.

BASA's value is strongest if it improves B=30-80 stability and singleton-cluster recall relative to temporal grid/top-proxy/diversity. In this run, compare `replay/basa_replay_summary.csv` against `replay/budget_replay_corrected_summary.csv`; the final decision below reflects that comparison.

## 6. Certificate / Missed Positive Simulation

The certificate simulation is usable only as mechanics. It separates unbiased known-probability samples from proxy-ranked exploitation samples. It does not constitute a formal recall certificate.

## 7. Safe Claims

- Dataset3 full center10 pseudo-oracle reference is complete.
- Corrected proxy analysis identifies `object_count_mean` as stronger than score fusion.
- Corrected budget replay now includes object-count, diversity, calibrated, DCA, and upper-bound methods with saved selections.
- BASA has a reproducible no-new-VLM replay grid.
- Certificate mechanics can estimate missed positives only from known-probability samples.

## 8. Unsafe Claims

- `object_count_mean` is anti-predictive.
- Score-fusion AUROC is 0.624.
- DCA or BASA is a main algorithm without comparing against object-count baselines.
- `cluster_aware_upper_bound` is deployable.
- Dataset3 boundary fields support event-IoU claims.
- Formal G-ARC certificate is complete.

## 9. Need For New VLM

No new VLM is needed for the immediate next step. The next step is method selection and possibly a smaller theory/certificate refinement on the existing labels. New VLM is only needed for second-video replication or boundary redesign.

## 10. Required Question Answers

1. GLM AUROC bug source: custom AUROC implementation, not join/filter mismatch.
2. Corrected proxy ranking: hindsight AUROC winner is `person_count_max`; deployable corrected default is `object_count_mean`.
3. `object_count_mean` is strong: AUROC=0.627; B=80 top-proxy anchor recall=0.375.
4. `score_fusion` still has diagnostic value but is weak: AUROC=0.550; B=80 top-proxy anchor recall=0.250.
5. Corrected strongest deployable non-oracle at B=80: `diversity_prefilter_object_count_mean`.
6. Score-fusion diversity prefilter advantage still holds within score-fusion family: B=80 event recall 0.444 vs top score-fusion 0.370.
7. Object-count baselines change the main conclusion: object-count diversity B=80 event recall 0.444, stronger than score-fusion diversity.
8. Fixed DCA is replayed but not main: B=80 object-count DCA event recall 0.259; score-fusion DCA event recall 0.370.
9. BASA does not beat the best corrected baseline at B=80: best BASA event recall 0.369 vs best baseline 0.444.
10. BASA B=30-80 stability is weaker than the best baseline on mean event recall: BASA mean 0.275, baseline mean 0.324.
11. BASA singleton recall helps somewhat at B=80 (0.281) but remains below the best baseline singleton recall (0.286).
12. BASA_two_channel creates an audit channel, but current recall tradeoff is not enough to beat object-count/diversity baselines.
13. Certificate simulation is usable as mechanics only; formal certificate remains unproven.
14. Current paper main algorithm should be corrected object-count diversity/budget-decomposition baseline, not BASA.
15. Safe claims are listed in Section 7.
16. Unsafe claims are listed in Section 8.
17. No new VLM is needed for immediate method recomputation; new VLM is only needed for replication/boundary redesign.
18. Final decision is below.

FINAL_DECISION: DIVERSITY_OR_OBJECT_COUNT_BASELINE_STRONGER_THAN_BASA
