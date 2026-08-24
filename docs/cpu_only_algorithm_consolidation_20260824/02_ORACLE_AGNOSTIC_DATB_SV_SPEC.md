# Oracle-Agnostic DATB-SV Specification

Date: 2026-08-24

Algorithm ID: `DATB_SV_CPU_REPLAY_V1`

## 1. Problem definition

Given an initially unscanned video, an open-semantic query, a replaceable semantic oracle, and a hard wall-clock deadline, return as many distinct, durable query-relevant events as possible without admitting work that cannot safely finish and commit before the deadline.

Let temporal cells be immutable units \(C=\{c_1,\ldots,c_n\}\). SCAN exposes candidates from an unscanned cell. VERIFY evaluates one exposed candidate using an oracle. COMMIT atomically materializes a confirmed event in `EventRelation`.

Only results durably committed before deadline \(D\) contribute utility:

\[
U_D = \left|\{e: \operatorname{commit\_time}(e) \le D\}\right|.
\]

## 2. Oracle contract

The scheduler may use only the following oracle-facing interface:

```python
confirm(candidate, query) -> confirmation_result
```

The oracle may be a human, a heavy vision-language model, a cached label map, or another verified semantic procedure. The scheduler must not branch on oracle identity, model name, prompt, confidence implementation, or annotation source.

The oracle source is provenance metadata, not a scheduling feature. Replacing `cached_vlm` with `human` while preserving returned confirmation records must leave the action trace unchanged.

## 3. Scheduling policy

### SCAN order

Use deterministic breadth-first temporal bisection. For an interval of cells `[lo, hi]`, scan its midpoint, then enqueue left and right subintervals. This spreads early observations over the full video without fitting a data-dependent controller.

For 35 cells, the prefix is:

```text
17, 8, 26, 3, 12, 21, ...
```

### VERIFY order

VERIFY the highest-exposed eligible candidate according to the frozen candidate priority supplied by the replay manifest. A candidate cannot be verified before its source cell is scanned.

### Operator interleaving

Use fixed 1:1 alternation:

```text
SCAN, VERIFY, SCAN, VERIFY, ...
```

If the preferred operator has no legal deadline-safe action, fall back to the other operator. Stop when neither action can safely complete.

This is intentionally not a learned controller. Current evidence does not support learning action choice.

## 4. Deadline admission

Let `scan_upper` and `verify_upper` be frozen conservative duration bounds and `commit_reserve` the reserved time for durable commit. At elapsed time \(t\), an action of type \(a\) is admitted only if:

\[
t + \operatorname{upper}(a) + \operatorname{commit\_reserve} \le D.
\]

If observed action duration exceeds its declared upper bound, execution stops with a cost-bound violation. The system must not silently continue under a broken safety assumption.

## 5. Durable result semantics

1. A positive oracle response is not yet a query result.
2. The corresponding event must be atomically committed before the deadline.
3. Repeated confirmations with the same utility/event ID count once.
4. Post-deadline completions may appear in diagnostics but cannot mutate durable output.
5. Partial writes are forbidden.

## 6. Determinism and replay manifest

A valid replay manifest must contain:

```text
video_id
query_id
temporal cells and boundaries
candidate IDs and source cells
candidate priority
SCAN duration per cell or a frozen duration source
VERIFY duration per candidate or a frozen duration source
oracle result per candidate or a callable adapter
oracle provenance
requires_new_inference=false
```

The runner rejects inputs that declare new inference. No training or model invocation is part of this CPU implementation.

## 7. Baselines required for scientific evaluation

1. Uniform temporal SCAN with the same VERIFY policy.
2. Sequential/linear SCAN with the same VERIFY policy.
3. Largest-gap SCAN with the same VERIFY policy.
4. Fixed-ratio policies such as 1:3, 1:1, and 3:1 under identical admission rules.
5. VERIFY-only only when its initial candidate population is legally available; otherwise mark it infeasible rather than granting free candidates.
6. Full-oracle exhaustive processing as an offline ceiling, not a deployable baseline.

## 8. Primary evaluation target

For algorithm development with cached VLM labels, the primary endpoint is oracle-relative deadline utility:

\[
\operatorname{DistinctCommittedEvents@Deadline}.
\]

Secondary endpoints are anytime utility AUC, time to first committed event, candidate exposure recall relative to the same oracle, wasted post-deadline work, and action-level deadline violations.

Human-event MEC remains a later external-validity endpoint and must not be mixed into scheduler tuning.

## 9. Falsification

Reject the DATB-SV mechanism as a paper contribution if, on a diverse preregistered workload set under measured common costs:

1. it does not improve deadline utility over simple uniform or sequential scanning;
2. gains disappear after equalizing candidate access and commit semantics;
3. gains are driven by one video-query workload;
4. the required duration bounds are too loose to admit useful work;
5. oracle replacement materially changes scheduling despite identical confirmation records.

## 10. Claim boundary

The current implementation establishes an executable contract and supports CPU replay. It does not establish superior scientific performance. Performance claims require compatible real traces, multiple independent workloads, and eventually external semantic validation.
