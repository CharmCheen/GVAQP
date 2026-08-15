# EQUAL_YIELD_REPORT (ERAEA E1)

Scope: FIXED_CANDIDATE_REPLAY, MODEL_RELATIVE_DIAGNOSTIC (Q_VULNERABLE, C1,
full-grid model-relative reference). Statistical unit: video x query.

## Construction
- Pairs are (policy_i, policy_j, budget) with |yield_i - yield_j| <= 1 and
  |coverage_i - coverage_j| / max <= 5% (coverage = final C1 component span
  fraction). Cost is identical (same budget = same VERIFY count).
- Source: BASELINE_MATRIX.csv; all pairs in EQUAL_YIELD_PAIRS.parquet.

## Results (relation-greedy-centric pairs)
| cluster | n_pairs | median delta_EventF1 | positive-direction share | |delta|>=0.03 share |
|---|---:|---:|---:|---:|
| DALI | 14 | 0.0 | 0.071 | 0.286 |
| HANGZHOU | 27 | 0.0 | 0.148 | 0.111 |
| WUHAN | 31 | 0.0 | 0.097 | 0.097 |
| pooled | 72 | 0.0 | 0.111 | 0.139 |

## Verdict
- Median matched-yield Delta EventF1 = **0.0 in all three clusters**.
- The 10-29% of pairs with |delta| >= 0.03 are dominated by the negative
  direction (positive share only 7-15%).
- -> **NO_GO_EQUAL_YIELD_RESIDUAL_EMPTY**: once positive yield (and near-equal
  coverage) is controlled, the relation structure of acquired evidence has no
  stable effect on final EventRelation quality on this substrate.
