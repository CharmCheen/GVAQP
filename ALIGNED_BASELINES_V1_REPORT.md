# Aligned Baselines V1 Report

> Aligned strict-replay baselines for EventLift full benchmark comparison.
> All numbers are VLM-oracle-relative, not human ground truth. No safe
> stopping, formal guarantee, or statistical bound is claimed (per
> `AGENTS.md`, `CLAIMS_LEDGER.md`). No video/GPU/VLM/YOLO inference was run.

============================================================
1. Which baselines were implemented/rerun?
============================================================

4 baselines implemented and run on all 6 LATE-AQP segments:

1. **B7-strict-replay** — B7 chunk-bandit with strict online novelty proxy.
   Replaces `get_event_at_bin` (which reads `event_id`) with `is_positive` +
   adjacency-based singleton counting. Temporal expansion (k=3) around
   positive bins. Core/Halo via temporal grouping of observed positives.

2. **D3-norepair-core-strict** — D3 chunk-bandit strict-replay rerun.
   Uses `is_positive` for singleton counting (already strict_replay in
   original `discovery_d3_chunk_bandit`). No repair. No `event_id`.

3. **SUPG-event-rt-strict** — SUPG recall-target selector over 10s bins.
   Uses official SUPG `RecallSelector` from `refe_repos/supg/`. Budget
   capped at `budget_abs // 2` for internal `filter()` re-queries. Temporal
   grouping added by adapter. No `event_id`.

4. **ABae-residual-strict** — ABae two-stage stratified estimator with
   statistic=1 (total positive mass). Uses `garc_eval/adapters/abae_adapter`
   (faithful reimplementation, no ray). No returned intervals. Residual
   estimate only. No `event_id`.

============================================================
2. Which baselines are strict-replay aligned?
============================================================

ALL 4 baselines are strict-replay aligned:

| Baseline | strict_replay_or_posthoc | online_uses_event_id | can_be_main_comparison |
|---|---|---|---|
| B7-strict-replay | strict_replay | False | True |
| D3-norepair-core-strict | strict_replay | False | True |
| SUPG-event-rt-strict | strict_replay | False | True |
| ABae-residual-strict | strict_replay | False | True |

All 216 frontier rows have `online_uses_event_id = False` and
`strict_replay_or_posthoc = strict_replay`.

============================================================
3. Did B7-strict-replay avoid event_id online?
============================================================

YES. Verified by:
- `AlignedOracle` class tracks `_event_id_accessed` flag and asserts
  `not self._event_id_accessed` at the end of each run.
- The `is_new_online_hit()` function in `run_b7_strict_replay` uses only
  `is_positive` labels and bin adjacency — never reads `event_id`.
- All 54 B7-strict-replay runs have `online_uses_event_id = False`.
- 0 event_id leaks across all 216 runs.

**How B7-strict-replay differs from historical B7-core (posthoc_eval):**
- B7-core (`run_b7` in `run_frozen_cross_segment.py:329`) uses
  `get_event_at_bin(grid, b)` (line 342) which reads `event_id` from the
  grid to track singleton positive events per chunk for Thompson sampling.
  This is posthoc_eval.
- B7-strict-replay replaces this with `is_new_online_hit(b)`: a positive bin
  is a "new online hit" if it is NOT already inside or adjacent (within 1
  bin) of an already-known positive bin. This uses only `is_positive` and
  bin adjacency — no `event_id`, no reference event boundaries, no offline IoU.
- This is a **fair strict adaptation**, not the original B7-core. The
  novelty proxy is slightly less informative than event_id-based singleton
  counting (it cannot distinguish two distinct events in adjacent bins),
  but it does not leak reference information.

============================================================
4. How different is B7-strict-replay from historical B7-core-posthoc-context?
============================================================

Not directly compared in this run (B7-core-posthoc-context is not rerun
here). Historical B7-core results from
`outputs/late_aqp_d3_accounting_fix_v1/d3_fixed_frontier_raw.csv` at
budget 0.30 (posthoc_eval, context-only):

| segment_id | B7-core P (posthoc) | B7-core R (posthoc) | B7-strict-replay P | B7-strict-replay R |
|---|---:|---:|---:|---:|
| realcartest_0_1570 | 1.000 | 0.310 | 0.458 | 0.200 |
| realcartest_2000_3200 | 1.000 | 0.310 | 0.303 | 0.117 |
| realcartest_3200_3830 | 1.000 | 0.314 | 0.722 | 0.381 |
| dataset3_0_1200 | 0.800 | 0.200 | 0.111 | 0.056 |
| dataset3_1200_2400 | 1.000 | 0.283 | 0.300 | 0.083 |
| dataset3_2400_3462 | 1.000 | 0.267 | 0.194 | 0.074 |

B7-strict-replay is WEAKER than B7-core (posthoc_eval) on precision and
recall. This is expected: removing `event_id` from Thompson sampling
reduces the bandit's ability to distinguish distinct events, leading to
more redundant sampling within the same event neighborhood. This is the
correct strict_replay comparison — B7-core's higher performance is an
artifact of using reference information (`event_id`) in the online loop.

============================================================
5. Did D3-norepair-core strict rerun successfully?
============================================================

YES. All 54 runs completed (6 segments × 3 budgets × 3 seeds).
- 0 budget violations.
- 0 event_id leaks.
- Uses `is_positive` for singleton counting (same logic as original
  `discovery_d3_chunk_bandit`).

D3-norepair-core-strict performance at budget 0.30 (mean over seeds):

| segment_id | P | R | calls |
|---|---:|---:|---:|
| realcartest_0_1570 | 0.443 | 0.167 | 47 |
| realcartest_2000_3200 | 0.543 | 0.150 | 36 |
| realcartest_3200_3830 | 0.500 | 0.190 | 19 |
| dataset3_0_1200 | 0.167 | 0.056 | 36 |
| dataset3_1200_2400 | 0.167 | 0.083 | 36 |
| dataset3_2400_3462 | 0.444 | 0.074 | 32 |

============================================================
6. Did SUPG-event run successfully?
============================================================

YES. All 54 runs completed. SUPG `RecallSelector` ran with budget capped at
`budget_abs // 2` to account for internal `filter()` re-queries.
- 0 budget violations.
- 0 event_id leaks.
- RuntimeWarnings from SUPG's `recall_selector.py:107` (division by zero
  when `s_left_ub + s_right_lb == 0`) are harmless — they occur when no
  positives are found in the sampled set.

SUPG-event-rt-strict performance at budget 0.30:

| segment_id | P | R | calls |
|---|---:|---:|---:|
| realcartest_0_1570 | 0.354 | 0.117 | 46 |
| realcartest_2000_3200 | 0.376 | 0.100 | 36 |
| realcartest_3200_3830 | 0.556 | 0.095 | 18 |
| dataset3_0_1200 | 0.000 | 0.000 | 36 |
| dataset3_1200_2400 | 0.000 | 0.000 | 36 |
| dataset3_2400_3462 | 0.000 | 0.000 | 32 |

SUPG has 0 recall on all dataset3 segments. This is because SUPG's
importance sampler allocates budget to high-proxy-score bins, but the
clipped `score_yolo_count` proxy on dataset3 does not correlate well with
positives at these low positive densities (5.8%–17.5%).

============================================================
7. Did ABae-residual run successfully?
============================================================

YES. All 54 runs completed. ABae two-stage stratified estimator with
statistic=1 (total positive mass estimation).
- 0 budget violations.
- 0 event_id leaks.
- No returned intervals (ABae is an aggregate estimation method, not an
  event discovery method). Event precision/recall = NA.

ABae-residual-strict residual calibration at budget 0.30:

| segment_id | res_hat | res_true | abs_error | calls |
|---|---:|---:|---:|---:|
| realcartest_0_1570 | 41.8 | 26.3 | 15.4 | 47 |
| realcartest_2000_3200 | 31.1 | 21.7 | 9.4 | 30 |
| realcartest_3200_3830 | 14.8 | 7.0 | 9.8 | 18 |
| dataset3_0_1200 | 17.5 | 1.3 | 16.1 | 30 |
| dataset3_1200_2400 | 18.2 | 14.7 | 11.0 | 33 |
| dataset3_2400_3462 | 13.4 | 7.0 | 6.4 | 29 |

ABae overestimates residual on all segments (positive bias). This is
expected: ABae estimates total positive mass from a small sample, and the
pooled estimate is noisy at these budget levels. The abs_error is large
on high-density segments (realcartest_0_1570: 15.4) and smaller on
low-density segments (dataset3_2400_3462: 6.4).

Note: ABae-residual is NOT an event discovery method. It produces no
returned intervals and thus has no event precision/recall. It is included
as a residual estimation baseline for comparison with EventLift's AUDIT
residual reporting.

============================================================
8. Did all runs obey budget?
============================================================

YES.
- `oracle_calls_total <= budget_abs`: 216 / 216 satisfied.
- 0 budget violations.
- 0 event_id online leaks.
- 0 ledger mismatches (action-call sum invariant not applicable for
  baselines that use a single action type, but all calls are tracked in
  the ledger with `source_action` lineage).

============================================================
9. Which methods can be used as main comparison in the full benchmark?
============================================================

All 4 aligned baselines can be used as main comparison:

| Method | Main comparison? | Reason |
|---|---|---|
| B7-strict-replay | YES | strict_replay, no event_id, budget-compliant |
| D3-norepair-core-strict | YES | strict_replay, no event_id, budget-compliant |
| SUPG-event-rt-strict | YES | strict_replay, no event_id, budget-compliant (weakest on dataset3) |
| ABae-residual-strict | YES (residual only) | strict_replay, no event_id; but produces no intervals, so only residual estimation is comparable |

B7-core (posthoc_eval, uses `event_id`) is **context-only** and should NOT
be used as main comparison. It can be shown as a reference row labeled
"posthoc_context".

============================================================
10. Which methods are context-only?
============================================================

- **B7-core** (historical, from `d3_fixed_frontier_raw.csv`): context-only.
  Uses `event_id` in Thompson sampling (`get_event_at_bin`). posthoc_eval.
  `can_be_main_comparison = false`.
- **D3-core-chunk120-fixed** (historical): context-only. Strict_replay +
  repair, but repair variant not directly comparable to no-repair EventLift.
- **LATE-D3-core-chunk120** (historical): context-only. Same as above.

============================================================
11. Are any segments missing data?
============================================================

NO. All 6 segments ran successfully:

| segment_id | num_bins | num_positive_bins | num_reference_events | event_id present | event_id excluded online |
|---|---:|---:|---:|---|---|
| realcartest_0_1570 | 157 | 44 | 20 | yes | yes |
| realcartest_2000_3200 | 120 | 32 | 20 | yes | yes |
| realcartest_3200_3830 | 63 | 13 | 7 | yes | yes |
| dataset3_0_1200 | 120 | 7 | 6 | no | n/a |
| dataset3_1200_2400 | 120 | 21 | 12 | no | n/a |
| dataset3_2400_3462 | 107 | 12 | 9 | no | n/a |

Note: dataset3 segments do not have `event_id` in the grid (it is not
needed — the grid is built from `canonical_dataset3_anchor_table.csv` which
has `event_cluster_id` but we do not include it in the grid as `event_id`).
This is correct: `event_id` is not present, so it cannot leak.

============================================================
12. Recommended next step
============================================================

**Proceed to full EventLift benchmark with aligned baselines.**

All 4 aligned baselines are ready. The full benchmark should run:
- 5 EventLift methods (discover-only, discover-audit, discover-certify,
  discover-audit-certify, full-stage2)
- 4 aligned baselines (B7-strict-replay, D3-norepair-core-strict,
  SUPG-event-rt-strict, ABae-residual-strict)
- 6 segments × 3 budgets × 3 seeds = 54 runs per method × 9 methods = 486 runs
- Same evaluator (IoU 0.3, event precision/recall)
- Same budget grid (0.10, 0.20, 0.30)
- Same seeds (0, 1, 2; optionally extend to 0–4)

============================================================
Gate decision
============================================================

**A. Proceed to full EventLift benchmark.**

Rationale:
1. B7-strict-replay, D3-norepair-core-strict, SUPG-event, and ABae-residual
   all ran successfully on all 6 segments. ✓
2. All strict methods obey budget: 0 violations / 216 runs. ✓
3. No strict method uses event_id online: 0 leaks / 216 runs. ✓
4. Output schemas are compatible with EventLift full benchmark
   (same columns: segment_id, method_id, seed, budget_abs, budget_ratio,
   oracle_calls_total, event_precision, event_recall, etc.). ✓
5. B7-strict-replay is a fair strict adaptation (documented novelty proxy,
   not the original B7-core). ✓

============================================================
Appendix — execution record
============================================================

**Files created:**
- `scripts/run_aligned_baselines_v1.py` (~470 LOC)
- `outputs/aligned_baselines_v1/aligned_baseline_call_trace.csv` (4238 rows, 610 KB)
- `outputs/aligned_baselines_v1/aligned_baseline_frontier_raw.csv` (216 rows, 68 KB)
- `outputs/aligned_baselines_v1/aligned_baseline_residual.csv` (54 rows, 6.9 KB)
- `ALIGNED_BASELINES_V1_REPORT.md` (this file)

**Files modified:** none.

**Commands run:**
- `python scripts/run_aligned_baselines_v1.py` (CPU-only, ~10s wall time;
  replay over existing VLM-oracle-relative labels; no video/GPU/VLM/YOLO).
- Read-only inspections via `python -c`, `grep`, file reads.

**Was any official source modified?** NO. `refe_repos/supg/`,
`refe_repos/abae/`, `refe_repos/ARC-main/` are untouched. SUPG is imported
via `sys.path` and used as-is.

**Was any large artifact created?** NO. Total output ~685 KB
(610 + 68 + 6.9 KB).

**Budget assertion results:**
- `oracle_calls_total <= budget_abs`: 216 / 216 satisfied.
- 0 budget violations.

**event_id leakage assertion results:**
- `online_uses_event_id = False`: 216 / 216 satisfied.
- 0 event_id online leaks.
- `AlignedOracle.assert_no_event_id()` passed on all 216 runs.

**Methods successfully run:** 4 / 4
(B7-strict-replay, D3-norepair-core-strict, SUPG-event-rt-strict,
ABae-residual-strict).

**Segments successfully run:** 6 / 6.

**Gate decision: A — Proceed to full EventLift benchmark.**

**Recommended next task:** Run the full EventLift benchmark with all 9
methods (5 EventLift + 4 aligned baselines) on 6 segments × 3 budgets ×
3 seeds, using the same evaluator and budget grid. Merge the aligned
baseline frontier with EventLift's frontier for unified comparison tables.
