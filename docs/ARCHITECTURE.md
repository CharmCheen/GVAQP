# Architecture

The runtime is a causal loop with five narrow boundaries:

1. `garc.scan` represents public coverage and selects the next microchunk.
2. `garc.controller` binds frozen candidate witnesses, admits/deduplicates/retains the bounded Frontier, checks complete-action deadline fit, and applies the fixed realized-time ratio.
3. `garc.confirm` constructs the selected-candidate request, invokes only an injected replay/physical adapter, parses the result, materializes frozen event identities, and atomically commits completed results and the final STOP snapshot.
4. `garc.evaluation` computes replay utility and exposes opt-in baselines.
5. `garc.audit` performs research-support provenance, decode, seek, overlap, leakage, and artifact checks; it is not consulted by runtime scheduling.

No module reads the source repository, legacy `outputs/`, video identity, semantic labels, or future outcomes to make a scheduling decision. The combined runner is a local replay/dry-run integration and does not include an Oracle client.

The formal online order is:

```text
AnytimeLargestGap SCAN -> candidate generation -> Frontier admission/deduplication/retention
-> deadline admission + fixed 25:75 realized-wall-clock choice -> CONFIRM adapter
-> result parsing -> event materialization -> distinct-event deduplication
-> durable action commit -> STOP/final durable result
```
