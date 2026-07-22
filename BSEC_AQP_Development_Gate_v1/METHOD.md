# Fixed-budget EventRelation retrieval methods

## Current candidate: PSTR-5:4

Proxy-Stratified Temporal Retrieval (PSTR) is the most consistent controlled-ARC/proxy candidate on the opened domains. It uses only the public per-unit proxy already available to ARC and the temporal order of units. It is not the unqualified strongest method: CLIP, NMS, DASR, and descriptive native ARC remain higher on dataset3.

For a population of `n` ten-second units and an exact oracle budget `B`:

1. Set `M = min(n, B + floor(B/4))`.
2. Partition the ordered unit IDs into `M` contiguous cells. Cell `c` contains unit IDs from `floor(n*c/M)` through `floor(n*(c+1)/M)-1`.
3. In every cell, keep the unit with the largest public proxy score. Break proxy ties by the smaller unit ID.
4. Sort cell winners by decreasing proxy score, again breaking ties by unit ID.
5. Query the first `B` winners, then materialize all methods with the same `k3_bridge_safe` operator.

The selector is deterministic, label-blind, and returns exactly `B` distinct units whenever `B <= n`. It is not nested across budgets because the temporal partition changes with `B`.

The intended mechanism is modest: pure proxy top-k can spend too much budget in one temporally concentrated high-score region; PSTR first admits a slightly larger set of temporal representatives and then preserves proxy relevance within that set. The `1/4` overhead was selected after all currently available realcartest domains were open. It is a fitted constant, not a theoretical optimum.

PSTR has a cardinality and determinism guarantee, but no distribution-free guarantee on true event recall or F1. Its temporal cells are a public surrogate for event opportunities. The terminal external falsification test is frozen in `config/frozen_external_confirmation_v5.json`; v4 is preserved as a superseded record.

The retrospective domains do not all use one proxy generator. Dataset3 uses ARC's normalized `score_fusion_yolo_motion`; `realcartest_2000_3200` uses the maximum `cheap_fused_score` from its clean-no-leak two-second cheap-signal table; the other three domains use the maximum overlapping RoadCLIP `score_count`. PSTR and ARC share the same proxy within each domain. This variation is documented in `PSTR_PROXY_PROVENANCE.md`; it does not prove proxy-model invariance.

## Rejected or limited predecessors

- BSEC used a monotone-submodular semantic-temporal coverage surrogate. Its greedy approximation guarantee applied only to that surrogate. It reached development F1-AUC `0.524155`, below CLIP top-k `0.538949`, and was rejected.
- QTPC used local CLIP peak contrast. It improved the development video but failed the disjoint `realcartest_2000_3200` gate: `0.593589` versus CLIP `0.619170` and shared-K3 ARC `0.602761`.
- PNIR interleaved QTPC and temporal NMS. It reached fitting AUCs `0.573986` and `0.648640`, then failed `realcartest_0_1570`: `0.524589` versus ARC `0.548629` and NMS `0.542895`.
- DASR mixed CLIP temporal NMS with CLIP temporal strata. Its frozen local gate passed, but the final curves were identical to stratified-only retrieval, and pure proxy top-k beat it on the event-rich interval. It is retained as a reproducible intermediate result, not the terminal method.

## Comparator naming and fairness

The primary ARC comparator in this package is precisely:

`threshold-0.4 ARC-refinement + proxy-order exact-fill, shared K3`

ARC refinement usually consumed only zero to two unique observations on the final intervals. The adapter appended unused units in public-proxy order until exactly `B` observations were present, after which the same K3 materializer and event evaluator were applied. This is an exact-call adaptation, not native ARC and not a claim about every ARC configuration.

Logical oracle accounting counts exactly `B` cached observations per method and budget. The experiments made zero new physical VLM oracle calls.

## Computational cost

With proxy scores already available, PSTR scans `n` units to find cell winners and sorts at most `M` winners. Its selection cost is `O(n + M log M)` time and `O(M)` memory. Oracle and K3 costs are outside the public selector and are shared across methods.
