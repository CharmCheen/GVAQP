# Barrier-Constrained Event Materialization Headroom and Formal Algorithm Gate v1

## Decision

`PUBLIC_BCEM_NO_GO`.

The exact legal-partition ceiling establishes `MATERIALIZER_HEADROOM_GO`, but the single frozen public objective fails the runnable gate. The operator route is not rescued by implementation correctness: safety, determinism, exactness, and incremental equivalence all pass.

## Formal operator

At budget B, queried positives are ordered anchors and queried negatives are hard interior barriers; unqueried units remain unknown. A legal EventRelation is an ordered partition of all positive anchors into nonempty contiguous anchor slices. Each event is the minimal first-anchor-start to last-anchor-end interval, crosses no queried negative, and satisfies both the 40-second core and 60-second output caps. Canonical relation/event IDs hash sorted observations, configuration, and ordered anchor tuples.

## Exact algorithms and complexity

Legal groups are edges in an anchor-index DAG. Counting and an additive public optimum take `O(mL)` time, where m is positive-anchor count and L is the number of cap-reachable anchors; reconstruction uses `O(m)` DP state plus edges. Explicit enumeration is output-sensitive. The evaluator-only ceiling uses a joint exact DP over legal partition edges, ordered reference matching, prediction count, and match count; it is validated against exhaustive enumeration on 100 random small instances. No greedy, submodular, approximation, or latent-event completeness claim is made.

## Headroom

Family-macro K3-safe AUC is `0.317644196` and the exact legal ceiling is `0.318514361`, a `+0.000870165` gap. Headroom appears in non-random families ['ABAE', 'SUPG'], at five nonzero aggregate budgets, after removing the single 80.7-second reference, and under anchor-certified matching. MAP, ARC, top-proxy, and component-first have no ceiling gain. Minimal convex-hull boundaries are fixed, so ceiling gain is partition-only.

## Frozen public BCEM-DP

After headroom GO, one reference-free objective was frozen without a grid:

`C(G) = 1 + span(G)/40s + unknown_gap_seconds(G)/40s`.

The exact public DP is implemented in `garc_eval/bcem_gate_v1/public.py`. Family-macro public AUC is `0.310124036`, giving `-0.007520160` versus K3-safe. Only ['SUPG'] improve; no aggregate non-random budget improves. The loss persists after excluding the pathological reference. Therefore headroom is real but not recoverable from this geometry/barrier-only public objective.

## Safety, correctness, and resources

- 738/738 fixed traces; 8 selector variants, 7 families, 6 budgets.
- 13/13 synthetic/property tests pass, including 100+100 random brute-force comparisons.
- Positive-anchor coverage, queried-negative barrier safety, both caps, and row-order determinism: PASS.
- Interval non-crossing: PASS after an independent-review correction; 738/738 frozen runs are partition/count/metric equivalent under the repaired legal engine.
- Incremental versus batch: 32307/ 32307 saved query-prefix checks pass.
- Maximum observed evidence region rebuilt per update: 100 units; maximum cap-affected anchor suffix: 19.
- Physical VLM calls: 0. Baseline acquisition reruns: 0.
- Independent adversarial review: `PASS`.

## Ablations

Removing duration cost and removing unknown-gap cost were evaluated without a parameter sweep; both make higher-budget performance worse on aggregate. Batch execution without incremental maintenance is output-identical. Original-K3 and K3-safe constraint controls are reported. Public-support ablation is not applicable because no such term was introduced.

## Interpretation and non-claims

Observed evidence supports a small evaluator-only partition gap, localized to SUPG and ABae. The main competing explanation for public failure is non-identifiability: temporal geometry and negative barriers do not reveal which legal merge/split is the correct latent event relation. This single-video oracle-relative result does not establish a general BCEM impossibility, multi-video performance, or human-ground-truth validity. It does reject the frozen cap-normalized public objective and prohibits post-hoc retuning on this reference.

## Exact next task

Do not tune another BCEM objective on the strict reference. Run a separate preregistered, held-out EventRelation identifiability/feasibility gate that asks whether any planner-public pairwise same-event evidence exists across multiple videos; only if that signal is established should a new public materializer be proposed.

Stop here; do not execute that task in this gate.
