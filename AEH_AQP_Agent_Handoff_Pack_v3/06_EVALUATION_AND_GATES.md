# Evaluation and Gates

## Primary evaluation axes

1. Event precision, recall and one-to-one event-F1.
2. Event-F1 versus budget and normalized AUC using the frozen integration rule.
3. Proposal/candidate event coverage.
4. Boundary quality and duration/overcoverage.
5. Merge and split errors.
6. Unique events per oracle query.
7. Logical calls, physical calls, GPU seconds and wall time.
8. Negative-query rejection where applicable.
9. Residual audit accuracy/coverage only when an independent audit protocol exists.

## Required five-part error decomposition

```text
search/proposal miss
ranking/query miss
oracle semantic error
boundary/materialization and merge/split error
certification/audit miss
```

Under the current oracle-exact abstraction, oracle semantic error may be fixed to zero for algorithm evaluation, but the paper must label that assumption.

## Baseline families

- random/uniform;
- top cheap proxy;
- native ARC, SUPG and ABae;
- each applicable selector with shared BB-EM;
- MAP/M1;
- frame/clip embedding retrieval;
- retrieve-then-ground;
- position-uniform retrieval;
- CoMET-style search-and-aggregate or the closest reproducible agentic baseline;
- record-level AQP/proxy workflow baseline;
- monolithic long-video VLM when compute and input limits make it meaningful.

## Existing empirical gates

### Candidate gate

Current full legal universe covers only 20/26 events. Candidate construction is not ready for a planner claim.

### Ranking/calibration gate

Oracle-informed AUC 0.664458 shows headroom; public blocked-CV AUROC 0.548282 fails the stable-signal gate. Do not call this outcome calibration GO.

### Materializer gate

BB-EM/K3-safe has defensible evidence and contributed materially in H1 replay, but it still requires selector/video generalization and fixed-evidence ceiling comparison.

### Planner gate

Real-data BCM/H1 is below MAP/M1 and ARC. The controlled gate returned `IDEAL_SIGNAL_ONLY`: exploration and counterfactual work are stopped; real cheap-primitive engineering is not justified.

## Frozen S2 representation gate

The only remaining planner-related gate changes representation without changing the action universe. Success requires all of the following:

- R1 P1−P0 paired event-F1 AUC strictly positive;
- 95% paired bootstrap CI lower bound above zero, if the frozen cells provide a valid resampling unit;
- positive aggregate effect over B=5/10/20;
- no degradation large enough to reverse the full-budget AUC conclusion;
- trace evidence that reduced within-cell redundant queries causes the improvement;
- no evaluator leakage;
- the candidate/action universe and oracle observations remain identical.

If R1 saturation remains non-positive, use `PLANNER_ROUTE_REJECTED`. Do not run another representation variant.

## Paper-level GO

A top-tier algorithm claim ultimately needs:

- multiple videos and held-out evaluation;
- strong modern search/multi-event baselines;
- a reproducible public signal or index;
- improvement on the cost–event-quality frontier, not only B=100;
- ablations that isolate event saturation, counterfactual materialization and audit;
- human-GT validation or a carefully scoped oracle-relative claim;
- statistical uncertainty across videos/queries/seeds.
