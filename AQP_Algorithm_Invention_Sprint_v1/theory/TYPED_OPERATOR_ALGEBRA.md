# Typed semantic-operator algebra

| Operator | Input | Reference output | Physical implementation | Main errors | Cache key / composability |
|---|---|---|---|---|---|
| `UNIT_PRESENCE` | 10 s unit, predicate | Boolean/abstain | Existing Qwen3-VL unit prompt | FN/FP/abstain; no identity | Video+unit+model+prompt; can seed or patch enumeration |
| `BLOCK_ANY` | interval, predicate | Boolean/unknown | Interval VLM prompt | Catastrophic FN if used for pruning | Never final-prune unless contract permits; closed route here |
| `BLOCK_COUNT` | interval, predicate | nonnegative count/unknown | Interval VLM prompt | under/over-count | Ordering/diagnostic only without calibrated contract |
| `EVENT_ENUMERATE` | padded interval, predicate, local time origin | zero or more typed events with local boundaries | Frozen Qwen3-VL video prompt | missed events, hallucinated events, duplicate identity, boundary error, parse failure | Window+sampling+contract hash; output is a relation fragment |
| `EVENT_LOCALIZE` | candidate event and context | refined event object | Focused VLM prompt | boundary shift or wrong instance | Composes after enumerate; not used merely to turn retrieval into the claimed algorithm |
| `BOUNDARY_REFINE` | event plus adjacent frames | refined start/end | Higher-rate focused call | templated boundaries, truncation | Optional escalation; separately charged |
| `BATCH_UNIT_PRESENCE` | independent unit batch | vector of booleans | Physical model batch | cross-item parse/coupling, OOM | Logical cost is batch size; GPU cost is measured batch runtime |
| `CHEAP_SEMANTIC_INDEX` | video, query family | reusable public index | CLIP/X-CLIP or other frozen index | search miss, query mismatch | Cold build charged; content-addressed reuse |
| `REUSE_CACHED_EMBEDDING` | video/query | ranking features | Existing sealed CLIP cache | weak separability | Cannot be tuned on strict reference |
| `AUDIT_BLOCK` | block under fixed audit contract | exact unit audit relation | Dense exact unit operator | cost | Known inclusion design required for certificates |
| `RECONCILE_RELATIONS` | overlapping relation fragments and core ownership | one deterministic ApproxEventRelation | CPU interval/identity matching | overmerge/oversplit | Idempotent under canonical sort and owner rule |

## Algebraic rules

1. `EVENT_ENUMERATE` is set-valued; it cannot be substituted by `BLOCK_ANY`
   without losing multiplicity, identity and boundaries.
2. Each enumeration edge owns a disjoint core. An event is eligible for final
   ownership only in the core containing its reported canonical point. Events
   reported solely in overlap context are evidence for reconciliation, not
   independent output rows.
3. `UNKNOWN`, parser failure or OOM triggers a frozen exact/unit fallback; it
   never becomes a negative.
4. A cached result is equivalent only under the complete semantic and physical
   cache key. Reusing merely by video interval is invalid.
5. COUNT can prioritize/refine but never removes an event without a separate
   validated rule.

## Reference versus approximate behavior

The reference enumerator returns every reference event whose canonical point
lies in the core, using overlap only as context. The physical operator may
miss, hallucinate or mislocalize, and its result is explicitly approximate.
The final relation retains operator/window lineage so every event row can be
audited or patched.

