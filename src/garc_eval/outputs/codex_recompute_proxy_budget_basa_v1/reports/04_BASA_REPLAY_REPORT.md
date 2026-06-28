# 04 BASA Replay Report

## BASA Grid

Variants: BASA_mean, BASA_ucb, BASA_thompson, BASA_two_channel. Block sizes: 150/300/600s. Initial samples m=1/2/3. Within-block modes: random, object_count_mean, score_fusion, calibrated_best_proxy. Seeds: 0..199.

Best BASA overall row: `BASA_ucb_block300_m2_calibrated_best_proxy`, B=150, event recall=0.589, anchor recall=0.551.

Best BASA at B=80: `BASA_mean_block600_m1_calibrated_best_proxy`, event recall=0.369, anchor recall=0.365.

BASA is evaluated as deployable because it uses only sampled oracle outcomes during simulated budget allocation. Full labels are used only after selection for replay metrics.

See `replay/basa_replay_long.csv`, `replay/basa_replay_summary.csv`, and `replay/basa_selected_anchors/`.
