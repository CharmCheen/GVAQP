# GVAQP CPU-only Algorithm Execution and Idea Verdict

**Date:** 2026-08-24  
**Scope:** Frozen CPU-only execution through T2-C1  
**Canonical-state impact:** None. This report is an evidence artifact and does not silently modify the project state-of-truth files.  
**Final algorithmic status:** `FAIL_RETIRE_CURRENT_DATB_ALGORITHMIC_CLAIM`

## 1. Executive Verdict

The current DATB-SV algorithmic direction does not pass its frozen evidence gates.

The decisive result is the existing-corpus T2-C1 comparison against the adapted ExSample envelope. Across 360 exact policy-condition comparisons from six video-query cells, DATB-SV has a mean anytime committed-utility AUC difference of **-0.040842**, a median difference of **-0.039983**, and a positive/equal/negative count of **44/0/316**. Its workload-level mean difference is positive in **0/6** cells.

Therefore, the permitted conclusion is:

> Under the frozen C1 simulated cost model, cached VLM-relative outcomes, and the current six-cell corpus, DATB-SV is consistently worse than the adapted ExSample envelope in anytime committed event utility.

This does not prove that every causal SCAN/VERIFY planner is impossible. It does falsify the current DATB-SV superiority claim on the available natural cached evidence. The claim must not be rescued by controller training, threshold tuning, workload removal, seed selection, or post-outcome mechanism revision.

## 2. What Was Executed

The CPU-only path produced and exercised the following components:

1. A shared deterministic causal-frontier execution engine for SCAN, VERIFY, commitment, utility, and regret accounting.
2. Focused unit tests for interval/event behavior and planner execution semantics.
3. A T0 provenance audit of historical endogenous-scan evidence.
4. A T0.5 evaluator-parity audit against the always-VERIFY baseline path.
5. Three frozen synthetic H2 screens, including the repaired cost-aware DATB-SV implementation.
6. An explicitly adapted ExSample-style Gamma-Thompson chunk-sampling envelope.
7. A frozen synthetic DATB-SV versus adapted-ExSample killer test.
8. A T2-C1 replay over cached natural video-query outcomes using the same policy evaluation path.

No GPU inference, VLM rerun, controller training, MAB training, RL training, proxy training, or human-outcome-dependent tuning was performed.

## 3. Evidence Chain

| Stage | Evidence | Result | Scientific interpretation |
|---|---:|---|---|
| T0 provenance recovery | Historical artifacts and code paths | `RETIRED_FOR_CLAIM_USE` | Historical endogenous-scan results cannot support a current algorithmic claim. |
| T0.5 evaluator parity | Same always-VERIFY trace and accounting boundary | `EVALUATOR_PARITY_UNRESOLVED` | Historical controller/MAB/RL regret comparisons are retired; they cannot establish algorithm success or failure. |
| H2 synthetic V1 | DATB-SV versus LargestGap | `FAIL_SYNTHETIC_MECHANISM_SCREEN_ONLY` | The original DATB implementation was behaviorally identical to LargestGap. |
| H2 synthetic V2 | Repaired cost-aware DATB-SV | Nonidentity 99.14%; original interaction failed | Repair created a distinct policy, but did not support the preregistered sparse/multimodal mechanism. |
| H2 synthetic V3 holdout | Coupling mechanism | Mean AUC delta +0.019116; coupling interaction 0.009531 < 0.05 | A synthetic average benefit existed, but the named mechanism gate failed. |
| Synthetic ExSample killer | DATB-SV versus adapted ExSample envelope | `PASS_SYNTHETIC_EXSAMPLE_KILLER`; mean delta +0.123738 | The implementation can win in the constructed synthetic environment; this is not natural-corpus evidence. |
| T2-C1 existing corpus | Six cached video-query cells, 360 paired rows | Mean delta -0.040842; 44/0/316; 0/6 positive workloads | The synthetic advantage does not transfer to the available cached natural corpus. |

## 4. Decisive T2-C1 Results

### 4.1 Evaluation scope

- Independent descriptive cells: 3 videos x 2 queries = 6 video-query workloads.
- Policy replays: 2,880.
- Paired DATB-SV versus adapted-ExSample rows: 360.
- Cached semantic labels: 2,430 `not_relevant`, 515 `relevant`, 4 `parse_failure`, and 1 `unknown`.
- Cost tier: `C1_SIMULATED_COST_ONLY` with VERIFY/SCAN ratios `{1, 3, 10, 30}`.
- Deadlines: `{20%, 40%, 60%}`.
- Seeds: five frozen holdout seeds.
- Reference: cached VLM-relative 10-second-unit outcomes.
- Event construction: contiguous relevant units form model-relative events.
- Candidate model: every complete 10-second unit is available as a candidate.
- Exclusions: one trailing partial unit per video, applied uniformly before policy comparison.

### 4.2 Workload-level differences

| Video | Query | DATB-SV minus adapted ExSample AUC | DATB-SV minus LargestGap AUC |
|---|---|---:|---:|
| DALI | driver | -0.035041 | -0.019123 |
| DALI | vulnerable | -0.042250 | +0.019859 |
| HANGZHOU | driver | -0.026421 | +0.010702 |
| HANGZHOU | vulnerable | -0.027809 | +0.029520 |
| WUHAN | driver | -0.039412 | +0.017428 |
| WUHAN | vulnerable | -0.074119 | -0.062742 |

The ExSample comparison is directionally consistent across all six descriptive cells. The LargestGap comparison is heterogeneous and does not support a robust DATB-SV advantage.

## 5. Synthetic-to-Corpus Contradiction

The synthetic ExSample killer test favored DATB-SV, whereas the cached natural-corpus replay favored the adapted ExSample envelope in every workload-level mean comparison.

The strongest interpretation is not that one run is a software error by default. The two evaluations answer different questions:

- The synthetic test shows that constructed temporal/cost regimes exist in which DATB-SV's causal commitment behavior is useful.
- T2-C1 shows that those regimes, or the assumed mechanism strength, do not describe the available cached corpus sufficiently well to produce a benefit.
- The earlier preregistered sparse/multimodal and coupling interaction tests already failed to establish the proposed mechanism boundary.

Consequently, synthetic success cannot be promoted into a natural-workload algorithm claim. Further tuning against these six cells would convert the frozen holdout into development data and invalidate the current test.

## 6. Claims Allowed

The following statements are supported:

1. DATB-SV and LargestGap are behaviorally distinct after the cost-aware repair.
2. Synthetic regimes can be constructed in which DATB-SV beats an adapted ExSample-style envelope.
3. The preregistered sparse/multimodal and coupling mechanism claims did not pass their frozen gates.
4. On the existing six-cell cached corpus under C1 simulated costs and model-relative events, adapted ExSample outperforms DATB-SV consistently.
5. Historical controller/MAB/RL negative results are not valid evidence because evaluator parity remains unresolved.

## 7. Claims Not Allowed

The following statements are not supported:

1. DATB-SV is superior to ExSample on natural workloads.
2. DATB-SV is deadline-safe under real physical costs.
3. The observed C1 results generalize beyond the three videos and two queries.
4. Model-relative contiguous units are equivalent to independently annotated human events.
5. The existing corpus measures candidate-generation recall, because every complete unit is exposed as a candidate.
6. The failed DATB-SV result proves that all causal SCAN/VERIFY allocation algorithms are impossible.
7. The historical controller/MAB/RL results prove an algorithmic failure or success.

## 8. Closest-Work Implication

ZEUS, ExSample, LAVA, VOCAL-UDF, and SemBench already cover substantial parts of adaptive video search, query processing, semantic operator construction, and benchmark evaluation. The remaining proposed novelty was conditional on demonstrating that causal SCAN/VERIFY operator allocation improves anytime committed event utility over strong adaptive sampling.

T2-C1 does not demonstrate that condition. Because the strongest current baseline wins consistently, the present DATB-SV formulation is not a defensible standalone VLDB/SIGMOD algorithm contribution.

## 9. Venue-Potential Assessment

### Current DATB-SV algorithm paper

**Verdict:** `NOT_READY_FOR_VLDB_OR_SIGMOD`

The main algorithm loses to the closest strong adaptive-sampling envelope on the available cached natural corpus, its named synthetic mechanism did not pass, real C3 costs are absent, and the independent workload support is only three videos and two queries.

### Human-event measurement/evaluation direction

**Verdict:** `CONDITIONAL_POTENTIAL`

The stronger remaining research question is whether equal positive-clip yield or model-relative utility corresponds to equal independently defined human-event utility. This direction can become a systems/evaluation contribution if it demonstrates a reproducible mismatch across a deliberately expanded set of independent videos and queries, uses frozen human-event definitions and statistics, and shows concrete implications for query-system evaluation or design.

It currently remains unvalidated because independent human-event annotations have not yet been analyzed. Its potential must not be represented as an established result.

### Rigorous negative/measurement study

**Verdict:** `POSSIBLE_BUT_SECONDARY`

The synthetic-to-natural reversal, evaluator-parity failure, and cost-tier distinctions may support a rigorous negative study about when adaptive scan/verify mechanisms fail to transfer. Such a paper would require broader workloads, real cost measurements, and a sharper systems lesson than a report that one planner loses.

## 10. Frozen Decision

The current DATB-SV superiority claim is retired. The six existing video-query cells must not be used for additional planner selection, hyperparameter search, policy-family expansion, or mechanism rescue. Any future algorithm must begin from a newly preregistered hypothesis and fresh evaluation data, not from tuning against this failed holdout.

This decision applies to the present implementation and claim. It does not alter the already frozen human-event evaluation protocol and does not convert cached VLM labels into independent human ground truth.

## 11. Engineering Observation

The completed T2-C1 command took approximately 4,214 seconds wall-clock. This runtime mainly reflects repeated Python state recomputation and orchestration overhead. It is an implementation-efficiency issue and must not be interpreted as the C1 SCAN/VERIFY action-cost model or as evidence about physical GPU cost.

## 12. Exact Next Action

> Freeze DATB-SV as a negative algorithmic result, complete independent human-event annotations under the already frozen protocol, and run the preregistered human-event utility pipeline without changing metrics, pair selection, or statistical procedures.

