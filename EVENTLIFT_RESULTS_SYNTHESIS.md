# EventLift Results Synthesis

> Paper-facing result synthesis for EventLift-AQP full benchmark v1. All
> numbers are VLM-oracle-relative (source: `center10_vlm_oracle_events` /
> `reference_events` / `canonical_dataset3_anchor_table`), not human ground
> truth. No safe stopping, formal guarantee, or statistical bound is claimed
> (per `AGENTS.md`, `CLAIMS_LEDGER.md`). Track: strict_replay for all 9
> methods. B7-core (posthoc_eval) is context-only.

============================================================
1. Executive conclusion
============================================================

**EventLift-discover-certify** is the strongest supported variant. It
achieves the highest macro-average event recall (0.156) among all
strict-replay methods at budget 0.30, with competitive precision (0.358)
and the highest unique event coverage (2.222).

The effective contribution is **unified DISCOVER + CERTIFY** in a single
utility arbitration loop. CERTIFY improves precision on 4/6 segments and
recall on 2/6 segments, without hurting recall on any segment.

**AUDIT/residual reporting is limited.** AUDIT fires only on the dev
segment (17 calls out of 36 budget); on 5/6 segments it is never selected
because its utility is too low to compete with DISCOVER. Residual estimates
are uninformative when AUDIT doesn't fire. AUDIT is a diagnostic instrument,
not a main performance contribution.

**SUPPRESS is unsupported.** SUPPRESS was never selected in any of the 486
runs. SUPPRESS effectiveness is unproven and should be removed from the
main method claim.

**Safe stopping is not claimed.** All 486 runs abstain
(`stop_status = abstain_or_budget_exhausted`). The residual UCB is too
loose to issue a stop certificate at these sample sizes.

============================================================
2. RQ1: Strict-replay validity
============================================================

| Metric | Value |
|---|---|
| Total runs | 486 (9 methods × 6 segments × 3 budgets × 3 seeds) |
| Budget violations | 0 / 486 |
| event_id online leaks | 0 / 486 |
| EventLift action-sum mismatches | 0 / 270 |
| Non-strict-replay rows | 0 / 486 |

Methods included (all strict_replay):
1. EventLift-discover-only
2. EventLift-discover-audit
3. EventLift-discover-certify
4. EventLift-discover-audit-certify
5. EventLift-full-stage2
6. B7-strict-replay
7. D3-norepair-core-strict
8. SUPG-event-rt-strict
9. ABae-residual-strict (residual-only, no intervals)

**Why B7-strict-replay is the main B7 baseline:**
B7-core (`run_b7` in `run_frozen_cross_segment.py:329`) uses
`get_event_at_bin(grid, b)` which reads `event_id` from the grid for
Thompson sampling singleton counting. This is **posthoc_eval** — it uses
reference information (`event_id`) in the online selection loop. B7-core is
therefore **context-only** (`can_be_main_comparison = false`).

B7-strict-replay replaces `get_event_at_bin` with `is_positive` +
adjacency-based singleton counting: a positive bin is a "new online hit"
if it is not already inside or adjacent (within 1 bin) of an already-known
positive bin. This uses only `is_positive` and bin adjacency — no `event_id`,
no reference event boundaries. This is the correct strict_replay comparison.

Source: `ALIGNED_BASELINES_V1_REPORT.md` §3, `CLAIMS_LEDGER.md`,
`AGENTS.md` (oracle_replay_isolation_audit).

============================================================
3. RQ2: Main comparison
============================================================

See `table_main_comparison.csv` for full data. Summary at budget 0.30
(mean over seeds, macro-averaged across 6 segments):

| Method | P | R | cov | dup_rate | calls |
|---|---:|---:|---:|---:|---:|
| EventLift-discover-certify | 0.358 | **0.156** | **2.222** | 0.000 | 34.3 |
| EventLift-discover-audit-certify | 0.325 | 0.153 | 2.167 | 0.000 | 34.3 |
| EventLift-full-stage2 | 0.325 | 0.153 | 2.167 | 0.000 | 34.3 |
| D3-norepair-core-strict | **0.377** | 0.120 | 1.611 | NA | 34.3 |
| B7-strict-replay | 0.348 | 0.152 | 1.833 | NA | 34.3 |
| EventLift-discover-only | 0.270 | 0.140 | 2.056 | 0.000 | 34.3 |
| EventLift-discover-audit | 0.257 | 0.138 | 2.000 | 0.000 | 34.3 |
| SUPG-event-rt-strict | 0.214 | 0.052 | 0.833 | NA | 34.0 |
| ABae-residual-strict | NA | NA | NA | NA | 31.2 |

- **Best macro recall:** EventLift-discover-certify (0.156).
- **Best macro precision:** D3-norepair-core-strict (0.377), but with
  lower recall (0.120) and coverage (1.611).
- **Best precision-recall tradeoff:** EventLift-discover-certify (P=0.358,
  R=0.156) — highest recall among methods with precision > 0.30.
- **Best unique coverage:** EventLift-discover-certify (2.222).

**Where EventLift wins** (best P AND R combined):
- realcartest_0_1570: EventLift-discover-only R=0.283 (best).
- dataset3_2400_3462: EventLift-discover-certify P=0.500, R=0.222 (best both).

**Where EventLift loses:**
- realcartest_3200_3830: B7-strict-replay dominates (P=0.722, R=0.381).
- dataset3_1200_2400: B7-strict-replay (P=0.300, R=0.083).
- realcartest_2000_3200: D3-strict precision (0.543) but EventLift-discover-certify (0.497) is competitive.

============================================================
4. RQ3: CERTIFY effect
============================================================

See `table_certify_ablation.csv` for full data. Summary at budget 0.30
(mean over seeds):

**discover-certify vs discover-only:**

| segment_id | ΔP | ΔR | certify_success | certify_share |
|---|---:|---:|---:|---:|
| realcartest_2000_3200 | **+0.097** | +0.000 | 0.704 | 0.250 |
| realcartest_3200_3830 | **+0.106** | +0.000 | 0.333 | 0.105 |
| dataset3_1200_2400 | **+0.194** | **+0.056** | 0.556 | 0.056 |
| dataset3_2400_3462 | **+0.133** | **+0.037** | 0.167 | 0.042 |
| realcartest_0_1570 | +0.000 | +0.000 | 0.000 | 0.000 |
| dataset3_0_1200 | +0.000 | +0.000 | 0.000 | 0.000 |

- CERTIFY improves precision on **4/6 segments** (marked bold).
- CERTIFY improves recall on **2/6 segments** (dataset3_1200_2400, dataset3_2400_3462).
- CERTIFY does NOT hurt recall on any segment (ΔR ≥ 0 everywhere).
- CERTIFY does not fire on 2/6 segments (realcartest_0_1570, dataset3_0_1200)
  because DISCOVER doesn't find positive anchors early enough.
- certify_success_rate ranges from 0.167 to 0.704 when CERTIFY fires.
- certify_budget_share ranges from 0.042 to 0.250 — modest.

**discover-audit-certify vs discover-audit:**
- Identical ΔP/ΔR to discover-certify vs discover-only on 5/6 segments.
- On dev segment: ΔP = -0.023 (slight precision drop from tighter intervals
  missing IoU ≥ 0.3 threshold; recall unchanged).

**Conclusion: CERTIFY has cross-segment evidence and should remain in the
main method.** It is the primary performance contribution of EventLift.

============================================================
5. RQ4: AUDIT/residual effect
============================================================

See `table_audit_residual.csv` for full data.

**AUDIT firing frequency** (budget 0.30):

| segment_id | audit_calls (mean) | audit fires? |
|---|---:|---|
| realcartest_2000_3200 | 17.0 | YES |
| dataset3_1200_2400 | 0.7 | barely |
| realcartest_0_1570 | 0.0 | NO |
| realcartest_3200_3830 | 0.0 | NO |
| dataset3_0_1200 | 0.0 | NO |
| dataset3_2400_3462 | 0.0 | NO |

- AUDIT fires only on the dev segment (17/36 = 47% of budget).
- On 5/6 segments, AUDIT's utility is too low to compete with DISCOVER.
- **AUDIT is not yet cross-segment active.**

**Residual calibration** (budget 0.30, mean over all segments/seeds):

| Method | residual_hat | abs_error | audit_n |
|---|---:|---:|---:|
| EventLift-discover-audit | 4.4 | 16.5 | 2.9 |
| EventLift-discover-audit-certify | 4.6 | 17.6 | 2.6 |
| EventLift-full-stage2 | 4.6 | 17.6 | 2.6 |
| ABae-residual-strict | 22.8 | 11.4 | 31.2 |

- ABae-residual-strict has better-calibrated residual estimates (abs_error=11.4)
  because it dedicates all budget to stratified sampling (audit_n=31.2).
- EventLift's residual_hat is biased low (4.4–4.6) because AUDIT rarely fires,
  so the pooled estimate is based on very few samples.
- EventLift's residual_ucb is uninformative (≈ N_U) when AUDIT doesn't fire.

**No stop certificate is issued** because:
- `audit_n < 29` (n_min for p_ucb ≤ 0.10) on all 486 runs.
- Per `RC_AQP_PREFLIGHT.md` Gate 2, per-segment safe stopping is
  statistically weak at this scale.

**Conclusion: AUDIT is a diagnostic instrument, not a main performance
contribution.** Residual reporting is informative only when AUDIT fires
(dev segment). On 5/6 segments, the residual report is structurally
available but uninformative. This should be honestly reported as a
limitation.

============================================================
6. RQ5: SUPPRESS effect
============================================================

| Metric | Value |
|---|---|
| SUPPRESS selected count | 0 (across all 486 runs) |
| suppressed_bin_count (mean) | 0.0 |
| duplicate_rate (mean) | 0.0 |

SUPPRESS was never selected on any segment in any run. SUPPRESS utility is
computed but always lower than DISCOVER/CERTIFY alternatives. The
`covered` set already prevents re-queries structurally, so SUPPRESS's
marginal benefit is fully captured without it.

**Conclusion: SUPPRESS never fires and should be removed from the main
claim.** It may be mentioned in an appendix as a design element that was
tested but not activated at these budget scales.

============================================================
7. RQ6: Failure analysis
============================================================

**dataset3_0_1200** (7 positive / 120 bins = 5.8% density):
- All EventLift variants: P=0.000, R=0.000.
- B7-strict: P=0.111, R=0.056. D3-strict: P=0.167, R=0.056. SUPG: 0/0.
- This segment is nearly impossible at budget 36 (30% of 120 bins). The
  clipped `score_yolo_count` proxy does not correlate with positives.
- **No method achieves meaningful recall on this segment.** This is an
  honest failure that should be reported.

**Weak proxy on dataset3:**
- dataset3 uses `score_yolo_count` (clipped to non-negative) as proxy.
- This proxy has negative z-scores in its raw form and does not rank
  positives well at low positive densities.
- SUPG-event-rt-strict has 0 recall on all 3 dataset3 segments because its
  importance sampler allocates budget to high-proxy-score bins that don't
  contain positives.

**Where B7-strict wins:**
- realcartest_3200_3830 (short, high-density): B7's temporal expansion
  (k=3) is very effective. P=0.722, R=0.381 vs EventLift P=0.467, R=0.190.
  B7's expansion is more aggressive than EventLift's CERTIFY (depth=2).
- dataset3_1200_2400: B7-strict P=0.300, R=0.083. EventLift's CERTIFY
  helps here (P=0.194, R=0.056) but B7's chunk-bandit is more effective.

**Where EventLift wins:**
- realcartest_0_1570 (high-density, good proxy): EventLift R=0.283 (best).
  DISCOVER's sqrt(proxy) importance sampling is effective when the proxy
  correlates with positives.
- dataset3_2400_3462: EventLift-discover-certify P=0.500, R=0.222 (best
  both). CERTIFY's boundary expansion finds adjacent positives that other
  methods miss.

============================================================
8. Claim ledger
============================================================

See `table_claims_supported.csv` for the full table. Summary:

| Claim | Supported? | Allowed wording |
|---|---|---|
| Unified strict-replay oracle-call ledger | **SUPPORTED** | EventLift produces a full oracle-call ledger with source_action lineage; all 486 runs obey budget and use no event_id online. |
| EventLift-DC highest macro recall | **SUPPORTED** | EventLift-discover-certify achieves the highest macro-average event recall (0.156) among strict-replay methods at budget 0.30. |
| CERTIFY improves precision on 4/6 segments | **SUPPORTED** | CERTIFY improves precision on 4/6 segments without hurting recall on any segment. |
| CERTIFY improves recall on 2/6 segments | **SUPPORTED** | CERTIFY also improves recall on 2/6 segments via boundary expansion. |
| AUDIT cross-segment usefulness | **NOT SUPPORTED** | AUDIT is not yet cross-segment active; fires only on dev segment. |
| SUPPRESS effectiveness | **NOT SUPPORTED** | SUPPRESS effectiveness is unproven; never selected in any run. |
| Safe stopping | **NOT SUPPORTED** | Safe stopping is not claimed; system abstains when bounds are too loose. |
| Superiority over B7-core-posthoc | **NOT SUPPORTED** | No claim against B7-core-posthoc; B7-strict-replay is the fair comparison. |
| Human-ground-truth performance | **NOT SUPPORTED** | All results are VLM-oracle-relative, not human ground truth. |
| EventLift dominates all baselines | **NOT SUPPORTED** | EventLift wins on 2/6 segments; loses on 2/6; no method dominates. |
| ABae-residual better calibrated | **SUPPORTED** | ABae-residual-strict has better-calibrated residual estimates but produces no intervals. |

============================================================
9. Recommended paper framing
============================================================

**Main method:** EventLift-discover-certify (DISCOVER + CERTIFY in unified
utility loop). This is the variant with the strongest supported evidence:
highest macro recall, CERTIFY improves precision on 4/6 segments.

**Secondary diagnostic:** AUDIT/residual reporting. Frame as a diagnostic
instrument that is structurally available but only informative when AUDIT
fires (dev segment). Do NOT claim it as a main performance contribution.
Report honestly that AUDIT is not cross-segment active.

**SUPPRESS:** Remove from main text. Mention only in an appendix as an
inactive action that was tested but never selected at these budget scales.

**No safe stopping claim:** Explicitly state that all runs abstain and
that safe stopping is not supported at these sample sizes.

**Main baselines:**
- B7-strict-replay (fair strict B7 comparison)
- D3-norepair-core-strict (strict_replay chunk-bandit)
- SUPG-event-rt-strict (record-selection adapter)

**Residual table only:**
- ABae-residual-strict (better calibrated but no intervals)

**Context-only reference (not main comparison):**
- B7-core-posthoc (uses event_id online; context-only per AGENTS.md)

**Paper structure recommendation:**
1. Problem setup: event-level AQP with limited oracle budget
2. Method: unified DISCOVER + CERTIFY utility arbitration
3. Experimental setup: 6 segments, 3 budgets, 3 seeds, VLM-oracle-relative
4. Main results table (Table A / `table_main_comparison.csv`)
5. CERTIFY ablation (Table B / `table_certify_ablation.csv`)
6. Segment winners (Table D / `table_segment_winners.csv`)
7. Residual reporting (Table C / `table_audit_residual.csv`) — honestly
   report AUDIT limitation
8. Limitations: SUPPRESS inactive, AUDIT not cross-segment, dataset3_0_1200
   failure, no safe stopping, VLM-oracle-relative only

============================================================
Appendix — files and execution
============================================================

**Files created:**
- `EVENTLIFT_RESULTS_SYNTHESIS.md` (this file)
- `outputs/eventlift_full_benchmark_v1/table_main_comparison.csv`
- `outputs/eventlift_full_benchmark_v1/table_certify_ablation.csv`
- `outputs/eventlift_full_benchmark_v1/table_audit_residual.csv`
- `outputs/eventlift_full_benchmark_v1/table_segment_winners.csv`
- `outputs/eventlift_full_benchmark_v1/table_claims_supported.csv`

**Files modified:** none.

**Commands run:** read-only data analysis via `python3` (pandas queries on
existing benchmark CSVs). No experiments were run. No parameters were tuned.
No benchmark outputs were modified.

**Was any experiment run?** NO. This is a synthesis document based on
existing `outputs/eventlift_full_benchmark_v1/` data.

**Recommended next paper section to write:** Results & Analysis section,
starting with the main comparison table (`table_main_comparison.csv`) and
the CERTIFY ablation table (`table_certify_ablation.csv`), followed by
the honest limitations subsection.
