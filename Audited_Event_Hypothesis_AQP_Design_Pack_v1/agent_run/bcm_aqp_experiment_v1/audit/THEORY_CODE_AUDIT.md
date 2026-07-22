# BCM-AQP v1 Theory/Code Audit

Audit date: 2026-07-10 UTC  
Scope: frozen clean-benchmark materialization, native canonicalization, matching,
event metrics, `OracleAccessor`, and saved-trace replay.  This is a source audit;
no benchmark, BCM, ceiling, ablation, synthetic suite, or VLM inference was run.

## Strongest conclusion

The previously missing clean-benchmark helper is present and auditable.  The
exact M0/M1 difference is one predicate:

- `original_k3` may join positive anchors with at most `g_max=1` intervening
  unit, provided no queried negative lies in that open interval;
- `k3_bridge_safe` may join only immediately adjacent positive unit IDs.

Both variants apply the same first-anchor-to-new-anchor duration test and the
same queried-negative test.  Under the frozen configuration, the 40-second cap
binds and the 60-second cap is redundant.  The clean matcher uses a Hungarian
assignment over the scalar score `1000 * overlap_any + temporal_iou`; exact
equal-score assignment ties have no explicit semantic tie key in repository
code.

## Authoritative sources and hashes

Paths are relative to `/qiuyeqing/llama_prl/G-ARC`.

| Source | File SHA256 | Authoritative symbols (inclusive lines; symbol-source SHA256) |
|---|---|---|
| `Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v1/scripts/benchmark_lib.py` | `0a7a8ad4a13cc4404b0cfe7dfb1aef8958197267e22ff1df545ac4dbbf744610` | `materialize_from_trace` 80–149, `81f83ee4fee07d6985596c2e62abcd82f88eafd400db3297286d1b1eb3b1c195`; `canonicalize_native_segments` 152–205, `641c64690659f4c025a6db9f4d29289f62f6be463594714bdaa273644bca07df`; `match_events` 208–273, `76234232cec79476cd5ccd9e0e2f7058e5d6fa3e6b4d714a01ceeda16996f471`; `compute_metrics` 276–318, `eb99d54b99e71bd77f1b9d66002c5f36ab3642f797fd6ebe915dafbbece5a501`; `evaluate_events` 321–329, `71692d4eb767efa62a6dcf03ba9c36641422d38df7b407f4622540f364f8fc97` |
| `Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v1/scripts/run_clean_benchmark.py` | `df269c9d0afa35966e4353bb04985aac406681981b819ea0272fd3f05b3d300f` | `OracleAccessor` 365–383, `8cb7158e1bc3591e80af81fff0ae51a0cfaa6bb49e988eb36bccfa665da12d4a`; `trace_from_order` 516–544, `5c384c5f9c4e34768dae8a3d37cc1947e72049bee06f8d85c2ab5910e219b38d`; `write_run` 584–677, `ebc3b084dab5c01ef8aa2f335bbe6457db535f910434820a2ada7472de4273bd`; comparison/AUC aggregation 980–1107 |
| `Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v1/scripts/replay_baseline_acquisition.py` | `5f4123685d49431825c7d797a2f991352870ab25ba7ffc92be5a494dd746930a` | `main` 20–65, `d61c0d92d7f31cd9e78871147cc257c88b4745824e2685d88d92d4ebbfb676c9` |
| `Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v1/frozen_inputs/evaluator_config.json` | `2466f38a74c65e56a2c52a99b033f81a5dee80cad33a31433a1a1b7219f01aa5` (physical file); canonical evaluator hash `ca34f7fe2ab23accd22d42dba299091890157fb7c913068199f318f4dc5db407` | frozen materializer and evaluator parameters |

Symbol-source hashes are SHA256 over the exact inclusive source lines plus a
terminal LF.  File hashes are SHA256 over bytes.

Runtime libraries installed during this audit were NumPy 2.2.6, SciPy 1.13.1,
and pandas 2.2.2.  These versions are evidence about the current replay
environment, not proof of the original benchmark-generation environment.

## Exact `materialize_from_trace` pseudocode

```text
INPUT trace, units, run_meta, materializer, config
IF trace empty: return empty canonical EventSegment table

labels := trace indexed by unit_id, lower-case oracle_label_after_query
P := sorted unique unit IDs whose label is "positive"
N := set of unit IDs whose label is "negative"
IF P empty: return empty canonical EventSegment table

unit_by_id := units indexed by unit_id
g_max := int(config.g_max, default 1)
core_cap := float(config.d_core_max, default 40)
seg_cap := float(config.d_seg_max, default 60)

groups := []
current := [first(P)]
FOR uid IN remaining(P):
    left := last(current)
    bridge_ids := integer IDs strictly between left and uid
    no_negative_barrier := bridge_ids has no intersection with N

    IF materializer == "original_k3":
        bridge_ok := (uid - left - 1 <= g_max) AND no_negative_barrier
    ELSE IF materializer == "k3_bridge_safe":
        bridge_ok := (uid == left + 1) AND no_negative_barrier
    ELSE:
        raise ValueError

    proposed_start := units[first(current)].start_time
    proposed_end := units[uid].end_time
    duration_ok := proposed_end - proposed_start
                   <= min(core_cap, seg_cap) + 1e-9

    IF bridge_ok AND duration_ok: append uid to current
    ELSE: append current to groups; current := [uid]
append current to groups

materializer_config_hash := canonical JSON SHA256 of
                            {"name": materializer, **config}
FOR each group in creation order:
    start/end := start of minimum anchor / end of maximum anchor
    inside_negatives := queried-negative IDs strictly between min/max anchors
    emit segment whose:
        anchor_unit_ids = all positive anchors in the group
        evidence_unit_ids = anchors union inside_negatives
        num_positive_anchors = group size
        num_negative_barriers = inside_negatives size
        verification_state = "oracle_confirmed"
        returned_seconds = end - start
RETURN rows in group creation order
```

### Exact `original_k3` behavior

For consecutive positive anchors in sorted positive-ID order, M0 permits a
join when all three conditions hold:

1. `uid - left - 1 <= g_max` (frozen `g_max=1`);
2. no queried-negative unit ID is strictly between `left` and `uid`;
3. the interval from the current group’s first anchor start to `uid`’s end is
   at most `min(d_core_max, d_seg_max) + 1e-9`.

An unqueried bridge is not evidence and is not listed in `evidence_unit_ids`,
although the returned temporal interval spans it.  A queried negative outside
the open interval between two positive anchors does nothing.  A boundary
negative does not shrink an isolated positive segment.

### Exact `k3_bridge_safe` behavior

M1 is identical except condition 1 becomes `uid == left + 1`.  It therefore
never joins across an unqueried unit-ID gap.  The negative-barrier predicate is
still evaluated, but for immediately adjacent IDs the open bridge set is empty,
so it is vacuously true under a consistent one-label-per-unit trace.

### Rule-by-rule difference

| Rule | `original_k3` | `k3_bridge_safe` | Consequence |
|---|---|---|---|
| Positive anchors | sorted unique queried positives | same | identical anchor universe |
| Unqueried bridge | up to `g_max` intervening IDs | zero intervening IDs | M1 may produce more/smaller groups, never fewer under valid common inputs |
| Queried negative | blocks if strictly between consecutive anchors | same predicate, normally vacuous because adjacency is required | M0 gives a gap-negative direct split role; M1 already splits that gap |
| Duration | first group anchor start to candidate anchor end `<= min(core,seg)+1e-9` | same | same cap semantics |
| Boundary expansion | none | none | boundary negatives do not trim |
| Output endpoints | first/last anchor unit times | same | no selected expansion |
| Evidence IDs | group anchors plus internal negatives | same | valid produced groups have no internal negatives |
| Confidence/state | fixed `1.0`, `oracle_confirmed` | same | no semantic difference |
| Ordering/IDs | sorted anchors, group creation order | same | deterministic absent invalid/ambiguous input |

## Queried negatives, coverage, and barrier safety

Observed implementation facts:

- Only rows whose lower-cased label is exactly `positive` or `negative` enter
  the anchor/barrier sets.  `abstain` is neither.
- Unqueried units never enter the negative set and never create a hard barrier.
- The materializer itself does not reject duplicate/conflicting trace rows.
  Valid acquisition and standalone replay paths reject duplicate `unit_id`s;
  the proofs below assume that contract.

Derived conclusions under valid unique-unit traces:

- **Positive-anchor coverage holds for both variants.** Each sorted positive is
  either appended to the current group or starts a new group, and every final
  group emits one interval containing its first/last anchors.
- **Barrier safety holds for M0.** Before every append, every queried negative
  strictly between the previous and proposed anchor blocks that append.  Thus
  no emitted multi-anchor group can contain such a negative between consecutive
  anchors.
- **Barrier safety is vacuous but still true for M1.** An allowed adjacent pair
  has no integer unit ID strictly between it.
- A queried negative before the first or after the last group anchor has no
  effect, and the code performs no negative-driven boundary contraction.

Failure conditions are a missing anchor in `units`, conflicting duplicate
observations supplied directly to the helper, non-temporal unit-ID ordering, or
later external filtering/canonicalization.  None is checked inside this helper.

## Which 40-second and 60-second caps bind

The clean helper literally reads both caps and tests:

```text
span <= min(d_core_max, d_seg_max) + 1e-9
```

With frozen values `40` and `60`, the 40-second cap binds and the 60-second cap
cannot independently reject a group.  Both output core and output segment have
the same endpoints, so both are at most 40 seconds.  If a future configuration
set `d_seg_max < d_core_max`, the segment cap would bind; this is a difference
from saying that the clean helper never reads the 60-second parameter.

## `canonicalize_native_segments` pseudocode and semantics

```text
IF native empty: return empty EventSegment table
frame_key := "frame_idx" if units has that column else "unit_id"
unit_by_frame := map units[frame_key] to units.unit_id
P/N := queried positive/negative unit-ID sets from trace
FOR each native row in existing row order:
    raw_ids := parsed/sorted/deduplicated source_frame_ids
    ids := map raw_ids through unit_by_frame, defaulting each ID to itself
    anchor_ids := ids intersect P
    IF ids empty:
        ids := all units with strict temporal overlap with native interval
        anchor_ids := ids intersect P
    emit native interval unchanged, with:
        evidence_unit_ids = ids
        anchor_unit_ids = anchor_ids
        num_negative_barriers = |ids intersect N|
        verification_state = native value or "native"
        confidence = segment_score or 0
        returned_seconds = native end - start
```

This path does not apply M0/M1 gap rules, either duration cap, barrier
exclusion, positive-anchor existence filtering, overlap merging, interval
sorting, or clipping to video bounds.  It canonicalizes repository-native rows
and preserves their order.

## Matcher and `evaluate_events`

### Exact objective

For prediction `i` and reference `j`:

```text
overlap[i,j] = 1 iff min(end_i,end_j) > max(start_i,start_j), else 0
iou[i,j] = positive intersection / enclosing union, else 0
score[i,j] = 1000 * overlap[i,j] + iou[i,j]
```

SciPy `linear_sum_assignment(-score)` chooses a rectangular one-to-one
assignment maximizing the sum of `score`.  Assigned zero-overlap pairs are then
discarded.  Thus the implementation’s literal ordering is:

1. maximize the scalar sum of `1000 * overlap_count + summed_tIoU`;
2. within assignments with the same overlap count, maximize summed tIoU.

For the frozen benchmark’s small event counts, a one-match gain of 1000 exceeds
the maximum possible aggregate tIoU change, so this acts as cardinality-first.
It is not a general lexicographic proof for arbitrary assignments containing
more than 1000 edges; the code uses a finite scalar constant, not a two-stage
optimizer.

### Deterministic tie behavior

Prediction and reference row order are preserved via `reset_index(drop=True)`.
SciPy returns row indices sorted, and SciPy 1.13.1 is deterministic for a fixed
matrix in the current environment.  However, repository code supplies no
secondary perturbation or explicit key for assignments with exactly equal
overlap count and exactly equal summed tIoU.  Therefore:

- repeated current-version execution on byte-equivalent ordered inputs is
  operationally deterministic;
- the semantic tie resolution among multiple exactly optimal assignments is
  solver/row-order dependent and is not frozen explicitly across SciPy
  versions;
- evaluator config text `assignment_tie_break=maximum_temporal_iou` describes
  the second objective, not a complete deterministic tie key after tIoU ties.

Matches are emitted first in solver return order, then unmatched predictions by
ascending reset row index, then unmatched references by ascending reset row
index.  `overmerge_count` is the number of overlapping references minus one;
`oversplit_count` is the number of overlapping predictions minus one.  These
are overlap-degree diagnostics, not assignment-optimization penalties.

### Event-F1

Let `TP` be the number of retained one-to-one positive-overlap matches,
`P=number of predicted rows`, and `R=number of reference rows`:

```text
precision = TP/P if P>0 else 0
recall    = TP/R if R>0 else NaN
F1        = 2*precision*recall/(precision+recall)
            if R>0 and precision+recall>0, else 0
```

Any strictly positive temporal overlap is eligible; event-F1 does not impose a
tIoU threshold or require `anchor_covered`.  The `tiou_03` and `tiou_05`
metrics separately divide the count of matched pairs meeting each threshold by
the total reference count.

`evaluate_events` contains no additional logic: it calls `match_events`, then
`compute_metrics`, and returns both tables.

### Event-F1 AUC

In `run_clean_benchmark.py` lines 1017–1028, each method’s available rows are
sorted by `horizon_budget`, then:

```text
AUC = trapezoid(event_f1, budget) / (max_budget - min_budget), if >=2 points
AUC = the single event_f1 value,                              if 1 point
```

The intended frozen grid is `[5,10,20,50,80,100]`; budget zero is absent.  The
normalization is over `[5,100]`, so this is a weighted average under piecewise
linear interpolation, not a sum and not an integral from zero.  Larger budget
intervals carry more area.  `comparison_valid` checks only that the number of
rows equals six; it does not itself assert exact grid identity or uniqueness.

## `OracleAccessor` and acquisition trace replay

### `OracleAccessor`

```text
INIT(frozen, run_id, budget):
    table := frozen oracle rows indexed by unit_id
    queried := empty set

QUERY(unit_id):
    coerce unit_id to int
    reject if already queried
    reject if |queried| >= integer budget
    reject if unit_id absent from table
    add unit_id to queried
    return a dictionary copy of that frozen cache row
```

The accessor enforces logical calls; it never decodes video or calls a VLM.
`trace_from_order` enumerates `order[:budget]` with zero-based `call_idx`, calls
the accessor once per unit, records the revealed label and before/after state
hashes, and marks each physical access as a cache hit.

Important isolation caveat: `map_order` and adapter-input construction build a
DataFrame containing all oracle labels before selection.  The current MAP
selector reveals the selected label only after selection, but this is weaker
static isolation than passing public fields plus an accessor alone.  The
mathematical reference correctly flags that future leakage risk.

### Standalone saved-trace replay

`replay_baseline_acquisition.py`:

1. reads the trace, frozen observations, unit table, reference, and evaluator;
2. checks required trace columns, duplicate unit IDs, and observation coverage;
3. overwrites/joins `oracle_label_after_query` from frozen observations;
4. takes run metadata from the trace’s first row;
5. rematerializes once under the requested M0 or M1 config;
6. re-evaluates and writes segments, matches, metrics, and a replay manifest;
7. records zero new oracle/VLM calls.

It does not validate that every row has the same run metadata as the first row,
does not validate the trace’s recorded label against the overwritten label, and
requires a new output directory (`exist_ok=False`).  Those are replay-audit
caveats, not evidence of a call.

`write_run` additionally rematerializes every non-empty acquisition prefix for
diagnostics.  It chooses M0 only when the config materializer string contains
`original_k3`; otherwise prefix replay defaults to M1.  Repository-native final
segments can therefore have M1 prefix diagnostics rather than native prefix
segments.

## Remaining disagreements with `BCM_AQP_MATHEMATICAL_REFERENCE.md`

The mathematical reference was not modified.  The following statements are
now contradicted or narrowed by the recovered authoritative code:

| Reference claim/location | Audit disposition |
|---|---|
| Sections 1.1, 3.1, 3.4, 13.7, 21.7, 23–25 and Appendix A/B say `benchmark_lib.py` or frozen traces are absent and the clean audit is blocked. | Contradicted by the current repository. The helper, frozen CSVs, and action traces are present and hashed above. The code-semantics blocker is resolved; oracle provenance remains separately blocked. |
| Exact `k3_bridge_safe` semantics are unknown. | Resolved: M1 requires immediately adjacent positive IDs; all other tested rules are shared with M0. |
| The clean matcher objective/tie behavior is unknown. | Resolved in part: exact scalar objective is `1000*overlap + tIoU`; exact equal-objective deterministic semantic tie key is absent. |
| Section 3.2 says the clean matcher is only manifest prose. | Contradicted: `match_events` is authoritative executable source. The separately described latent diagnostic IoU matcher remains a different implementation and must not be conflated with it. |
| Sections 3.2/3.3/13 say the 60-second cap is checked only in K4 and not used by K3. | True for the separately audited Stage-0.7 code described there, but not literally true for the clean helper: clean M0/M1 both read it through `min(core_cap,seg_cap)`. With 40/60 it is still redundant and never independently binds, so the reference’s practical conclusion remains correct. |
| Section 13.5 says conversion covers all extant units and implies contiguous evidence. | The clean output interval spans first-to-last anchor, but `evidence_unit_ids` lists queried anchors (plus any internal negatives, which valid groups cannot contain), not every unqueried bridged unit. Temporal coverage and evidence provenance must be distinguished. |
| Section 14 says bridge-safe invariants cannot be specified. | Resolved: positive coverage, <=40-second bound, and deterministic group order apply to both; negative barrier is substantive for M0 and vacuous for valid M1 joins. |
| Proposition 9.1/Test 4B destructive positive bridge might be removed by M1 but was unaudited. | Resolved: that M0 example is prevented by M1 because the second merge crosses one intervening unit and fails adjacency. This does not prove M1 utility is generally monotone. |
| Section 3.2 AUC description. | Confirmed, with the added caveat that code checks row count rather than exact grid equality when setting `comparison_valid`. |
| Section 3.2 trace-replay description. | Confirmed, with the metadata-consistency and native-prefix caveats above. |
| Config phrase “cardinality first, tIoU tie-break.” | Accurate for this frozen problem size, but the general code is a finite weighted sum rather than a formal lexicographic optimizer; exact ties after summed tIoU have no repository-defined tie key. |

Unrelated mathematical claims (Bayes VOI, non-identifiability, surrogate
calibration, candidate ceilings, submodularity, and audit estimators) were not
re-adjudicated because this blocker task requested code correspondence, not new
BCM theory or experiments.

## Decision-critical uncertainty after this audit

The materializer/evaluator semantics are no longer the dominant blocker.  The
dominant blocker is oracle-input provenance: unit 346’s frozen interval and
cached interval select different actual frames.  See
`ORACLE_CACHE_PROVENANCE_AUDIT.md` and the two frame-audit CSVs.  That mismatch
requires benchmark v2 before any formal BCM comparison.
