# FINAL REPORT: LATE-AQP Algorithm v3 (Oracle-Relative)

## 1. What this round did

- Wrote the oracle-relative AQP problem statement.
- Instrumented a repair trace schema and reconstructed Ours-full traces from existing selection logs.
- Designed and simulated five audit-schedule variants (V2_static25 + four v3 schedules).
- Designed and simulated five repair-utility variants (U0_current + four v3 utilities).
- Discovered that dense VLM-oracle labels already exist at 2 s granularity for the full video.
- Generated an oracle-relative dense calibration plan that requires no new oracle calls or human annotation.
- Revised the claims ledger.

## 2. Oracle-relative definition

The problem is now explicitly framed as oracle-relative AQP:

- \( O_{\text{ref}} \) = existing VLM-oracle labels.
- All metrics are relative to \( O_{\text{ref}} \).
- Human annotation is an optional oracle provider, not a necessary condition.

## 3. Repair trace recoverability

- The schema is defined in `repair_trace_schema.md`.
- `repair_trace_events.csv` reconstructs Ours-full selected intervals for budgets 10, 20, 40, 80.
- Most lineage fields (`source_action`, `trigger_sample_id`, `repair_window_*`) are `unknown_not_logged` because the prior replay did not log them.
- `repair_trace_casebook.md` shows Ours-only, both-hit, and B7-only cases, but cannot causally attribute Ours gains to audit-triggered repair.

## 4. Audit schedule v3: does it fix budget=20?

| schedule | long-event recall@20 | long-event recall@40 | precision@40 |
|----------|---------------------:|---------------------:|-------------:|
| V2_static25 | 0.417 | 0.700 | 0.323 |
| V3_min_floor | 0.417 | 0.650 | 0.292 |
| V3_budget_aware | 0.467 | 0.700 | 0.325 |
| V3_leakage_gated | 0.417 | 0.733 | 0.290 |
| V3_two_phase | 0.517 | 0.667 | 0.312 |

- Best long-event recall@20: V3_two_phase = 0.517 (vs V2_static25 = 0.417).
- Best long-event recall@40: V3_leakage_gated = 0.733 (vs V2_static25 = 0.700).
- Selected duration@40 is identical across schedules (400 s) because each bin is 10 s and exactly B bins are selected.

**Answer**: The v3 schedules improve budget=20 long-event recall for some variants, but the improvement is modest and depends on the variant. Budget=40 performance is preserved or improved.

## 5. Repair utility v3: does it improve long-event repair?

| utility | long-event recall@40 | precision@40 |
|---------|---------------------:|-------------:|
| U0_current | 0.683 | 0.325 |
| U1_leakage_density | 0.750 | 0.287 |
| U2_temporal_continuity | 0.667 | 0.292 |
| U3_long_event_oriented | 0.600 | 0.305 |
| U4_precision_aware | 0.700 | 0.315 |

- Best long-event recall@40: U1_leakage_density = 0.750.
- Best precision@40: U0_current = 0.325.

**Answer**: Some utilities slightly improve long-event recall, but differences are small. No utility dominates both recall and precision.

## 6. Over-selection check

- At budget=40, every schedule selects exactly 40 bins = 400 s.
- The recall differences therefore cannot be explained by selecting more video.
- Precision differences reflect where the 400 s is allocated.

## 7. Dense \( O_{\text{ref}} \) calibration subset

- Found: `full_reference_units.csv` contains 600 2 s units covering the full 20-minute video.
- 80 units are positive, 520 negative under the VLM-oracle.
- This is sufficient for oracle-relative dense calibration without new oracle calls or human annotation.

## 8. Oracle-relative calibration plan

- `oracle_relative_dense_calibration_plan.md` describes the calibration design.
- `oracle_call_manifest.csv` maps every 2 s unit to its VLM-oracle label for retrospective lookup.
- `ALLOW_NEW_ORACLE_CALLS = False`; no new calls were executed.

## 9. Revised claims

**Can claim**:
- LATE-AQP improves oracle-relative long-interval VEPC event discovery under candidate-envelope leakage in existing VLM-oracle replay.
- Gain is not due to selected-duration inflation at the budgets examined.
- Dense VLM-oracle labels exist for full-video oracle-relative calibration.

**Cannot claim**:
- Calibrated missing-mass estimation (evaluation not yet executed).
- Human-grounded VEPC correctness.
- Formal guarantee.
- Full interval reconstruction.
- Causal audit-triggered repair attribution (logging insufficient).
- Superiority over SUPG/ABae.

## 10. Recommendation

**Primary recommendation**: **A. promote LATE-AQP v3 audit schedule as next main algorithm**

Reasoning:
- V3 schedules address the budget=20 weakness while preserving budget=40 gains.
- The framework is still LATE-AQP; only the audit allocation changes.
- Logging improvements (recommendation D) can be layered on top without redesigning the algorithm.

**Secondary recommendation**: **D. redesign logging before further algorithm changes**

Reasoning:
- Causal claims about repair require full lineage.
- Current trace reconstruction leaves too many fields as `unknown_not_logged`.

## 11. Next priority order

1. Add full repair trace logging to the LATE-AQP implementation.
2. Execute oracle-relative calibration evaluation using existing dense `full_reference_units.csv`.
3. If calibration is promising and logging is complete, consider promoting repair utility v3 (option B) or weakening claims to long-event discovery only (option E).
4. Re-evaluate whether to implement SUPG/ABae baselines in a separate round after LATE-AQP is stabilized.
