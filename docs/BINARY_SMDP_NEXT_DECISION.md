# Binary SMDP Next Decision

Current decision: `INSUFFICIENT_EVIDENCE`

Do not expand to `CONFIRM(candidate)`, `SCAN(region)` or offline RL. The
decision-critical blocker is not model capacity; it is the absence of a safe,
independent, complete cross-video transition-cost basis for the conditioned
oracle.

## Next highest-value action

Construct one frozen cost-recovery experiment before any further value-model
work:

1. Recover the missing V0 raw action-cost artifact if an immutable copy exists.
   If it does not, create a new versioned trace rather than silently filling
   medians.
2. On an independent calibration video set, run the exact frozen verifier,
   clip sampler, decoding limit and dedicated-GPU execution stack. Freeze the
   sampling plan and latency-bound rule before looking at evaluated V0/V1
   tails. Retain timeouts, parse failures and incomplete calls.
3. Replay the current behavior policies with the new bound. The acceptance
   observation is zero deadline overrun, zero post-deadline commit and zero
   incomplete admitted action without using evaluated-task future costs.
4. Rerun beam widths 128/512/2048 and the unchanged headroom gate. Require both
   SCAN-better and VERIFY-better stable states from multiple videos, positive
   leave-best-video-out headroom over R4 and nonnegative low-budget behavior.

If step 3 fails, reject the current non-preemptive admission design and revise
the execution/safety mechanism before revisiting action values. If step 4
passes, proceed in order to PUBLIC_V0/PUBLIC_V1 sufficiency, simple linear
models, shallow trees/MLP only if justified, conservative closed-loop replay,
and then a frozen Hangzhou R4 versus shielded-controller versus best-fixed
comparison.

Only after all binary gates pass should the structured sequence be considered:

1. expand `CONFIRM(candidate)`;
2. then expand `SCAN(region)`;
3. finally unify them as `Q(s, action-object)`.
