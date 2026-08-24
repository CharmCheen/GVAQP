# GVAQP project state of truth

Status date: 2026-08-24 (Asia/Shanghai)

Scope: project-level scientific claims; raw artifacts remain the evidence base

Current phase: **B1a protocol frozen; execution blocked by unbound fresh inputs**
Experiment policy: **CPU-only contract/protocol work; pause new inference, human work, and controller training**

Read this file together with `CLAIM_LEDGER.csv`,
`EXPERIMENT_DECISION_LEDGER.csv`, `ACTIVE_HYPOTHESES.md`,
`CLOSED_BRANCHES.md`, and `NEXT_STAGE_STATE_MACHINE.md`.

## 1. Research question and decomposed claims

How should open-semantic temporal events be queried when cheap sensing is
imperfect, semantic verification is expensive, and resources are limited?

| Claim | Status | Exact boundary |
|---|---|---|
| A. Proxy imperfection creates query-optimization work. | **PARTIALLY SUPPORTED** | Natural ranking degradation matters on the cached, fully precomputed candidate universe. Natural exposure misses remain unmeasured. |
| B0. Cheap SCAN/PROPOSE creates query-conditioned legal capabilities that DirectVerify cannot cheaply replace. | **INFRASTRUCTURE QUALIFIED; EMPIRICAL CLAIM NOT ESTABLISHED** | The CPU executor satisfies the frozen causal/action contract. This does not establish that the capability is naturally useful. |
| B1. Natural workloads contain material endogenous sensing headroom. | **NOT ESTABLISHED** | Requires fresh prospective or physical evidence after B0 passes. |
| B2. The headroom is observable online from legal public state. | **NOT ESTABLISHED** | No qualified substrate or held-out predictability result exists. |
| B3. A deployable adaptive policy exploits the headroom safely. | **NOT ESTABLISHED** | Current DATB identities are retired; controller work is closed until B0-B2 pass. |
| C. Event-aware acquisition is more robust than positive-yield maximization. | **NOT ESTABLISHED; DEFERRED BY SCOPE** | Human validation remains scientifically relevant, but the user has explicitly deferred human auditing. |

`NOT ESTABLISHED` is not a failure verdict. CPU contract success is an
infrastructure result, not evidence for B1-B3.

## 2. Established bounded facts

- Natural proxy ranking is weak (per-video AUPRC 0.2584-0.3146), and severe
  ranking degradation produces a median low-budget EventF1 gap of 0.095134.
- The original one-candidate-per-unit substrate has exposure recall 1.0;
  synthetic exposure deletion produced median gap 0.0. It therefore cannot
  establish natural exposure headroom.
- Gap-only C1 explains almost all cached materialization gain. More complex K3
  mechanisms and the learned-controller branches remain closed.
- The independent-human P1 log has zero rows. This is deferred rather than
  interpreted as PASS or FAIL.

## 3. 2026-08-24 algorithm self-check

- T0 provenance reconstruction retired the initial fixed-bisection DATB
  identity. T0.5 did not establish evaluator parity.
- The later value-rate DATB failed the H2 synthetic V3 interaction gate.
- A synthetic ExSample killer is informative only on its synthetic support.
- On the six consumed T2 cells, the current DATB loses to the per-row ExSample
  envelope by mean anytime-AUC 0.040842 (0/6 workload wins).
- A CPU-only comparator audit adds an essential qualification: DATB minus
  fixed ExSample chunk 3/6/12 is -0.010108/+0.005561/-0.010999; leave-one-
  workload-out selection gives only +0.000117. The per-row oracle envelope's
  bonus over the best global fixed chunk is 0.029843, 73.1% of the reported
  absolute envelope gap.
- At one frozen representative condition for each video, current DATB has
  identical action traces for the two queries in 3/3 videos; fixed chunk-6
  ExSample has identical traces in 0/3. This is diagnostic, not a full-grid
  query-blindness proof.

Strongest supported conclusion: **retire the current DATB implementation and
its current algorithmic claim.** The evidence does **not** establish that one
deployable fixed ExSample policy consistently dominates, nor that all
SCAN/VERIFY algorithms fail.

Primary new evidence:
`docs/cpu_only_algorithm_consolidation_20260824/14_FINAL_CPU_EXECUTION_AND_IDEA_VERDICT.md`
and `outputs/t2_comparator_semantics_cpu_audit_v1/REPORT.md`.

## 4. Current decision

The dominant uncertainty is upstream of policy optimization: does a faithful
endogenous executor create distinct, query-conditioned information and legal
actions without reference leakage or hidden fallback candidates?

CPU result: **B0_CPU_INFRASTRUCTURE_QUALIFIED**. The new executor passed all
frozen invariants and the focused executor suite (26 tests). Therefore the next
scientific uncertainty is B1 natural opportunity, but its fresh/physical
execution remains blocked pending a new explicit authorization.

B1a protocol result: **B1A_PROTOCOL_FROZEN_EXECUTION_BLOCKED_INPUTS_UNBOUND**.
The minimum natural-opportunity killer is frozen for three new independent
videos, all six discovery queries, six simple fixed policies, measured
wall-clock costs, an exhaustive model-relative DirectVerify reference, and
result-neutral gates. No eligible new video bytes, query-conditioned SCAN
artifact/runtime, or bound semantic verifier is present, and external execution
has not been authorized. No semantic outcome was generated.

Authorized now:

- freeze the B0 action/information/evaluator contract;
- implement and test a CPU-only executor with SCAN/PROPOSE, candidate VERIFY,
  and region-level DirectVerify as distinct operations;
- run synthetic invariants, exact trace-parity tests, and read-only audits;
- freeze baselines, consumed workloads, stop rules, and evidence requirements.
- perform read-only input discovery and prepare exact hash binding for B1a.

Not authorized by this state:

- GPU, VLM, API, or new video inference;
- human annotation or human audit;
- tuning on the six consumed T2 workload cells;
- claims about natural headroom, prevalence, physical costs, or human utility;
- adaptive-planner/controller training;
- B1-B3 or physical P4 execution without a new explicit gate decision.

## 5. Evidence precedence and update rule

Use: (1) frozen direct results and gate decisions; (2) later adversarial or
identifiability audits; (3) this consolidation; (4) older narratives. Update
the ledgers before broadening a claim. Preserve negative results. A B0 CPU PASS
only unlocks writing a fresh-workload/physical protocol for separate approval;
it does not unlock inference or establish Claim B.
