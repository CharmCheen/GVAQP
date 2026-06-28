# Realcartest Strategy 7 Replay Report

- Output timestamp: 2026-06-27T14:37:38Z
- Deployable selection policies use cheap proxy score, timestamps, random seeds, and GLM parsed labels only.
- Existing Qwen labels and `event_cluster_id` are evaluation-only.
- Realcartest positive rate: 0.235589 (94/399).
- GLM parsed labels: positive 106, uncertain 0, negative 292, parse_error 1.
- GLM positive/uncertain enrichment: 1.882075x vs base rate; low-L3 GLM positive/uncertain enrichment: 1.061170x.

## Budget Curve

| B | S7 L3-missed recovery | uniform-audit L3-missed recovery | S7 gap | S7 anchor recall | L3 anchor recall | S7 audit hit rate |
|---:|---:|---:|---:|---:|---:|---:|
| 20 | 0.018026 | 0.016026 | 0.002000 | 0.132191 | 0.170213 | 0.237667 |
| 30 | 0.034889 | 0.024361 | 0.010528 | 0.207957 | 0.234043 | 0.283111 |
| 40 | 0.055224 | 0.032119 | 0.023104 | 0.263553 | 0.287234 | 0.314500 |
| 60 | 0.088327 | 0.052000 | 0.036327 | 0.361872 | 0.414894 | 0.278667 |
| 80 | 0.156500 | 0.070682 | 0.085818 | 0.460000 | 0.531915 | 0.301667 |
| 100 | 0.197171 | 0.089902 | 0.107268 | 0.578085 | 0.563830 | 0.278000 |
| 150 | 0.291500 | 0.153875 | 0.137625 | 0.688277 | 0.659574 | 0.215511 |

## Required Questions

1. Strategy 7 **does** improve L3-missed positive recovery on realcartest: gap is positive at 7/7 budget points; mean gap is 0.057524.
2. Strategy 7 is better than the 70/30 uniform audit for the target metric: every budget has positive L3-missed recovery gap, and mean audit-hit-rate gap is 0.093733.
3. In this higher-positive-rate, stronger-proxy setting, disagreement audit still has marginal value for missed positives, especially at B=80/100/150 where gaps are 0.085818/0.107268/0.137625.
4. This is not a dataset3-only effect under this replay: dataset3 showed a positive target signal and realcartest independently shows positive missed-positive recovery gaps at all requested budgets.
5. The effect is not because L3 is weak overall: L3 P@20 is 0.800 on realcartest. The gain comes from GLM/proxy disagreement exposing low-L3 missed positives; `GLM_positive_or_uncertain` has 1.882075x enrichment and contains 34 B20 L3-missed positives. Overall anchor recall is still below pure L3 at small B because 30% of budget is reserved for audit.
