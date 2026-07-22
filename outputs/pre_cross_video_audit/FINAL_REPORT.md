# Stage 1B.5 Pre-Cross-Video Claim Audit Final Report

## 1. Summary Decision

PREFLIGHT_PASS

## 2. K3/C6 Trigger and Path Audit

K3/C6 metric equality legitimate: True. Segment-hash equality: False. Optional C6 trigger count aggregate: 3712. Output changes vs K3 among C6 rows: 204. This means optional mechanisms were exercised and sometimes changed paths, but did not change the aggregate AUC/B20/B100 decision used to freeze K3.

## 3. ARC Native Claim Boundary

ARC-refinement@th0.3 native wins primary overlap_any F1 at B=5 and B=10. MAP-BBEM wins boundedness diagnostics there and wins/equals the strengthened-baseline comparison; it should not be claimed as an unconditional low-budget winner over native ARC.

Allowed wording is in `outputs/pre_cross_video_audit/CLAIM_WORDING.md`.

## 4. Stage 1B Overcoverage Forensics

B=100 root-cause labels: `{'F_metric_denominator_artifact': 16, 'C_new_positive_anchor_from_barrier_query': 5}`. Overcoverage rise is mainly bounded event-set expansion/new or shifted segments after additional positive evidence, not a K3 cap violation or negative-barrier crossing. Stage 1B remains optional high-budget refinement / WEAK_GO.

## 5. SUPG Variant Equivalence

SUPG case counts: `{'Case_B_differences_collapse_under_K3_materialization': 30}`. No same-file path alias was found. SUPG variants can be reported separately with a note if they collapse under K3; merging for plots is acceptable only if clearly stated.

## 6. Frozen Config

Frozen parameter document: `docs/FROZEN_CONFIG_FOR_CROSS_VIDEO.md`. Cross-video validation must not modify these parameters.

## 7. Go / No-Go for Cross-Video

Run cross-video validation with MAP-anchor-only + K3 and MAP-anchor-barrier + K3, plus native and strengthened baselines. Keep Stage 1B marked optional/high-budget refinement unless cross-video confirms the boundedness/AUC tradeoff.

Sanity failures: 0.
