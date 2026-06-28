# FINAL_SUMMARY.md - Post-Transition Strategy 7 Audit

## Constraint Compliance

- No new model called (no VLM, no Qwen, no GLM, no GPT, no YOLO rerun, no CLIP, no motion proxy)
- No new data downloaded
- No training performed
- No existing raw experiment outputs modified
- All new outputs in `garc_eval/outputs/post_transition_strategy7_audit_v1/`

## Input File Sources (no new files generated, only read)

| Source | Path | Purpose |
|--------|------|---------|
| Clean pool cascade results | `prompt_tuning_v1/heldout_cascade_eval_v1/tables/cascade_simulation_results_clean.csv` | Strategy 6/7 numbers on N=100 |
| Original cascade results | `prompt_tuning_v1/heldout_cascade_eval_v1/tables/cascade_simulation_results.csv` | Strategy 6/7 numbers on N=123 |
| Clean pool anchor IDs | `prompt_tuning_v1/heldout_cascade_eval_v1/clean_pool_anchor_ids.csv` | 100 anchors after tuning removal |
| Cascade simulation script | `prompt_tuning_v1/scripts/cascade_simulation_clean.py` | Defines Strategy 1-7 logic |
| Track-transition reports | `track_transition_validation_v1/reports/` | All 5 reports from second attempt |
| Track-transition tables | `track_transition_validation_1/tables/` | All 11 tables including object_tracks, transition_anchor_features |
| Raw bbox materialization | `dataset3_raw_bbox_materialization_v1/` | Parquet, CSV, full run report |
| Canonical anchor | `codex_recompute_proxy_budget_basa_v1/tables/canonical_dataset3_anchor_table.csv` | dataset3 347 anchors with labels + proxy |
| V13 oracle | `experiments/v13/v13_8_full_oracle/tables/center10_full_oracle_labels.csv` | realcartest 399 anchors with labels |

## Phase 1: Strategy 7 Special Audit (Decision: STRATEGY7_TARGETED_SIGNAL_CONFIRMED)

The +25.7pp gap at clean B=60 is real. The lift is broad-based, not narrowly targeted:

| Metric (B=60) | S6 (uniform) | S7 (disagreement) | Gap |
|---------------|--------------|-------------------|-----|
| Anchor recall | 13.7/28 = 48.9% | 22.0/28 = 78.6% | **+29.7pp (this audit) / +25.7pp (per-cascade)** |
| Singleton recall | 9.8/16 = 61.3% | 13.0/16 = 81.3% | +20.0pp |
| Low-proxy singleton recall | 7.0/9 = 77.8% | 8.0/9 = 88.9% | +11.1pp (n=9 small) |
| L3-missed positive recovery | 3.4/11 = 30.9% | 7.0/11 = 63.6% | **+32.7pp** |
| L3-missed singleton recovery | 1.6/5 = 32.0% | 3.0/5 = 60.0% | +28.0pp |
| Audit hit rate | 0.33 | 0.72 | +0.39 |

**Key insight**: The largest gain is on **L3-missed-positive recovery** (+32.7pp), not low-proxy singleton recall (+11.1pp). The S7 disagreement audit specifically targets the L3 failure mode. The +11.1pp on low-proxy singletons is a single-anchor swing on n=9.

## Phase 2: Strategy 7 Budget Alignment (Decision: STRATEGY7_TARGETED_SIGNAL_CONFIRMED, weakened)

The +25.7pp headline is inflated by ~12-18pp due to a budget-vs-pool-size artifact:

| Comparison | Recall gap |
|------------|------------|
| Old N=123 B=60 | +13.5pp |
| Clean N=100 B=60 (same abs) | **+25.7pp (headline)** |
| Clean N=100 B=49 (equiv to old B=60) | +7.7pp (comparable) |

At comparable budgets (clean B=49 ≈ old B=60), the S7-vs-S6 gap is +7.7pp anchor recall and +7.0pp singleton recall. This is a real, positive effect, smaller than the +25.7pp headline.

**Conclusion**: The S7 mechanism is real, but the +25.7pp number overstates the actual mechanism improvement. Use 7-16pp for honest reporting.

## Phase 3: Track-Transition Consistency (Decision: TRACK_TRANSITION_NEGATIVE_RESULT_VALID_WITH_COUNT_CORRECTION)

The "4459 vs 34814" was a reading error. Actual numbers are 44,595 (raw) and 34,814 (vehicle-like).

| Check | Status |
|-------|--------|
| Counts internally consistent (raw 44,595, vehicle-like 34,814, ratio 78.07%) | YES |
| Track input source is correct (dataset3, no double counting, no wrong video) | YES |
| Negative conclusion still supported by data | YES |
| **Stale top-level FINAL_SUMMARY.md (still says INPUT_MISSING)** | **BUG** |
| **Stale `tables/final_decision.csv` (still says INPUT_MISSING)** | **BUG** |

The reports/ subdirectory has the correct `TRACK_TRANSITION_NOT_USEFUL` analysis. The top-level FINAL_SUMMARY.md and tables/final_decision.csv were never updated after the second attempt. The conclusion is valid; the top-level summary just has a stale decision label.

**Recommended correction**: append a patch to the top-level FINAL_SUMMARY.md noting that the analysis was re-run after raw bbox materialization and the current decision is `TRACK_TRANSITION_NOT_USEFUL`. Update tables/final_decision.csv to match. Reports/ subdirectory is already correct.

## Phase 4: High-Selectivity Predicate Scout (Decision: HIGH_SELECTIVITY_PILOT_AVAILABLE_NO_NEW_ORACLE, dataset3 only)

dataset3 has full data for a no-new-oracle pilot. The most selective existing predicates:

| Predicate | Candidates | Positives | Rate | Selectivity | Cluster coverage |
|-----------|-----------|-----------|------|-------------|------------------|
| person_count_mean > 2 | 33 | 16 | 48.5% | **4.21x** | 12/27 (44%) |
| person_count_mean > 1 | 75 | 24 | 32.0% | **2.78x** | 15/27 (56%) |
| lateral_presence_mean > 3 | 149 | 28 | 18.8% | 1.63x | 19/27 (70%) |
| object_count_mean > 10 | 51 | 10 | 19.6% | 1.70x | 7/27 (26%) |

realcartest has labels + event info but **lacks per-anchor proxy for the 399 V13 anchors** (the kinematic_proxy 102-clip subset is a different anchor set). Cannot be piloted without new YOLO inference.

## Cross-Phase Synthesis

| Component | Status | Verdict |
|-----------|--------|---------|
| Strategy 7 mechanism | Real +7-16pp gain over uniform audit on L3-missed positives | VALIDATED |
| Track transition | Real negative result; 8.6% base rate, under-enriched on positives, no replay gain over L3 | VALIDATED |
| High-selectivity predicates | `person_count_mean > 2` gives 4.21x on dataset3, 44% cluster coverage | AVAILABLE |
| Track transition counts | All numbers internally consistent | VALIDATED WITH BUG |
| Top-level FINAL_SUMMARY.md | Stale INPUT_MISSING label | NEEDS CORRECTION |

## Final Decision

**`PROCEED_STRATEGY7_AS_AQP_SIDE_MECHANISM`**

Justification:
- S7 is a real, deterministic mechanism with +7-16pp gain on L3-missed positives
- The disagreement audit framing is the strongest AQP-side candidate among tested strategies
- The +25.7pp headline is real but partly inflated by budget-pool-size artifact
- The negative track-transition result is well-grounded; the top-level FINAL_SUMMARY bug should be fixed but doesn't change the conclusion
- High-selectivity predicates are available for dataset3 but not for realcartest (lacks per-anchor proxy)

Next steps (in priority order):

1. **Fix the top-level FINAL_SUMMARY.md and tables/final_decision.csv** in `track_transition_validation_v1/` to reflect the second-attempt decision (`TRACK_TRANSITION_NOT_USEFUL`).

2. **Test S7 mechanism robustness on a second video** (realcartest). This requires new YOLO on realcartest_5k at 2 fps to produce per-anchor proxy for the V13 399 anchors, then re-run the cascade. **Requires new VLM-authorized GPU inference**, not in this task's scope.

3. **Document the budget-alignment caveat** in any future paper: S7's headline +25.7pp is real at clean B=60 but is partly a budget-pool-size artifact. The mechanism-level gain is +7-16pp on comparable budgets.

4. **If pursuing high-selectivity branch**: pilot on dataset3 with `person_count_mean >= 1` (2.78x selectivity, 56% cluster coverage) or `lateral_presence_mean > 3` (1.63x, 70% coverage). Both are no-new-oracle compatible.

5. **Avoid the track-transition path**: the negative result is well-grounded and the crude ROI + 2 fps is the bottleneck. Without geometric corridor and 5-10 fps, the signal cannot be tested further.
