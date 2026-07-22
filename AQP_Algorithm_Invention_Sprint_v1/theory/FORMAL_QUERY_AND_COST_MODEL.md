# Formal query and cost model

## Reference query

For video `V`, predicate `q`, and reference semantic contract `O`, let

`E*(V,q) = {e_1,...,e_m}`

be the reference EventRelation. Each event has an identity, type, temporal
support and one canonical ownership point. The query returns an explicitly
approximate relation `E_hat`, not positive clips:

```text
ApproxEventRelation(
  event_id, event_type, start_time, end_time,
  evidence_window_ids, confidence_status, lineage, owner_core_id
)
```

The strict experiment uses the frozen VLM-defined pseudo-reference and its
one-to-one event evaluator. This is not human ground truth.

## Quality

The primary constraints are frozen before headroom simulation:

- event recall at least `0.80`;
- event F1 at least `0.80`;
- total semantic execution cost strictly below `0.70` of dense execution.

Both mean and lower-tail diagnostics are reported in simulation; the physical
gate uses the single realized strict relation and therefore makes no
distribution-free coverage claim.

## Cost vector

Every plan reports

`C(P) = (logical_calls, gpu_seconds, wall_seconds, decoded_frames,
vision_tokens, output_tokens, peak_memory, cold_index_seconds)`.

The scalar optimization objective is GPU seconds for a fixed hardware/model
identity. Wall time and logical calls are mandatory secondary results. A
warm-query result may exclude only a content-addressed reusable index whose
build cost is separately reported. Model loading is charged to the cold plan.

## VERA query-plan problem

Let the timeline be partitioned into atomic units `1..N`. A candidate physical
edge `a=(i,j,o,m)` assigns core units `[i,j)` to one operator `o` and reads an
input window padded by overlap margin `m`. Its predicted cost is `c(a)` and its
pre-frozen additive missed-event-risk surrogate is `r(a)`. The dense exact edge
for every unit is always available.

VERA solves the resource-constrained shortest path

`min sum_a c(a)` subject to `sum_a r(a) <= R_max`,

over a DAG whose vertices are timeline positions and whose edges are legal
operator windows. A discretized risk dimension gives an exact DP for the
discretized model. A Lagrangian shortest path is used only as a diagnostic, not
as a guarantee about the undiscretized problem.

The risk profile is an assumption learned outside the frozen test or supplied
as a sensitivity parameter. If no approximate plan satisfies the constraint,
the dense path is selected. A physical pilot tests operator viability; it does
not validate a portable risk model from one video.

## Cold, warm and amortized semantics

- **Cold:** model load, decoding/preprocessing and every operator call are
  charged.
- **Warm single query:** model is resident; no semantic result cache is reused.
- **Warm compatible workload:** a cached EventRelation fragment may be reused
  only if video hash, predicate contract, model hash, prompt/parser hash, frame
  sampling and window bounds match exactly.
- **Amortized:** `(index build + all misses + reconciliation)/Q` for `Q`
  compatible queries. No amortized claim is made without an explicit workload.

## Non-guarantees

This formulation does not make event errors independent, does not identify
unseen events from one video, and does not certify recall. It provides an
optimizer conditional on a frozen operator profile and a direct empirical
falsification route.

