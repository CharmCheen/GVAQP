# Primary-source algorithm comparison

## Audit method

The audit used the original PVLDB/arXiv papers linked in
`QUERY_OBJECT_COMPARISON.csv`, the official local ARC/SUPG/ABae repositories,
and the strict adapter source audit. The local code establishes that ARC builds
contiguous candidate clips and progressively samples/propagates *frame
labels*; SUPG samples records to choose a proxy threshold; and ABae allocates a
two-stage stratified sample for an aggregate. None of those implementations
exposes a physical operator whose one invocation returns zero or more typed
event objects.

Primary papers establish additional novelty threats:

- Seiden already uses segment-level exploration/exploitation and temporal
  label propagation; an adaptive video sampler is therefore not new.
- EQUI-VOCAL already represents compositional events using spatio-temporal
  scene graphs and synthesizes queries; an event graph is not new.
- LOTUS already formalizes reference semantic operators and chooses optimized
  implementations with reference-relative accuracy; merely defining a typed
  operator is not new.
- CoMET-Agent already frames conditional multi-event grounding as structured
  search-and-aggregate.
- ExtremeWhen shows retrieve-then-ground explicitly; retrieving a long clip
  and asking a VLM to localize is not new.
- PLOP/Horrila and task-cascade work cover semantic-operator placement and
  heterogeneous operation/document/model cascades.

## Surviving distinction

The surviving candidate, VERA, is narrower than a new video-search framework:
it is a database physical-plan algorithm for a set-valued
`EVENT_ENUMERATE(window)` operator. It jointly chooses temporal granularity,
overlap ownership and exact/unit fallback in a shortest-path/DP plan, then
reconciles relation fragments deterministically. Its objective is GPU seconds
subject to frozen event-recall/F1 constraints. The contribution would be the
operator-cover optimization and its properties—not the prompt, longer input,
retriever, graph or batching.

That distinction remains a working hypothesis until two falsification tests
pass: (1) the formal plan must have nontrivial headroom at non-perfect operator
accuracy and conservative cost scaling; (2) a frozen physical enumerator must
produce multiple correct event objects per invocation at lower end-to-end cost.

## Source implementation observations

- `refe_repos/ARC-main/arc/arc.py` updates a per-frame score array and emits
  `findCandClips`; it does not compose event identities returned by an oracle.
- `refe_repos/supg/supg/selector/recall_selector.py` returns record IDs after
  proxy-ordered importance sampling and confidence adjustment.
- `refe_repos/abae/abae/algorithm.py` and `online.py` implement proxy strata,
  pilot estimates and second-stage allocation for an aggregate statistic.
- `refe_repos/adapter/SOURCE_AUDIT.md` confirms that event segments in this
  project are adapter postprocessing and do not inherit the papers' original
  guarantees.

## Uncertainty

No exhaustive novelty search can prove nonexistence of an identical algorithm.
The closest threats are multi-event search-and-aggregate, task cascades, and
semantic-operator DP. Accordingly, the claim is deliberately limited to the
specific conjunction of relation-valued temporal enumeration, overlap
ownership, variable-resolution cover optimization and dense fallback.

