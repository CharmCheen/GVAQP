# Binary SMDP Value Validation Report V1

Final decision: `INSUFFICIENT_EVIDENCE`

## Strongest supported conclusion

The binary `SCAN` versus `VERIFY_TOP1` formulation is aligned with the real
objective in its contract and implementation: it optimizes deadline-time
distinct events lexicographically before AnytimeAUC, treats candidates only as
diagnostics, conditions both actions from an identical causal state, and
prevents post-deadline state commits. However, the available artifacts do not
establish that a deployable value policy can improve on R4. The learning
mainline therefore stopped at its preregistered oracle headroom gate.

This is not a finding that binary allocation has no value. It is a finding that
the current evidence cannot distinguish genuine multi-video headroom from a
single-state timing effect under an unsafe latency bound.

## Evidence by epistemic status

### Observed trace-grounded evidence

- The strongest frozen fixed policy is R4 (`SCAN:VERIFY` target 25:75), with
  historical macro AnytimeAUC 187.5.
- The historical width-16 multi-step result has AnytimeAUC 281.25, but it used
  the old Q90 admission contract, admitted 35 deadline overruns and is not a
  comparable estimate of the new conditioned oracle.
- Eleven V1_Q1/60 pilot behavior states reached a point where both actions were
  legal. Four selected conditioned labels were stable across beam widths
  128/512/2048 and were all `EFFECTIVELY_TIED`; three were exact.
- One deliberately informative V1_Q2/120 post-SCAN state was
  `SCAN_BETTER`: both branches ended with one event and SCAN-first increased
  AnytimeAUC by 0.144552. Its sign was stable across widths, but the result was
  approximate because unsafe continuations were rejected.
- Nine of the eleven V1_Q1/60 behavior rollouts completed after the deadline.
  The corrected two-phase transition committed no Frontier, event, estimator
  or scan-state effects after those overruns.
- V0 lacks the original raw per-unit cost artifact: 345/347 V0_Q1 and 346/347
  V0_Q2 confirmation costs are explicitly imputed. It cannot provide an
  independent complete cross-video cost calibration.
- The independent 20-call physical profile has maximum VERIFY time 16.063 s,
  while the evaluated V1 trace contains a complete 44.197 s call. Increasing a
  multiplier after reading V1 would be post-hoc leakage.

### Observed physical-runtime evidence

The unmodified Hangzhou video is 5600.566 seconds, 852x480, 30 fps, H.264 with
AAC audio; `ffprobe` completed successfully. A content-blind frozen subset of
three 10-second clips produced the following results:

| Model | Inference mean | GPU memory | Labels at 1400 / 2800 / 4200 s | Repeat stability |
|---|---:|---:|---|---|
| Qwen3-VL-8B-Instruct | 8.281 s | 17.93 GiB, one A100 | negative / positive / negative | byte-identical |
| Qwen3-VL-32B-Instruct-FP8 | 24.726 s | 58.95 + 61.95 GiB, two A100s | negative / positive / positive | byte-identical |

Formal parse success was 8/8 and model inputs had identical frame hashes and
tensor shapes. Cross-model label agreement was 2/3. A direct contact-sheet
review did not support the 32B claim that a pedestrian crossed from the left at
4205-4206 s. This is qualitative contradiction evidence, not human annotation.

The 32B checkpoint cannot execute its FP8 path on A100 compute capability 8.0.
Transformers dequantized it; a single 80 GB GPU OOMed at 78.97 GiB process
memory, and a two-GPU run required normalizing residual FP32 ignored layers to
BF16. Thus 8B is the more plausible online-verifier candidate of the two tested
paths; 32B is at most an expensive, fallible offline reviewer on this host.

### Derived conclusions

- The new oracle's real headroom over R4 is **not estimable** from the bounded
  pilot. The only new non-tie has zero terminal-event advantage and +0.144552
  state-local AnytimeAUC, not a macro policy improvement.
- Both action classes are not established: one approximate SCAN-better state,
  zero VERIFY-better states and four ties are observed.
- Multi-video contribution, leave-best-video-out behavior and low-budget
  nonnegativity are not evaluable under the missing/imputed V0 costs.
- The current independent latency calibration cannot serve as a zero-overrun
  safety bound. Therefore any apparent benefit under it is not deployable
  evidence.
- The Hangzhou probe establishes cost, memory, stability and disagreement. It
  does not establish candidate recall, model accuracy or controller benefit.

### Working hypotheses and competing explanations

`H1`: early SCAN sometimes has genuine option value because it discovers a
candidate soon enough to leave later verification time. The V1_Q2 state is
consistent with this.

`H2`: the observed sign is a single-video/query artifact amplified by rejected
unsafe continuations or the frozen top-candidate rule. The lack of any
VERIFY-better state, missing V0 costs and approximate label are also consistent
with this.

The evidence does not discriminate H1 from H2. A safe, complete cross-video
cost replay is the dominant missing measurement.

## Answers to the required questions

1. **Does the design target many and early events?** Yes at the formal level:
   terminal distinct events are primary and AnytimeAUC is secondary. Empirical
   improvement is not established.
2. **How much real oracle headroom over R4 exists?** Unknown. The old macro
   difference of 93.75 AnytimeAUC is invalid under the new safety contract. The
   only new informative state has terminal delta 0 and Anytime delta +0.144552.
3. **Which states should SCAN or VERIFY?** No deployable rule is supported.
   One V1_Q2/120 state after an initial scan favored another SCAN on timing;
   four sampled V1_Q1/60 states tied; no stable VERIFY-better state was found.
4. **Is public state sufficient?** Not tested after the headroom stop. Neither
   insufficiency nor sufficiency may be inferred from a `NOT_RUN` experiment.
5. **Are LightGBM or MLP better than simple models?** Unknown; none was trained
   because the prerequisite gate failed. LightGBM was also not installed.
6. **Did a conservative controller improve closed loop?** Unknown; learned and
   unshielded controllers were not created. The implemented fallback always
   uses R4 subject to a frozen-bound safety shield and makes no improvement
   claim.
7. **What was Hangzhou resource-allocation behavior?** No formal policy
   allocation comparison ran. The physical probe measured verifier service:
   8B requires roughly one 8.3-second GPU service per fixed clip; the tested
   32B path requires two GPUs and roughly 24.7 seconds.
8. **What are the 8B/32B roles?** Of the tested paths, 8B is the more plausible
   online-verifier candidate on this A100 host; no full online-service deadline
   was validated. 32B is an offline reviewer, not ground truth and not a third
   SMDP action; its observed unsupported positive weakens teacher trust.
9. **What is the evidence level?** Mechanism pilot with direct trace and
   physical-runtime evidence, but insufficient independent cross-video and
   safety evidence for a learned policy.
10. **Final decision?** `INSUFFICIENT_EVIDENCE`.

## Stop decision and rejection trigger

PUBLIC_V0/V1 modeling, evaluator upper-bound modeling, LightGBM/MLP, replay
aggregation, learned closed loop, ablations and the formal Hangzhou
R4/shielded/best-fixed comparison are `NOT_RUN_HEADROOM_GATE_FAILED`. Running
them after the failed prerequisite would create analysis volume without making
the central oracle/safety claim valid.

The required `dataset/state_action_values.parquet` path contains only the four
pilot rows. Every row is tagged `INCOMPLETE_HEADROOM_GATE_STOP` with
`formal_eligibility=false`; the manifest lists the missing cross-video and
safety requirements. It must not be consumed as a completed formal dataset.

Reject or revise the current stop only after both of the following are
available: (1) complete non-imputed V0 per-action costs or a freshly frozen
equivalent independent trace, and (2) an independently preregistered
complete-action latency bound that produces zero overrun and zero incomplete
admitted actions. Rerun the unchanged headroom gate. Proceed to state modeling
only if stable SCAN-better and VERIFY-better states occur across multiple
videos, R4 headroom survives leave-best-video-out, and low-budget safety is
nonnegative.
