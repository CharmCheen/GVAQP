# Binary SMDP Value V1 run status

Current phase: `COMPLETE_AT_PREREGISTERED_STOP`
Decision: `INSUFFICIENT_EVIDENCE`
Learning mainline: `NOT_AUTHORIZED`
Base commit: `5047241b0561b911b9a519b18e8e7591c0074e70`
Branch: `research/binary-smdp-value-v1`

Completed evidence:

- repository, historical outputs, GPU, video and local-model audit;
- frozen validation contract and conditioned binary SMDP implementation;
- causal/deepcopy/legality/budget/determinism tests;
- bounded conditioned-oracle pilots at beam widths 128/512/2048;
- explicit headroom/safety audit and gate decision;
- Hangzhou content-blind 8B/32B physical cost, stability and agreement probe;
- executable R4 fail-closed fallback with independent frozen-bound shield;
- final evidence synthesis and next decision.

Stopped by the frozen headroom gate before PUBLIC model training, LightGBM/MLP,
replay aggregation, learned closed-loop evaluation, ablations and formal
Hangzhou policy comparison. Those directories contain explicit `NOT_RUN`
status artifacts rather than fabricated negative or positive results.

Highest-value restart condition: acquire complete non-imputed V0 action costs
and an independently frozen complete-action latency bound that produces zero
replay overruns, then rerun the same oracle headroom gate without changing its
criteria.
