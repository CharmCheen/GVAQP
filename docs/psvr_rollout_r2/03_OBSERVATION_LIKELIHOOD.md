# Observation likelihood

Actions are interventions. For a finite world `omega`, the likelihood is one
iff deterministic replay under `do(action)` reproduces every observed action
outcome in the visible history, and zero otherwise. No action-selection
probability occurs in this likelihood.

R2 uses a result-blind 288-world finite quadrature of the pre-existing
sparse/dense/bursty and scan-cheap/balanced/scan-expensive regimes. Quality has
four rank bins, duplicate rate three, grouping error four, and hard-negative
Oracle outcomes are binary. Durations are integer ticks. The representation
resolution is at most one rank bin (1/4, 1/3, 1/4 respectively); no method
result selected a bin. No floating-point equality is used for posterior
consistency.
