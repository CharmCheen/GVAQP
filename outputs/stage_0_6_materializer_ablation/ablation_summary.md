# Stage 0.6 EVENT_MATERIALIZE Mechanism Ablation

## Scope

This is a CPU CSV replay ablation. It does not change oracle allocation, selected units, oracle order, proxy generation, or model outputs. All materializer parameters are fixed across methods and budgets.

## Variant Averages

| materializer_variant                 |   mean_auc |   mean_b20 |   mean_b100 |   mean_max_duration |   mean_overmerge |   selector_count |
|:-------------------------------------|-----------:|-----------:|------------:|--------------------:|-----------------:|-----------------:|
| NativeOriginal                       |  0.41005   |  0.309777  |   0.497002  |            374.63   |         4.93708  |                9 |
| C0_common_naive_merge                |  0.0772487 |  0.0783069 |   0.0783069 |            544.889  |        10.2333   |                9 |
| C1_gap_limited_merge                 |  0.366715  |  0.246515  |   0.479542  |             40.037  |         0.901013 |                9 |
| C2_duration_prior                    |  0.38935   |  0.245822  |   0.52887   |             21.037  |         0.850014 |                9 |
| C3_negative_hard_barrier             |  0.406993  |  0.245822  |   0.569108  |             21.037  |         0.797478 |                9 |
| C4_proxy_valley_soft_barrier         |  0.406993  |  0.245822  |   0.569108  |             21.037  |         0.797478 |                9 |
| C5_duplicate_suppression             |  0.406993  |  0.245822  |   0.569108  |             21.037  |         0.797478 |                9 |
| C6_full_EVENT_MATERIALIZE            |  0.406993  |  0.245822  |   0.569108  |             33.1481 |         0.797478 |                9 |
| F0_full_EVENT_MATERIALIZE            |  0.406993  |  0.245822  |   0.569108  |             33.1481 |         0.797478 |                9 |
| F1_full_minus_duration_prior         |  0.411964  |  0.246515  |   0.577932  |             36.8889 |         0.800141 |                9 |
| F2_full_minus_negative_barrier       |  0.390442  |  0.245822  |   0.531833  |             36.037  |         0.850014 |                9 |
| F3_full_minus_proxy_valley           |  0.406993  |  0.245822  |   0.569108  |             33.7037 |         0.797478 |                9 |
| F4_full_minus_duplicate_suppression  |  0.406993  |  0.245822  |   0.569108  |             33.1481 |         0.797478 |                9 |
| F5_full_minus_conservative_expansion |  0.406993  |  0.245822  |   0.569108  |             21.037  |         0.797478 |                9 |

## Leave-one-out Contributions

| removed_rule                                |   mean_auc_drop_when_removed |   positive_drop_selectors |   selector_count |
|:--------------------------------------------|-----------------------------:|--------------------------:|-----------------:|
| removed_2_full_minus_negative_barrier       |                   0.0165512  |                         7 |                9 |
| removed_4_full_minus_duplicate_suppression  |                   0          |                         0 |                9 |
| removed_3_full_minus_proxy_valley           |                   0          |                         0 |                9 |
| removed_5_full_minus_conservative_expansion |                   0          |                         0 |                9 |
| removed_1_full_minus_duration_prior         |                  -0.00497082 |                         2 |                9 |

## Required Questions

1. Full EVENT_MATERIALIZE vs common naive merge: C6 mean AUC=0.4070, C0 mean AUC=0.0772.
2. Full EVENT_MATERIALIZE vs gap/duration merge: C1 mean AUC=0.3667, C2 mean AUC=0.3893.
3. Largest leave-one-out contributor: `removed_2_full_minus_negative_barrier` with mean AUC drop 0.0166.
4. Cross-selector behavior is in `auc_by_selector_materializer.csv`; gains are not uniform across every selector, so selector-specific evidence quality still matters.
5. Overmerge reduction: C0 overmerge=10.2333, C6 overmerge=0.7975; C0 max duration=544.8889, C6 max duration=33.1481.
6. B=100 Ours repair reproduced: C6 Ours B=100 F1=0.975610.
7. Low-budget B=20 average F1 delta C6-NativeOriginal=-0.0640; positive means helped on average, negative means hurt on average.

## Pass Criteria

- C6 improves event-F1 AUC over C0/C1/C2 on average: True.
- C6 lowers overmerge and max duration vs C0: True.
- C6 does not improve only by over-shortening: C6 is compared against C2 duration-prior and leave-one-out duration removal.
- At least two event-aware mechanisms beyond duration show independent AUC contribution >0.005: False (1 mechanisms).

Overall pass: False.
