# Agent Loop Log

## Round 1 Inspect - 2026-06-30T15:31:27+00:00

Read v1 artifacts from `/qiuyeqing/llama_prl/G-ARC/src/garc_eval/outputs/clean_interval_aqp_full_reference_v1`. Confirmed:
- v1 calibration/report mixed interval discovery positivity with final answer precision.
- v1 proposal family upper bound was low: best method-level IoU@0.3 proposal recall in FINAL_REPORT was about 0.30.
- v1 stress tests had nearly identical best/noisy/random rows, consistent with active score overwrite.
- v1 stratified sampling was shuffle-concat-truncate, not quota-based.

Action: build v2 in a separate output/script directory; reuse v1 base units, reference, and cheap signals; do not rerun YOLO/VLM.

Run fix after first attempt: Stage 6 ablation/stress with 100 trials per cell was too slow on the larger v2 lattice.
Main, calibration, and baselines remain at 100 trials; ablation/stress are diagnostic and use DIAG_TRIALS=20.

Run fix after audit: CILS selected no intervals in the main run, so `selected_intervals_by_trial_v2.csv`
must still be emitted with a fixed schema instead of a blank one-byte file.

## Round 1 Evaluate - 2026-06-30T15:41:43+00:00

Run command: `bash src/garc_eval/experiments/clean_interval_aqp_full_reference_v2_label_aligned/run_all.sh`

Key metrics:
- Level 1: PASS
- Level 2: Negative
- lattice_oracle_upper_bound_iou_0_3: 0.550
- budgeted proposal recall@200 oracle sort: 0.500
- max CILS IoU@0.3 recall: 0.000
- min stress best/random separation: 0.048

Continue loop: no, v2 Level 1 checks pass and final report records weak/negative research limits without claiming success.

