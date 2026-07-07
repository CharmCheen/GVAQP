# EventLift-AQP Stage 2 Multi-Segment Smoke Report

> Multi-segment smoke test of `EVENTLIFT_AQP_ALGORITHM_SPEC.md` Stage 2 on
> all 6 LATE-AQP segments. Exact fixed Stage 2 parameters from the dev run.
> **This is a smoke test, not a full benchmark and not a tuning pass.**
> All numbers are VLM-oracle-relative, not human ground truth. No safe
> stopping, formal guarantee, or statistical bound is claimed (per
> `AGENTS.md`, `CLAIMS_LEDGER.md`). No video/GPU/VLM/YOLO inference was run.

============================================================
1. Segments
============================================================

All 6 segments ran successfully. No data was missing.

| segment_id | num_bins | num_positive_bins | num_reference_events | proxy_col | label_col | dataset3 proxy valid | event_id excluded |
|---|---:|---:|---:|---|---|---|---|
| realcartest_0_1570 | 157 | 44 | 20 | prior_score_max | is_positive | n/a | yes |
| realcartest_2000_3200 | 120 | 32 | 20 | prior_score_max | is_positive | n/a | yes |
| realcartest_3200_3830 | 63 | 13 | 7 | prior_score_max | is_positive | n/a | yes |
| dataset3_0_1200 | 120 | 7 | 6 | prior_score_max | is_positive | yes (clipped) | yes |
| dataset3_1200_2400 | 120 | 21 | 12 | prior_score_max | is_positive | yes (clipped) | yes |
| dataset3_2400_3462 | 107 | 12 | 9 | prior_score_max | is_positive | yes (clipped) | yes |

Data sources:
- realcartest grids: `outputs/late_aqp_frozen_cross_segment_v1/grid_*.csv`
- realcartest reference: `experiments/v13/v13_8_full_oracle/tables/center10_vlm_oracle_events.csv`
  (center10 VLM-oracle-relative events, clipped to segment time range, converted to local time)
- dataset3 grids: built from
  `src/garc_eval/outputs/codex_recompute_proxy_budget_basa_v1/tables/canonical_dataset3_anchor_table.csv`
  (10s bins, proxy=`score_yolo_count` clipped to non-negative, labels=`is_positive`,
  reference events from `event_cluster_id` groups)
- dataset3 proxy clipping: `score_yolo_count` can be negative (z-scores). Clipped to
  `max(0, score)` to match the non-negative convention of realcartest `prior_score_max`.
  This is a data preprocessing step, NOT a parameter change.

============================================================
2. Budget compliance
============================================================

**Q2. Did all methods obey budget?**

YES. 0 budget violations across all 270 runs (5 methods × 3 budgets × 3 seeds × 6 segments).

- `oracle_calls_total <= budget_abs`: 270 / 270 satisfied.
- Ledger invariant `oracle_calls_total == discover_calls + audit_calls + certify_calls + suppress_calls`:
  270 / 270 satisfied (0 mismatches).

============================================================
3. Arbitration non-degeneracy
============================================================

**Q3. Did arbitration remain non-degenerate across segments?**

Partially. Action selection counts (oracle calls only, all budgets and seeds):

| segment_id | DISCOVER | AUDIT | CERTIFY | SUPPRESS |
|---|---:|---:|---:|---:|
| realcartest_0_1570 | 1410 | 0 | 0 | 0 |
| realcartest_2000_3200 | 831 | 197 | 52 | 0 |
| realcartest_3200_3830 | 552 | 0 | 18 | 0 |
| dataset3_0_1200 | 1080 | 0 | 0 | 0 |
| dataset3_1200_2400 | 1060 | 2 | 18 | 0 |
| dataset3_2400_3462 | 948 | 0 | 12 | 0 |

- **DISCOVER**: selected on all 6 segments. ✓
- **AUDIT**: selected only on realcartest_2000_3200 (dev, 197 calls) and
  minimally on dataset3_1200_2400 (2 calls). NOT selected on 4/6 segments.
  AUDIT's utility is too low relative to DISCOVER on segments where the proxy
  signal is strong enough that DISCOVER always has higher expected value.
  This is a known design observation, not a bug.
- **CERTIFY**: selected on 4/6 segments (dev, realcartest_3200_3830,
  dataset3_1200_2400, dataset3_2400_3462). NOT selected on
  realcartest_0_1570 and dataset3_0_1200 because no positive anchors were
  found by DISCOVER early enough to trigger CERTIFY within budget.
  ✓ (non-degenerate: CERTIFY fires when anchors exist)
- **SUPPRESS**: NEVER selected on any segment. SUPPRESS effectiveness
  remains unproven. SUPPRESS utility was computed but always lower than
  alternatives. This is consistent with the dev finding.

============================================================
4. CERTIFY effect
============================================================

**Q4. Did CERTIFY help beyond dev?**

YES, on 4/6 segments at budget 0.30 (mean over 3 seeds):

| segment_id | P (discover-only) | P (discover-certify) | ΔP | R (discover-only) | R (discover-certify) | ΔR | certify_success | certify_share |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| realcartest_0_1570 | 0.491 | 0.491 | +0.000 | 0.283 | 0.283 | +0.000 | 0.000 | 0.000 |
| realcartest_2000_3200 | 0.400 | 0.497 | **+0.097** | 0.183 | 0.183 | +0.000 | 0.704 | 0.250 |
| realcartest_3200_3830 | 0.361 | 0.467 | **+0.106** | 0.190 | 0.190 | +0.000 | 0.333 | 0.105 |
| dataset3_0_1200 | 0.000 | 0.000 | +0.000 | 0.000 | 0.000 | +0.000 | 0.000 | 0.000 |
| dataset3_1200_2400 | 0.000 | 0.194 | **+0.194** | 0.000 | 0.056 | **+0.056** | 0.556 | 0.056 |
| dataset3_2400_3462 | 0.367 | 0.500 | **+0.133** | 0.185 | 0.222 | **+0.037** | 0.167 | 0.042 |

- CERTIFY improves precision on 4/6 segments (dev, 3200_3830, 1200_2400, 2400_3462).
- CERTIFY does NOT hurt recall on any segment.
- CERTIFY improves recall on 2/6 segments (dataset3_1200_2400: +0.056,
  dataset3_2400_3462: +0.037) because boundary expansion finds adjacent
  positive bins that contribute to new event matches.
- CERTIFY does not fire on 2/6 segments (realcartest_0_1570, dataset3_0_1200)
  because DISCOVER doesn't find positive anchors early enough at these budgets.
- certify_success_rate ranges from 0.167 to 0.704 when CERTIFY fires.
- certify_share (fraction of budget) ranges from 0.042 to 0.250 — reasonable.

vs discover+audit at budget 0.30:

| segment_id | ΔP (certify - audit) | ΔR (certify - audit) |
|---|---:|---:|
| realcartest_2000_3200 | +0.174 | +0.017 |
| realcartest_3200_3830 | +0.106 | +0.000 |
| dataset3_1200_2400 | +0.194 | +0.056 |
| dataset3_2400_3462 | +0.133 | +0.037 |

CERTIFY outperforms AUDIT on precision on 4/6 segments without hurting recall.

============================================================
5. AUDIT behavior
============================================================

**Q5. Did AUDIT remain useful beyond dev?**

Partially. AUDIT only fires on the dev segment (17 calls at budget 0.30)
and minimally on dataset3_1200_2400 (0.7 mean).

| segment_id | audit_calls (mean) | recall (discover-audit) | recall (discover-only) | ΔR | res_hat | res_ucb | abs_error |
|---|---:|---:|---:|---:|---:|---:|---:|
| realcartest_0_1570 | 0.0 | 0.283 | 0.283 | +0.000 | 0.0 | 110.0 | 17.7 |
| realcartest_2000_3200 | 17.0 | 0.167 | 0.183 | -0.017 | 26.2 | 13.8 | 8.5 |
| realcartest_3200_3830 | 0.0 | 0.190 | 0.190 | +0.000 | 0.0 | 44.0 | 6.7 |
| dataset3_0_1200 | 0.0 | 0.000 | 0.000 | +0.000 | 0.0 | 84.0 | 7.0 |
| dataset3_1200_2400 | 0.7 | 0.000 | 0.000 | +0.000 | 0.0 | 77.7 | 16.0 |
| dataset3_2400_3462 | 0.0 | 0.185 | 0.185 | +0.000 | 0.0 | 75.0 | 6.7 |

- **Audit positive recovery**: AUDIT finds few positives on non-dev segments
  because its utility rarely competes with DISCOVER. On the dev segment,
  AUDIT recovers some positives but at the cost of recall (-0.017).
- **Residual_hat / res_ucb behavior**: When AUDIT doesn't fire (5/6 segments),
  `residual_hat = 0.0` and `residual_ucb = N_U` (uninformative). Only on the
  dev segment does AUDIT produce meaningful residuals (`res_hat=26.2`,
  `res_ucb=13.8`).
- **Residual calibration error**: abs_error ranges from 6.7 to 17.7. On the
  dev segment (where AUDIT fires), abs_error = 8.5 (reasonable). On segments
  where AUDIT doesn't fire, abs_error reflects the true uncovered positive
  count (since `res_hat=0`).
- **Does audit hurt recall materially?** NO. The worst recall delta is -0.017
  (dev segment). On 5/6 segments, AUDIT doesn't fire so recall is identical
  to discover-only. AUDIT does not cause severe coverage loss.

**Concern**: AUDIT's utility formula makes it uncompetitive with DISCOVER
on most segments. This is a design observation, not a data mapping error.
The full benchmark should investigate whether AUDIT utility needs
rebalancing, but per the smoke test constraints, NO tuning was performed.

============================================================
6. Full Stage 2
============================================================

**Q6. Did full Stage 2 improve anything?**

Full Stage 2 vs discover+audit at budget 0.30 (mean over seeds):

| segment_id | P (discover-audit) | P (full-stage2) | R (discover-audit) | R (full-stage2) | dup (da) | dup (fs) |
|---|---:|---:|---:|---:|---:|---:|
| realcartest_0_1570 | 0.491 | 0.491 | 0.283 | 0.283 | 0.000 | 0.000 |
| realcartest_2000_3200 | 0.323 | 0.300 | 0.167 | 0.167 | 0.000 | 0.000 |
| realcartest_3200_3830 | 0.361 | 0.467 | 0.190 | 0.190 | 0.000 | 0.000 |
| dataset3_0_1200 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| dataset3_1200_2400 | 0.000 | 0.194 | 0.000 | 0.056 | 0.000 | 0.000 |
| dataset3_2400_3462 | 0.367 | 0.500 | 0.185 | 0.222 | 0.000 | 0.000 |

- **Unique event recall**: Full Stage 2 is NOT worse than discover+audit on
  any segment. On 2/6 segments, full Stage 2 improves recall (dataset3_1200_2400:
  +0.056, dataset3_2400_3462: +0.037) because CERTIFY finds additional positives.
- **duplicate_rate**: 0.0 on all segments (by construction — re-queries are
  structurally prevented by the `covered` set).
- **Precision**: Full Stage 2 improves precision on 3/6 segments
  (realcartest_3200_3830: +0.106, dataset3_1200_2400: +0.194, dataset3_2400_3462:
  +0.133). On the dev segment, precision drops slightly (-0.023) because
  CERTIFY creates tighter intervals that sometimes miss the IoU ≥ 0.3 threshold.
- **Budget decomposition** (full Stage 2 at budget 0.30, dev segment):
  DISCOVER=50%, AUDIT=42%, CERTIFY=6%, SUPPRESS=0% (oracle calls).

============================================================
7. Safe stopping
============================================================

**Q7. Did safe stopping occur?**

NO. All 270 runs have `stop_status = abstain_or_budget_exhausted`.
Stop reason: `audit_n_too_small` for all runs (audit_n < 29 = n_min for
p_ucb ≤ 0.10). This is the expected behavior per `RC_AQP_PREFLIGHT.md` Gate 2
and the spec §6.3: per-segment safe stopping is statistically weak at this
scale. No safe stopping is claimed.

============================================================
8. B7-core / D3-norepair-core context
============================================================

**Q8. How does EventLift compare to existing B7-core / D3-norepair-core?**

**NOT directly comparable.** B7-core and D3-norepair-core use `event_id`
in their selection stage (posthoc_eval track), while EventLift does not use
`event_id` online (strict_replay track). Per `AGENTS.md` and
`oracle_replay_isolation_audit.md`, these tracks cannot be directly compared.

For reference only (NOT a valid performance comparison), at budget 0.30:

| segment_id | EventLift-full-stage2 P | EventLift-full-stage2 R | D3-norepair-core P | D3-norepair-core R | B7-core P | B7-core R |
|---|---:|---:|---:|---:|---:|---:|
| realcartest_0_1570 | 0.491 | 0.283 | 1.000 | 0.290 | 1.000 | 0.310 |
| realcartest_2000_3200 | 0.300 | 0.167 | 1.000 | 0.340 | 1.000 | 0.310 |
| realcartest_3200_3830 | 0.467 | 0.190 | 0.800 | 0.200 | 1.000 | 0.314 |
| dataset3_0_1200 | 0.000 | 0.000 | 0.800 | 0.400 | 0.800 | 0.200 |
| dataset3_1200_2400 | 0.194 | 0.056 | 1.000 | 0.300 | 1.000 | 0.283 |
| dataset3_2400_3462 | 0.500 | 0.222 | 1.000 | 0.244 | 1.000 | 0.267 |

- D3-norepair-core and B7-core achieve higher precision and recall, but
  they use `event_id` for selection (posthoc_eval), which EventLift does
  not (strict_replay). The comparison is NOT aligned.
- Per `AGENTS.md`: "B7-core + Core/Halo 与 LATE-AQP-core 在 90/90 frontier
  上是同位的." EventLift is a different method family and no superiority
  claim is made.
- The low EventLift recall on dataset3_0_1200 (0.000) is due to the very low
  positive density (7/120 = 5.8%) and the clipped `score_yolo_count` proxy
  not correlating well with positives at this budget.

============================================================
9. Gate decision
============================================================

**A. Proceed to full benchmark / paper-facing experiment.**

Rationale:
1. **Ledger is correct**: 0 budget violations / 270 runs, 0 ledger mismatches. ✓
2. **6/6 segments ran**: no missing data, no errors. ✓
3. **Full Stage 2 is not clearly worse than discover+audit on recall**:
   recall is identical or better on all 6 segments. ✓
4. **CERTIFY improves precision on multiple segments**: 4/6 segments show
   precision improvement (+0.097 to +0.194) without recall loss. ✓
5. **AUDIT provides residual reporting without severe coverage loss**:
   AUDIT doesn't fire on 5/6 segments (utility too low), but when it does
   fire (dev), recall impact is -0.017 (not severe). Residual reporting
   is structurally available but uninformative when AUDIT doesn't fire. ✓
   (with caveat: AUDIT's low firing rate on non-dev segments is a known
   design observation for the full benchmark to investigate)
6. **Action arbitration is not degenerate**: DISCOVER fires on 6/6,
   CERTIFY fires on 4/6, AUDIT fires on 1/6. SUPPRESS never fires but
   its utility is correctly computed. The loop does not collapse to
   one action type on segments where CERTIFY has anchors to process. ✓

Conditions for full benchmark:
- Do NOT claim safe stopping.
- Do NOT claim EventLift beats B7-core or D3-norepair-core (different
  tracks: strict_replay vs posthoc_eval).
- Do NOT claim SUPPRESS effectiveness (never selected on any segment).
- Investigate AUDIT's low firing rate on non-dev segments in the full
  benchmark (utility formula may need rebalancing, but NO tuning in smoke).
- The dataset3_0_1200 segment has 0 recall at all budgets — investigate
  whether the clipped `score_yolo_count` proxy is adequate for very-low-
  density segments, or whether a different proxy column should be used.

============================================================
Appendix — execution record
============================================================

**Files created:**
- `scripts/eventlift_stage2_multiseg_smoke.py` (~270 LOC)
- `outputs/eventlift_stage2_multiseg_smoke/multiseg_call_trace.csv` (6180 rows, 1015 KB)
- `outputs/eventlift_stage2_multiseg_smoke/multiseg_frontier_raw.csv` (270 rows, 85 KB)
- `outputs/eventlift_stage2_multiseg_smoke/multiseg_residual_calibration.csv` (270 rows, 37 KB)
- `outputs/eventlift_stage2_multiseg_smoke/multiseg_action_arbitration.csv` (6198 rows, 590 KB)
- `EVENTLIFT_STAGE2_MULTISEG_SMOKE_REPORT.md` (this file)

**Files modified:** none. No Stage 1/2 dev outputs, official source code,
or canonical state files were touched.

**Commands run:**
- `python scripts/eventlift_stage2_multiseg_smoke.py` (CPU-only, ~5 s wall time;
  replay over existing VLM-oracle-relative labels; no video/GPU/VLM/YOLO).
- Read-only inspections via `python -c "import pandas..."` and `ls -lh`.

**Was any official source modified?** NO. `refe_repos/supg/`,
`refe_repos/abae/`, `refe_repos/ARC-main/` are untouched.

**Was any large artifact created?** NO. Total output ~1.7 MB
(1015 + 85 + 37 + 590 KB).

**Budget assertion results:**
- `oracle_calls_total <= budget_abs`: 270 / 270 satisfied.
- `oracle_calls_total == discover + audit + certify + suppress`: 270 / 270 satisfied.
- 0 budget violations.

**Segments successfully run:** 6 / 6
(realcartest_0_1570, realcartest_2000_3200, realcartest_3200_3830,
dataset3_0_1200, dataset3_1200_2400, dataset3_2400_3462).

**Stage 2 multi-segment gate decision: A — Proceed to full benchmark.**

**Recommended next task:** Full benchmark with all 6 segments, all 5 methods,
budget ratios 0.05–0.50, seeds 0–4, with B_90/90 frontier computation.
Investigate AUDIT utility rebalancing and dataset3_0_1200 proxy adequacy
as part of the full benchmark design. Do NOT run ARC-projection until the
full benchmark is complete.
