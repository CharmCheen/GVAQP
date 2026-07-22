# H-ROLLOUT1A execution protocol — rebound but blocked

H-ROLLOUT1A is rebound to D1 + D2-L + D2-T + D3 and does not depend on D2-P.
It tests ideal mechanism value under an exact generative model, full symmetric
continuation, zero estimator error, and zero primary planning cost.

It does not test physical calibration, physical planning overhead, real
world-model accuracy, M0 transferability, or real runtime deadline safety.

Execution is not authorized. Before the held-out command can be used, D3/D4
must be reissued result-blind with domain-separated RNG keys, action-identity
potential costs shared across methods, an incremental grouping kernel, an
explicit seed/parameter visibility policy, and a visible-history conditional
model for M1. All affected hashes must then be regenerated and independently
reviewed. The held-out seed file and held-out runner must remain unopened by
development smoke.

