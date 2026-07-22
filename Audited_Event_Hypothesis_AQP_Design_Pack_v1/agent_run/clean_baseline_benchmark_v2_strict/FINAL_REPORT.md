# Strict Clean Baseline Benchmark v2 Report

- Benchmark source: `/qiuyeqing/llama_prl/G-ARC/data/realcam/long_video_data/long_video_dataset3.mp4`
- Benchmark ID: `cbbv2_514c0d360fd5b2a4b5fe`
- Strict oracle-build ID: `strict_oracle_3b9ba1187c0449426978`
- Baseline execution: `CLEAN_RERUN_FROM_FROZEN_INPUTS`
- Result scope: `SINGLE_VIDEO_TEMPORAL_HOLDOUT_DIAGNOSTIC`
- Reference: `VLM_DEFINED_PSEUDO_ORACLE` (not human ground truth)

## Provenance and execution

The strict oracle contains 347 accepted fresh outputs and reuses zero legacy
raw responses. Full model weights, critical package contents, prompt, parser,
frame inputs, resolved runtime, preprocessing tensors, RNG states, and attempt
events are content-bound by the strict oracle package. Every acquisition run
starts from empty observation state and makes zero new physical VLM calls;
logical calls remain fully charged.

All baseline/current selections, segments, metrics, aggregates, and rankings
were regenerated for this benchmark ID. Sanity failures:
`0`.

## Result summary

- Best repository baseline: `baseline/B5_ARC_native/arc_refinement_th0.4_native`
- MAP/M1 K3-bridge-safe directional benchmark decision: `WEAK GO`
- Event-F1 AUC delta: `-0.001604`
- Per-budget event-F1 wins/ties/losses: `[50, 80, 100]` / `[]` / `[5, 10, 20]`

Precision and review-cost tradeoffs:

|   budget |   current_precision |   baseline_precision |   current_cost |   baseline_cost |
|---------:|--------------------:|---------------------:|---------------:|----------------:|
|        5 |            0        |             0.25498  |              0 |            1886 |
|       10 |            1        |             0.261882 |             20 |            1862 |
|       20 |            1        |             0.267385 |             30 |            1830 |
|       50 |            0.875    |             0.293701 |             80 |            1714 |
|       80 |            0.909091 |             0.981818 |            110 |              92 |
|      100 |            0.916667 |             0.90343  |            130 |             112 |

## Baseline coverage

- B0 random: 100 deterministic seeds per budget with uncertainty summaries.
- B1 top-proxy and B2 component-first: deterministic clean reruns.
- B3 ARC controlled and B5 ARC native: repository implementation, threshold 0.4.
- B4 SUPG adapted: all-selected and confirmed-only, native and controlled.
- B6 ABae: stratified diagnostic, native and controlled.
- MAP/M1: original K3 and K3-bridge-safe over the same acquisition trace.

ARC/SUPG adapter results are labeled `ADAPTED_NO_ORIGINAL_GUARANTEE`.
Relation methods remain gated because no relation oracle is frozen.

## Failures and scope impact

| method                | variant     |   seed | budget   | track          | exception                                                           |   traceback | missing_dependency          | affects_best_available_baseline   |
|:----------------------|:------------|-------:|:---------|:---------------|:--------------------------------------------------------------------|------------:|:----------------------------|:----------------------------------|
| M2_coverage_variant   | not_run     |      0 | all      | current_method | No frozen coverage variant in docs/FROZEN_CONFIG_FOR_CROSS_VIDEO.md |         nan | frozen method specification | False                             |
| M3_relation_heuristic | gate_failed |      0 | all      | current_method | Relation oracle table absent; relation gate did not pass            |         nan | relation oracle             | False                             |
| M4_relation_adaptive  | gate_failed |      0 | all      | current_method | Relation oracle table absent; relation gate did not pass            |         nan | relation oracle             | False                             |

This is an oracle-relative conclusion on one long video. It is not a human-GT,
cross-video, or deployment-safety claim. Strict freeze readiness is decided by
the separate completion/provenance/replay audits, not by this report alone.
