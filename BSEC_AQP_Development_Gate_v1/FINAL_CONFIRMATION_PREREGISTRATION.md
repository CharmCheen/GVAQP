# DASR final confirmation preregistration

Freeze time: 2026-07-13 01:44:24 UTC, before CLIP scoring on either remaining labeled interval.

## Updated bottleneck

The confirmatory `realcartest_0_1570` interval showed that mean uniform-random AUC exceeded ARC and every semantic ranking tested. That contradicts the assumption that better semantic diversity is the universal bottleneck. The robust mechanism is temporal opportunity coverage with limited semantic exploitation.

## Frozen method

Density-Adaptive Stratified Retrieval (DASR) uses the same CLIP scores as the baselines. At each budget it reserves `round(alpha*B)` slots for temporal-NMS candidates, where `alpha=n/(n+8B)`. It fills the remaining slots using the highest-CLIP representatives of `round(1.5B)` equal temporal cells. No oracle outcome or reference event is used for selection.

The constants `10`, `1.5`, and `8` were selected on all three already opened domains. Their apparent robustness is fitting evidence only.

## Final untouched intervals

- `realcartest_1630_2000`: 37 units, 2 pseudo-events, budgets 5/10/20.
- `realcartest_3200_3830`: 63 units, 7 pseudo-events, budgets 5/10/20/50.

Both are disjoint from every interval used to select DASR. The CLIP scorer remains label-blind and must seal both rankings before evaluation.

The event-rich interval must show strict DASR AUC superiority over shared-K3 ARC, CLIP, and NMS. The sparse interval must be no worse than shared-K3 ARC, and the unweighted two-interval macro AUC must strictly exceed ARC. Exact-call and shared-materializer checks are mandatory.

Native ARC is descriptive because its broad outputs do not satisfy the shared materialization contract. Any conclusion must keep that distinction visible.
