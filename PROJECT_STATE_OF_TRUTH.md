# GVAQP project state of truth

Status date: 2026-08-13 UTC  
Scope: project-level scientific claims, not a replacement for raw artifacts  
Current phase: **P1 waiting for an independent human reference**  
Experiment policy: **pause ungated escalation**

This file is the mandatory entry point for future agents. Read it together with
`CLAIM_LEDGER.csv`, `EXPERIMENT_DECISION_LEDGER.csv`,
`ACTIVE_HYPOTHESES.md`, `CLOSED_BRANCHES.md`, and
`NEXT_STAGE_STATE_MACHINE.md` before interpreting older plans or results.

## 1. Original research question

How should open-semantic temporal events be queried when cheap sensing is
imperfect, semantic verification is expensive, and resources are limited?

The question decomposes into three claims:

| Claim | Current status | Exact boundary |
|---|---|---|
| A. Imperfect proxy creates meaningful query-optimization work. | **PARTIALLY SUPPORTED** | Natural ranking degradation causes low-budget loss on the current fully precomputed candidate universe. Natural exposure misses and human-event utility are not established. |
| B. Under truly costly/incomplete SCAN, state-dependent SCAN/VERIFY allocation is valuable. | **NOT ESTABLISHED** | The cached substrate partially instantiates delayed visibility and legal-action expansion, but not endogenous sensing, natural exposure failure, measured physical costs, natural state prevalence, or human utility. |
| C. Event-aware acquisition is more robust to proxy error than maximizing positive yield alone. | **THEORETICALLY MOTIVATED; EMPIRICALLY NOT ESTABLISHED** | Worst-case constructions and model-relative diagnostics motivate the claim. Independent-human equal-yield benefit has not been measured. |

These statuses supersede broader language in older roadmaps. In particular,
`NOT ESTABLISHED` must not be paraphrased as failure, and theoretical
motivation must not be described as empirical support.

## 2. Controlled vocabulary

Use only these empirical claim statuses:

- **SUPPORTED**: sufficient direct empirical evidence within the stated scope.
- **PARTIALLY SUPPORTED**: direct evidence exists, but the claim scope is
  materially narrower than the general claim.
- **NOT ESTABLISHED**: the claim is plausible or motivated but has not been
  faithfully tested or has insufficient evidence.
- **DISFAVORED / WEAKENED**: direct negative evidence reduces plausibility, but
  does not justify universal rejection.
- **NO-GO / CLOSED**: current evidence does not justify further investment in
  the frozen branch. Reopening requires an explicit condition in
  `CLOSED_BRANCHES.md`.

Stage states such as `WAITING_HUMAN_REFERENCE`, `PASS`, `PARTIAL`, and `FAIL`
are gate outcomes, not substitutes for empirical claim status.

## 3. Established experimental facts

### Proxy and resource scaling

- The current natural proxy has weak ranking quality: per-video AUPRC is
  0.2584–0.3146. Severe ranking degradation produces a median low-budget
  EventF1 gap of 0.095134.
- The original one-candidate-per-unit substrate has structural and positive
  exposure recall 1.0. Synthetic exposure deletion produced a corresponding
  median gap of 0.0. Therefore the demonstrated bottleneck is ranking; natural
  cheap-sensor exposure misses have not been measured.
- For nested query-count traces, quality is nearly monotone with budget
  (0.48% transition violations). This is an oracle-call budget result, not a
  physical hard-deadline result.

Primary evidence: `outputs/main_thesis_alignment_v1/FINAL_ALIGNMENT_REPORT.md`
and `outputs/original_theory_identifiability_audit_v1/FINAL_IDENTIFIABILITY_REPORT.md`.

### Materialization

- Sparse semantic outcomes do not map trivially to an `EventRelation` in the
  frozen model-relative evaluation. Across 54 same-trace K3/K0 pairs, median
  Delta EventF1 is +0.1457; K3 is better/equal/worse in 40/14/0 cells.
- Policy spread with C1 fixed is 0.1403, comparable to the historical
  materializer effect; selector × materializer interaction has range 0.2573.
- Mechanism ablation attributes almost all measured gain to a simple
  10-second gap constraint: median increment +0.1377. Duration cap, negative
  barrier, and current-K3 extras have median increments 0.0.
- These are cached, query-budget, K3-reference/model-relative findings. They do
  not establish human event boundaries or physical-deadline superiority.

Primary evidence: `outputs/p0_materializer_validation_v3/FINAL_RESEARCH_REPORT.md`,
`outputs/p0_materializer_mechanism_ablation_v1/MECHANISM_REPORT.md`, and
`outputs/main_thesis_alignment_v1/FINAL_ALIGNMENT_REPORT.md`.

### Controller and action selection

- Fixed SCAN1→VERIFY1 is the strongest observed cached sequential default
  (mean anytime event-recall AUC 0.13323 versus dynamic V3 0.12228).
- The 108-state cached branch table contains 25 SCAN-better, 26 VERIFY-better,
  and 57 tied states, but it is sampled from two sources under abstract costs.
- Public-state learning does not generalize: best learned regret is 0.009693,
  contextual-bandit regret 0.010325, versus fixed always-VERIFY regret
  0.000885. The cached public-state gate fails.
- Physical probes give 0/18 immediate strong positives and only 1/7 bounded
  continuation conversions, with no event-count gain. MAB/RL/controller work
  is therefore NO-GO on the current substrate.

Primary evidence: `RC_SEM_PACKAGE_MANIFEST.json`,
`outputs/public_state_predictability_cached_v3/SUMMARY.json`, and
`MAB_RESEARCH_DIRECTION_DECISION.md`.

### Evidence geometry and human P1

- The old 378-cell, K3-reference/model-relative audit found yield-only LOVO
  R2 0.006 and yield-plus-public-geometry R2 0.795. Its decision was already
  `EVENT_EVIDENCE_GEOMETRY = PARTIAL`, not strong; only 1/3 videos supplied a
  top equal-yield counterexample with F1 gap at least 0.15.
- The later VLM-direct shadow weakens the geometry hypothesis: macro coverage
  effect +0.003193; 2/6 clusters positive, 2 zero, 2 negative; 2/3 source-video
  means positive; YOLO effect -0.004974; optical-flow effect +0.009136;
  geometry improves LOVO MAE by only 0.000665. The shadow reference has low
  independence/agreement and is not human truth.
- Formal P1 remains `WAITING_HUMAN_REFERENCE`. The frozen human label log has
  0 rows. The automated grid, two proxies, traces, and analysis code are ready,
  but no P1 PASS/PARTIAL/FAIL decision exists.

Primary evidence: `outputs/event_evidence_geometry_v1/EVENT_EVIDENCE_GEOMETRY_DECISION.md`,
`outputs/p1_shadow_vlm_direct_reference_v1/FINAL_SHADOW_REPORT.md`, and
`outputs/gvaqp_long_horizon_p1_p3_v1/RESEARCH_STATE.json`.

### Existing model-relative P2 diagnostic

- A cached model-relative generic relevance+coverage/MMR novelty-killer was
  executed before human P1 resolution. Its canonical rule is essentially tied
  with StaticProxyRank: video-query-cluster median Delta F1 0.0, 95% bootstrap
  interval [-0.0136, 0.0223]; equal-yield median Delta EventF1 and EventRecall
  are both 0.0; observed semantic-state residual is absent.
- Its decision is `INCONCLUSIVE`, query-policy geometry becomes weak /
  non-confirmatory, and it authorizes neither P3 nor MAB.
- Because formal P1 was unresolved, this artifact is retained as a completed
  **non-authorizing diagnostic**, not treated as the gated P2 confirmation in
  the future decision tree.

Primary evidence: `outputs/p2_query_policy_novelty_killer_v1/FINAL_P2_REPORT.md`
and `P2_DECISION.md` in the same directory.

## 4. Current project judgment

The project is not a sequence of undifferentiated failures. It has converged
from a broad controller/materializer/policy idea into two falsifiable open
questions:

1. Does equal-yield, policy-visible evidence geometry improve recovery of
   independently human-defined temporal events? This is the only active
   confirmatory question, and it is waiting for human labels.
2. Does faithful endogenous costly/incomplete SCAN create non-rare, material,
   policy-visible action regret? This is not faithfully tested and is deferred
   to a future P4 gate; it is not authorized now.

Everything else is either a bounded system finding, a weakened hypothesis, or
a closed branch. No new P2/P3/P4/P5 experiment is authorized by this state.

## 5. Evidence precedence and update rule

When sources disagree, use this order:

1. frozen direct result tables, completion manifests, and gate decisions;
2. later adversarial/identifiability audits that narrow claim scope;
3. this project-level consolidation;
4. older narrative reports and roadmaps.

New evidence does not silently overwrite this file. Update the relevant CSV
ledger first, record the gate outcome and source artifact, then revise all six
state files in one change. Never delete a negative result; mark it superseded,
bounded, weakened, or closed with a reason.

