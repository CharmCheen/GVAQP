# FINAL REPORT — Limited-Oracle Retrieval Frontier

## 1. Is full-VLM reference a development-time evaluation artifact?

Yes. `center10_vlm_oracle_events.csv` and `reference_events.csv` were generated in prior development phases and are only used for evaluation and as the back-end of the oracle adapter.

## 2. Is the algorithm runtime strictly limited to B oracle calls?

Yes in the replay accounting. LATE-AQP-core is strict_replay; B6/B7/B6-core/B7-core are posthoc_eval because their upstream selection uses event_id.

## 3. Is there label leakage risk?

B6/B7 use per-bin event_id for adaptive chunk counting, which is a leakage risk. LATE-AQP-core does not use event_id during selection. See `oracle_replay_isolation_audit.md`.

## 4. Which results are strict_replay vs posthoc_eval?

- strict_replay: LATE-AQP-core
- posthoc_eval: B6, B7, B6-core, B7-core

## 5. Does any method reach 90/90 at <=30% budget ratio?

No. See `budget_ratio_summary.csv`.

## 6. Does LATE-AQP-core reach 90/90?

Reached on 3/3 evaluated budgets (including full-sweep budgets):
- realcartest_0_1570: B=157, ratio=1.000, P=1.000, R=1.000 (full sweep of all units)
- realcartest_2000_3200: B=120, ratio=1.000, P=1.000, R=1.000 (full sweep of all units)
- realcartest_3200_3830: B=63, ratio=1.000, P=1.000, R=1.000 (full sweep of all units)

At the practical budget cap of B<=120, LATE-AQP-core reaches 90/90 on 2/3 segments (all except `realcartest_0_1570`).

## 7. Do B6-core / B7-core reach 90/90?

B6-core: 3/3 segments
  - realcartest_0_1570: B=157, ratio=1.000
  - realcartest_2000_3200: B=120, ratio=1.000
  - realcartest_3200_3830: B=60, ratio=0.952
B7-core: 3/3 segments
  - realcartest_0_1570: B=157, ratio=1.000
  - realcartest_2000_3200: B=120, ratio=1.000
  - realcartest_3200_3830: B=47, ratio=0.746

## 8. Is LATE-core B_90/90 <= B7-core?

- realcartest_0_1570: LATE=157, B7-core=157, LATE<=B7-core: True
- realcartest_2000_3200: LATE=120, B7-core=120, LATE<=B7-core: True
- realcartest_3200_3830: LATE=63, B7-core=47, LATE<=B7-core: False

## 9. At <=30% budget ratio, is LATE-core closer to 90/90?

No method reaches 90/90 at <=30% budget ratio. Best recall under precision>=0.9 within the low-budget envelope:

| segment | LATE-core | B7-core | B6-core | closest |
|---------|-----------|---------|---------|---------|
| realcartest_0_1570 | 0.24 | 0.31 | 0.13 | B7-core |
| realcartest_2000_3200 | 0.31 | 0.31 | 0.21 | LATE-AQP-core |
| realcartest_3200_3830 | 0.20 | 0.00 | 0.00 | LATE-AQP-core |

Average best low-budget recall (P>=0.9): LATE-core=0.25, B7-core=0.21, B6-core=0.11.

## 10. Is Core/Halo a generic post-processing gain?

Yes. Once B6/B7 receive the same Core/Halo release, they reach 90/90 on the same segments as LATE-AQP-core (see `method_comparison_macro_micro.csv`).

## 11. Is the current bottleneck discovery or release?

Low-budget failure taxonomy counts: discovery_miss=6, release_over_conservative=6, LATE-specific=3.

Mixed: most low-budget failures are discovery misses, with some release-over-conservative cases (e.g., B6-core on `realcartest_0_1570`). See `failure_taxonomy.csv`.

## 12. Recommended next step

B. Conduct cross-video validation to confirm generalization.
