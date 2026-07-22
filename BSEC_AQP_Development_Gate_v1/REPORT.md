# Fixed-budget EventRelation AQP research report

## Decision

The original BSEC hypothesis is rejected. A later method, DASR, mechanically passed its locally preregistered five-seed gate, but that pass is too weak for a broad “beats ARC” conclusion. The most consistent controlled-ARC/proxy candidate on opened domains is PSTR-5:4, a deterministic temporal stratification of ARC's own public proxy. It is not the unqualified strongest method. PSTR has encouraging leave-one-domain-out evidence and is now frozen, but it still lacks prospectively unopened, independently sourced confirmation videos.

Therefore the terminal scientific status is:

`PSTR_FROZEN_CANDIDATE_AWAITING_EXTERNAL_CONFIRMATION`

This is stronger than the starting state—a concrete method, exact implementation, falsification rule, negative-result ledger, and independently checked evidence now exist—but it is not a statistically reliable or broadly generalized victory over native ARC.

## Observed evidence

All AUC values are normalized trapezoidal event-F1 AUC over the budgets available in that domain. Every controlled method uses exactly `B` unique cached oracle observations and the identical K3 materializer/evaluator. Physical new VLM calls were zero.

### Mechanism search

| Stage/domain | Candidate | Candidate AUC | CLIP | NMS-h10 | Shared-K3 ARC | Decision |
|---|---:|---:|---:|---:|---:|---|
| dataset3 development | BSEC | 0.524155 | 0.538949 | 0.562378 | 0.250568 | reject BSEC |
| dataset3 development | QTPC | 0.567718 | 0.538949 | 0.562378 | 0.250568 | advance |
| realcartest 2000–3200 | QTPC | 0.593589 | 0.619170 | 0.641261 | 0.602761 | reject QTPC |
| realcartest 0–1570 | PNIR | 0.524589 | 0.518892 | 0.542895 | 0.548629 | reject PNIR |

The proposed BSEC mechanism did not beat the stronger retrieval baselines. Low-budget CLIP duplicate burden at budgets 5, 10, and 20 was zero, directly contradicting the initial hypothesis that early CLIP queries were mainly wasted on duplicate event hits.

### Frozen DASR gate

The final v3 protocol was hashed before CLIP scoring on its two disjoint intervals. Those intervals were not globally unseen: labels and other evaluations already existed in July 5–7 artifacts. The valid description is “prospectively CLIP-scored disjoint intervals,” not “untouched test data.”

| Interval | Events | DASR | Stratified-only | ARC five-seed mean | CLIP | NMS | Random mean |
|---|---:|---:|---:|---:|---:|---:|---:|
| realcartest 1630–2000 | 2 | 0.222222 | 0.222222 | 0.222222 | 0.222222 | 0.000000 | 0.412222 |
| realcartest 3200–3830 | 7 | 0.674074 | 0.674074 | 0.663854 | 0.641667 | 0.655556 | 0.647877 |
| unweighted interval macro | 9 total | 0.448148 | 0.448148 | 0.443038 | — | — | — |

On the rich interval, DASR event-F1 by budget was `[0, 0.444444, 0.600000, 1.000000]`; ARC was `[0.250000, 0.250000, 0.676364, 0.923077]`. DASR won only budgets 10 and 50 and lost budgets 5 and 20. Its unweighted mean across the four budget points was `0.511111`, below ARC's `0.524860`; the normalized AUC conclusion depends on budget-axis weighting.

An adversarial review found that three of the original five ARC seeds scored `0.686480`, above DASR, while two scored `0.629915`. A post-hoc audit over deterministic seeds 0–999 reproduced sealed seeds 0–4 exactly. On the rich interval, ARC's seed mean was `0.655448`, population SD `0.032759`, and 48.1% of seeds were strictly above DASR. This supports an expected-AUC advantage over this stochastic adapter, but not consistent per-run dominance.

Most importantly, pure public-proxy top-k scored `0.686480` on the rich interval and beat DASR. This falsified DASR as the strongest deployable method even though the frozen local decision rule said `CONFIRMED_GO`.

### PSTR exploration after DASR

PSTR was proposed after all five label domains were open. The following are observed post-hoc results, not prospective confirmation. Dataset3 uses normalized fusion of YOLO-count and motion, realcartest 2000–3200 uses a clean-no-leak fused cheap-signal proxy, and the other three use RoadCLIP `score_count`. PSTR and ARC receive identical proxy values within each domain, but this is not a fixed-proxy-model generalization test.

| Domain | PSTR-5:4 | Pure proxy top-k | DASR | Shared-K3 ARC | PSTR − ARC |
|---|---:|---:|---:|---:|---:|
| dataset3 | 0.380363 | 0.354212 | 0.568778 | 0.250568 | +0.129795 |
| realcartest 2000–3200 | 0.700302 | 0.667553 | 0.654310 | 0.602761 | +0.097541 |
| realcartest 0–1570 | 0.612482 | 0.554221 | 0.576507 | 0.548629 | +0.063853 |
| realcartest 1630–2000 | 0.222222 | 0.222222 | 0.222222 | 0.222222 | 0.000000 |
| realcartest 3200–3830 | 0.811396 | 0.686480 | 0.674074 | 0.663854 | +0.147542 |

The overhead grid was nested inside a five-domain leave-one-domain-out replay. Parameter selection used only the other four domains for each fold. It yielded four strict test-domain wins and one tie versus shared-K3 ARC, with no losses. For the rich fold, training selected a larger overhead (`1.0`) and achieved test AUC `0.730128`; the other folds selected `0.25`. This evaluates a tuning procedure, not one universally fixed parameter. After all domains were pooled, `0.25` was frozen for the next external test.

Dataset3 prevents an overbroad strongest-method claim: PSTR `0.380363` is below CLIP `0.538949`, NMS `0.562378`, DASR `0.568778`, and descriptive native ARC `0.389659`. It only strengthens consistency relative to pure proxy and the controlled exact-call ARC comparator.

On the rich interval, fixed PSTR-5:4 achieved F1 `[0.600000, 0.600000, 0.833333, 0.923077]` at budgets `[5,10,20,50]`; it never returned more seconds than ARC at those points (`[30,30,70,120]` versus ARC mean `[30,30,76,120]`). The gain there is distinct-event discovery rather than broader output. On 2000–3200, PSTR often returned more total seconds because it discovered more positive units/events; the identical K3 contract prevents a materializer-width advantage, but output-efficiency generalization remains unresolved.

## Derived conclusions

1. The original claim that CLIP already beat native ARC under a fair contract was not established. Native ARC used broad output intervals and a different effective query/materialization contract. On dataset3, a method restricted to five safe confirmed outputs cannot exceed F1 `10/(5+26)=0.322581`, while reported native ARC at budget 5 was `0.337708`; the contracts are mathematically incompatible.
2. Semantic duplication was not the dominant low-budget bottleneck in the development data. BSEC's extra complexity did not earn its place.
3. For the available realcartest domains, temporal opportunity coverage applied to the public proxy is more robust than ARC's stochastic refinement and more effective than pure proxy top-k. PSTR is the simplest method consistent with that evidence.
4. The available data do not establish broad superiority. The frozen DASR final evidence contains only nine pseudo-events across two same-source intervals; four of five PSTR domains share realcartest; and every reference is VLM-defined rather than human adjudicated.

## Main competing explanation

PSTR may be exploiting source-specific regularity in the realcartest proxy/time layout. Because PSTR was designed after these domains were opened, its consistent retrospective gains can still be selection bias. The sparse interval supplies no directional discrimination, and there is no second unopened source to reject this explanation.

## Missing baselines and claim restrictions

MMR and facility location were run in the initial gate; BSEC lost to them on development. A DPP-style baseline and an exact-B shared-K3 SUPG adaptation were not completed in this package. MAP/M1 and native ARC values are descriptive because their frozen query/materialization contracts differ. No novelty or state-of-the-art claim is permitted until the missing strong baselines and external confirmation are complete.

## Next highest-value action

Acquire at least five independently sourced videos meeting the v5 population rule, freeze their unit grids and public scores without opening oracle labels, seal PSTR/ARC/proxy/SUPG/diversified selections, then evaluate with human-adjudicated references. The exact video-macro, seed, bootstrap, missing-baseline, and rejection rules are frozen in `config/frozen_external_confirmation_v5.json`. This action requires new oracle/annotation budget and is intentionally not performed silently.
