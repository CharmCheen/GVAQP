#!/usr/bin/env python3
"""Sprint 4 Summary."""
import common as C

decisions = {
    "Stage 19": ("BUDGET_SCHEDULE_PARTIALLY_IMPROVED_TARGET_NOT_MET", "Stage 18 relabel: -0.128 at B=80 does not meet -0.05 threshold. Schedule was tested but doesn't help at B=80 (uses alpha=0.15 there, same as fixed)."),
    "Stage 20": ("STRUCTURAL_CLUSTER_GAP_FOUND", "B=80 anomaly is NOT rounding. Missed clusters are low-proxy-score singletons (mean 6.5 vs hit 9.8) spread across 8 blocks. Same clusters missed across 200 seeds. Fundamental certification-vs-exploitation tradeoff."),
    "Stage 21": ("STRATIFIED_BOUND_NO_MEANINGFUL_GAIN", "Bonferroni correction (delta/L=0.004/stratum) makes per-stratum bounds so conservative that stratified bound is LOOSER than non-stratified (R_lower improvement = -0.007). Coverage valid (1.0) but no tightness gain."),
    "Stage 22": ("PERSON_CYCLIST_BACKFILL_BLOCKED_NO_YOLO_DATA", "person_count cannot be computed on realcartest without YOLO reprocessing. non_vehicle_count proxy (object_count - vehicle_count) shows AUROC 0.81 on realcartest non_vehicle, directionally consistent with dataset3 person_count (0.84)."),
}

report = """# Sprint 4 Summary: Stage 18 Relabel + B=80 Diagnosis + Stratified Bound + Feature Backfill

## Four DECISION labels

| Stage | DECISION | Summary |
|---|---|---|
"""
for stage, (dec, summary) in decisions.items():
    report += f"| {stage} | `{dec}` | {summary} |\n"

report += """
## Three core conclusions for the paper

### 1. Certificate mechanism: status and tightness

**Current status**: The exact hypergeometric bound (Stage 17) is VALID (coverage
1.0 >= nominal 0.95). The stratified version with Bonferroni (Stage 21) is also
valid but LOOSER, not tighter — the Bonferroni correction (delta/L) makes
per-stratum bounds too conservative.

**R_lower tightness**: Very conservative at all tested configurations.
- Non-stratified (Stage 17): R_lower = 0.02-0.08 vs true recall 0.19-0.50
- Stratified Bonferroni (Stage 21): R_lower = 0.02-0.07 (slightly worse)
- The bound is rarely non-vacuous at B<100

**Deployability**: The proportional allocation stratified bound is deployable
(no oracle info needed) but provides no tightness advantage over non-stratified.
The Neyman allocation (oracle-informed) is also not tighter, confirming the
bottleneck is the Bonferroni correction, not the allocation.

**What to write in the paper**: "We provide a valid recall lower bound estimate
under simulated replay using the exact hypergeometric one-sided upper bound. The
bound is conservative (R_lower << true_recall at small budgets) due to the small
positive rate (11.5%) and estimation pool size. Stratification with Bonferroni
correction does not improve tightness because the per-stratum confidence budget
(delta/L) is too small. A less conservative joint correction (Simes, exact joint
hypergeometric) is left for future work."

**What NOT to write**: strong certificate wording, formal theorem wording,
"we solved the certificate problem", or "stratification improves the bound".

### 2. B=80 anomaly: root cause

**Root cause**: Structural cluster gap, NOT a rounding artifact.

The B=80 fine-grid test (B=70-90) shows smooth, monotonic recall increase — no
phase boundary discontinuity. The budget split (c=12, audit=7, exploit=61) is
smooth at B=80.

The clusters missed by L4 at B=80 are consistently the same across 200 seeds:
- All are singleton clusters with low proxy scores (mean 6.5 vs hit clusters 9.8)
- Spread across 8 of 12 time blocks (blocks 1,2,5,6,7,9,10,11)
- L3 barely covers them with its full 80-anchor exploit budget; L4's 61 exploit
  anchors (after 12 cal + 7 audit) miss them

**This is a fundamental certification-vs-exploitation tradeoff**: any budget
spent on random calibration/audit samples displaces exploit anchors that could
cover borderline clusters. No alpha schedule can fix this — reducing alpha helps
at some budgets but the displaced anchors always miss some borderline clusters.

**What to write in the paper**: "At mid-budgets (B=60-80), the calibration/audit
overhead (15-20% of B) displaces exploit anchors that cover low-proxy-score
singleton clusters. This is a structural tradeoff: the same budget cannot be
used for both exploitation (proxy-guided selection) and certification (random
sampling). The recall drop is concentrated in singleton clusters with proxy
scores below the top-PB pool threshold."

### 3. Query-aware proxy prior: final boundary

**Final boundary**: NOT a universal rule, but NOT a complete failure either.

| Query type | Cross-video status | Evidence |
|---|---|---|
| all_event | object_count_mean consistent | AUROC 0.627 (ds3) / 0.738 (rc), strongest common feature on both |
| non_vehicle | object_count_mean consistent | AUROC 0.638 (ds3) / 0.740 (rc) |
| pedestrian | person_count strong on ds3 only | AUROC 0.841 (ds3), CANNOT test on rc (no person_count feature) |
| cyclist | person_count strong on ds3 only | AUROC 0.785 (ds3), CANNOT test on rc |
| vehicle | INCONSISTENT | score_fusion > vehicle_count on ds3 (n=4), reversed on rc (n=67) |

**Indirect evidence for person proxy cross-video**: `non_vehicle_count` (= object_count - vehicle_count, a rough proxy for person+bike+other) achieves AUROC 0.81 on realcartest non_vehicle_event, directionally consistent with `person_count_mean` AUROC 0.84 on dataset3. This is NOT a direct validation (non_vehicle_count ≠ person_count) but suggests the person proxy prior would likely generalize if the feature were available.

**What to write in the paper**: "object_count_mean is the only cross-video-consistent deployable proxy (strongest on both videos for all-event and non-vehicle queries). Person-specific proxies (person_count_mean, AUROC 0.84 on dataset3) cannot be directly cross-validated due to missing per-class YOLO features on realcartest, but the non_vehicle_count proxy (AUROC 0.81 on realcartest) provides indirect directional evidence. Vehicle-specific proxy selection is cross-video inconsistent (direction reverses between dataset3 and realcartest due to different event mixes). A query-aware proxy prior is therefore only partially supported: object_count_mean as a robust default generalizes; query-specific proxies are video-dependent."

## Safe claims (updated)

1. L3 (object_count_mean + P=2.0 + greedy_maxmin_time) is the strongest deployable
   selection on dataset3 (event recall 0.519 at B=80).
2. object_count_mean is the strongest deployable proxy on BOTH dataset3 (0.627)
   and realcartest (0.738) for all_event.
3. Exact hypergeometric bound provides valid coverage (1.0 >= 0.95) under
   simulated replay. Temporal clustering does NOT invalidate random-sample
   estimation.
4. greedy_maxmin_time >= linspace_spread at all budgets.
5. The B=80 recall drop is a structural tradeoff (calibration displaces exploit
   anchors covering low-proxy singletons), not a bug.
6. Stratification with Bonferroni does NOT improve bound tightness (the
   correction is too conservative at L=12 strata).
7. non_vehicle_count proxy on realcartest (AUROC 0.81) is directionally
   consistent with person_count_mean on dataset3 (0.84) — indirect evidence
   for person proxy generalization.

## Unsafe claims (updated)

1. Strong certificate or formal theorem wording — only "recall lower bound
   estimate under simulated replay" is validated.
2. "Stratification improves the certificate" — it does NOT (Bonferroni is
   too conservative).
3. "Budget schedule solves the B=80 problem" — it does NOT meet the -0.05
   target (best is -0.097 at alpha=0.10).
4. "Person proxy generalizes cross-video" — NOT directly tested (feature
   missing on realcartest).
5. "Query-aware proxy prior is a universal rule" — vehicle branch is
   inconsistent, person branch is untestable, only object_count_mean is
   cross-video stable.
6. "Formal G-ARC certificate is complete" — Monte Carlo validation only,
   not a formal theorem.
7. "Geometric features generalize cross-video" — they don't (Stage 11/15),
   and they're not actually geometric (Stage 15: image-plane ROI, not
   camera projection).

## Next steps

1. **Less conservative joint correction**: replace Bonferroni with Simes
   correction or exact joint hypergeometric distribution. This could tighten
   the stratified bound significantly. Pure theory+experiment, no new compute.

2. **YOLO reprocessing on realcartest**: extract per-class counts (person=0,
   bicycle=1) to enable direct person proxy cross-validation. This is YOLO
   (not VLM) but requires compute authorization.

3. **Formal theorem**: state and prove the hypergeometric coverage result
   rigorously for the clip-level setting. The result is standard for SRSWOR
   but needs careful statement for temporal-correlated units.

4. **Adaptive alpha as a function of B and proxy AUC**: the current fixed
   alpha=0.15 is a compromise. An adaptive schedule that uses less overhead
   at mid-budgets (where the structural gap is worst) and more at high
   budgets (where the bound tightens) could improve the tradeoff curve.

5. **Second video with full features**: a second long video with per-class
   YOLO counts + VLM oracle labels would validate both the certificate and
   the proxy prior cross-video. This requires both YOLO and VLM compute.

## Sprint 4 outputs

- `reports/STAGE19_STAGE18_RELABEL_AUDIT.md`
- `reports/STAGE20_B80_ANOMALY_DIAGNOSIS.md`
- `reports/STAGE21_STRATIFIED_HYPERGEOMETRIC_BOUND.md`
- `reports/STAGE22_PERSON_CYCLIST_BACKFILL.md`
- `tables/stage20_b80_missed_clusters.csv`, `stage20_fine_grid_l3.csv`, `stage20_fine_grid_l4.csv`
- `tables/stage21_stratified_bound_results.csv`, `stage21_b80_missed_clusters_*.csv`
- `tables/stage22_person_cyclist_backfill.csv`
- `replay/stage20_fine_grid_l3_selections.csv`, `stage20_fine_grid_l4_selections.csv`
- `replay/stage21_mc_selection_traces.csv`
- `scripts/` (common.py + stage19-22 scripts)
"""
(C.REPORTS / "SPRINT4_SUMMARY.md").write_text(report, encoding="utf-8")
print("Sprint 4 summary written.")
print("\n=== 4 DECISION labels ===")
for stage, (dec, summary) in decisions.items():
    print(f"{stage}: {dec}")
