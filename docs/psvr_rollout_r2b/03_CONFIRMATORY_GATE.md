# H-ROLLOUT1B confirmatory design and Gate

Before execution, create once a new isolated 1024-episode H1B seed universe and hash-bind it. It must be disjoint from development, the permanently contaminated legacy held-out universe, and the 1A sealed universe. All policy × episode identities are paired and append-only; common random numbers are keyed only by H1B seed, decision index, action pair, configuration, and trajectory.

The primary contrast is net time-weighted unique-event utility of planning-admission + LCB fallback versus immediate shielded pi0, paired across all 1024 H1B episodes. Zero is a valid planning-cost cell, but ACCEPT requires a strictly positive planning-cost cell.

`ACCEPT_APPROXIMATE_ROLLOUT` requires a predeclared fixed compute configuration and positive planning-cost cell: paired 95% lower bound > 0; paired median >= 0; positivity in a contiguous three-cell error/planning-cost neighborhood; no exact posterior enumeration; LCB fallback reduces incorrect override and 5th-percentile paired loss against ungated approximation; and no major process family has a lower 95% bound below -0.01 times mean pi0 utility.

`PARTIAL_NARROW_ROBUSTNESS_REGION` applies when a positive finite-cost cell exists but neighborhood or no-collapse conditions fail. `REJECT_PLANNING_COST_ERASES_GAIN` applies when exact-model finite-cost net utility has no positive lower bound. `REJECT_MODEL_ERROR_ERASES_GAIN` applies when exact-model finite-cost benefit exists but all nonzero error cells fail. `REJECT_APPROXIMATION_UNSTABLE` applies when agreement/regret and fallback criteria fail. Any hash, universe, pairing, trace, or verifier failure yields `BLOCKED_EXECUTION_INTEGRITY`.
