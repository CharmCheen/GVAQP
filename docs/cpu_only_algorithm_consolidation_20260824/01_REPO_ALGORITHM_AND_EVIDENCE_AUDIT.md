# GVAQP Algorithm and Evidence Audit

Date: 2026-08-24

Status: `PROPOSED_PIVOT_NOT_CANONICAL`

## 1. Executive finding

The repository does not yet contain a scientifically complete end-to-end query system. It contains useful but historically separate components and experiments: proxy diagnostics, candidate materialization, scan scheduling, confirm adapters, replay controllers, geometry analyses, regret analyses, exact-yield comparisons, shadow VLM labels, and a frozen human-event evaluation protocol.

The main integration defect was semantic rather than syntactic: the existing controller replay used a largest-gap scan policy and a 25% scan target, while the retained deterministic research direction specified breadth-first temporal bisection and fixed 1:1 SCAN/VERIFY interleaving. A unified CPU replay implementation now exists as `DATB_SV_CPU_REPLAY_V1`.

## 2. Reconstructed system pipeline

The intended query path is:

```text
natural-language query
  -> replaceable semantic oracle contract
  -> cheap SCAN over previously unexposed temporal cells
  -> candidate exposure/materialization
  -> expensive VERIFY of exposed candidates
  -> durable EventRelation commit
  -> deadline-safe query result
```

The scientific distinction is causal: SCAN is not merely another score on a fixed candidate set. It creates future VERIFY opportunities. VERIFY cannot legally inspect candidates that have not yet been exposed.

## 3. Component inventory and interpretation

| Component | Current role | Evidence status | Main limitation |
|---|---|---|---|
| Proxy/VLM scoring | Produces cheap or cached query-relative evidence | Development oracle/proxy only | Not independent human truth |
| Candidate materialization | Converts observed evidence into candidate records | Necessary systems component | Historical experiments use heterogeneous schemas |
| Scan scheduling | Chooses where to expose new evidence | Multiple experimental versions exist | No previously unified retained policy |
| Confirm adapter | Calls a mapping or callable oracle and emits utility IDs | Oracle-agnostic interface exists | Real workload manifest is incomplete |
| Replay controller | Simulates budgeted SCAN/VERIFY execution | Useful infrastructure | Historical policy differs from retained DATB-SV |
| Geometry analyses | Measures spread, fragmentation, and regions touched | Motivation/mechanism only | Not human event utility |
| Regret/state prediction | Tested learned action selection | Negative evidence | Learned controller underperformed fixed VERIFY baseline |
| Exact-yield pairs | Isolates output composition at equal clip yield | Relevant to measurement paper | Does not complete the query algorithm |
| Human-event protocol | Defines independent semantic events and utility | Frozen external-validity layer | Human outcomes are not yet available |

## 4. What the existing experiments actually show

### Established or directly observed

1. Cheap detector exposure is high but not complete on the vulnerable-road-user workload: unit exposure 257/264 and event exposure 170/173; three events have zero exposure and four have partial exposure.
2. Cached fixed-candidate experiments contain large VERIFY-allocation oracle headroom, but this does not establish headroom for endogenous SCAN because the candidate population was already fixed.
3. Across 108 cached abstract states, both SCAN-better and VERIFY-better states exist, but their natural prevalence is not identifiable from the constructed state set.
4. The learned state predictor performed worse than always-VERIFY on the audited cached setup. This closes, rather than motivates, the learned controller branch.
5. Query-specific best policy identities differ across the two production queries, but specialization gain is only 0.000585 EventRecall-AUC. Two queries and negligible gain do not justify a universal planner.
6. Adaptive batching has no current paper-level opportunity: measured headroom is 0 to 0.003 in the CPU preflight.
7. Two same-source Guangzhou traces suggest temporal bisection can recover one deadline-safe event near 224 seconds. This is an exploratory observation, not a general result.

### Not established

1. A learned controller, MAB, or RL policy improves the end-to-end system.
2. SCAN/VERIFY adaptivity is broadly beneficial under physical wall-clock costs.
3. Temporal geometry is a reliable surrogate for independently defined human events.
4. VLM labels are equivalent to human semantic ground truth.
5. The current algorithm generalizes across open semantic queries, videos, and oracle implementations.

## 5. Why the repository felt fragmented

The experiments answered different conditional questions under different abstractions:

| Experiment family | Conditional question |
|---|---|
| Proxy audit | Is cheap evidence imperfect? |
| Fixed-candidate allocation | If candidates already exist, where should VERIFY budget go? |
| Endogenous scan trace | Can scanning create useful candidates before a deadline? |
| Geometry analysis | Do equal-yield outputs differ temporally? |
| Human-event evaluation | Do those output differences matter to independent semantic events? |
| Universal planner audit | Is cross-query policy specialization large enough to learn? |

Combining their numbers as if they came from one end-to-end protocol would be invalid. The new unified replay contract keeps these layers separate.

## 6. Decision

Human annotation may be deferred while the algorithm contract and oracle-relative evaluation are completed. The safe interpretation is:

> The algorithm is independent of who implements the oracle, but the scientific meaning of its accuracy and utility results depends on the oracle used for evaluation.

Therefore, cached VLM labels may drive algorithm development, debugging, and oracle-relative comparisons. They cannot alone support claims about human event utility or real-user correctness.

## 7. Current readiness

- Algorithm contract: `READY_FOR_CPU_REPLAY`
- Synthetic end-to-end execution: `PASS`
- Existing real-workload adapter: `NOT_READY`
- Physical cost evidence: `BLOCKED_BY_NON_CPU_REQUIREMENT`
- Cross-query generalization: `NOT_IDENTIFIABLE`
- Human external validity: `DEFERRED_NOT_REMOVED`

## 8. Next highest-value action

Run the bounded CPU forensic action `RECOVER_OR_RETIRE_ENDOGENOUS_SCAN_PREFLIGHT_PROVENANCE`. If the missing package is recovered with compatible candidate exposure, durations, oracle outputs, and costs, bind it to the new replay interface. If not, retire the historical performance claim rather than reconstructing favorable data.
