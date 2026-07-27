# SCAN Optimization Headroom Audit — Final Report

## Strongest supported conclusion

- `PSP_V0_SHORT`: best causal replay `ANYTIME_LARGEST_GAP` AUC=0.5296 vs Sequential=0.5007; offline greedy=0.9039. At matched 60 s Replay, `SEQUENTIAL` is best; actual Physical winner is `SEQUENTIAL` AUC=0.1327 vs Sequential=0.1327.
- `PSP_V1_LONG`: best causal replay `MACRO_REGION_LARGEST_GAP` AUC=0.5282 vs Sequential=0.5202; offline greedy=0.8637. At matched 60 s Replay, `UNIFORM_PREFIX` is best; actual Physical winner is `UNIFORM_PREFIX` AUC=0.0497 vs Sequential=0.0304.

These are controlled two-video mechanism results relative to a frozen pseudo-reference, not cross-video generalization claims.

## Interpretation

- A positive simple-coverage gain is direct evidence that time allocation is optimizable without changing SCAN fidelity.
- A positive offline-greedy gap is an achievable hidden-information witness of remaining scheduling headroom; it is not a proven optimality gap.
- Replay gain that disappears physically identifies path/seek batching—not a more elaborate event score—as the next bottleneck.
- Temporal refinement is tested only when the frozen headroom gate passes; guarded marginal scheduling remains gated on simple refinement.

## Frozen status

```text
PUBLIC_UNTRUSTED_POLICY_BENCHMARK = BLOCKED
TRUSTED_FROZEN_POLICY_EXPERIMENT = ALLOWED
TEMPORAL_CORRELATION_AUDIT_GATE = PASS
PUBLIC_BENCHMARK_CLAIM = DEFERRED
```
