# EventLift-AQP Full Benchmark Plan & Baseline-Alignment Plan

> Paper-facing full benchmark design for EventLift Stage 2. This document
> does NOT run the benchmark; it defines the frozen method set, frozen
> parameters, baseline alignment status, analysis tables, decision rules,
> and claim boundaries. All prior results are VLM-oracle-relative, not
> human ground truth. No safe stopping, formal guarantee, or statistical
> bound is claimed (per `AGENTS.md`, `CLAIMS_LEDGER.md`).

============================================================
1. Current evidence summary
============================================================

**Stage 1 dev** (`EVENTLIFT_STAGE1_DEV_REPORT.md`):
- Segment: realcartest_2000_3200 (120 bins, 32 positive, 20 reference events).
- Methods: SUPG-event adapter, ABae-residual adapter, EventLift DISCOVER+AUDIT.
- 36 runs (4 methods × 3 budgets × 3 seeds), 0 budget violations.
- Gate decision: A (proceed to Stage 2).

**Stage 2 dev** (`EVENTLIFT_STAGE2_DEV_REPORT.md`):
- Segment: realcartest_2000_3200.
- Added CERTIFY and SUPPRESS into the unified utility loop.
- 45 runs (5 methods × 3 budgets × 3 seeds), 0 budget violations.
- CERTIFY improves precision by +0.097 at budget 36 without hurting recall.
- SUPPRESS never selected (utility computed but always lower than alternatives).
- All runs abstain on stopping.
- Gate decision: A (proceed to multi-segment smoke).

**Stage 2 multi-segment smoke** (`EVENTLIFT_STAGE2_MULTISEG_SMOKE_REPORT.md`):
- All 6 LATE-AQP segments, 270 runs (5 methods × 3 budgets × 3 seeds × 6 segments).
- 0 budget violations, 0 ledger mismatches.
- CERTIFY improves precision on 4/6 segments (+0.097 to +0.194) without hurting
  recall; also improves recall on 2 dataset3 segments.
- AUDIT only fires on the dev segment (utility too low to compete with DISCOVER
  on 5/6 segments).
- SUPPRESS never selected on any segment.
- All 270 runs abstain on stopping.
- Gate decision: A (proceed to full benchmark).

**What is established:**
- The unified utility loop with DISCOVER/CERTIFY is non-degenerate: both fire
  when anchors exist, and the budget split is reasonable.
- CERTIFY has cross-segment evidence: it improves precision on 4/6 segments
  at budget 0.30 without hurting recall.
- The oracle-call ledger is correct: budget invariant and action-sum invariant
  hold on all 270+45+36 = 351 runs to date.
- The system produces a full oracle-call ledger with `source_action` lineage
  and a residual uncertainty report.

**What is NOT established:**
- AUDIT is not yet cross-segment active: its utility formula makes it
  uncompetitive with DISCOVER on 5/6 segments. Residual reporting is
  structurally available but uninformative when AUDIT doesn't fire.
- SUPPRESS effectiveness is unproven: SUPPRESS was never selected on any
  segment in any run to date.
- Safe stopping is not supported: all runs abstain (audit_n < 29 at all
  budgets). No formal guarantee or certificate is claimed.
- B7/D3 comparison is not aligned yet: B7-core uses `event_id` in its
  selection stage (posthoc_eval track), while EventLift does not
  (strict_replay track). D3-norepair-core IS strict_replay aligned but
  the evaluation metric (IoU threshold, event precision/recall definition)
  must be verified as identical.

Required wording (per `AGENTS.md`, `CLAIMS_LEDGER.md`):
- CERTIFY has cross-segment evidence.
- AUDIT is not yet cross-segment active.
- SUPPRESS effectiveness is unproven.
- Safe stopping is not supported; all runs abstain.
- B7/D3 comparison is not aligned yet.

============================================================
2. Frozen method set
============================================================

The full benchmark will run exactly these 5 EventLift methods:

1. `eventlift_discover_only` — DISCOVER only (ablation control).
2. `eventlift_discover_audit` — DISCOVER + AUDIT (Stage 1 control + residual).
3. `eventlift_discover_certify` — DISCOVER + CERTIFY (CERTIFY ablation).
4. `eventlift_discover_audit_certify` — DISCOVER + AUDIT + CERTIFY.
5. `eventlift_full_stage2` — DISCOVER + AUDIT + CERTIFY + SUPPRESS.

Optional baselines (if aligned, see §4):

6. `SUPG-event` — SUPG adapter for event-level AQP (from Stage 1, strict_replay).
7. `ABae-residual` — ABae adapter with residual estimation (from Stage 1, strict_replay).
8. `B7-core-strict-replay` — B7 with `event_id` removed from selection (requires
   alignment, see §4). If not alignable, marked context-only.
9. `D3-norepair-core-strict-replay` — D3-norepair-core is already strict_replay
   (uses `is_positive` label, not `event_id`, in `discovery_d3_chunk_bandit`).
   Requires evaluation metric alignment.

ARC-projection: restricted appendix only, NOT a main semantic-task baseline.
ARC operates on clip-level tasks with different oracle semantics. Any ARC
comparison would be in a separate appendix with explicit task-mapping caveats.

============================================================
3. Frozen parameters
============================================================

Extracted from `scripts/eventlift_stage2_dev.py` and
`scripts/eventlift_stage2_multiseg_smoke.py`. These are the exact parameters
used in the dev and multi-segment smoke runs. They must NOT be changed or tuned.

**Utility hyperparameters (fixed, NOT tuned — per spec §5.1):**
```
ETA    = 1.0    # oracle cost weight
LAMBDA = 0.5    # residual uncertainty reduction weight
GAMMA  = 0.3    # dual-purpose positive recovery weight
KAPPA  = 0.5    # opportunity cost weight
OMEGA  = 0.3    # over-suppression risk weight
```

**CERTIFY parameters (fixed):**
```
CERTIFY_MAX_DEPTH = 2    # max bins left and right to check around an anchor
```

**SUPPRESS parameters (fixed):**
```
SUPPRESS_RADIUS = 2    # bins to downweight on each side of a certified interval
```

**AUDIT stratum definition (fixed):**
```
NUM_STRATA = 5    # number of proxy-score strata for AUDIT sampling
```
Strata are assigned by ranking uncovered bins by proxy score, then dividing
into `NUM_STRATA` equal-size groups. AUDIT selects the stratum with highest
`LAMBDA * p_ucb_s * n_in_stratum + GAMMA * 0.1 * n_in_stratum`.

**Budget ratios (fixed):**
```
0.10, 0.20, 0.30
```
Optional finer grid for paper frontier plots (if cheap): 0.05, 0.15, 0.25, 0.40, 0.50.
The finer grid is for frontier visualization only, NOT for tuning.

**Seeds (fixed):**
```
0, 1, 2  (smoke test set)
```
Full benchmark should use seeds 0–4 (5 seeds) for stable means. If runtime
remains <60s, use seeds 0–9 (10 seeds) for paper-grade stability.

**IoU threshold (fixed):**
```
IOU_THRESHOLD = 0.3    # event-level IoU threshold for precision/recall
```

**Bin size (fixed):**
```
BIN_SIZE = 10.0    # seconds per atomic bin
```

**Stop/abstain thresholds (fixed):**
```
n_min_for_stop = 29         # minimum audit_n for p_ucb <= 0.10
res_ucb_threshold = 0.10 * N_U    # residual UCB must be <= 10% of uncovered bins
ALPHA = 0.05              # binomial UCB confidence level
```

**Proxy column (fixed):**
```
PROXY_COL = "prior_score_max"
LABEL_COL = "is_positive"
```
For dataset3 segments, proxy is `score_yolo_count` clipped to non-negative
(data preprocessing, not a parameter change).

**Discovery importance sampling (fixed):**
```
DISCOVER uses sqrt(proxy) importance weighting within selected component.
Component threshold: theta = median(proxy_scores).
Random seed: seed * 100003 + oracle.calls (per-call RNG).
```

**Event evaluation (fixed):**
```
Event precision = fraction of returned intervals with IoU >= 0.3 vs reference.
Event recall = fraction of reference events with IoU >= 0.3 vs returned intervals.
Returned intervals are built from certified intervals + grouped positive bins.
```

============================================================
4. Baseline alignment plan
============================================================

**Key finding (from code inspection):**

B7-core (`run_b7` in `run_frozen_cross_segment.py:329`) uses
`get_event_at_bin(grid, b)` (line 342) which reads `event_id` from the grid
to track singleton positive events per chunk for Thompson sampling. This
makes B7-core **posthoc_eval** (uses `event_id` in selection).

D3-norepair-core (`discovery_d3_chunk_bandit` in
`run_event_diverse_discovery.py:349`) uses `bin_to_row[b]["is_positive"]`
(line 381) for singleton counting, NOT `event_id`. This makes D3-norepair-core
**strict_replay** (does not use `event_id` in selection).

Source: `outputs/late_aqp_event_diverse_discovery_v1/run_event_diverse_discovery.py:1075-1076`,
`1593-1594` explicitly state:
- "B7-core uses the existing B7 temporal expansion + Core/Halo; it is
  posthoc_eval because it uses event_id."
- "D3-norepair-core uses strict-replay chunk-bandit discovery (no event_id)
  + Core/Halo; no repair."

| Baseline | Existing status | Aligned? | Needed action | Can be main comparison? |
|---|---|---|---|---|
| B7-core | posthoc_eval (uses `event_id` in Thompson sampling) | NO | Replace `get_event_at_bin` with `is_positive`-based singleton counting in `run_b7`. Requires a new `run_b7_strict_replay()` that counts singletons by `is_positive` label instead of `event_id`. Cheap (code change ~20 lines, no video/GPU). | YES if aligned; otherwise context-only |
| D3-norepair-core | strict_replay (uses `is_positive`, not `event_id`) | PARTIALLY | Evaluation metric alignment: verify IoU threshold (0.3), event precision/recall definition, and budget definition match EventLift. D3 uses `compute_metrics()` from `run_frozen_cross_segment.py` which computes `event_recall` as `len(hit_event_ids) / n_ref` — same as EventLift. Budget definition: D3 uses absolute oracle calls, same as EventLift. | YES (main strict_replay comparison) |
| SUPG-event | strict_replay (adapter from Stage 1, no `event_id`) | YES | Already implemented in `scripts/eventlift_stage1_dev.py` as SUPG adapter. Needs to be run on all 6 segments with same budget/seed grid. | YES (adjacent-task baseline) |
| ABae-residual | strict_replay (adapter from Stage 1, no `event_id`) | YES | Already implemented in `scripts/eventlift_stage1_dev.py` as ABae adapter. Needs to be run on all 6 segments. | YES (adjacent-task baseline) |
| ARC-projection | n/a (clip-level task, different oracle semantics) | NO | Would require task-mapping from clip to event-level. Not a main baseline. | NO (appendix only) |

**Aligned strict-replay comparison set (if alignment is done):**
- EventLift-full-stage2 (strict_replay, no `event_id`)
- D3-norepair-core (strict_replay, no `event_id`) — already aligned
- SUPG-event (strict_replay, no `event_id`) — already aligned
- ABae-residual (strict_replay, no `event_id`) — already aligned
- B7-core-strict-replay (requires code change to remove `event_id`)

**Context-only comparison (not aligned, for reference):**
- B7-core (posthoc_eval, uses `event_id`) — context-only
- D3-core-chunk120-fixed (strict_replay + repair, uses `is_positive`) —
  context-only (repair variant, not directly comparable to no-repair EventLift)

**Alignment is cheap and safe:**
- B7-core strict-replay: ~20 line code change in `run_b7` to replace
  `get_event_at_bin` with `is_positive`-based counting. No video/GPU/VLM.
- D3-norepair-core: already aligned, just needs same-seed rerun on all 6
  segments with EventLift's budget grid and evaluator.
- SUPG-event / ABae-residual: already implemented in Stage 1 code, just
  need multi-segment rerun.

============================================================
5. Full benchmark design
============================================================

**Segments:** current 6 LATE-AQP segments
- realcartest_0_1570 (157 bins, 44 positive, 20 events)
- realcartest_2000_3200 (120 bins, 32 positive, 20 events, dev)
- realcartest_3200_3830 (63 bins, 13 positive, 7 events)
- dataset3_0_1200 (120 bins, 7 positive, 6 events)
- dataset3_1200_2400 (120 bins, 21 positive, 12 events)
- dataset3_2400_3462 (107 bins, 12 positive, 9 events)

**Budget ratios:** 0.10, 0.20, 0.30 (primary); 0.05, 0.15, 0.25, 0.40, 0.50
(optional, for frontier plots only, if cheap).

**Seeds:** 0, 1, 2, 3, 4 (5 seeds for stable means). If runtime <60s, extend
to 0–9.

**Labels:** VLM-oracle-relative only. No human ground truth.

**Online decision constraint:** No `event_id` in online decisions. `event_id`
and reference intervals used for final evaluation only.

**Per-call ledger:** Required for every run. Columns per §4 of the task spec
(segment_id, method_id, seed, budget_abs, call_idx, action_type, source_action,
bin_id, component_id, stratum_id, anchor_bin_id, proxy_score, oracle_label,
online_positive, added_to_returned_intervals, certified_interval,
suppressed_bins, cumulative_oracle_calls, budget_remaining,
residual_hat_before, residual_hat_after, notes).

**Budget assertions:** Required for every run:
- `oracle_calls_total <= budget_abs`
- `oracle_calls_total == discover_calls + audit_calls + certify_calls + suppress_calls`

**Primary metrics:**
- event_precision (IoU >= 0.3)
- event_recall (IoU >= 0.3)
- unique_event_coverage (count of reference events hit)
- duplicate_rate
- oracle_calls_by_action (DISCOVER / AUDIT / CERTIFY / SUPPRESS)
- certify_success_rate
- residual_hat / residual_ucb
- residual calibration error (abs_error = |residual_hat - true_uncovered_positives|)
- abstain_rate (fraction of runs with stop_status = abstain_or_budget_exhausted)
- false_stop_rate (only if any stop occurs; expected: 0)

**Expected runtime:** CPU-only, <60s for 5 EventLift methods × 6 segments ×
3 budgets × 5 seeds = 450 runs. With aligned baselines (D3-norepair-core,
SUPG-event, ABae-residual, B7-strict-replay): ~4 additional methods × same
grid = ~360 more runs. Total ~810 runs, estimated <5 min wall time.

============================================================
6. Main analysis tables
============================================================

**Table A: EventLift ablation frontier by budget**
- Rows: 5 EventLift methods
- Columns: budget_ratio (0.10, 0.20, 0.30), mean event_precision, mean event_recall,
  mean unique_event_coverage, mean oracle_calls_total
- Aggregation: mean over seeds, per segment (6 sub-tables) + macro-average

**Table B: CERTIFY effect by segment**
- Rows: 6 segments
- Columns: P(discover-only), P(discover-certify), ΔP, R(discover-only),
  R(discover-certify), ΔR, certify_success_rate, certify_budget_share
- Budget: 0.30 (primary), with 0.10/0.20 as secondary

**Table C: AUDIT selection and residual calibration**
- Rows: 6 segments × 3 budgets
- Columns: audit_calls (mean), audit_positive_n (mean), residual_hat (mean),
  residual_ucb (mean), abs_error (mean), signed_error (mean), stop_status
- Purpose: show where AUDIT fires and whether residual reporting is informative

**Table D: Budget decomposition by action**
- Rows: 5 EventLift methods × 6 segments
- Columns: D%, A%, C%, S% of oracle calls at budget 0.30
- Purpose: show arbitration non-degeneracy and budget allocation

**Table E: Aligned baseline comparison**
- Rows: 6 segments
- Columns: method (EventLift-full-stage2, D3-norepair-core, SUPG-event,
  ABae-residual, B7-strict-replay if aligned), event_precision, event_recall,
  oracle_calls
- Budget: 0.30 (primary)
- Track label: strict_replay for all methods in this table
- B7-core (posthoc_eval) shown separately as context-only

**Table F: Forbidden/unsupported claims ledger**
- Lists all claims that CANNOT be made from the benchmark results:
  - "EventLift achieves safe stopping" (FORBIDDEN: all runs abstain)
  - "SUPPRESS is effective" (FORBIDDEN: never selected)
  - "AUDIT consistently helps across segments" (FORBIDDEN unless evidence shows it)
  - "EventLift beats B7-core" (FORBIDDEN unless B7-strict-replay is aligned
    and EventLift wins on aligned comparison)
  - "Formal guarantee / certificate" (FORBIDDEN per AGENTS.md)
  - "Human ground truth recall" (FORBIDDEN: VLM-oracle-relative only)

============================================================
7. Decision rules after full benchmark
============================================================

**Proceed to paper claim only if ALL of:**
1. Budget ledger remains correct (0 violations, 0 mismatches across all runs).
2. CERTIFY improves precision or interval quality on multiple segments
   (at least 3/6 at budget 0.30).
3. Full EventLift does not materially reduce recall vs discover-only or
   discover+audit on any segment (ΔR >= -0.02).
4. Residual reporting is calibrated enough to be informative on at least
   the dev segment (abs_error < 50% of true uncovered positives).
5. Aligned baselines (D3-norepair-core at minimum) are included in Table E,
   or explicitly marked context-only if alignment fails.

**Re-scope if ANY of:**
1. CERTIFY gain disappears (ΔP < +0.03 on fewer than 3/6 segments at budget 0.30).
2. Recall drops materially (ΔR < -0.05 on any segment vs discover-only).
3. AUDIT remains inactive on 5/6 segments AND residual reporting is empty
   (residual_hat = 0 on 5/6 segments) — in this case, AUDIT is a pure budget
   tax and should be removed or redesigned.
4. Aligned B7/D3 dominate EventLift across all relevant metrics (precision
   AND recall AND oracle efficiency) on 4/6 segments — in this case,
   EventLift adds complexity without measurable gain.
5. SUPPRESS never fires AND CERTIFY has no cross-segment benefit — in this
   case, EventLift reduces to discover+audit and should be re-scoped.

============================================================
8. Claim boundary
============================================================

**Allowed claims:**
- EventLift proposes unified event-level AQP action arbitration.
- CERTIFY integrated into the unified loop improves precision in smoke tests
  and (if full benchmark confirms) in the full benchmark.
- The system produces a full oracle-call ledger and residual uncertainty report.
- Safe stopping is not claimed; the system abstains when bounds are too loose.
- SUPG/ABae/ARC cover adjacent tasks but require lifting/adaptation for this
  semantic-event setting.
- D3-norepair-core is a strict_replay baseline (does not use `event_id` in
  selection); B7-core is posthoc_eval (uses `event_id` in selection).

**Forbidden claims:**
- Guaranteed safe stopping (all runs abstain; no formal guarantee).
- EventLift is proven optimal (no optimality proof exists).
- SUPPRESS is effective (never selected on any segment to date).
- AUDIT consistently helps across segments (only fires on dev segment).
- EventLift beats B7/D3 before aligned baseline comparison (B7-core is
  posthoc_eval; comparison is not aligned until B7-strict-replay is implemented).
- ARC cannot handle clips (ARC handles clip-level tasks; the issue is
  task-mapping, not capability absence).
- SUPG/ABae/ARC are absent (they exist for adjacent tasks; EventLift lifts
  their ideas into the event-level setting).

============================================================
9. Next executable task
============================================================

**Recommended next task: A. Implement aligned B7/D3 strict-replay baselines.**

Rationale:
- D3-norepair-core is already strict_replay but needs to be rerun on all 6
  segments with EventLift's exact budget grid (0.10/0.20/0.30) and seed
  policy (0–4) using the same evaluator (IoU 0.3, event precision/recall).
  This is cheap (~20 min code + <1 min runtime).
- B7-core needs a `run_b7_strict_replay()` variant that replaces
  `get_event_at_bin` (which reads `event_id`) with `is_positive`-based
  singleton counting. This is a ~20 line code change, no video/GPU.
- SUPG-event and ABae-residual adapters already exist in Stage 1 code and
  need multi-segment rerun.
- Once all 4 aligned baselines are ready, the full benchmark (task B) can
  run all methods (5 EventLift + 4 baselines = 9 methods) in one shot
  with the same evaluator, same budget grid, same seeds.

**Exact next command:**
```
# Implement aligned baselines:
# 1. Create scripts/eventlift_aligned_baselines.py that:
#    a. Imports discovery_d3_chunk_bandit from run_event_diverse_discovery.py
#    b. Implements run_b7_strict_replay() (replaces get_event_at_bin with is_positive)
#    c. Imports SUPG-event and ABae-residual adapters from Stage 1
#    d. Runs all 4 baselines on 6 segments × 3 budgets × 5 seeds
#    e. Uses the same evaluator as EventLift (IoU 0.3, event precision/recall)
#    f. Outputs aligned_baseline_frontier_raw.csv with same schema as multiseg_frontier_raw.csv
# 2. Verify budget assertions and ledger invariants
# 3. Compare aligned baselines vs EventLift-full-stage2 on the same grid
```

**Unresolved risks:**
1. B7-strict-replay may perform worse than B7-core (posthoc_eval) because
   removing `event_id` from Thompson sampling reduces its information. This
   is expected and does NOT invalidate the comparison — it's the correct
   strict_replay comparison.
2. dataset3_0_1200 has 0 recall for all EventLift methods at all budgets due
   to very low positive density (7/120 = 5.8%) and weak proxy correlation.
   The full benchmark should report this honestly; it may be a segment where
   no method works well at these budgets.
3. AUDIT's low firing rate on non-dev segments may persist in the full
   benchmark. If so, AUDIT is a pure budget tax on 5/6 segments and should
   be flagged as a design issue for future work (not a tuning pass).
4. SUPPRESS may never fire in the full benchmark either. If so, SUPPRESS
   should be removed from the paper's main method description and mentioned
   only as a design element that was tested but not activated at these budgets.

============================================================
Appendix — files and commands
============================================================

**Files created:**
- `EVENTLIFT_FULL_BENCHMARK_PLAN.md` (this file)

**Files modified:** none.

**Commands run:** read-only inspections via `python -c`, `grep`, and file
reads. No benchmark was run. No video/GPU/VLM/YOLO inference.

**Was any official source modified?** NO.

**Was any large artifact created?** NO.

**Budget assertion results:** n/a (no benchmark run, only planning).

**Unresolved risks:** see §9 above (4 risks listed).

**Recommended next task:** A. Implement aligned B7/D3 strict-replay baselines
(see §9 for exact next command).
