# CRAQ-lite / CILS Score & Calibration Anatomy

Purpose: explain why `cils_craq_lite` cannot achieve nonzero recall at observed precision >= 0.8 in the patch_smoke run, using only the existing patch_smoke outputs plus reconstruction of `p_answer` from the clean v2 lattice.

Run analyzed: `runs/craq_lite_v1/20260701T075242Z/patch_smoke/`
Reference: 6 true interval events (`is_interval_event == 1`), 14 point anchors ignored for recall.
Lattice: `interval_lattice_v2_clean.csv`, 11939 candidates, single `overlap_group_id = og2_00000`.
Selector: `cils_select` with `calibrate_cils` (Wilson lower, z=1.0) over 4 strata keys (`answer_quality_proxy_bin`, `duration_bin`, `method`, `boundary_quality_bin`), pilot = top-`B` by `answer_quality_proxy`.
Precision label: `ANSWER = "answer_iou_0_3"` (any-overlap IoU>=0.3 with any of the 20 reference events).

---

## 1. CILS by tau and budget

Reconstructed from `predictions_cils_craq_lite.csv` (1800 rows) and `metrics_by_method_seed.csv` (cils rows = 480). Budget=160 produced **zero** predictions for every tau, so all 1800 rows come from budget=80, tau in {0.5, 0.6}.

| budget | cils_tau | per-seed pred count | empty-return rate | observed precision (mean) | recall@IoU0.3 (mean) | recall@IoU0.5 (mean) |
| --- | --- | --- | --- | --- | --- | --- |
| 80 | 0.5 | 40.0 | 0.5 | 0.20 | 0.25 | 0.333 |
| 80 | 0.6 | 50.0 | 0.5 | 0.16 | 0.25 | 0.333 |
| 80 | 0.7 | 0.0 | 1.0 | NaN | 0.0 | 0.0 |
| 160 | 0.5 | 0.0 | 1.0 | NaN | 0.0 | 0.0 |
| 160 | 0.6 | 0.0 | 1.0 | NaN | 0.0 | 0.0 |
| 160 | 0.7 | 0.0 | 1.0 | NaN | 0.0 | 0.0 |

Notes:
- Candidate count before selection: 11939 (full lattice).
- Distinct interval_ids ever selected: 28 (all from budget=80, tau in {0.5,0.6}).
- Observed precision is computed as `answer_iou_0_3.mean()` over returned intervals; max observed is 0.20.
- "Empty-return rate 0.5" at tau=0.5/0.6 reflects the per-seed metric rows where `returned_interval_count == 0` (the selector returned nothing for half the seeds); the other half return a fixed deterministic set because `cils_select` is seed-independent (the only seed dependence is the audit trace of `audited_proposal_repair`).

---

## 2. Selected CILS intervals: label cross-tabs

Across the 28 distinct selected intervals (budget=80, tau in {0.5, 0.6}):

| | `answer_iou_0_3 = True` | `answer_iou_0_3 = False` | total |
| --- | --- | --- | --- |
| distinct selected | 4 | 24 | 28 |

| | `answer_iou_0_5 = True` | `answer_iou_0_5 = False` | total |
| --- | --- | --- | --- |
| distinct selected | 2 | 26 | 28 |

Cross-tab `answer_iou_0_3` vs `matches_interval_event` (matched_event_id is one of the 6 interval events):

| | matches interval event = True | matches interval event = False | total |
| --- | --- | --- | --- |
| `answer_iou_0_3 = True` | 4 | 0 | 4 |
| `answer_iou_0_3 = False` | 5 | 19 | 24 |

Cross-tab `answer_iou_0_5` vs `matches_interval_event`:

| | matches interval event = True | matches interval event = False | total |
| --- | --- | --- | --- |
| `answer_iou_0_5 = True` | 2 | 0 | 2 |
| `answer_iou_0_5 = False` | 7 | 19 | 26 |

Key facts:
- **No selected interval has `answer_iou_0_3 = True` without also matching an interval event.** The precision label and the recall-event family are aligned at the candidate level for this run (no point-anchor false positives sneak in via the precision label).
- 5 selected intervals match an interval event but fall below IoU 0.3 (near misses, see Section 3).
- 19 of 24 false positives match **no** reference event at all (true background).

---

## 3. Selected false positives

### 3a. Top recurring false-positive intervals (by selection frequency)

All 24 distinct false positives are selected in every seed where CILS returns anything, so recurrence = 40 (tau=0.5, 20 seeds × 2 precision_targets) or 60 (tau=0.6). The most diagnostic split is by region:

| FP cluster | t_start range | n distinct | matched_event_id | IoU to its matched interval event | character |
| --- | --- | --- | --- | --- | --- |
| 0026 region | 250-288 | 2 | 0026 (point anchor) | n/a | point-anchor region |
| 0031 region | 554-566 | 1 | 0031 (point anchor) | n/a | point-anchor region |
| 0033 region | 680-720 | 1 | 0033 | 0.268 | near miss (just below 0.3) |
| 0034 region | 768-784 | 1 | 0034 | 0.113 | wide boundary, low IoU |
| 0036/0037 region | 806-900 | 5 | 0036, 0037 | 0.011-0.124 | wide/boundary intervals around the long 0037 event |
| 0040 region | 1024-1072 | 2 | 0040 (point anchor) | n/a | point-anchor region |
| pure background | 354, 468, 544, 618-674, 796-936, 984-1042 | 12 | NaN | n/a | no event nearby |

### 3b. Scores / p_answer of false positives

All 24 false positives carry `p_answer = 0.6667` (the maximum reachable at budget=80). They are indistinguishable from the 4 true positives by `p_answer` — all sit in the same calibration bin (`answer_quality_proxy_bin=q5`, `duration_bin=10-20`, `method=signal_peak_multiscale`/`dense_multiscale_windows`, `boundary_quality_bin=q5`) whose Wilson lower with (sum=2, count=2) or (sum=1, count=1) collapses to 0.667.

### 3c. Region / video

All candidates come from the single video `realcartest.mp4` (t in [0, 1200]s). The false positives cluster around three time regions where the cheap proxy fires strongly:
- 250-566s (around point anchors 0026, 0031 and interval event 0029),
- 618-720s (between interval events 0033 and 0034),
- 796-1072s (around the long interval event 0037 and point anchors 0036, 0040).

### 3d. Near misses vs completely wrong

Of 24 false positives:
- 5 are near misses (match an interval event, IoU 0.011-0.268, below 0.3) — wrong boundary, right region.
- 7 match a point anchor region (no recall credit, but the proxy correctly fired on a real anchor region that was promoted from a sub-2s event).
- 12 are pure background with no nearby event.

So ~12 of 24 false positives are completely wrong, ~5 are boundary errors on real events, ~7 are correct-region-but-wrong-granularity.

---

## 4. Missed true events

For each of the 6 true interval events (candidate coverage and CILS fate, reconstructed against the budget=80 calibration):

| event | t range | n candidates | best candidate IoU | n candidates IoU>=0.3 | top p_answer among its candidates | appears in CILS selected? | appears as TP (IoU>=0.3)? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0022 | 30-51 | 280 | 0.966 | 136 | 0.667 | NO | NO |
| 0028 | 380-401 | 246 | 0.966 | 107 | 0.667 | NO | NO |
| 0029 | 490-501 | 281 | 0.892 | 174 | 0.667 | YES | YES |
| 0033 | 700-711 | 379 | 0.935 | 181 | 0.667 | YES (near-miss only) | NO |
| 0034 | 760-771 | 368 | 0.935 | 208 | 0.667 | YES | YES |
| 0037 | 830-881 | 1089 | 0.789 | 371 | 0.667 | YES | YES |

Findings:
- **Every true interval event is present in the lattice** with high-quality candidates (best IoU 0.79-0.97, 107-371 candidates at IoU>=0.3).
- 0022 and 0028 are **completely missed by CILS**: their candidates exist, have `p_answer = 0.667` (same as everyone else), but CILS's NMS/duration cap and the greedy utility order pick other intervals first in the 250-566s and 380-566s regions. They are not rejected by the tau gate; they are outranked by false positives with identical `p_answer` and slightly higher `utility` (driven by `active_score` and `boundary_quality`).
- 0033 is selected but only via a wide 40s interval (IoU 0.268 < 0.3), so it counts as a false positive for precision and gives no recall credit at IoU=0.3.
- The audited_proposal_repair baseline recovers all 6 because it audits candidate-external 2s windows and repairs near each event (recall 1.0 ignoring precision).

---

## 5. Calibration analysis

### 5a. p_answer distribution (reconstructed via `calibrate_cils`)

| budget | min | median | mean | q0.9 | q0.95 | q0.99 | q0.999 | max | >=0.5 | >=0.6 | >=0.7 | >=0.8 | >=0.9 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 80 | 0.000 | 0.067 | 0.073 | 0.067 | 0.067 | 0.500 | 0.667 | 0.667 | 169 | 87 | 0 | 0 | 0 |
| 160 | 0.000 | 0.043 | 0.045 | 0.043 | 0.043 | 0.276 | 0.386 | 0.386 | 0 | 0 | 0 | 0 | 0 |

### 5b. Why no candidate reaches 0.8

The calibration pilot is top-`B` by `answer_quality_proxy`. At budget=80 the sample has 10/80 = 12.5% positives; at budget=160 it has 13/160 = 8.1% positives. The 4-key stratification (`answer_quality_proxy_bin`, `duration_bin`, `method`, `boundary_quality_bin`) fragments these positives across 18 (b=80) / 23 (b=160) bins, most of which have count 1-8. Wilson lower with z=1.0 on a bin with (sum=2, count=2) is 0.5, on (sum=1, count=1) is ~0.5, and the observed maximum 0.667 comes from a single-bin fluke where the raw rate is 1.0 with very small n (the `(centre-adj)/denom` math with z=1.0 yields ~0.667 for n=1, p=1). The fallback for the majority of candidates is `global_p * 0.5` ~ 0.067, which is why the median is 0.067.

**No candidate reaches 0.8 because the calibration sample positive rate is ~0.08-0.13 and the binning is too fine for Wilson(z=1) to ever push a lower bound above 0.5, let alone 0.8.** The maximum achievable `p_answer` at this reference is 0.667 (budget=80) and 0.386 (budget=160).

### 5c. Why tau=0.7 empties everything

At budget=80, max `p_answer` = 0.667 < 0.7, so the running-precision gate `safe_div(ntp, ntotal) + 1e-12 < tau` rejects the first candidate and the selector returns nothing. This is **fully explained** by the score distribution — no calibration or selection bug is needed to explain it.

### 5d. Why budget=160 empties even at tau=0.5

At budget=160 the pilot positive rate drops (8.1% vs 12.5%) and the 4-key bins get larger but lower-rate, so the best Wilson lower collapses to 0.386 < 0.5. The selector returns 0 for every tau at budget=160. This is a direct consequence of "more samples -> more dilution -> lower lower-bound" under a fixed positive rate of ~0.08. It is a **calibration design pathology**, not a selector bug.

---

## 6. Label alignment

| question | answer |
| --- | --- |
| Is CILS optimizing the same label used for final precision? | YES. `ANSWER = "answer_iou_0_3"` is used both for `p_answer` calibration (the `y` column in `calibrate_cils`) and for observed precision (`sel[ANSWER].mean()`). |
| Is `answer=True` aligned with IoU@0.3 event hit? | PARTIALLY. `answer_iou_0_3` is "any candidate with IoU>=0.3 vs any of the 20 reference events" (including 14 point anchors). Recall uses only the 6 `is_interval_event==1` events. |
| Quantify the mismatch | Of 1192 `answer_iou_0_3=True` candidates, 1177 match one of the 6 interval events and 15 match only point anchors. So ~1.3% of precision-True candidates are recall-irrelevant. Among the 28 selected intervals, 0 of 4 TPs are point-anchor matches. **The mismatch is small for this run and is NOT the bottleneck.** |

The bigger label issue is the **5 near-miss selected intervals** that match an interval event with IoU 0.011-0.268: they are `answer_iou_0_3=False` (so they hurt precision) AND they do not yield recall@0.3 (so they do not help recall). They are the worst of both worlds, but they are a boundary-quality problem, not a label-definition problem.

---

## 7. Diagnosis

**Primary bottleneck: overly conservative lower bound (calibration collapse), with a secondary score-separation failure.**

Evidence chain:
1. **No candidate reaches `p_answer >= 0.8`** at any budget (max 0.667 at b=80, 0.386 at b=160). This alone makes the precision-target=0.8 filter unreachable by construction, independent of the selector.
2. The cause is calibration, not the candidate set: the lattice contains 107-371 IoU>=0.3 candidates per true event (best IoU 0.79-0.97), so coverage is not the problem.
3. The 4-key Wilson(z=1.0) lower bound on a pilot with positive rate ~0.08-0.13 cannot exceed ~0.5-0.67 with the current bin granularity. Increasing the budget makes it worse (dilution), not better.
4. The selector itself is not the bottleneck at tau<=0.6: it does return 20-25 intervals at tau=0.5/0.6, and 4 of them are true positives. The problem is that **observed precision of the returned set is 0.16-0.20**, far below 0.8, because the selector cannot distinguish the 4 TPs from the 24 FPs that share `p_answer = 0.667`.
5. The secondary score-separation failure: among the 28 selected, `p_answer` is constant (0.667) for all, and `utility` is driven by `active_score` and `boundary_quality`, which rank several FPs above TPs. This is why 0022 and 0028 are missed entirely — their candidates lose the utility tiebreak to FPs in adjacent regions.
6. Label mismatch (Section 6) is small (~1.3%) and is NOT the bottleneck.
7. Reference sparsity (6 interval events) limits statistical validity but is NOT the cause of zero precision>=0.8 recall — the cause is the score ceiling.

Rejected alternative diagnoses:
- "candidate overgeneration": no — coverage is high, the issue is calibration, not lattice size.
- "post-selection precision filtering": no — precision is computed on the returned set; the filter is just `precision >= 0.8`, which fails because the returned set's precision is 0.16-0.20.
- "NMS/group-id bug": no — that bug was patched (CILS now returns up to 25 intervals, 28 distinct across seeds).

---

## 8. Recommended next action

**Minimal next experiment: relax the calibration lower bound and re-run the same patch_smoke grid.**

Concretely, in a new independent output directory, replace the Wilson(z=1.0) lower bound in `calibrate_cils` with one of:
- (a) Wilson with z=0.5 (less conservative), or
- (b) raw bin positive rate (no lower-bound shrinkage), or
- (c) coarser stratification (drop `method` and `boundary_quality_bin` from the 4 keys, keeping only `answer_quality_proxy_bin` x `duration_bin`).

Keep everything else fixed (same lattice, same selector, same grid: budgets 80/160, taus 0.5/0.6/0.7, seeds 0..19, IoU 0.3/0.5). Hypothesis: at least one of (a)/(b)/(c) will push max `p_answer` above 0.8 for the true-positive bin, allowing tau=0.8-equivalent selection and a non-empty precision>=0.8 result. If none does, the bottleneck shifts definitively to score separation (TPs and FPs in the same bin), and the next step would be to add a TP/FP-separating feature into `answer_quality_proxy` — but that is a separate experiment, not this one.

Do not change metric definitions, do not expand the grid, do not add new methods.

---

## Reproducibility

All numbers in this report are reproducible from:
- `runs/craq_lite_v1/20260701T075242Z/patch_smoke/predictions_cils_craq_lite.csv`
- `runs/craq_lite_v1/20260701T075242Z/patch_smoke/metrics_by_method_seed.csv`
- `src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/interval_lattice_v2_clean.csv`
- `src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/interval_lattice_features_only.csv`
- `src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/interval_labels_v2_clean.csv`
- `runs/craq_lite_v1/20260701T075242Z/patch_smoke/reference_audit.csv`

via `prepare_candidates` + `calibrate_cils` in `src/garc_eval/experiments/craq_lite_v1/run_craq_lite.py` (lines 116-132, 296-316) and `cils_select` (lines 319-345).
