# Duration-Stratified Diagnosis Report — clean_interval_aqp_full_reference_v2_clean_no_leak

> Read-only diagnostic. No algorithm change, no model inference, no pipeline rerun.
> All numbers are computed from the existing v2-clean output CSVs (see *Inputs*).
> Conclusions tagged `[NEEDS_GPT_CODEX_REVIEW]` require GPT/Codex复核 before
> being treated as research findings.

## 0. Scope and inputs

Inputs (read-only, from the v2-clean output dir):
- `reference_events.csv` — 20 stitched reference events
- `interval_lattice_v2_clean.csv` — 11,939 proposal intervals with per-interval labels
- `interval_labels_v2_clean.csv` — same labels in standalone form
- `proposal_quality_v2_clean.csv`, `proposal_recall_curve_v2_clean.csv`
- `precision_recall_duration_duplicate_summary_v2_clean.csv`

Diagnostic definitions:
- **Point / anchor event**: `num_supporting_anchors == 1` OR `duration <= 1.0 s`.
- **Interval event**: multi-anchor AND `duration > 1.0 s`.
- IoU brittleness math: for a proposal of length `P` fully covering an event of
  length `E`, `IoU = E / P`; to reach `IoU >= 0.3` need `P <= E/0.3 = 3.333·E`.

## 1. Reference composition

| metric | value |
|---|---|
| total reference events | 20 |
| point / anchor events | 14 (70.0%) |
| true interval events  | 6 (30.0%) |

Per-event table:

| event_id | dur(s) | anchors | type |
|---|---|---|---|
| realcartest_event_0022 | 20.70 | 3 | INTERVAL |
| realcartest_event_0023 |  0.70 | 1 | POINT |
| realcartest_event_0024 |  0.70 | 1 | POINT |
| realcartest_event_0025 |  0.20 | 1 | POINT |
| realcartest_event_0026 |  0.70 | 1 | POINT |
| realcartest_event_0027 |  0.70 | 1 | POINT |
| realcartest_event_0028 | 20.70 | 3 | INTERVAL |
| realcartest_event_0029 | 10.70 | 2 | INTERVAL |
| realcartest_event_0030 |  0.70 | 1 | POINT |
| realcartest_event_0031 |  0.70 | 1 | POINT |
| realcartest_event_0032 |  0.70 | 1 | POINT |
| realcartest_event_0033 | 10.70 | 2 | INTERVAL |
| realcartest_event_0034 | 10.70 | 2 | INTERVAL |
| realcartest_event_0035 |  0.70 | 1 | POINT |
| realcartest_event_0036 |  0.70 | 1 | POINT |
| realcartest_event_0037 | 50.70 | 6 | INTERVAL |
| realcartest_event_0038 |  0.70 | 1 | POINT |
| realcartest_event_0039 |  0.70 | 1 | POINT |
| realcartest_event_0040 |  0.70 | 1 | POINT |
| realcartest_event_0041 |  0.70 | 1 | POINT |

**Answer to Q1**: YES — the reference is dominated by point/anchor events (70%).
All point events are exactly `0.7 s` (one VLM-defined center10 anchor framed as a
`[t, t+0.7]` window). The "event" mid-time equals the anchor time; the 0.7 s end
is simply the clip duration, not a measured event boundary. These are anchor points
dressed as intervals.

## 2. IoU brittleness on point events (mechanism, not algorithmic)

For a 0.7 s point event, even a **perfectly covering** 4 s proposal yields
`IoU = 0.7 / 4 = 0.175 < 0.3`. Only proposals of length `<= 2.33 s` can possibly
reach `IoU@0.3` against a 0.7 s event; for the 0.2 s event (0025) the limit is
`0.67 s`. The v2 lattice is dominated by windows of length 4 – 32 s, so most
propositions are structurally unable to score IoU@0.3 on point events.

| E (s) | P_max for IoU@0.3 (full cover) | compatible w/ lattice >=2 s? |
|---|---|---|
| 0.20 | 0.67 | NO |
| 0.70 | 2.33 | only shortest windows |
| 10.70 | 35.67 | YES for all |
| 20.70 | 69.00 | YES for all |
| 50.70 | 169.00 | YES for all |

## 3. Per-event pooled lattice upper bound (whole lattice, no budget)

For each event we report the best achievable IoU over **all** 11,939 lattice
intervals, and the center-hit / any-overlap flags pooled over all methods.

| event_id | type | dur | best_IoU | any_overlap | center_hit | IoU03 hit | IoU05 hit | best_method |
|---|---|---|---|---|---|---|---|---|
| _0028 | INTERVAL | 20.70 | 0.966 | T | T | T | T | fixed_window |
| _0022 | INTERVAL | 20.70 | 0.966 | T | T | T | T | fixed_window |
| _0033 | INTERVAL | 10.70 | 0.935 | T | T | T | T | fixed_window |
| _0034 | INTERVAL | 10.70 | 0.935 | T | T | T | T | fixed_window |
| _0029 | INTERVAL | 10.70 | 0.892 | T | T | T | T | dense_multiscale_windows |
| _0037 | INTERVAL | 50.70 | 0.789 | T | T | T | T | boundary_refined_expansion |
| _0031 | POINT |  0.70 | 0.350 | T | T | T | F | threshold_merge_v2 |
| _0035 | POINT |  0.70 | 0.350 | T | T | T | F | threshold_merge_v2 |
| _0039 | POINT |  0.70 | 0.350 | T | T | T | F | threshold_merge_v2 |
| _0040 | POINT |  0.70 | 0.350 | T | T | T | F | threshold_merge_v2 |
| _0041 | POINT |  0.70 | 0.350 | T | T | T | F | boundary_refined_expansion |
| _0030 | POINT |  0.70 | 0.175 | T | T | F | F | dense_multiscale_windows |
| _0032 | POINT |  0.70 | 0.175 | T | T | F | F | dense_multiscale_windows |
| _0036 | POINT |  0.70 | 0.175 | T | T | F | F | dense_multiscale_windows |
| _0038 | POINT |  0.70 | 0.175 | T | T | F | F | dense_multiscale_windows |
| _0023 | POINT |  0.70 | 0.175 | T | T | F | F | dense_multiscale_windows |
| _0024 | POINT |  0.70 | 0.175 | T | T | F | F | dense_multiscale_windows |
| _0026 | POINT |  0.70 | 0.175 | T | T | F | F | dense_multiscale_windows |
| _0027 | POINT |  0.70 | 0.175 | T | T | F | F | dense_multiscale_windows |
| _0025 | POINT |  0.20 | 0.100 | T | T | F | F | threshold_merge_v2 |

## 4. Stratified pooled upper bound recall

| flag | overall | INTERVAL (n=6) | POINT (n=14) |
|---|---|---|---|
| any_overlap  | 20/20 = 1.000 | 6/6 = 1.000 | 14/14 = 1.000 |
| center_hit   | 20/20 = 1.000 | 6/6 = 1.000 | 14/14 = 1.000 |
| hit_iou03    | 11/20 = 0.550 | **6/6 = 1.000** | 5/14 = 0.357 |
| hit_iou05    |  6/20 = 0.300 | **6/6 = 1.000** | 0/14 = 0.000 |

**Answer to Q2**: YES — every point event is a `center_hit` (the proposal center
falls inside the event span) and an `any_overlap` hit, yet fails IoU@0.3. The
12 of 14 point events that anchor at dense/fixed/peak proposals score 0.175 and
the metric can only pass for them through the `threshold_merge_v2` short-window
family, which reaches 0.35 exactly because 0.7/2 = 0.35.

**Answer to Q3**: YES — pooled lattice upper bound IoU@0.3 on the **six true
intervals is 6/6 = 1.000**, vs 0.55 overall. The whole 0.45 gap to a perfect
upper bound is entirely absorbed by point-event IoU brittleness. The same is true
at IoU@0.5 (6/6 = 1.000 on intervals vs 0.30 overall).

## 5. Per-method upper-bound recall (whole lattice, no budget), stratified

| method | any_all | ctr_all | i03_all | i03_INT (6) | i03_PT (14) |
|---|---|---|---|---|---|
| boundary_refined_expansion | 0.75 | 0.70 | 0.35 | **1.00** | 0.07 |
| dense_multiscale_windows | 1.00 | 1.00 | 0.30 | **1.00** | 0.00 |
| fixed_window | 1.00 | 1.00 | 0.30 | **1.00** | 0.00 |
| low_density_blindspot_proposals | 0.70 | 0.65 | 0.10 | 0.33 | 0.00 |
| signal_peak_multiscale | 1.00 | 1.00 | 0.30 | **1.00** | 0.00 |
| threshold_merge_v2 | 0.90 | 0.90 | 0.50 | **1.00** | 0.29 |

Every mainstream proposal method already achieves the **full** event-recall ceiling
on the 6 true intervals. Loss on point events is purely length-driven.

## 6. Calibration label sparsity by event type

`answer_iou_0_3 = True` is the CILS calibration target. Distribution of the 1,192
answer-positive lattice intervals across matched events:

| event type | # answer_iou_0_3=True intervals |
|---|---|
| INTERVAL (6 events) | **1,177** (98.7% of all answers) |
| POINT (14 events) | **15** (1.3%) |

Per-event: only `_0031`, `_0035`, `_0039`, `_0040`, `_0041` contribute a handful
of point-event answer-positives (mostly from threshold_merge_v2 short windows).
The remaining 9 point events have **zero** answer-positive lattice intervals.

Consequence: under-budgeted calibration cannot statistically distinguish a
window that hits a point event from a window that hits nothing — both have
near-zero `answer_iou_0_3` density. This is exactly the asymmetry the v2
calibration (brier / ECE on `answer`) was blind to. Expected precision collapses
to zero before the budget can build any positive mass, and CILS returns the
empty set at all `B` and `tau`.

## 7. Stratified interpretation of the v2 Negative

**Recall observed (clean v2, FINAL_REPORT):**
- `lattice_oracle_upper_bound` recall@B=80, IoU@0.3: **0.40** (= 8/20)
- `CILS_full` recall at all budgets: **0.0** (empty return rate = 1.0)
- per-method aggregated IoU@0.3 ceiling: 0.30 – 0.50

**Re-decomposition by event stratum:**

| quantity | overall (20) | INTERVAL (6) | POINT (14) |
|---|---|---|---|
| lattice pooled upper bound IoU@0.3 | 0.550 | 1.000 | 0.357 |
| lattice pooled upper bound IoU@0.5 | 0.300 | 1.000 | 0.000 |
| any_overlap / center_hit feasible | 1.000 / 1.000 | 1.000 / 1.000 | 1.000 / 1.000 |
| answer-positive intervals | 1,192 | 1,177 | 15 |
| budgeted oracle UB @ B=80 (from curve) | 0.40 | (not isolated) | (not isolated) |
| CILS recall (all budgets) | 0.00 | 0.00 | 0.00 |
| CILS number_returned | 0 | 0 | 0 |

**Answer to Q4 (decomposed):**
- The single 0.55 "lattice upper bound" headline is a **reference/evaluation
  mismatch** artifact: 70% of the reference are 0.7 s point events that the
  IoU@0.3 metric cannot reach against the lattice's natural window lengths
  (≥ 2 s). The mismatch is not algorithmic; on the interval subset the pooled
  upper bound is literally 1.000.
- The 0.40 ceiling of the budgeted oracle upper bound at B=80 is *partially*
  reference-mismatch (point events capped at ~5/14 structurally) and *partially*
  budget competition. Disentangling requires a budget-stratified oracle count
  on the interval subset alone — see *Open check* O1 `[NEEDS_GPT_CODEX_REVIEW]`.
- The CILS = 0 (empty return at all B, all tau) is a **selector / calibration
  failure**, *not* a proposal failure: at B=80 with `answer_iou_0_3` density of
  1,177 intervals on the interval subset, an oracle-with-budget selector has
  material to work with; CILS returns empty because expected precision never
  crosses tau, not because the lattice has no acceptable candidate. This is the
  failure mode the v2 FINAL_REPORT itself flags ("bottleneck:
  calibration/precision and answer-compatible interval ranking"). It is real and
  independent of the point-event issue.
- Therefore: the **clean v2 Negative is a mixed signal**. On the interval-only
  retrieval problem it is a calibration/selector story. On point events it is a
  metric/reference-mismatch story. The two should NOT be collapsed into a
  single "CILS direction failed" verdict.

## 8. Event-set recommendation

**KEEP as interval-evaluation set (IoU@0.3 / IoU@0.5 applicable)** — 6 events:

| event_id | dur(s) | anchors |
|---|---|---|
| realcartest_event_0022 | 20.70 | 3 |
| realcartest_event_0028 | 20.70 | 3 |
| realcartest_event_0029 | 10.70 | 2 |
| realcartest_event_0033 | 10.70 | 2 |
| realcartest_event_0034 | 10.70 | 2 |
| realcartest_event_0037 | 50.70 | 6 |

These are the multi-anchor stitched events with durations an interval-retrieval
metric can meaningfully score. Note all six already saturate the pooled
upper bound at IoU@0.3 = 1.0.

**RELABEL / EXCLUDE FROM IoU-EVAL, treat as anchor-point events** — 14 events:
all `_0023/_0024/_0025/_0026/_0027/_0030/_0031/_0032/_0035/_0036/_0038/_0039/_0040/_0041`.

Recommended handling options (any of these, or a combination):
- (a) Drop from the IoU@0.3 evaluation; these should count a hit at the cheaper
  `any_overlap` or `center_hit` granularity (already 1.000 each).
- (b) Re-evaluate against a point-event metric (point precision / point recall
  where a return is judged by containment of the anchor time inside the
  proposal, no duration overlap IoU).
- (c) Relabel the centroid-based point events back to anchor-time references
  and only stitch events when `num_supporting_anchors >= 2`. This is a
  reference-construction change and must be examined by V13.6/V13.8 source
  `[NEEDS_GPT_CODEX_REVIEW]`.

**ESTIMATE of bias corrected**: If only the 6 interval events are scored at
IoU@0.3, the v2-clean numbers would read approximately:

* Pooled lattice upper bound IoU@0.3: **1.000** (was 0.55).
* Per-method ceiling IoU@0.3: **1.000** for 5 of 6 mainstream proposers (was 0.30 – 0.50).
* CILS = 0 unchanged (this is a selector/calibration issue, not a metric issue), but now interpretable as "CILS does not select any of the 1,177 candidate answer-positive intervals even at B=80" — a calibration-floor problem, not a proposal problem.

## 9. Open checks that need GPT/Codex复核

- `[NEEDS_GPT_CODEX_REVIEW]` **O1**: Recompute the *budgeted* `lattice_oracle_upper_bound`
  curve restricted to the 6 interval events, for B in {5,10,20,40,80}. Diagnostic-only
  `agent_loop` task: this clarifies how much of the 0.40 overall UB at B=80 is budget
  competition vs point-event mismatch.
- `[NEEDS_GPT_CODEX_REVIEW]` **O2**: Decide the canonical event-stitching rule.
  Specifically whether single-anchor "events" should exist at all for an
  interval-retrieval metric, or whether they should be reported as anchor hits.
  This is a reference-construction policy decision and must be made by the
  research owner, not the diagnostic agent.
- `[NEEDS_GPT_CODEX_REVIEW]` **O3**: Whether the CILS empty return at B=80 is
  recoverable with a calibration prior that does not require dense answer positives,
  or whether it implies a fundamental selector flaw — to be answered by an
  AQP-side agent, not here. The diagnostic only states that the empty-return mode
  is structurally separable from the point-event IoU brittleness.

## 10. Boundary statement

- This report is a diagnostic, not a research verdict.
- No algorithm, proposal method, calibration, or model was modified or rerun.
- The clean v2 Negative must NOT be re-stated as "CILS direction failed"; on the
  interval-only subset the Negative is a calibration/selector story and on the
  point-event subset it is a reference/metric-mismatch story. The two must be
  reported separately.
- The single-anchor center10 "events" must NOT be treated as legitimate
  variable-length interval ground truth without the reference-construction review
  flagged in O2.

## 11. Reproduction

The numbers in this report are reproducible by running
`/tmp/opencode/diag_v2.py` over the v2-clean output directory (asks only
`reference_events.csv` and `interval_lattice_v2_clean.csv`; both already exist).
No new model inference is needed.