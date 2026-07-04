# Calibration / Tie-Break Diagnostic Report

Purpose: determine whether the CILS precision>=0.8 failure is caused by an overly conservative lower bound, calibration score inflation, within-bin utility bias, score separation failure, or reference sparsity — without running the full grid or implementing a new framework.

Run: `runs/craq_lite_v1/20260701T075242Z/patch_smoke/calibration_tiebreak_diagnostic/`
Lattice: 11939 candidates. Reference: 6 true interval events (recall target).
Selector: deterministic `cils_select` (seed-independent; seed/precision_target rows duplicated for schema parity).
Calibration variants: `current_wilson_z1`, `wilson_z0_5`, `raw_bin_rate`, `coarse_2key_wilson_z1`, `coarse_2key_raw_rate`.

---

## 1. Calibration variant score distribution

From `calibration_variant_summary.csv` (budget=80; budget=160 shown for comparison):

| variant | budget | max p_answer | n >=0.8 | n_TP >=0.8 | n_FP >=0.8 | any TP >=0.8 | any FP >=0.8 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| current_wilson_z1 | 80 | 0.667 | 0 | 0 | 0 | NO | NO |
| wilson_z0_5 | 80 | 0.889 | 169 | 26 | 143 | YES | YES |
| raw_bin_rate | 80 | 1.000 | 169 | 26 | 143 | YES | YES |
| coarse_2key_wilson_z1 | 80 | 0.094 | 0 | 0 | 0 | NO | NO |
| coarse_2key_raw_rate | 80 | 0.143 | 0 | 0 | 0 | NO | NO |
| current_wilson_z1 | 160 | 0.386 | 0 | 0 | 0 | NO | NO |
| wilson_z0_5 | 160 | 0.522 | 0 | 0 | 0 | NO | NO |
| raw_bin_rate | 160 | 0.667 | 0 | 0 | 0 | NO | NO |
| coarse_2key_wilson_z1 | 160 | 0.062 | 0 | 0 | 0 | NO | NO |
| coarse_2key_raw_rate | 160 | 0.092 | 0 | 0 | 0 | NO | NO |

Key observations:
- Only `wilson_z0_5` and `raw_bin_rate` push any candidate above 0.8 at budget=80.
- When they do, they push **both** TPs and FPs above 0.8: 26 TPs and 143 FPs cross the threshold. The TP/FP ratio among >=0.8 candidates is 26/169 = 0.154 — essentially the same as the bin base rate (16/87 = 0.184 in the top bin). The threshold does not separate TPs from FPs.
- At budget=160 no variant reaches 0.8 (pilot positive rate drops to 8.1%, dilution dominates).
- The coarse 2-key variants make things **worse**, not better: collapsing `method` and `boundary_quality_bin` merges the small high-positive bins into large low-rate bins, pulling the max down to 0.09-0.14. This falsifies the "coarser bins help" hypothesis.

---

## 2. Within-bin tie-break audit

From `tiebreak_bin_audit.csv`. Focus on `current_wilson_z1`, budget=80, k=20 (the actual patch_smoke selected count at tau=0.5):

| metric | value |
| --- | --- |
| top bin p_answer | 0.667 |
| n in bin | 87 |
| n TP in bin (answer_iou_0_3=True) | 16 |
| n IoU@0.5 in bin | 10 |
| bin precision (all 87) | 0.184 |
| precision of top-20 by utility | 0.20 |
| precision of bottom-20 by utility | 0.30 |
| precision of random-20 (mean over 100 seeds) | 0.188 (95% interval 0.000-0.326) |
| TP rank positions under utility (1-indexed) | [1, 8, 13, 14, 24, 25, 32, 43, 66, 67, 72, 74, 75, 81, 83, 84] |
| n TP within top-20 by utility | 4 |
| utility median TP | 4.85 |
| utility median FP | 5.60 |
| active_score median TP | 0.677 |
| active_score median FP | 0.698 |
| boundary_quality median TP | 0.735 |
| boundary_quality median FP | 0.828 |
| duration median TP | 12.0 |
| duration median FP | 12.0 |

Same pattern at k=25: top-25 precision=0.24, bottom-25 precision=0.32, random=0.180.

For `raw_bin_rate` the top bin grows to 169 candidates (26 TP, 143 FP, bin precision 0.154): top-20 by utility precision=0.20, bottom-20=0.10, random=0.146. Here top-by-utility slightly beats random, but it is still far below 0.8.

For `coarse_2key_*` the "top bin" is huge (816 candidates, 94 TP, bin precision 0.115): top-20 by utility precision=0.50, random=0.113. Here utility does concentrate TPs at the top — but the selector cannot use this bin because its p_answer (0.094) is below every tau.

---

## 3. Selector rerun with calibration variants

From `selector_variant_summary.csv`. Best non-empty rows per variant (budget=80):

| variant | tau | returned | obs precision | recall@0.3 | TP | FP |
| --- | --- | --- | --- | --- | --- | --- |
| current_wilson_z1 | 0.5 | 20 | 0.20 | 0.50 | 4 | 16 |
| current_wilson_z1 | 0.6 | 25 | 0.16 | 0.50 | 4 | 21 |
| wilson_z0_5 | 0.5 | 20 | 0.25 | 0.50 | 5 | 15 |
| wilson_z0_5 | 0.7 | 21 | 0.19 | 0.50 | 4 | 17 |
| wilson_z0_5 | 0.8 | 24 | 0.21 | 0.50 | 5 | 19 |
| raw_bin_rate | 0.5 | 15 | 0.27 | 0.50 | 4 | 11 |
| raw_bin_rate | 0.6 | 18 | 0.33 | 0.67 | 6 | 12 |
| raw_bin_rate | 0.7 | 20 | 0.35 | 0.67 | 7 | 13 |
| raw_bin_rate | 0.8 | 25 | 0.28 | 0.67 | 7 | 18 |
| coarse_2key_* | any | 0 | NaN | 0 | 0 | 0 |

Budget=160: only `current_wilson_z1` empty, `wilson_z0_5` returns 28 at tau=0.5 (precision 0.143, recall 0.5), `raw_bin_rate` returns 15-27 (precision 0.148-0.267). All coarse_2key empty.

Aggregate:
- Best observed precision with nonzero recall: **0.35** (`raw_bin_rate`, b=80, tau=0.7).
- Best recall@IoU0.3 at observed precision >=0.8: **0.0** (no row reaches).
- Best recall@IoU0.3 at observed precision >=0.9: **0.0** (no row reaches).

**Calibration score inflation confirmed**: `raw_bin_rate` raises max p_answer to 1.0 and lets tau=0.7/0.8 fire (returning 20-25 intervals), but observed precision is only 0.28-0.35 — far below 0.8. The high p_answer is an artifact of small-n raw rates (a bin with sum=1,count=1 gets rate=1.0), not a real TP signal. The 143 FPs that cross 0.8 dwarf the 26 TPs.

---

## 4. Answers to required questions

1. **Does relaxing Wilson z or using raw bin rate push any TP candidate above p_answer >= 0.8?**
   YES — `wilson_z0_5` and `raw_bin_rate` at budget=80 push 26 TP candidates above 0.8.

2. **Does it also push many FP candidates above p_answer >= 0.8?**
   YES — 143 FP candidates also cross 0.8, vs 26 TPs. The threshold does not separate TP from FP; it inflates both equally.

3. **Does any calibration variant achieve observed precision >= 0.8 with nonzero recall?**
   NO. Best observed precision with nonzero recall is 0.35 (`raw_bin_rate`, b=80, tau=0.7), still <0.8.

4. **Does any calibration variant achieve observed precision >= 0.9 with nonzero recall?**
   NO. No row reaches 0.9.

5. **Is current utility positively or negatively correlated with answer_iou_0_3 inside the top p_answer bin?**
   **NEGATIVELY**. In the top bin (current_wilson_z1, b=80): top-20 by utility precision = 0.20, bottom-20 by utility precision = 0.30. Utility median is higher for FPs (5.60) than for TPs (4.85). The component driving this is `boundary_quality` (median TP=0.735 vs FP=0.828) and to a lesser extent `active_score` (TP=0.677 vs FP=0.698). FPs have sharper boundary drops and slightly higher active scores than TPs.

6. **Are TPs ranked below FPs inside the same calibrated bin?**
   YES. Of 16 TPs in the top bin, only 4 fall within the top-20 by utility (ranks [1, 8, 13, 14]); the other 12 sit at ranks 24-84. The median TP rank is ~50, well below the cutoff.

7. **Would random tie-breaking inside the top bin have better precision than current utility tie-breaking?**
   NO, random is roughly equal (0.188 vs 0.20). But **bottom-by-utility** would do better (0.30), which means the current utility signal is anti-informative for TP/FP separation within this bin — it actively picks FPs over TPs.

8. **Is the main failure:**
   - conservative lower bound only: NO — relaxing it (wilson_z0_5, raw_bin_rate) does not fix precision.
   - calibration score inflation: YES, present — raw_bin_rate inflates both TP and FP scores without separation.
   - within-bin utility bias: YES, present — utility ranks FPs above TPs (boundary_quality and active_score both favor FPs).
   - score separation failure: YES, primary — no available signal (p_answer, active_score, boundary_quality, duration) separates the 16 TPs from the 71 FPs in the top bin. The bin base rate is 0.184, and no tie-break improves on it meaningfully.
   - reference sparsity: secondary — 6 interval events limit statistical validity but are not the cause of precision<0.8; the cause is the score ceiling and within-bin FP majority.

**Primary diagnosis: score separation failure with within-bin utility bias.** The calibration lower bound is conservative, but relaxing it only inflates FP scores alongside TP scores. The real problem is that TPs and FPs share the same calibration bin (same `answer_quality_proxy_bin` x `duration_bin` x `method` x `boundary_quality_bin` cell) and within that bin the utility components (`boundary_quality`, `active_score`) are slightly higher for FPs than for TPs, so the selector preferentially picks FPs. This is not a calibration problem; it is a feature discrimination problem.

---

## 5. Recommended next action

**Minimal next experiment: within-bin tie-break ablation on the existing top bin.**

In a new independent output directory, keep `current_wilson_z1` calibration fixed, but modify only the `utility` formula inside `cils_select` to test three ablations against the current `p_answer * value * boundary_quality`:
- (a) drop `boundary_quality` (use `p_answer * value` only),
- (b) invert `boundary_quality` (use `p_answer * value * (1 - boundary_quality)`),
- (c) replace `boundary_quality` with `1 / (1 + signal_disagreement)`.

Run only budget=80, taus {0.5, 0.6}, the same 6-event reference, single seed (selector is deterministic). Hypothesis: if (b) raises top-20 precision above 0.30 (the bottom-k baseline), then `boundary_quality` is actively anti-informative and should be dropped or inverted; if none of (a)/(b)/(c) raises precision above ~0.35, the failure is definitively score-separation and the next step is a new feature (e.g., IoU-resolution or event-geometry signal), not further calibration/tie-break tuning.

Do not change metric definitions, do not expand the grid, do not add new calibration variants.

---

## Reproducibility

Commands:
```
python runs/craq_lite_v1/20260701T075242Z/patch_smoke/calibration_tiebreak_diagnostic/run_diagnostic.py
```

Inputs:
- `src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/interval_lattice_features_only.csv`
- `src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/interval_lattice_v2_clean.csv`
- `src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/interval_labels_v2_clean.csv`
- `runs/craq_lite_v1/20260701T075242Z/patch_smoke/reference_audit.csv`

Outputs:
- `calibration_variant_summary.csv`
- `tiebreak_bin_audit.csv`
- `selector_variant_metrics.csv` (full per-seed/precision_target rows)
- `selector_variant_summary.csv` (per variant/budget/tau)
- `config_used.json`
- `_report_data.json` (machine-readable report inputs)
- `REPORT.md` (this file)
