# H-ROLLOUT1B approximation and error model

At a decision state, every legal action including STOP and the shielded pi0 action is evaluated symmetrically with common random numbers. For action `a` and pi0 action `a0`, the estimator records `D_n(a)=G(a;omega_n)-G(a0;omega_n)`. Exact M1 is evaluator-only: it may label action agreement and regret but cannot be queried by an approximate policy.

The fixed compute configurations are `(posterior worlds, trajectories) = (4,4), (16,16), (64,64), (256,256)`. No adaptive horizon, sample count, configuration selection, or early stopping is allowed.

Perturb one mechanism at a time and use predeclared joint corners. Mechanisms are SCAN candidate yield, CONFIRM positivity, novelty/duplicate probability, grouping transition, action duration, and materialization success. For each, use independent variance, systematic optimism, systematic pessimism, and state-dependent calibration error at magnitudes `0, 0.05, 0.10, 0.20`. Probabilities clip to `[0.01,0.99]`; durations round upward to whole ticks. State-dependent error applies only to the highest visible score bin. The joint corner applies all six mechanisms at magnitude `0.10` with a common sign.

Required outcomes per fixed configuration/error cell are action agreement with exact M1, incorrect override rate, paired value regret, 95% paired confidence interval width, planning invocation count, and raw paired action estimates.
