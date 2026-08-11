# Unknown-video sequential SCAN/VERIFY findings

Status: completed cached causal mechanism study.  The result is exploratory,
not a physical-deadline or broad-generalization claim.

## 1. Objective and causal contract

The study tests the actual closed loop requested for a completely unknown
video:

```text
empty public state
→ choose SCAN(cell) or VERIFY(unit)
→ reveal only that action's observation
→ atomically update coverage, posterior, K3 and cost state
→ choose again
→ STOP before the budget
```

`SCAN` reveals public proxy scores for one label-blind, contiguous 10-unit
cell. `VERIFY` is legal only for an already scanned unit and reveals exactly
that unit's frozen label.  A policy never receives the oracle table or
reference events.  Unknown and parse-failure outcomes are preserved.

The mechanism-cost profile is:

```text
SCAN one 10-unit cell: 0.1 cost units
VERIFY one unit:       1.0 cost units
budgets:               5, 10, 20, 50, 80, 100
```

These are explicit abstract costs, not measured seconds.  SCAN must reserve a
complete VERIFY because no probable event passed the prior 0.80 risk gate.

The primary utility is time/cost-weighted event recovery:

\[
J_B(\pi)=\frac{1}{B}\int_0^B N_{\mathrm{matched\ K3}}(c)\,dc,
\]

with terminal event recall/F1 and precision reported separately.

## 2. Label-hiding design

Five candidate policies were selected using only reciprocal folds between:

```text
realcartest_0_1570
realcartest_2000_3200
```

For each development target slice, the posterior used only the other slice.
`dataset3_development` labels were not used for candidate selection or
posterior fitting.  The frozen candidate-selection rule was:

```text
maximum mean AnytimeEventRecallAUC
→ tie by AnytimeEventF1AUC
→ tie by terminal recall
subject to mean precision >= 0.70
```

Only after `FROZEN_SELECTION.json` was written was the query-bound primary
video evaluated.  Policies were deterministic except ARC; deterministic rows
are not treated as independent seeds.

## 3. Five candidate iterations

| Candidate | Main change | Development Anytime recall AUC | Development terminal F1 |
| --- | --- | ---: | ---: |
| `FIXED_SCAN1_VERIFY1` | broad SCAN followed by one VERIFY | 0.249 | 0.511 |
| `FIXED_SCAN1_VERIFY3` | one SCAN followed by three VERIFY | 0.270 | 0.540 |
| `DYNAMIC_PROXY_VALUE_V1` | compare expected proxy VERIFY and SCAN option value | 0.231 | 0.496 |
| `DYNAMIC_K3_VALUE_V2` | add K3 new-event novelty | 0.272 | 0.530 |
| `DYNAMIC_ADAPTIVE_K3_VALUE_V3` | add online revealed-label calibration and uncertainty value | 0.272 | 0.530 |

`DYNAMIC_ADAPTIVE_K3_VALUE_V3` won by the frozen development ordering and was
therefore the only valid selected-method result on the held-out primary video.
V2 and V3 were nearly tied, which was an early warning that the adaptive term
was weakly identified.

## 4. Primary held-out result

At nominal cost, selected V3 compared with the two shared-environment
baselines as follows.

| Budget | Method | Returned events | Precision | Recall | F1 | Anytime recall AUC | First-event cost |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | ARC | 0.0 | 0.000 | 0.000 | 0.000 | 0.000 | — |
| 5 | Current two-stage | 0.0 | 0.000 | 0.000 | 0.000 | 0.000 | — |
| 5 | Selected V3 | 2.0 | 1.000 | 0.077 | 0.143 | 0.040 | 1.1 |
| 20 | ARC | 0.6 | 0.400 | 0.023 | 0.043 | 0.006 | 13.5 |
| 20 | Current two-stage | 3.0 | 1.000 | 0.115 | 0.207 | 0.026 | 14.5 |
| 20 | Selected V3 | 4.0 | 1.000 | 0.154 | 0.267 | 0.092 | 1.1 |
| 50 | ARC | 2.6 | 0.800 | 0.100 | 0.177 | 0.038 | 19.3 |
| 50 | Current two-stage | 4.0 | 1.000 | 0.154 | 0.267 | 0.099 | 14.5 |
| 50 | Selected V3 | 5.0 | 1.000 | 0.192 | 0.323 | 0.130 | 1.1 |
| 100 | ARC | 7.0 | 1.000 | 0.269 | 0.424 | 0.116 | 25.9 |
| 100 | Current two-stage | 11.0 | 1.000 | 0.423 | 0.595 | 0.204 | 14.5 |
| 100 | Selected V3 | 11.0 | 0.909 | 0.385 | 0.541 | 0.225 | 1.1 |

Across the six budgets, selected V3 achieved mean Anytime recall AUC `0.122`,
versus `0.081` for current two-stage and `0.041` for ARC.  This is about `+51%`
and `+200%`, respectively.  The gain is genuinely an early-return gain: at
budget 100 V3's Anytime recall is `+10%` above current, but terminal F1 is
`9%` lower.

## 5. Adversarial mechanism result

The outer result did **not** establish that the adaptive selector is the best
or universal scheduler.

`FIXED_SCAN1_VERIFY1`, which was a candidate before primary evaluation, was the
strongest observed method on the primary video:

| Nominal mean across budgets | ARC | Current two-stage | Selected V3 | Fixed 1:1 |
| --- | ---: | ---: | ---: | ---: |
| Anytime recall AUC | 0.041 | 0.081 | 0.122 | 0.133 |
| Anytime F1 AUC | 0.071 | 0.133 | 0.207 | 0.225 |
| Terminal recall | 0.101 | 0.167 | 0.212 | 0.212 |
| Terminal F1 | 0.166 | 0.256 | 0.332 | 0.334 |

At budget 100, fixed 1:1 preserved the current method's 11 events, precision
`1.0`, recall `0.423`, and F1 `0.595`, while raising Anytime recall AUC from
`0.204` to `0.232` and reducing first-event cost from `14.5` to `1.1`.

Relative to current two-stage, fixed 1:1 improved mean Anytime recall AUC by
about `64%`; relative to ARC, by about `227%`.  This supports interleaving and
broad temporal coverage.  It does not support a learned switching surface.

Because fixed 1:1 was identified as strongest after the primary results were
visible, it cannot be retrospectively substituted for V3 as the held-out
winner.  It is the strongest observed baseline and a required fallback for the
next independent evaluation.

## 6. Cost sensitivity

A post-heldout diagnostic varied SCAN cost without changing any policy:

| SCAN cost | V3 Anytime recall AUC | Fixed 1:1 | Current | ARC |
| ---: | ---: | ---: | ---: | ---: |
| 0.05 | 0.094 | 0.136 | 0.086 | 0.043 |
| 0.10 | 0.122 | 0.133 | 0.081 | 0.041 |
| 0.20 | 0.108 | 0.128 | 0.071 | 0.036 |

Fixed 1:1 exceeded V3 at all three costs.  The dynamic-selector failure is not
an artifact of only the nominal `0.1` choice.

## 7. Why V3 failed to become universal

Observed evidence supports four explanations:

1. The early gain comes primarily from the label-blind temporal bisection SCAN
   order and immediate interleaving.  Fixed 1:1 receives the same benefit.
2. Cross-video posterior calibration is weak.  The two development slices are
   one source video and lack prompt/parser hashes.
3. V3 sometimes performs several cheap SCAN actions while a useful VERIFY is
   already available; its expected cell-maximum model does not transfer well
   enough to know when exploration should stop.
4. K3 novelty discount changes VERIFY targets but does not consistently
   improve canonical event recovery.  At the largest budget it reduced heldout
   terminal precision/recall relative to raw-proxy VERIFY.

The dominant bottleneck is therefore state/action-value transfer, not absence
of a complicated controller.

## 8. Decision and next iteration

```text
REVISE_STATE
```

The next scheduler must use fixed 1:1 as a conservative fallback and learn
only the *advantage of overriding it*:

\[
A(S,a)=Q(S,a)-Q(S,\pi_{\mathrm{fixed\ 1:1}}).
\]

An override is legal only when:

\[
\hat A(S,a)-\beta\sigma_A(S,a)>0.
\]

Required next evidence:

- more independent training videos with the same query identity;
- forced SCAN-first/VERIFY-first continuation targets at naturally reachable
  states;
- a content-aware but label-blind SCAN-region feature set;
- measured physical SCAN/VERIFY costs;
- an entirely new held-out video after the revised selector is frozen.

If the revised selector cannot beat fixed 1:1 on a new video, the correct
conclusion is that a fixed interleaving schedule is sufficient for the current
state representation.

## 9. Artifacts

Primary study:

```text
outputs/sequential_unknown_video_study/
```

Cost sensitivity:

```text
outputs/sequential_unknown_video_cost_sensitivity/
```

Implementation:

```text
src/rc_sem/sequential.py
src/rc_sem/sequential_policies.py
experiments/sequential_unknown_video_study.py
experiments/sequential_cost_sensitivity.py
```

No GPU inference or new 32B call was made.
