# Sprint 3 Summary: Certificate Redesign + Query-Prior Cross-Video Completion

## Four DECISION labels

| Stage | DECISION | Summary |
|---|---|---|
| Stage 15 | `CORRIDOR_CALIBRATION_CONFOUND_RULED_OUT` | No camera calibration exists — corridor is image-plane ROI, not geometric projection. Stage 11 reversal is genuine, not a confound. |
| Stage 16 | `PERSON_CYCLIST_PRIOR_PARTIALLY_CONSISTENT_OBJECT_COUNT_STABLE` | object_count_mean is cross-video consistent for non_vehicle. person_count_mean specifically CANNOT be tested (missing in realcartest). |
| Stage 17 | `EXACT_HYPERGEOMETRIC_BOUND_VALIDATED` | Exact hypergeometric upper bound gives valid coverage (1.0 >= nominal 0.95) under SRSWOR and stratified sampling. i.i.d. violation does NOT affect random-sample estimation validity. |
| Stage 18 | `BUDGET_SCHEDULE_FOUND` | alpha=0.15 with stratified hypergeom bound: coverage=1.0, mean recall drop -0.036 vs L3, worst drop -0.128 at B=80 (improved from -0.161). R_lower is valid but very conservative (0.02-0.08 vs true recall 0.19-0.50). |

## What can be safely written in the paper (mainline)

### 1. L3 remains the strongest deployable selection (no certificate)
`object_count_mean + P=2.0 + greedy_maxmin_time`: event recall 0.519 at B=80.
Cross-video: object_count_mean is the strongest deployable proxy on BOTH
dataset3 (AUROC 0.627) and realcartest (AUROC 0.738).

### 2. Exact hypergeometric bound is valid (certificate mechanism)
The recall lower bound `R_lower = H / U_{1-delta}(K)` using the exact
hypergeometric one-sided upper bound on total positives K achieves coverage
= 1.0 >= nominal 0.95 under Monte Carlo simulation (500 reps, delta=0.05/0.10).

**Key theoretical insight for the paper**: temporal clustering (P(1→1)=2.83x)
does NOT invalidate random-sample-based population estimation. The hypergeometric
distribution is exact for SRSWOR regardless of how positives are distributed.
The "i.i.d. violation" objection to certificates conflates exploitation efficiency
(clustering hurts) with estimation validity (clustering is irrelevant for random
samples). This distinction should be a core contribution of the paper.

### 3. Budget schedule: alpha=0.15 is the best tradeoff
With alpha=0.15 (15% cal + ~8% audit = 23% overhead), the L4 vs L3 recall gap
narrows to mean -0.036 (worst -0.128 at B=80). Coverage remains 1.0. The
certificate is valid at all budgets.

### 4. greedy_maxmin_time >= linspace_spread (confirmed from Sprint 1)
Consistent across all budgets. No further validation needed.

## What CANNOT be written in the paper (yet)

### 1. "The certificate is practically useful"
R_lower is valid but VERY conservative: 0.02-0.08 vs true recall 0.19-0.50.
The bound is rarely non-vacuous at B<100. This is a fundamental limitation
of estimating 40 positives from a small random sample — not a bug. The paper
should present this as an honest tradeoff, not as "we solved certification."

### 2. "Query-aware proxy prior is a universal rule"
- Vehicle proxy prior: cross-video INCONSISTENT (Stage 11, confirmed Stage 15
  as genuine, not a calibration confound). The feature ranking reverses because
  the event mix differs (pedestrian-dominated vs vehicle-dominated).
- Person proxy prior: CANNOT be tested cross-video (person_count features
  missing in realcartest). The dataset3 finding (AUROC 0.81) is dataset3-only.
- object_count_mean: cross-video consistent but mediocre (AUROC 0.63-0.74).
  It is the safest single default, but NOT a "query-aware" rule — it's just
  the most robust single proxy.

### 3. "Geometric features generalize cross-video"
score_fusion_geometry_motion = z(bbox_area) + z(motion). It's not a geometric
projection — it's a size+motion heuristic. The "ego-path corridor" naming is
a misnomer; the paper should use accurate naming (e.g., "center-region object
density" for center_roi, "size-motion fusion" for score_fusion).

### 4. "Formal G-ARC recall guarantee"
The bound is validated by Monte Carlo on known ground truth, NOT by a formal
theorem. Use "recall lower bound estimate under simulated replay" in the paper.
A formal theorem would require proving the hypergeometric coverage under
arbitrary population structures (which is standard for SRSWOR but needs to
be stated rigorously for the clip-level setting).

## Certificate mechanism: current status

**Status**: `EXACT_HYPERGEOMETRIC_BOUND_VALIDATED`

The exact hypergeometric bound works (coverage 1.0) but is very conservative.
The paper should present this as:
1. A valid but conservative recall lower bound under simulated replay
2. The key insight that temporal clustering does NOT block certificate validity
3. The tradeoff: more estimation budget → tighter bound but less recall
4. The honest limitation: at small budgets (B<100), the bound is often vacuous

The "why naive HT+normal-approx fails and what fixes it" story is itself a
legitimate systems-design contribution: the HT estimator is high-variance on
small samples, the normal approximation is invalid with few positive observations,
and the exact hypergeometric bound is the correct finite-population solution.

## Query-aware proxy prior: final boundary

**Status**: `PARTIALLY VALID, NOT UNIVERSAL`

- object_count_mean: cross-video consistent (strongest deployable on both videos)
- person_count_mean: strong on dataset3 (0.81) but CANNOT be cross-validated
- vehicle query: cross-video INCONSISTENT (direction reverses)
- The "query-aware" mechanism is NOT a universal rule. It is:
  - Valid for object_count_mean as a robust default
  - Potentially valid for person proxy (untested cross-video)
  - Invalid for vehicle-specific proxy selection

The paper should present object_count_mean as the robust deployable default,
acknowledge that query-specific proxies (person, vehicle) are video-dependent,
and frame the query-aware idea as a "direction for future work with per-video
feature engineering" rather than a validated contribution.

## Next steps

1. **Formal theorem for hypergeometric bound** (theory): state and prove that
   the exact hypergeometric upper bound provides valid coverage for the recall
   lower bound under SRSWOR, regardless of population structure. This is
   straightforward (it's a standard finite-population result) but needs to be
   stated rigorously for the clip-level setting.

2. **Tighten the bound** (theory+experiment): the current bound is very
   conservative. Options:
   a. Use the Fisher exact test instead of Clopper-Pearson (less conservative)
   b. Use a Bayesian approach with a prior on K
   c. Use the Hájek estimator with a ratio estimator (lower variance than HT)
   d. Increase positive rate via stratification (stratify by proxy score bins)

3. **Realcartest person-count features** (engineering): re-run YOLO with
   person/bike class extraction on realcartest to enable the person proxy
   cross-video validation. This is YOLO reprocessing, not VLM.

4. **Second video for certificate cross-validation** (needs new VLM or at
   least new oracle labels): the certificate Monte Carlo is on dataset3 only.
   A second video with different positive rate / clustering would test
   whether the bound remains valid and how tight it is.

5. **L4 with alpha=0.15 as the paper's deployable method**: it provides both
   recall (close to L3) AND a valid (if conservative) recall lower bound.
   This is the first method in the project that does both.

## Sprint 3 outputs

- `reports/STAGE15_CORRIDOR_CALIBRATION_AUDIT.md`
- `reports/STAGE16_PERSON_CYCLIST_PRIOR_CROSS_VIDEO_CHECK.md`
- `reports/STAGE17_EXACT_BOUND_REDESIGN.md`
- `reports/STAGE18_BUDGET_SCHEDULE_REDESIGN.md`
- `tables/stage16_person_cyclist_cross_video.csv`
- `tables/stage17_exact_bound_coverage.csv`
- `tables/stage18_budget_schedule.csv`
- `scripts/` (common.py + stage15-18 scripts)
