# CILS Config Audit — runs/craq_lite_v1/20260701T075242Z

Conservative audit of the CRAQ-lite / CILS full-grid run. No new experiments were
run; only static inspection plus a single in-process re-execution of `cils_select`
at fixed `(B, tau)` to verify behavior against the recorded artifacts.

## Files Inspected

Run artifacts:
- `runs/craq_lite_v1/20260701T075242Z/config_used.json`
- `runs/craq_lite_v1/20260701T075242Z/REPORT.md`
- `runs/craq_lite_v1/20260701T075242Z/metrics_summary.csv`
- `runs/craq_lite_v1/20260701T075242Z/metrics_by_method_seed.csv`
- `runs/craq_lite_v1/20260701T075242Z/predictions_cils_craq_lite.csv`
- `runs/craq_lite_v1/20260701T075242Z/predictions_audited_proposal_repair.csv`
- `runs/craq_lite_v1/20260701T075242Z/predictions_oracle_confirmed_only.csv`
- `runs/craq_lite_v1/20260701T075242Z/predictions_lattice_oracle_upper_bound.csv`
- `runs/craq_lite_v1/20260701T075242Z/oracle_budget_trace.csv`
- `runs/craq_lite_v1/20260701T075242Z/proposal_recall.csv`

Code:
- `src/garc_eval/experiments/craq_lite_v1/run_craq_lite.py`
- `src/garc_eval/metrics/craq_lite_metrics.py`
- `src/garc_eval/tests/test_craq_lite_metrics.py` (4 passed)
- `src/garc_eval/experiments/cils_calibration_repair_smoke_v1/smoke.py` (reference for the earlier CILS smoke semantics)
- `src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/interval_lattice_v2_clean.csv`
- `src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/interval_labels_v2_clean.csv`

## Exact Config Values Found (config_used.json)

- `oracle_budgets`: `[20, 40, 80, 160]`
- `precision_targets`: `[0.8, 0.9]`
- `iou_thresholds`: `[0.3, 0.5]`
- `seeds`: `0..99` (100 seeds)
- `fixed_cils_policy.pilot`: `answer_quality_proxy_top`
- `fixed_cils_policy.calibration`: `beta_bin_strata_lower`
- `fixed_cils_policy.selector`: `clean_v2_no_leak_cils_selector`

Note: `fixed_cils_policy` is **descriptive metadata only**. It is not consumed by
the runner; the actual selector is hard-coded in `run_craq_lite.py` (`cils_select`).

## Exact CILS tau Values Used in the Full Grid

The full grid calls CILS via `run_craq_lite.py:425`:

```python
"cils_craq_lite": cils_select(cand, budget, precision_target, events),
```

`cils_select(cand, budget, tau, interval_events)` (signature at `run_craq_lite.py:315`).
Therefore the **selector tau** in the full grid was exactly `{0.8, 0.9}` — the
`precision_targets` values. No `0.5` or `0.6` tau was run for `cils_craq_lite` in
this run.

## Exact Precision Target Values Found

- In `config_used.json`: `[0.8, 0.9]`.
- In `run_craq_lite.py:36`: `PRECISION_TARGETS = [0.8, 0.9]`.
- Used in two distinct ways inside `run_grid`:
  1. As the value passed to `cils_select` as `tau` (line 425).
  2. As a reporting / filtering label carried into per-row `precision_target`
     columns and used by `report()` to filter `mean_precision >= 0.8` for the
     selector gate (`run_craq_lite.py:594-600`).

So `precision_target` is **not** used only for reporting. It is also used as the
selector threshold.

## Core Configuration Answers

### 1. Are `precision_targets` used only for reporting / filtering observed results?
**No.** They are ALSO used as the CILS selector `tau` (line 425). The reporting
filter at lines 594-600 additionally uses a hard-coded `0.8`, not the configured
targets.

### 2. Are `precision_targets` accidentally used as CILS selector `tau`?
**Yes — this is a confirmed configuration bug.** Evidence:
- `run_craq_lite.py:425`: `"cils_craq_lite": cils_select(cand, budget, precision_target, events)`.
- `run_craq_lite.py:315`: `def cils_select(cand, budget, tau, interval_events)`.
- The grid iterates `for precision_target in PRECISION_TARGETS` (line 417), so
  `tau ∈ {0.8, 0.9}` for every CILS call in the full grid.
- The earlier CILS smoke (`cils_calibration_repair_smoke_v1/smoke.py:24`) used
  `TAUS = [0.5, 0.6, 0.7, 0.8, 0.9]` as a distinct selector-threshold axis and
  iterated them as `tau` (`smoke.py:424-425`). The craq_lite wrapper collapsed
  the precision-reporting axis onto the selector-threshold axis.

### 3. What tau values did `cils_craq_lite` actually run with in the full-grid run?
`{0.8, 0.9}` (one CILS call per `(budget, precision_target, seed)`, with
`precision_target ∈ {0.8, 0.9}` mapped to `tau`).

### 4. Did the code distinguish desired precision target from selector threshold?
**No.** There is no separate `tau` config field; `precision_target` is passed
directly as `tau`. The `fixed_cils_policy` metadata block in `config_used.json`
does not list a tau either.

### 5. Did CILS return zero intervals because of which failure?

Verified in-process by re-invoking `rc.cils_select(cand, 80, tau, events)` on the
exact same inputs (`seed` is irrelevant to `cils_select`; only the calibration
sample of size `budget` is used, which is deterministic given `cand`):

| B  | tau | selected | exp_prec | top selected answer |
|----|-----|----------|----------|---------------------|
| 80 | 0.5 | 1        | 0.6667   | True                |
| 80 | 0.6 | 1        | 0.6667   | True                |
| 80 | 0.7 | 0        | 0.0000   | —                   |
| 80 | 0.8 | 0        | 0.0000   | —                   |
| 80 | 0.9 | 0        | 0.0000   | —                   |

Calibration distribution at B=80 (`calibrate_cils`): `p_answer` max = `0.6667`,
median = `0.0671`, mean = `0.0726`. The selection rule
(`run_craq_lite.py:336-339`) is

```
if safe_div(ntp, ntotal) + 1e-12 < tau: continue
```

For the first candidate `ntp/ntotal = p_answer ≤ 0.6667 < 0.8`, so at
`tau ∈ {0.8, 0.9}` every candidate (including the first) is rejected and the
selector returns the empty set.

Diagnosis (multiple compounding causes, in priority order):

1. **Selector tau too high (primary, confirmed).** `tau = 0.8/0.9` exceeds the
   maximum achievable `p_answer` lower bound (0.6667) in this calibration, so
   the precision constraint rejects all candidates. This is the
   precision-target-vs-tau bug above.
2. **Single overlap_group_id (secondary, caps recall even if tau were fixed).**
   The clean v2 lattice has exactly one `overlap_group_id` (`og2_00000`) across
   all 11939 candidates. `cils_select` (`run_craq_lite.py:330`) skips any
   candidate whose `overlap_group_id` is already in `groups`. With one group id,
   at most **one** interval can ever be selected regardless of `B`. The same
   defect affects `nms()` (`run_craq_lite.py:218-233`) used by
   `fixed_window_topk`, `threshold_merge`, `arc_style_prune_refine`, and
   `audited_proposal_repair`.
3. **Calibration lower bounds are low (tertiary).** Even at the permissive
   `tau = 0.5/0.6`, only one interval is selected, because (a) Wilson lower
   bounds on small per-stratum samples are very conservative and (b) cause 2
   above caps the count to 1.

Not the cause: the candidate lattice is not empty (11939 candidates, 1192
positive under `answer_iou_0_3`), and the metric code matches intervals
correctly (verified by `oracle_confirmed_only` reaching recall 0.333 at B=160).

### 6. Why did `audited_proposal_repair` get zero recall while `oracle_confirmed_only` reached 0.333?

Two compounding reasons:

- **Same single-group-id NMS defect.** `audited_proposal_repair` builds
  `base = arc_style(...)` and `repairs` from lattice candidates, then calls
  `nms(combined, budget)` (`run_craq_lite.py:289`). Because every candidate
  shares `og2_00000`, NMS keeps exactly one interval — the highest
  `answer_quality_proxy` row, which is `iv2_0007500` (554.0–586.0s, 32s
  duration, `answer_iou_0_3 = False`). All repair candidates (which share the
  same group id) are dropped regardless of how many audit positives were found.
- **The audit step DID find positives** (`oracle_budget_trace.csv`:
  `oracle_positive=True` in 3342 / 30000 audit calls, ~11.1%), but those
  positives are converted into lattice repair candidates that NMS then
  discards. So the repair mechanism generated candidates and then filtered
  them all out — confirming the user's hypothesis that repair "generated
  candidates but later filtered them out."

  Verification: `predictions_audited_proposal_repair.csv` has 800 rows (= 4
  budgets × 2 precision_targets × 100 seeds), every row is `rank=1` and
  `interval_id=iv2_0007500` with `answer_iou_0_3=False`. So across the entire
  grid the repair wrapper returns the same single false-positive base interval.

`oracle_confirmed_only` reaches 0.333 because it does **not** use `nms` — it
returns `probed[probed[ANSWER].astype(bool)]`
(`run_craq_lite.py:256-258`), i.e. all top-`B` candidates whose existing oracle
label is positive. At B=160 it returns 17 positive intervals (precision 1.0),
two of which hit distinct true interval events at IoU@0.3, giving recall 2/6 =
0.333.

### 7. Is `lattice_oracle_upper_bound = 1.000` computed on the same candidate lattice used by CILS?
**Same lattice, different (more permissive) selection rule.**
`lattice_oracle_for_events` (`run_craq_lite.py:347-375`) iterates the same
`cand` dataframe (clean v2 lattice + labels) but:
- does NOT apply `nms`,
- does NOT consult `overlap_group_id`,
- does NOT apply any precision/tau constraint,
- picks, per true event, the single candidate with the highest IoU to that
  event, subject only to a one-candidate-per-event uniqueness constraint.

So the upper bound is a valid coverage diagnostic on the same lattice, but it
is **not** an upper bound on what `cils_select` (or any nms-based method) could
reach under the run's NMS and tau constraints. The proposal gate (Gate 2) PASS
is therefore correct as a lattice-coverage statement but does not imply the
selectors were operating on an equivalent selection rule.

### 8. Any evidence of data leakage or ground-truth peeking?
- `oracle_confirmed_only`: uses `cand[ANSWER]` (existing oracle replay labels)
  directly. This is by design and is explicitly labeled "conservative
  lower-bound baseline" in `REPORT.md`. Not leakage in the sense of training-on
  test, but it is oracle-access and cannot be compared to budget-constrained
  selectors.
- `lattice_oracle_upper_bound`: uses `events` (true reference events) to pick
  best candidates. Explicitly labeled "diagnostic only" in code comment
  (`run_craq_lite.py:349-353`). Diagnostic, not a method baseline.
- `audited_proposal_repair`: the audit hit check at `run_craq_lite.py:276-279`
  uses `events` (true interval events) as the simulated oracle, and each call
  is recorded in `oracle_budget_trace.csv` with an `oracle_positive` flag. This
  is a simulated oracle audit budget, counted and traced. Not silent leakage,
  but the repair mechanism does have direct reference access via the simulated
  oracle — acceptable for a budgeted-audit simulation, not for an unsupervised
  method claim.
- `cils_select`: calibration at `run_craq_lite.py:300-312` samples top-`budget`
  candidates by `answer_quality_proxy` and reads their `answer_iou_0_3` labels
  to fit per-stratum Wilson lower bounds. This is the intended CILS
  calibration use of oracle labels (calibration on a budget-B labeled subset),
  consistent with the stated CILS policy. Not leakage under the CILS framing,
  but it does mean calibration is fit on the same label column used to evaluate
  precision. This is inherent to the CILS design and not a new defect.

No evidence of an additional off-script leakage path was found.

## Summary of Bugs Found

1. **Precision-target-vs-tau bug (CONFIRMED).** `run_craq_lite.py:425` passes
   `precision_target` (configured as 0.8/0.9 for reporting) directly as the
   CILS selector `tau`. The earlier CILS smoke used a separate `TAUS` axis
   including 0.5/0.6. Result: every CILS call in the full grid ran with
   `tau ∈ {0.8, 0.9}`, which exceeds the maximum achievable `p_answer`
   (0.6667) and forces an empty return.
2. **Single overlap_group_id in the clean v2 lattice (CONFIRMED, independent
   of bug 1).** All 11939 candidates share `og2_00000`. The `nms` helper and
   `cils_select` skip any candidate whose group id is already used, so
   nms-based methods and CILS can return at most 1 interval regardless of
   budget. This independently caps recall for `fixed_window_topk`,
   `threshold_merge`, `arc_style_prune_refine`, `audited_proposal_repair`, and
   `cils_craq_lite`, and is the reason `audited_proposal_repair` collapses to
   a single false-positive base interval despite the audit finding 3342
   positives.

## Whether the Selector Gate Failure is Trustworthy

**PARTIAL.**

- The recorded selector gate (`CILS recall at precision ≥ 0.8 = 0.000`) is
  **trustworthy as a measurement of this run**: with `tau = 0.8/0.9`, CILS
  genuinely returned zero intervals in every cell (verified against
  `predictions_cils_craq_lite.csv`, which contains only the header).
- However, the gate is **not trustworthy as a statement about CILS as a
  method**: the run used the wrong `tau` values (bug 1) and an NMS setup that
  caps every selection to one interval regardless of budget (bug 2). The
  earlier smoke at `tau = 0.5/0.6` returned a non-empty, high-precision
  interval (a true positive), and a re-invocation here at `B=80, tau=0.5`
  reproduces that (1 selected, `answer_iou_0_3 = True`, `exp_prec = 0.6667`).
- Therefore the selector-gate FAIL reflects **config + lattice-NMS defects**,
  not a validated negative result on CILS. The gate should be marked
  INCONCLUSIVE pending a rerun with (a) a decoupled `tau` axis and (b) either
  a fixed `overlap_group_id` assignment in the lattice or an NMS rule that
  does not collapse to a single group.

## Minimal Recommended Next Action

1. **Decouple `tau` from `precision_target`** in `run_craq_lite.py:425`. Add a
   separate `taus: [0.5, 0.6, 0.7]` axis (matching the earlier smoke) and keep
   `precision_targets` only for the reporting/filter side. One-line patch at
   line 425 plus a grid extension; no framework rewrite.
2. **Rerun the smoke-scale grid** (`--smoke`, budgets 20/40/80, seeds 0..9)
   with the decoupled tau axis and inspect `predictions_cils_craq_lite.csv`
   for non-empty returns before any full-grid rerun.
3. **Separately diagnose the single `overlap_group_id`** in
   `clean_interval_aqp_full_reference_v2_clean_no_leak/interval_lattice_v2_clean.csv`.
   Either regenerate the lattice with proper per-cluster group ids, or change
   the `nms` helper to rely only on IoU > threshold (drop the group-id skip).
   This is needed before any nms-based method (including the ARC-style and
   repair baselines) can produce a non-degenerate recall curve.

A one-line patch for issue 1 (do NOT apply without explicit authorization):
```python
# run_craq_lite.py:425 — replace
"cils_craq_lite": cils_select(cand, budget, precision_target, events),
# with (after adding a TAUS axis and iterating `for tau in TAUS`)
"cils_craq_lite": cils_select(cand, budget, tau, events),
```

## Limitations of This Audit

- Only the recorded artifacts and the two cited source files were inspected.
- The in-process re-invocation of `cils_select` was a deterministic single-cell
  check at B=80; it does not re-run the full grid.
- The single-`overlap_group_id` finding is a property of the clean v2 lattice
  file; whether upstream generation intended a single group is outside this
  audit.
- `audited_proposal_repair`'s trace shows 3342 audit positives, but this audit
  did not enumerate which (budget, seed) cells produced them; the conclusion
  that all repairs were NMS-discarded is inferred from the uniform
  single-interval, single-`interval_id` structure of
  `predictions_audited_proposal_repair.csv`.
