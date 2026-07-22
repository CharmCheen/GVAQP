# State and transitions

## State

```text
PlanState(
  video_hash, predicate_contract_hash, model_prompt_parser_hash,
  ordered_plan_edges, next_edge_index, executed_window_ids,
  relation_fragments, canonical_relation, fallback_queue,
  logical_calls, physical_calls, gpu_seconds, wall_seconds,
  decoded_frames, input_tokens, output_tokens, cold_or_warm
)
```

No event reference, full unit labels or future physical outcomes may enter this
state.

## Transitions

1. `PLAN`: validate disjoint ownership cores and physical-call cap.
2. `EXECUTE_ENUM(edge)`: commit atomic request identity, then call the model.
3. `PARSE_OK(fragment)`: store raw/parsed output and add fragment rows.
4. `EMPTY_OK`: record a valid empty relation fragment.
5. `UNKNOWN_OR_PARSE_FAIL`: enqueue all dense units in the edge core according
   to the frozen fallback rule; do not record a negative fragment.
6. `RECONCILE`: core-owner filter, overlap duplicate matching and canonical
   sorting.
7. `STOP`: only after all owned cores or their fallbacks complete, or when the
   fixed physical cap is reached; cap exhaustion is an incomplete failure.

All per-call files are written by atomic replace before the next transition.
Retry attempts receive new attempt IDs and remain in the ledger.

