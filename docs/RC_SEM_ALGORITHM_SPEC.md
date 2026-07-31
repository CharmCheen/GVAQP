# RC-SEM algorithm specification

Status: staging specification for independent review.  This document does not
modify the frozen V3 oracle, its K3 reference relation, or the sealed full-grid
execution.

## 1. Research objective

RC-SEM (Risk-Controlled Speculative Event Materialization) maximizes events
returned before a hard deadline, not the number of expensive labels purchased.
An event may be returned as `PROBABLE_EVENT` before VERIFY when its event-level
calibrated probability lower bound clears a frozen precision requirement.

The primary objective is

\[
\max_\pi \frac{1}{D}\int_0^D M(s_t)\,dt + \eta M(s_D),
\]

subject to

\[
\operatorname{LCBPrecision}(R_t^{probable}) \ge \pi_{min},
\qquad t + C^+(a_t) \le D.
\]

`PROBABLE_EVENT` and `VERIFIED_EVENT` are different public identities.  A
probable event never becomes an authoritative oracle label.

## 2. Evidence semantics

The runtime relation is

\[
R_t = R_t^{verified} \cup R_t^{probable}.
\]

- `VERIFIED_EVENT`: frozen K3 has an authoritative positive support record.
- `PROBABLE_EVENT`: no authoritative positive support exists, but an
  event-level lower confidence bound passes the frozen admission rule.
- `EVENT_HYPOTHESIS`: visible runtime hypothesis that is not returnable.

Unknown and parse-failure labels are not negatives.  Evaluator-only reference
labels are forbidden from the runtime state and controller input.

`VERIFIED_EVENT` verifies event existence under the frozen support rule; any
remaining temporal-boundary uncertainty is still reported explicitly and is
not silently treated as zero.

## 3. Event probability and risk admission

The event model predicts the probability that a canonical runtime hypothesis
will match a final K3 reference event:

\[
\hat p_e=P(e\in R^*_{K3}\mid s_t), \qquad
\ell_e=\max(0,\hat p_e-\beta\sigma_e).
\]

This is an event-level prediction.  A maximum unit or candidate score is not a
valid substitute because K3 merge, split, deduplication, negative barriers and
boundary uncertainty are non-additive.

An unverified event is published only when

\[
\ell_e\ge\max(\tau_p,\pi_{min}),
\]

and the admitted probable set also satisfies

\[
|R_t^p|^{-1}\sum_{e\in R_t^p}\ell_e\ge\pi_{min}.
\]

The implementation uses deterministic ordering by lower bound, probability and
canonical event ID.  Thresholds, uncertainty multiplier and probability model
identity must be frozen before held-out evaluation.

## 4. Risk-adjusted materialization utility

For a returned event,

\[
u(e)=
\begin{cases}
1, & e\in R_t^v,\\
\ell_e-\lambda(1-\ell_e), & e\in R_t^p.
\end{cases}
\]

The runtime score is

\[
M(s_t)=\sum_{e\in R_t}u(e).
\]

Canonical event IDs are deduplicated before utility is computed.  Probable and
verified versions of the same event cannot both earn utility.

## 5. Actions and value targets

The action space is `SCAN`, `VERIFY`, and `STOP`.

`SCAN` value includes:

- new canonical event discovery;
- direct probable-event publication;
- frontier expansion and later verification opportunity;
- boundary extension or fragmentation reduction.

`VERIFY` value includes:

- probable-to-verified promotion;
- rejection of false hypotheses;
- K3 merge/split and boundary resolution;
- calibration improvement for later decisions.

The action-value model estimates safe-continuation returns
`Q_scan`, `Q_verify`, and their uncertainties.  VERIFY target selection should
maximize expected EventRelation change per conservative cost, rather than
simply choosing the candidate with the largest positive score.

## 6. Decision rule

For safe SCAN and VERIFY values,

\[
\Delta=Q_{scan}-Q_{verify},\qquad
\sigma_\Delta=\sqrt{\sigma_{scan}^2+\sigma_{verify}^2}.
\]

- choose SCAN when `Delta - beta * sigma_Delta > scan_margin`;
- choose VERIFY when `Delta + beta * sigma_Delta < -verify_margin`;
- otherwise use the frozen best fixed/two-stage fallback;
- choose STOP when no action fits its conservative complete-action bound, or
  every safe action has non-positive optimistic value.

Unlike a verify-only materializer, RC-SEM may admit a final safe SCAN without
reserving time for a subsequent VERIFY, because SCAN can itself publish a
risk-controlled probable event.  `scan_requires_verify_reserve` remains a
frozen configuration and mandatory ablation.

## 7. Deadline safety and commits

Every action uses two-phase state publication:

1. validate unique action ID and conservative complete-action cost;
2. stage physical outputs outside public state;
3. validate completion time and integrity;
4. commit only when completion time is at or before the deadline.

Late output is preserved for audit but cannot update runtime state or event
relations.  Duplicate attempts and duplicate commits fail closed.

## 8. Label hiding and training

For evaluation video `v`, event and Q models must be trained and calibrated
without any hidden labels from `v`.  Leave-one-video-out evaluation is the
minimum valid mechanism test.  The evaluator may use the held-out reference to
score actions and generate reports, but runtime code receives only:

- scanned coverage and candidate features;
- revealed VERIFY labels;
- runtime K3 hypotheses;
- probable/verified public state;
- cost estimates and remaining budget.

Training on all three videos and evaluating on the same three is development
evidence only, not a label-hiding result.

## 9. Required metrics

Report separately:

- probable, verified and combined event recall/precision;
- probability calibration and precision-coverage curves;
- probable-to-verified latency;
- time to first returned event;
- AnytimeReturnedEventUtility and AnytimeEventRecallAUC;
- false-positive probable events;
- incomplete admitted actions and post-deadline commits.

The success criterion is a strict improvement over the best fixed/two-stage
policy at the same deadline and probable-event precision floor, without a
negative leave-one-video-out result.

## 10. Main-repository integration contract

The current repository already has `PROBABLE_EVENT`, `IncrementalK3`, public
probable-event state fields, and a binary deadline shield.  Integration after
the sealed full-grid run should be a reviewed change with these boundaries:

1. keep evaluator K3 and runtime K3 entry points separate;
2. add event posterior mean, uncertainty and lower bound to the runtime event
   record or to a sidecar publication record;
3. replace raw maximum-candidate thresholding as the probable publication gate
   with `RiskControlledMaterializer`;
4. add RC-SEM Q estimates to the public controller state, never oracle labels;
5. preserve the current shield as a baseline and compare its mandatory
   SCAN-plus-VERIFY reserve against the speculative-SCAN rule;
6. freeze thresholds and hashes before held-out replay.

The staged code is deliberately dependency-free and can be adapted behind
these interfaces without changing the frozen 1,475-unit oracle definition.

`configs/rc_sem_reference_v1.json` binds the reference defaults but is marked
`STAGING_NOT_CONFIRMATORY`.  Confirmatory thresholds require calibration and a
new preregistered hash; the reference defaults are not post-hoc authority.

## 11. Unknown-video sequential realization

The runtime scheduler is a closed-loop belief-state policy, not a static
ranking.  The concrete action is parameterized:

\[
a_t\in\{SCAN(r,d),VERIFY(e,i),STOP\}.
\]

Every committed action produces an observation and a new public state:

\[
S_{t+1}=F(S_t,a_t,o_{t+1}).
\]

The state records only scanned coverage, public proxy/candidate features,
revealed VERIFY labels, runtime K3, probable/verified events, observed action
costs and remaining budget.  It never contains the evaluator reference or
unrevealed unit labels.

For call-equivalent cached replay, optimize:

\[
J_B(\pi)=\mathbb E\left[\frac{1}{B}\int_0^B U(S_c)dc+\eta U(S_B)\right].
\]

For physical execution, replace cost (c) with committed wall-clock time.
Actions are selected by conservative continuation value, with a frozen safe
fallback:

\[
a_t=\arg\max_{a\in A_{safe}(S_t)}\hat Q(S_t,a)-\beta\sigma_Q(S_t,a).
\]

The preferred transferable target is advantage over the best fixed policy:

\[
A(S,a)=Q(S,a)-Q(S,\pi_{fallback}).
\]

This prevents an uncertain learned selector from replacing a stronger simple
schedule.

## 12. Current sequential evidence

The cached unknown-video study implemented five candidates plus common current
and ARC baselines.  Development selected `DYNAMIC_ADAPTIVE_K3_VALUE_V3`, but a
held-out mechanism test found that `FIXED_SCAN1_VERIFY1` had higher Anytime
recall/F1 AUC.  The fixed schedule also dominated V3 for SCAN costs
`0.05/0.10/0.20`.

Therefore the current algorithm decision is `REVISE_STATE`: interleaving is
supported, but a universal learned switching surface is not.  Fixed 1:1 is the
mandatory fallback for the next independently held-out revision.  Full
evidence and non-reselection boundaries are in
`docs/SEQUENTIAL_UNKNOWN_VIDEO_STUDY_FINDINGS.md`.
