# Binary SMDP oracle headroom report

Decision: `INSUFFICIENT_EVIDENCE`
Learning mainline: `NOT_AUTHORIZED`

## Strongest supported conclusion

The conditioned SMDP implementation exposes a plausible long-horizon timing
effect, but the current evidence cannot establish safe oracle headroom over R4.
In one V1_Q2/120 state, SCAN-first and VERIFY-first both reached one event while
SCAN-first improved AnytimeAUC by 0.144552. The label agreed at beam widths
128/512/2048, but was approximate because admitted transitions overran.

The decisive counterevidence is deadline safety: 9 of 11 V1_Q1/60 behavior
rollouts admitted a VERIFY that completed after the deadline. Two-phase commit
correctly prevented post-deadline event/Frontier updates, so the gain is not
manufactured, but the public bound is unusable as a safety shield. The
independent same-model valid physical profile has 20 calls and maximum 16.063 s,
whereas the evaluated V1 trace contains a 44.197 s complete CONFIRM. Selecting a
larger factor after observing V1 would be post-hoc leakage, not frozen causal
calibration.

## Required questions

1. **Does the oracle stably exceed R4?** Not established. Historical width-16
   multi-step AUC (281.25 versus R4 187.5) used the old unsafe Q90 contract and
   is not the new conditioned oracle. The new informative state is stable but
   approximate and unsafe.
2. **Does it select both actions?** One SCAN-better and four tied states are
   observed; no VERIFY-better state is established.
3. **Is headroom multi-video?** No. V1 supplies the new value evidence; V0 is
   missing 345/347 and 346/347 per-unit costs for its two queries.
4. **Is leave-best-video-out positive?** Not evaluable.
5. **Is low-budget behavior nonnegative?** No safety claim is possible: nine
   60-second behavior runs overran, with zero post-deadline commits.
6. **Is top-candidate pathology excluded?** No. Only the frozen top candidate
   was evaluated and the safe multi-video comparison is unavailable.

## Competing explanation and uncertainty

The observed SCAN advantage may be genuine early-discovery option value, but it
may also depend on a single video/query state and evaluator rejection of unsafe
continuations. The decision-critical missing evidence is a frozen, independent
complete-action cost calibration that covers tail latency without reading the
evaluated video, plus complete V0 replay costs.

## Stop action

Per the frozen contract, full dataset labeling, PUBLIC model comparison, MLP/
LightGBM training, replay aggregation and learned-controller claims stop here.
The required formal-path parquet is an explicitly row-tagged copy of the
bounded pilot (`artifact_status=INCOMPLETE_HEADROOM_GATE_STOP` and
`formal_eligibility=false`); it is not a formal cross-video dataset. Revision
requires new independent cost calibration and non-imputed V0 cost evidence,
after which the headroom gate must be rerun unchanged.
