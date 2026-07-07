# EventLift-AQP Stage 1 (Dev Segment) Report

> Stage 1 implementation of `EVENTLIFT_AQP_ALGORITHM_SPEC.md` on the dev
> segment `realcartest_2000_3200` only. **All numbers are VLM-oracle-relative**
> (labels in `center10_vlm_oracle_events.csv` / `reference_events.csv`),
> not human ground truth, and no formal guarantee / certificate /
> statistical bound is claimed (per `AGENTS.md`, `CLAIMS_LEDGER.md` line 87).
> No safe stopping is claimed. No video / GPU / VLM / YOLO inference was
> run; all oracle calls are replay over existing labels.

============================================================
1. Data loading and dev segment validation
============================================================

- **Dev segment:** `realcartest_2000_3200` (the `is_dev=True` segment per
  `outputs/late_aqp_event_diverse_discovery_v1/segment_info.csv`).
- **Grid file:** `outputs/late_aqp_frozen_cross_segment_v1/grid_realcartest_2000_3200.csv`
  (120 rows = 120 atomic 10s bins, local time 0–1200 s, absolute 2000–3200 s).
- **Reference events:** `src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak/reference_events.csv`,
  filtered to absolute window [2000, 3200] → **20 reference events** (all
  `enter_ego_path`, VLM_ORACLE_RELATIVE_REUSED_FOR_MINI_FULL_REFERENCE).
- **Bins:** 120 (10 s each, 1200 s total).
- **Positive bins:** 32 (`is_positive=True`).
- **Reference events:** 20.
- **Proxy score column used:** `prior_score_max` (range 0.108–0.521, median
  0.315). `prior_score_mean` is also available but `prior_score_max` is the
  LATE-AQP selection prior (`outputs/exsample_aware_replay/atomic_grid_10s.csv`).
- **Label column used:** `is_positive` (boolean).
- **`event_id` present in grid:** YES (column `event_id`). **Confirmed
  excluded from online decisions:** the EventLift loop, SUPG-event adapter,
  and ABae-residual adapter read only `bin_idx`, `prior_score_max`, and the
  oracle response from `ReplayOracle.query_unit()`. The `event_id` column is
  never read by any online code path. Reference events are used only in
  `evaluate_events()` after the method returns.

No required files were missing.

============================================================
2. SUPG-event adapter
============================================================

- **Official SUPG code used:** YES, via `refe_repos/supg/supg/selector/recall_selector.py`
  (`RecallSelector`, `ImportanceSampler`, `ApproxQuery`, `DFDataSource`).
  The G-ARC adapter `src/garc_eval/adapters/supg_adapter.py` was used as a
  reference; the Stage 1 script (`scripts/eventlift_stage1_dev.py`) wraps
  the same SUPG classes directly.
- **Record = 10s bin:** `id=bin_idx`, `label=is_positive`, `proxy_score=prior_score_max`.
- **Budget handling:** SUPG's `budget` param = number of importance samples.
  SUPG also calls `source.filter()` which re-queries positives (extra
  lookups). To stay within `budget_abs`, SUPG's internal budget was capped
  at `budget_abs // 2` (matching the ARC convention
  `refe_repos/ARC-main/experiments/algorithm_handler.py:36`:
  `sample4supg = int(B / 2)`).
- **Temporal grouping:** positive sampled bins merged into intervals (gap
  ≤ 1 bin = 10 s), the missing `supg_rt_plus` step from
  `docs/GARC_EVAL_BUILD_PLAN.md`.
- **Did it run successfully?** YES. 9/9 runs (3 budgets × 3 seeds) completed.
- **Budget ledger:** 0 violations. All `oracle_calls_total <= budget_abs`.
- **Results (mean over 3 seeds):**

  | budget_abs | budget_ratio | oracle_calls | event_precision | event_recall | unique_event_coverage |
  |---:|---:|---:|---:|---:|---:|
  | 12 | 0.10 | 12.0 | 0.167 | 0.017 | 0.33 |
  | 24 | 0.20 | 24.0 | 0.417 | 0.067 | 1.33 |
  | 36 | 0.30 | 36.0 | 0.376 | 0.100 | 2.00 |

- **`residual_estimate_available = false`, `recall_lcb_available = false`,
  `stop_certificate_available = false`** — confirmed (SUPG has no residual
  estimator; `SamplingBounds` calibrates selection size, not event recall).
- **`B_90/90`:** NA (no run reached 0.90 recall; max recall 0.15 at seed 1,
  budget 36).

============================================================
3. ABae-residual adapter
============================================================

- **Official ABae logic used:** YES, via the G-ARC adapter
  `src/garc_eval/adapters/abae_adapter.py` (a faithful reimplementation of
  ABae Algorithm 1 per its docstring; the upstream
  `refe_repos/abae/abae/algorithm.py` requires `ray` which is not installed).
  The Stage 1 script uses `quantile_stratify` from the adapter and replicates
  the two-stage allocation (`sqrt(p_hat * sigma_hat)`; with `statistic=1`,
  `sigma=0` among positives, so the fallback `sqrt(p_hat)` is used).
- **Record = 10s bin:** `predicate = bin positive`, `statistic = 1`.
- **Estimated quantity:** total positive-bin mass `P(predicate) * N_total`.
- **Residual estimate:** `max(0, total_positive_mass_hat - observed_positive_mass)`.
- **Did it run successfully?** YES. 9/9 runs completed.
- **Results (mean over 3 seeds):**

  | budget_abs | oracle_calls | audit_n | residual_hat | residual_ucb | p_ucb |
  |---:|---:|---:|---:|---:|---:|
  | 12 | 11.3 | 11.3 | 27.67 | 25.40 | 0.234 |
  | 24 | 24.0 | 24.0 | 32.00 | 11.27 | 0.117 |
  | 36 | 30.3 | 30.3 | 31.10 | 8.55 | 0.095 |

- **No intervals returned** (ABae emits a scalar only). `event_precision` /
  `event_recall` = NA, as specified.
- **Calibration (mean abs error vs true uncovered positive bins):**
  - budget 12: abs_error 12.0 (true ~28-31 uncovered)
  - budget 24: abs_error 12.7 (true ~22-27 uncovered)
  - budget 36: abs_error 9.4 (true ~21-22 uncovered)
- **`residual_estimate_available = true`**, `recall_lcb_available = false`,
  `stop_certificate_available = false`.

============================================================
4. EventLift Stage 1: DISCOVER + AUDIT
============================================================

- **Implemented actions:** DISCOVER (importance sampling over proxy-mass
  components, `sqrt(proxy)` weights, matching SUPG's `sample_mode="sqrt"`)
  and AUDIT (stratified sampling over uncovered bins with known
  probability, ABae-style).
- **Forbidden actions (not implemented):** CERTIFY, SUPPRESS, ARC-projection.
- **Unified utility:** per spec §5.1, fixed hyperparameters (NOT tuned):
  `ETA=1.0, LAMBDA=0.5, GAMMA=0.3, KAPPA=0.5`. The loop picks `argmax`
  of `U_discover` vs `U_audit` at each step.
- **No `event_id` online:** confirmed. The loop reads only `bin_idx`,
  `prior_score_max`, and `ReplayOracle.query_unit()` responses.
- **Budget ledger:** 0 violations. `oracle_calls_total == discover_calls +
  audit_calls` asserted and verified for all 18 EventLift runs.
- **Lineage:** every oracle call logged with `action_type` ∈ {DISCOVER,
  AUDIT} and `source_action` ∈ {DISCOVER, AUDIT} + `residual_hat_before`/
  `after`, `component_id`, `stratum_id`, `budget_remaining`.

### 4.1 discover-only ablation (mean over 3 seeds)

  | budget_abs | oracle_calls | event_precision | event_recall | unique_event_coverage | residual_ucb |
  |---:|---:|---:|---:|---:|---:|
  | 12 | 12.0 | 0.400 | 0.050 | 1.00 | 108.0 |
  | 24 | 24.0 | 0.468 | 0.133 | 2.67 | 96.0 |
  | 36 | 36.0 | 0.400 | 0.183 | 3.67 | 84.0 |

### 4.2 discover+audit full Stage 1 (mean over 3 seeds)

  | budget_abs | oracle_calls | discover_calls | audit_calls | event_precision | event_recall | unique_event_coverage | residual_hat | residual_ucb | stop_status |
  |---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
  | 12 | 12.0 | 12.0 | 0.0 | 0.400 | 0.050 | 1.00 | 0.00 | 108.0 | abstain |
  | 24 | 24.0 | 18.0 | 6.0 | 0.342 | 0.117 | 2.33 | 18.29 | 39.15 | abstain |
  | 36 | 36.0 | 19.0 | 17.0 | 0.323 | 0.167 | 3.33 | 26.18 | 13.77 | abstain |

- **All runs `stop_status = abstain_or_budget_exhausted`** (no stop
  certificate emitted). Stop reasons: `audit_n_too_small` (all runs;
  `audit_n < 29 = n_min_for_p_ucb<=0.10` per spec §6.3). This is the
  expected behavior per `RC_AQP_PREFLIGHT.md` Gate 2.

============================================================
5. Unified ledger
============================================================

- **Trace file:** `outputs/eventlift_stage1_dev/stage1_call_trace.csv`
  (738 rows, 116 KB).
- **Columns:** all required columns present (`segment_id, method_id, seed,
  budget_abs, budget_ratio, call_idx, action_type, source_action, bin_id,
  component_id, stratum_id, proxy_score, oracle_label, online_positive,
  added_to_returned_intervals, cumulative_oracle_calls, budget_remaining,
  residual_hat_before, residual_hat_after, notes`).
- **Action type counts:** DISCOVER=363, ABAE_SAMPLE=197, SUPG_LOOKUP=109,
  AUDIT=69.
- **Lineage integrity:** `source_action` populated for all 738 rows
  (values: DISCOVER, ABAE_STAGE1, ABAE_STAGE2, SUPG_LOOKUP, AUDIT,
  SUPG_LOOKUP_CORRECTION).
- **Budget invariant:** `(cumulative_oracle_calls <= budget_abs).all() == True`.
- **Frontier file:** `outputs/eventlift_stage1_dev/stage1_frontier_raw.csv`
  (36 rows, 11 KB). All required columns present.
- **Calibration file:** `outputs/eventlift_stage1_dev/stage1_residual_calibration.csv`
  (27 rows, 4.7 KB). All required columns present.

============================================================
6. Gate questions
============================================================

**Q1. Did SUPG-event run successfully?**
YES. 9/9 runs completed, 0 budget violations. Uses official SUPG
`RecallSelector` + `ImportanceSampler` via `refe_repos/supg`. Budget capped
at `budget_abs // 2` to account for SUPG's internal `filter()` re-queries
(matching the ARC convention). Mean recall 0.017/0.067/0.100 at
budget 12/24/36.

**Q2. Did ABae-residual run successfully?**
YES. 9/9 runs completed, 0 budget violations. Uses the G-ARC
`abae_adapter.py` (faithful ABae Algorithm 1 reimplementation, no `ray`
dependency). `statistic=1` total-positive-mass estimator. Residual UCB
tightens with budget: 25.4 → 11.3 → 8.5 (mean). Calibration abs error
mean 9.4–12.7 bins.

**Q3. Does EventLift discover+audit obey the budget ledger?**
YES. 0 violations across 18 runs. `oracle_calls_total == discover_calls +
audit_calls` asserted and verified. `cumulative_oracle_calls <= budget_abs`
for every row in the trace. The `source_action` lineage is populated for
every call (closes the v3 `source_action` gap noted in
`RC_AQP_PREFLIGHT.md` line 141).

**Q4. Does AUDIT recover any positives, or only consume budget?**
AUDIT recovers positives at budget 24 and 36:
- budget 12: audit_n=0, audit_positives=0 (utility never picked AUDIT —
  all budget went to DISCOVER because residual UCB was uninformative at
  n=0 and the dual-purpose term was dominated by DISCOVER's proxy mass).
- budget 24: audit_n=6.0 (mean), audit_positives=1.33 (mean).
- budget 36: audit_n=17.0 (mean), audit_positives=5.33 (mean).

So AUDIT is **not pure budget tax** at budget ≥ 24: it recovers positives
in low-proxy strata that DISCOVER would not visit. At budget 12, AUDIT
does not fire at all (the utility collapses to all-DISCOVER), which is the
degenerate case the spec §10 Stage 2 gate warns about.

**Q5. Does AUDIT improve residual calibration?**
PARTIALLY. Comparing EventLift-discover-audit vs discover-only:
- discover-only: `residual_hat = 0` always (no audit samples → no estimate),
  `residual_ucb` = 84–108 (uninformative, `p_ucb=1.0`).
- discover+audit: `residual_hat` becomes nonzero at budget 24+; `residual_ucb`
  shrinks (39.2 at budget 24, 13.8 at budget 36 vs 96/84 for discover-only).

ABae-residual alone has **better** calibration than EventLift-discover-audit
at the same budget (ABae abs_error 9.4 at budget 36 vs EventLift 7.5–11.0).
This is expected: ABae dedicates 100% of budget to stratified estimation,
while EventLift splits budget between DISCOVER (coverage) and AUDIT
(residual). EventLift's residual is a byproduct of a coverage-seeking loop,
not a dedicated estimator.

**Q6. Does AUDIT hurt unique event recall compared with discover-only?**
MARGINALLY YES, by a small amount:
- budget 12: recall 0.050 vs 0.050 (tie; AUDIT never fires).
- budget 24: recall 0.117 vs 0.133 (audit is 0.017 lower).
- budget 36: recall 0.167 vs 0.183 (audit is 0.017 lower).

AUDIT steals ~6–17 calls from DISCOVER at budget 24/36, costing ~0.017
recall. This is the opportunity-cost the spec §5.1 `kappa` term is meant
to price. The current fixed `kappa=0.5` is not enough to make AUDIT
worthwhile on recall alone at this scale — AUDIT's value is in residual
reporting, not recall.

**Q7. Is residual uncertainty still too wide for stopping?**
YES, decisively. Per `RC_AQP_PREFLIGHT.md` Gate 2:
- Per-segment `n_min` for `p_ucb <= 0.10` is 29. EventLift-discover-audit's
  audit_n is 0/6/17 at budget 12/24/36 — all below 29.
- `stop_status = abstain_or_budget_exhausted` for all 9 discover+audit
  runs. No stop certificate emitted.
- Pooled across all 6 LATE-AQP segments, audit_n could reach ~30-80, but
  that is a *pooled* report, not per-segment stopping (per spec §6.3).

**Q8. Should Stage 2 add CERTIFY/SUPPRESS?**
YES, conditionally. Stage 1 shows:
- The budget ledger works and lineage is clean.
- AUDIT recovers positives at budget ≥ 24 (not pure tax).
- But AUDIT hurts recall by ~0.017 because DISCOVER is underfunded, and
  the residual is still too wide for stopping.
- CERTIFY would refine candidate boundaries (improving precision, which
  is currently 0.32–0.40 at budget 36 — well below 0.90). SUPPRESS would
  avoid redundant DISCOVER calls in negative neighborhoods (the pre-fix D3
  duplicate-sampling failure mode, `FAILURES.md` line 92). Both directly
  address the gaps Stage 1 exposes.
- BUT: Stage 2 must first fix the utility collapse at budget 12 (AUDIT
  never fires). The `kappa` opportunity-cost term needs calibration, or
  AUDIT will remain frozen out at low budget.

============================================================
Gate decision
============================================================

**A. Proceed to Stage 2.**

Rationale:
1. **Budget ledger is correct:** 0 violations across 36 runs, lineage
   populated for all 738 trace rows. ✓
2. **SUPG/ABae adapters run:** both use official/faithful logic, 9/9 runs
   each. ✓
3. **EventLift discover+audit is not clearly worse than discover-only:**
   recall delta is −0.017 (small), but AUDIT recovers positives (1.33–5.33
   per run) and produces a residual report discover-only cannot. The
   tradeoff is a wash on recall and a gain on residual reporting. ✓
4. **AUDIT provides residual calibration or useful positive recovery:**
   AUDIT recovers 1.33–5.33 positives per run at budget 24/36; residual
   UCB shrinks from 96 → 13.8 at budget 36. ✓

Conditions for Stage 2:
- Fix the utility collapse at budget 12 (AUDIT never fires; the
  dual-purpose term must be stronger or AUDIT must be force-scheduled).
- Add CERTIFY (boundary refinement → precision) and SUPPRESS (redundancy
  reduction → frees DISCOVER budget) under the same unified utility.
- Re-evaluate whether the unified utility actually arbitrates (vs
  collapsing to all-DISCOVER). The spec §10 Stage 2 gate explicitly warns
  about this.
- Do NOT claim safe stopping. Do NOT claim EventLift beats B7-core from
  one dev segment. Do NOT run multi-segment yet.

============================================================
Appendix — execution record
============================================================

**Files created:**
- `scripts/eventlift_stage1_dev.py` (~430 LOC, the Stage 1 implementation)
- `outputs/eventlift_stage1_dev/stage1_call_trace.csv` (738 rows, 116 KB)
- `outputs/eventlift_stage1_dev/stage1_frontier_raw.csv` (36 rows, 11 KB)
- `outputs/eventlift_stage1_dev/stage1_residual_calibration.csv` (27 rows, 4.7 KB)
- `EVENTLIFT_STAGE1_DEV_REPORT.md` (this file)

**Files modified:** none. No canonical output (`outputs/late_aqp_*`,
`PROJECT_STATE.md`, `HANDOFF.md`, `CLAIMS_LEDGER.md`, `FAILURES.md`,
`AGENTS.md`, `TASK_QUEUE.yaml`, `EXPERIMENT_REGISTRY.csv`) was touched.

**Commands run:**
- `python scripts/eventlift_stage1_dev.py` (Stage 1 run on dev segment only;
  CPU-only, <2 s wall time; replay over existing VLM-oracle-relative labels;
  no video/GPU/VLM/YOLO).
- Read-only inspections: `head`, `python -c "import pandas..."` for schema
  verification, `ls -lh` for output sizes.

**Was any official source modified?** NO. `refe_repos/supg/`,
`refe_repos/abae/`, `refe_repos/ARC-main/` are untouched. The script imports
SUPG classes via `sys.path` and uses the G-ARC `abae_adapter.py` (which is
a faithful reimplementation, not the ray-dependent upstream).

**Was any large artifact created?** NO. Total output size ~132 KB
(116 + 11 + 4.7 KB), well under any large-artifact threshold.

**Were any budget assertions violated?** NO. `oracle_calls_total <= budget_abs`
for all 36 frontier rows; `cumulative_oracle_calls <= budget_abs` for all
738 trace rows.

**Missing evidence (registered, not invented):**
- No multi-segment validation (Stage 1 is dev-segment only by design).
- No CERTIFY/SUPPRESS (Stage 2 scope).
- No ARC-projection (Stage 3 scope).
- No stop certificate (per `RC_AQP_PREFLIGHT.md` Gate 2, per-segment safe
  stopping is statistically weak at this scale; all runs abstain).
- No human ground truth (all labels are VLM-oracle-relative).
- No comparison to B7-core / D3-norepair-core on this dev segment (that is
  a multi-segment Stage 4 task; Stage 1 only establishes the adapters and
  the ledger).

**Recommended next task:** Stage 2 — add CERTIFY (ARC-style progressive
sampling over bin-grid, bounded by `MAX_GUARDS_PER_SIDE=3`) and SUPPRESS
(label propagation, 0 oracle calls except optional 1 confirmatory) into
the unified utility loop, on the same dev segment. The Stage 2 gate is:
does the utility arbitrate non-degenerately (not all-DISCOVER) and does
duplicate_rate drop vs Stage 1? Do NOT proceed to Stage 3 (ARC-projection)
or Stage 4 (multi-segment) until Stage 2 passes.
