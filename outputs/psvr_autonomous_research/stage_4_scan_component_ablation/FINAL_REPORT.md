# H-SCAN1A final report

## Outcome

```text
H-SCAN1A = ACCEPT_STRUCTURAL_SIGNAL
COVERAGE_STRUCTURAL_SIGNAL = PRESENT
OBSERVED_PROXY_EXPLOITATION_DRIVER = NOT_SUPPORTED
H-COV1 = REVISE_MORE_SPECIFIC
PSVR_CORE_INNOVATION_PILOT = WEAK
```

All 4 smoke and 24 formal physical runs completed under one runtime identity with zero failure, deadline miss, cache replay, future-proxy access, visibility violation, or incomplete snapshot. The physical cap was exactly 28.

Formal effectiveness was D0=false, D1=true, D2=true, D3=false. D2 mean AnytimeAUC_F1 was 0.021592 versus D1 0.018749, and its median TTFC was 86.86 s versus 89.23 s. Both recover one unique event, but D2 recovers `vlm_event_0017` while D1 recovers `vlm_event_0022`.

D2 is the best method in this H-SCAN1A matrix by AnytimeAUC, TTFC, simplicity, and mechanism specificity. It becomes the current H-SCAN1A development candidate. Pre-existing archived evidence for a different debt+proxy variant remains separately disclosed and is not pooled into this decision.

The next highest-value experiment is H-SCAN1B: split the structural group into normalized unobserved-duration/coverage and scan-level/hierarchical-debt components. It is not executed in this cycle.
