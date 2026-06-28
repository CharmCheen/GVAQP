# Sprint 2 Summary: ACCE Preflight + Ablation Ladder

## Six DECISION labels

| Stage | DECISION | Topic |
|---|---|---|
| Stage 10 | `GEOMETRIC_PROXY_PROMISING_LOW_N` | Vehicle query geometric proxy check (n=4) |
| Stage 11 | `QUERY_PRIOR_CROSS_VIDEO_INCONSISTENT` | Query-aware proxy prior cross-video check |
| Stage 12 | `TASKD_AUROC_CONFIRMED` | Task D AUROC independent audit |
| Stage 13 | `ABLATION_LADDER_L4_RECALL_DROP_AT_MID_BUDGET` | Ablation ladder L0-L4 |
| Stage 14 | `CERTIFICATE_MECHANISM_UNRELIABLE` | Certificate coverage Monte Carlo |
| Stage 6 (Task 6) | `L5_NOT_TRIGGERED_FIXED_P_INSUFFICIENT_ISSUE_IS_BUDGET_SPLIT` | L5 conditional (not executed — issue is budget split, not P) |

## Key findings (ranked by importance)

### 1. Certificate mechanism is UNRELIABLE (Stage 14)

The HT-based recall lower bound `R_lower = H / U_{1-delta}(N_pos)` has coverage
far below nominal (0.83 vs 0.95 at B=80, delta=0.05). The HT estimator is
extremely high-variance on small estimation pools (~22 anchors at B=80) and is
biased (mean HT estimate 99.4 vs true 40 at B=80 — overestimates 2.5x due to
weight inflation from small per-block samples).

**Implication**: The ACCE certificate CANNOT be claimed in the paper. The
mechanism needs redesign: larger estimation pool, Wilson/block-level bounds
instead of normal-approx HT, or a completely different certification approach.

### 2. L4 has major recall drop at mid-budget (Stage 13)

L4 (ACCE with 20% cal + 10% audit overhead) drops event recall from 0.519 (L3)
to 0.359 at B=80 — a -0.160 absolute / -31% relative loss. The 30% budget
overhead for calibration+audit is too expensive at mid-budgets.

**Implication**: The budget split (alpha=0.20, audit=0.10) is not viable at
B=60-80. Either reduce overhead (alpha=0.10) or use an adaptive schedule that
allocates less to calibration at mid-budgets.

### 3. Query-aware proxy prior is cross-video INCONSISTENT (Stage 11)

On the vehicle sub-query:
- dataset3 (n=4 vehicle pos): `score_fusion_geometry_motion` (0.585) > `yolo_vehicle_mean` (0.462)
- realcartest (n=67 vehicle pos): `yolo_vehicle_mean` (0.692) > `score_fusion_geometry_motion` (0.582)

The direction REVERSES across videos. Feature ranking Spearman rho = -0.52
(anti-correlated). This is driven by dataset3 being pedestrian/cyclist-dominated
(10% vehicle) while realcartest is vehicle-dominated (71% vehicle).

**However**: `object_count_mean` is consistently strong on both videos for
all_event (0.627, 0.738) and vehicle_event (0.510, 0.702). It is the safest
cross-video deployable default.

**Person proxy cross-video check CANNOT be done** — realcartest V13.7 proxy
features lack person_count/bike_count/lateral_presence.

### 4. L3 (diversity + greedy_maxmin) remains strongest deployable (Stage 13)

At B=80: L3 event recall = 0.519, beating L2 (top-proxy, 0.370) by +0.149
and L1 (score_fusion top-proxy, 0.370) by +0.149. The proxy swap (L1→L2)
and diversity+greedy_maxmin (L2→L3) both contribute.

### 5. Task D AUROC confirmed (Stage 12)

All Sprint 1 Task D AUROC values match within 0.005. Label encoding is correct.
No discrepancy found.

### 6. Vehicle geometric proxy is PROMISING but n=4 (Stage 10)

`score_fusion_geometry_motion` (0.585) shows directional advantage over
`vehicle_count_mean` (0.462) on dataset3's vehicle sub-query, but n=4 makes
this noise-sensitive. The cross-video check (Stage 11) shows the direction
REVERSES on realcartest, so this signal does NOT generalize.

## What can be safely written in the paper

1. `object_count_mean` is the strongest deployable (non-hindsight) proxy on
   both dataset3 (AUROC 0.627) and realcartest (AUROC 0.738) for the all-event
   query. Cross-video consistent.
2. `person_count_max`/`person_count_mean` are hindsight AUROC winners on
   dataset3 (0.814/0.813) but are NOT deployable without reliable calibration
   and CANNOT be validated cross-video (missing features in realcartest).
3. L3 (`object_count_mean + P=2.0 + greedy_maxmin_time`) is the strongest
   deployable selection method on dataset3 (event recall 0.519 at B=80).
4. `greedy_maxmin_time` >= `linspace_spread` at every budget tested.
5. Query-aware proxy prior direction is NOT consistent across videos for the
   vehicle sub-query. A fixed "vehicle→geometric proxy" rule does not generalize.
6. The certificate mechanism (HT + normal approx on stratified samples) is
   UNRELIABLE and must NOT be claimed as a contribution.
7. L4 (ACCE with calibration+audit) has unacceptable recall loss at mid-budget
   due to 30% overhead. The budget split needs redesign.

## What CANNOT be written in the paper

1. "ACCE provides a valid recall certificate Pr[R̂≥γ]≥1−δ" — UNRELIABLE, coverage < nominal.
2. "Query-aware proxy prior is a universal rule" — INCONSISTENT cross-video.
3. "Geometric proxy works for vehicle events" — direction reverses cross-video.
4. "Calibration-based proxy selection is stable" — unstable at small c (Sprint 1 finding).
5. "L4/ACCE improves recall over L3" — it does NOT at B=60-80.
6. "Person proxy prior generalizes across videos" — CANNOT be tested (missing features).
7. "Formal G-ARC certificate is complete" — the mechanism is broken.
8. Any claim about adaptive slicing or quality-adaptive P — not tested, not validated.

## Next steps (revised)

1. **Certificate redesign** (highest priority): the HT+normal-approx approach is
   broken. Options:
   a. Block-level Wilson bounds + conservative summation (no normal approx)
   b. Increase estimation pool to 40-50% of B (trades recall for certificate validity)
   c. Use a completely different framework (e.g., conformal prediction, or the
      SUPG-style frame-level bound adapted to clusters)
2. **Budget split redesign**: reduce calibration/audit overhead at mid-budget.
   An alpha schedule (alpha=0.10 at B≤80, alpha=0.20 at B≥100) might fix L4's
   recall drop without sacrificing the certificate entirely.
3. **L5 (quality-adaptive P)**: the Stage 13 finding shows the L4 problem is
   budget-split, not P. L5 is NOT the right fix. Marked as not needed.
4. **Second video with person-count features**: recompute YOLO person/bike counts
   on realcartest to enable the person proxy cross-video check. Requires YOLO
   reprocessing (not VLM, but still new compute).
5. **Theory**: the proxy-agnostic feasibility bound (B_min as function of proxy
   AUC and γ) is still open and does not depend on the certificate mechanism.

## Sprint 2 outputs

- `reports/STAGE10_VEHICLE_QUERY_GEOMETRIC_PROXY_CHECK.md`
- `reports/STAGE11_QUERY_PRIOR_CROSS_VIDEO_CHECK.md`
- `reports/STAGE12_TASKD_AUROC_AUDIT.md`
- `reports/STAGE13_ABLATION_LADDER_L0_L4.md`
- `reports/STAGE14_CERTIFICATE_COVERAGE_MONTECARLO.md`
- `tables/stage10_vehicle_query_auroc.csv`
- `tables/stage11_cross_video_auroc.csv`
- `tables/stage12_auroc_audit.csv`
- `tables/stage14_certificate_coverage.csv`
- `replay/ablation_ladder_results.csv` (7200 rows, all selections saved)
- `replay/ablation_ladder_summary.csv`
- `replay/ablation_ladder_selections_sample.csv`
- `scripts/` (common.py + stage10-14 scripts)
