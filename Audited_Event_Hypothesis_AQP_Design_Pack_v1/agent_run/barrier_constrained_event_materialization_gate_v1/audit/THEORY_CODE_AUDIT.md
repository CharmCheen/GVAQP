# Theory and Executable-Code Audit

## Authority and scope

This gate uses the frozen strict benchmark `cbbv2_514c0d360fd5b2a4b5fe`. The executable source in `clean_baseline_benchmark_v2_strict/scripts/benchmark_lib.py` is authoritative where it differs from prose or the older mathematical reference. Acquisition is not executed: only saved `action_trace` rows and their saved oracle labels are replayed.

## Authoritative functions

| Function / rule | Source | SHA-256 | Executable semantics |
|---|---|---|---|
| `benchmark_lib.py` | strict benchmark `scripts/benchmark_lib.py` | `0a7a8ad4a13cc4404b0cfe7dfb1aef8958197267e22ff1df545ac4dbbf744610` | Shared materializer, canonicalizer, matcher, and evaluator. |
| `materialize_from_trace` | lines 80–149 | `d4bf4c3714556feeabac4cd6d148bd300767128a1ada185fc4acb5ed39607e72` | Reads queried labels; positives are anchors; negatives are hard interior barriers; other labels are neither. |
| `canonicalize_native_segments` | lines 152–205 | `bcde765dd7fd97aec64ef2e2d96935df6c4dbd526aedb11ad0c1bbba70f00467` | Converts repository-native intervals and records positive/negative queried evidence inside them. It is not the controlled materializer path. |
| `match_events` | lines 208–273 | `16ca215d80642eed97618046d528d23a222d86989078ac853cecfa383b88b3f4c` | Hungarian assignment on `1000*overlap_any + temporal_IoU`; only positive-overlap assignments count. |
| `compute_metrics` | lines 276–318 | `a43b2786252177514f0594c3c81580366fbb1922d9083092ad43afbf9c7a63a2` | `precision=TP/#pred`, `recall=TP/26`, `F1=2PR/(P+R)` plus boundary/count diagnostics. |
| `evaluate_events` | lines 321–329 | `ac9c9f800450ffa4b3f9832fce37211365040cfcd199c7de026699780a3b8c4c` | Exact composition of the frozen matcher and metric computation. |
| normalized event-F1 AUC | `run_clean_benchmark_v2_strict.py`, lines 1219–1222 and 1318–1323 | file hash `0f5a3b144dc13922ffd066e1beb4f69d89b8787aaa931b3606205b61b5903437` | Sort budgets `[5,10,20,50,80,100]`; trapezoidal integral divided by `100-5`. |

## Exact K3 pseudocode

```text
positives := sorted unique queried units labeled positive
negatives := queried units labeled negative
current := [first positive]
for positive u in time order:
    left := last anchor in current
    barrier_ok := no negative unit strictly between left and u
    if original_k3:
        bridge_ok := number of intervening unit IDs <= 1
    if k3_bridge_safe:
        bridge_ok := u is directly adjacent to left
    span_ok := end(u) - start(first(current)) <= min(40s, 60s)
    append u iff barrier_ok and bridge_ok and span_ok; otherwise open a group
emit the minimal interval start(first anchor) to end(last anchor) for each group
```

Thus `original_k3` permits one *unqueried* interior unit but never crosses a queried negative. `k3_bridge_safe` permits only adjacent unit IDs. Both cover every queried-positive anchor exactly once. Both use minimal convex-hull output and have an effective 40-second bound. The configured 60-second output cap is checked but never independently active because `min(40,60)=40`.

## Matcher and tie behavior

The primary objective is maximum overlap-any cardinality; total temporal IoU is secondary through a weight of 1 versus 1000 for cardinality. SciPy `linear_sum_assignment` supplies the assignment. The source specifies no additional semantic tie rule when cardinality and total IoU are exactly equal; reproducibility therefore depends on the frozen row ordering and numerical implementation. BCEM defines its own deterministic partition tie-break, then calls this unchanged evaluator.

## Trace replay and observation semantics

Controlled saved traces contain `unit_id`, `call_idx`, budget, seed, selector identity, and `oracle_label_after_query`. The ceiling takes these bytes as input and never calls `OracleAccessor` or acquisition code. The frozen oracle table has 39 positives, 308 negatives, and **zero abstains**. Runnable BCEM nonetheless validates labels and raises on `abstain` or unknown labels; it never silently maps abstain or unqueried units to negative. Unqueried units are absent from both positive and negative sets and remain unknown.

## Prose/reference versus executable code

1. `BCM_AQP_MATHEMATICAL_REFERENCE.md` says the clean helper and matcher were unavailable. They are present in the current strict artifact, so that historical limitation is superseded.
2. Its audited Stage-0.7 `original_k3` account (one unknown gap, queried-negative barrier, 40-second cap) agrees with current executable `original_k3`.
3. The exact current `k3_bridge_safe` difference is now auditable: adjacency only, not an unspecified safety mechanism.
4. The reference warns that some acquisition paths may coerce abstain. This gate does not execute them, observes zero frozen abstains, and makes abstain an explicit error in BCEM.
5. Design prose sometimes lists 40- and 60-second caps as independent. Executable controlled materialization applies their minimum, so 60 seconds is redundant.
6. Native canonicalization can preserve repository intervals with no positive anchor. Such native outputs are excluded from the legal EventRelation ceiling; selector comparison uses the saved trace under controlled materialization.

## Leakage boundary

The legal-partition engine receives only units, queried positive/negative observations, and frozen caps. The evaluator-only ceiling additionally receives the event reference and frozen evaluator. The public operator, if authorized after the headroom gate, is located in a separate module that has no reference parameter or reference-file access.
# Recovery correction: interval non-crossing

Independent recovery review falsified the earlier implicit assumption that monotone UnitTable endpoints imply disjoint unit intervals. Frozen units 345 and 346 overlap, so anchor-ID order alone admitted a split with overlapping output events. The legal-edge builder now rejects a cut whenever the preceding anchor end exceeds the next anchor start; invariant and emission checks enforce the same condition. This is a correctness repair to the claimed legal space, not an objective or metric change. Its effect on all 738 frozen traces is assessed in `FORMAL_REPAIR_EQUIVALENCE.csv` before seal.

