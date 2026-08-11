# MAB Research Direction Decision

Audit snapshot: `dspro@2c0d35c888f9711cacab964672c6094fc98e5c49` (2026-08-08). This decision uses only persisted repository evidence and public literature. No new policy run, branch run, semantic-oracle call, label, or source was produced.

## 1. Executive Verdict

```text
FINAL DECISION: DO_NOT_DO_MAB
```

现有证据支持固定 temporal-bisection 的覆盖顺序与 SCAN/VERIFY 交错，却不支持可学习的动作选择：18 个一步反事实无直接正例，7 个延续对仅 1 个同事件提前、6 个未转化或更差；动作模型近随机且劣于固定策略。MAB 结构也与有状态、延迟回报、动态合法动作集不匹配，投入后难形成可信或新颖的主贡献。

This is a direction freeze, not a request for more evidence. The project should converge on a deterministic, deadline-safe temporal-coverage executor with causal and durable event materialization.

## 2. Evidence Used

| Evidence | Result | What it proves | What it does **not** prove | Confidence |
|---|---|---|---|---|
| Guangzhou O, strict completion-based evaluation | A/C: all deadline metrics zero. B: Recall AUC `0.0139474`, Recall@300 `0.0555556`, F1 AUC `0.0264267`, F1@300 `0.1052632`, one event at `224.683840895 s` | Deterministic temporal order changes equal-time utility on this workload; B is the strongest tested fixed policy | Generalization, adaptive superiority, or multi-event gain | High for this run; exploratory scientifically |
| Guangzhou runtime repeat | B again recovers unit 346 at `224.200606149 s`; A/C remain zero | B is runtime-repeatable on the same source and stack | Source/query independence | High for repeatability; not independent |
| H0 causal reachability audit | `0` dependency violations; missing exact-state alternatives: A `1710`, B `1710`, C `845` | Legal-state model is coherent; realized trajectories are causally valid | Reachable dynamic oracle or valid off-policy estimate | High |
| Prior evaluator greedy | AUC about `0.664458` under cached reference and abstract costs | Loose clairvoyant diagnostic ceiling | Reachable or physical headroom | High that it is inapplicable |
| 18 one-step physical alternatives over 12 label-blind B states | `0` strong positives, `7` cost-only, `2` neutral, `9` worse | Immediate overrides reveal no direct event-utility dominance | Impossibility of every longer-horizon opportunity | High within selected states |
| Seven bounded paired continuations | `1` converted, `4` dissipated, `2` worse; rate `1/7` | Most one-step cost savings do not survive identical fixed-B continuation | Trajectory-level dynamic-oracle advantage | High within frozen probe |
| Sole converted pair | `B_DECISION_025`, `VERIFY:299 -> SCAN:34`; same event count, first event `10.54 s` earlier; Recall AUC `+0.009759`, F1 AUC `+0.018491`, cost `-4.247 s` | A local reachable timing opportunity exists | Robust boundary, count gain, or controller gain | Moderate; one selected pair |
| Candidate semantic-value modeling | M0 Logistic development LOSO AUPRC `0.555469`; raw YOLO `0.176400`; shuffled-label mean `0.142245`; source-ID-only `0.111111` | Candidate semantic value can be ranked above raw proxy in the Stage-A support sample | Whether to SCAN or VERIFY; closed-loop/source-general value | Moderate; enriched sample, undeployable model |
| Public action-state predictability | Pooled frozen blocked-CV AUROC `0.548282` | At most weak runtime-visible action-choice discrimination | Reliable online control | High for frozen result |
| Cached action-policy comparison | 108 states / 2 sources. Linear regret `0.009693`; contextual-bandit regret `0.010325`, sign accuracy `0.543380`; fixed always-VERIFY regret `0.000885`, accuracy `0.813915` | Learned selection is worse than a trivial fixed action in the cached abstraction | Physical Guangzhou performance | High for negative direction; abstract costs |
| Historical binary SMDP audit | `INSUFFICIENT_EVIDENCE`; learning `NOT_AUTHORIZED`; 9/11 low-budget behavior rollouts overran | Stateful timing effects are plausible but unsafe and not cross-video | Safe reachable headroom | High |
| Historical controller/bottleneck program | SCAN recovery, VERIFY selection, SCAN×VERIFY interaction all `ABSENT`; best simple baseline FIFO; `COMPLETE_NO_GO` | Repeated controller search did not establish a cross-video adaptive mechanism | Universal impossibility | High for this project state |

Primary local evidence and hashes:

- [`RESULTS_DEADLINE_SAFE.json`](outputs/exploratory_temporal_order_guangzhou_v1/exploratory_20260808_8b_300s/RESULTS_DEADLINE_SAFE.json): `72efde93d0581967190847cc7b4fbbf36021c2b823bad5e2eadae4961b129147`.
- [`B trace`](outputs/exploratory_temporal_order_guangzhou_v1/exploratory_20260808_8b_300s/B_TEMPORAL_BISECTION_FIXED_SCAN1_VERIFY1.trace.json): `bbfac511654fd308d5bac9dd6a8b1ce3e3caadc928c602918823e3a1e3fd6993`.
- [`H0 audit`](outputs/exploratory_temporal_order_guangzhou_v1/exploratory_20260808_8b_300s/H0_CAUSAL_REACHABILITY_AUDIT.json): `d8a33568268bb408a6ea000fe339a761f64ff298c50d25285d3137b202185cd4`.
- [`One-step results`](outputs/exploratory_temporal_order_guangzhou_v1/exploratory_20260808_8b_300s/counterfactual_probe_v1/COUNTERFACTUAL_BRANCH_PROBE_RESULTS.json): `f3d6468d4c8edf0f34abc94952ba9a857b1d6ac333a7ddafa3ef1e4ccbcc2070`.
- [`Continuation results`](outputs/exploratory_temporal_order_guangzhou_v1/exploratory_20260808_8b_300s/counterfactual_continuation_v1/CONTINUATION_PROBE_RESULTS.json): `061ea5c72bfafedc06bcb84d7427e8b026a423a8f3f39c387ca12bf35932298d`.
- [`Action predictability`](outputs/public_state_predictability_cached_v3/SUMMARY.json), [`SMDP report`](outputs/binary_smdp_value_v1/reports/ORACLE_HEADROOM_REPORT.md), and [`controller decision`](outputs/psvr_bottleneck_research/AUDITED_DECISION.json).

## 3. What the Current Data Actually Establishes

### Established

1. **Completion-based accounting matters.** A result completing after 300 s cannot enter `@300` or AUC `[0,300]`; this turns C's apparent success into zero deadline utility.
2. **Temporal order matters on Guangzhou.** With the same 1:1 operator ratio, B finds one event twice at about 224 s while chronological A finds none.
3. **A deterministic coverage schedule is causally realizable.** B obeys exposure and visibility rules; H0 found no dependency violation.
4. **The B result is runtime-repeatable, not source-independent.** Original/repeat completion differs by about `0.483 s`.
5. **Most tested B overrides are not useful.** `0/18` immediate improvements and `6/7` continuation non-conversions are direct physical evidence.
6. **Candidate ranking and operator selection differ.** Candidate AUPRC does not license a SCAN/VERIFY controller.

### Suggested

1. Coverage diversity plus prompt verification is the main mechanism.
2. Interleaving is useful in this trace; B versus C is suggestive because it also changes phase structure.
3. One local timing opportunity exists, but not a reliable policy boundary.

### Not established

- Positive reachable trajectory-level headroom `H` above B.
- A runtime-visible predictor of when an override converts cost into event utility.
- Cross-source order replication, controller generalization, or event-count gain.
- Stage-A candidate-model calibration/deployability in this runtime.
- That any MAB, contextual bandit, SMDP, or learned optimizer beats B.

### Rejected

- Treating evaluator AUC `0.664458` as reachable headroom.
- Inferring action learnability from candidate AUPRC.
- Promoting one `1/7` timing conversion to adaptive-policy evidence.
- Making “bandit chooses the next segment/action” the novelty claim.
- Spending the next research cycle on MAB implementation or experiments.

## 4. MAB Decision Gates

| Gate | Result | Evidence | Consequence |
|---|---|---|---|
| M1 Empirical necessity | **FAIL** | `0/18` direct positives; only `1/7` continuations improves timing with no count gain; `4/7` dissipate, `2/7` worsen | No demonstrated utility gap justifies controller complexity |
| M2 Learnability | **FAIL** | Blocked-CV AUROC `0.548`; contextual-bandit accuracy `0.543`; learned regret `0.0097–0.0103` versus fixed `0.000885` | Runtime state lacks a reliable SCAN/VERIFY boundary |
| M3 Structural fit | **FAIL** | Sleeping actions, exposure dependencies, consumed VERIFY arms, heterogeneous duration, delayed SCAN value, K3 deduplication, shrinking horizon | This is a constrained SMDP/query executor, not a natural MAB |
| M4 Scientific novelty | **FAIL** | LAVA uses MAB segment localization; ExSample/Seiden adaptively sample; ARC uses bandit-style refinement; Aero, Zeus, FiGO adapt expensive operators/fidelity | Applying a bandit is incremental, not a main contribution |
| M5 Evaluation credibility | **FAIL** | A/B/C lack alternatives; 18+7 probes are selected support, not a complete logged-bandit dataset; no propensities or broad action support | Existing-only MAB evaluation would fabricate or extrapolate transitions |

## 5. MAB Formulation Audit

This is not a classic stationary MAB. It is closest to a **hard-budget semi-Markov contextual decision process with sleeping actions and endogenous action creation**: SCAN creates VERIFY actions; VERIFY consumes a candidate; durations are heterogeneous; SCAN reward is delayed; deduplication makes utility history-dependent; and the horizon is physical time.

| Formulation | Merit | Main defect |
|---|---|---|
| A: `{SCAN, VERIFY}` | Small | Collapses heterogeneous cells/candidates; no stable VERIFY reward distribution |
| B: `{SCAN(cell), VERIFY(c_1), ...}` | Concrete legal actions | Arms appear/disappear, are consumed, and are created by other arms |
| C: `{SCAN_NEXT, VERIFY_TOP, STOP}` with a fixed ranker | Least unnatural and implementable | Still has delayed credit, state transitions, variable costs, and future-option effects |

If forced, C would be a **cost-aware sleeping contextual bandit** called after every durable action. Legal context would include remaining time, scanned fraction, next cell, queue size, top score/gap/age, action counts, confirmed-event count, observed cost EWMAs, and commit reserve. Evaluator labels and unscanned proxies would be forbidden.

The immediate reward

\[
r_t=\frac{U(E_{t+1})-U(E_t)}{C_t}
\]

assigns SCAN zero reward even when its later candidate causes an event. Back-propagating that reward requires eligibility traces, a value/transition model, or trajectory return—i.e. SMDP/RL. Candidate-count or proxy-mass shaping optimizes an unvalidated surrogate. Delayed credit is therefore the central technical defect.

Existing data cannot credibly evaluate this forced formulation. The 18 alternatives and seven continuations are a targeted subset, not randomized behavior with propensities or full downstream support. Coding a learner is possible; estimating its closed-loop utility without fabricated transitions is not.

## 6. Prior-Art / Novelty Audit

### Closest collisions

| Work | Overlap | Remaining difference | Collision risk |
|---|---|---|---|
| [LAVA](https://arxiv.org/abs/2507.19821), [ACM DOI](https://doi.org/10.1145/3746027.3754955) | Explicit **MAB segment sampling** for language-driven traffic-video localization | Our durable confirmed EventRelation and one-clock contract | **Very high** for a MAB claim |
| [Seiden](https://doi.org/10.14778/3598581.3598599), [PDF](https://www.vldb.org/pvldb/vol16/p2289-kakkar.pdf) | Query-time adaptive video sampling/exploration and interpolation | Ingest oracle index; different output/cost scope | High |
| [ExSample](https://arxiv.org/abs/2005.09141) | Thompson-style adaptive reprioritization of unindexed chunks | Distinct objects, no candidate-confirmed EventRelation | High |
| [ARC](https://doi.org/10.1145/3726302.3729896) | Proxy clips plus progressive oracle refinement and bandit-style priority | Exhaustive proxy first; call budget; no durable relation | High for refinement |
| [Zeus](https://doi.org/10.1145/3514221.3526181) | Learned segment length/rate/resolution choices | RL action localization | High for learned controller novelty |
| [FiGO](https://doi.org/10.1145/3514221.3517857) | Per-chunk fidelity/model planning with optimizer cost | Query plan rather than hard-stop EventRelation | High |
| [Aero](https://doi.org/10.1145/3725408) | Runtime feedback reorders costly ML predicates/resources | Relational UDF pipeline, not temporal candidate exposure | High for generic adaptive-operator claims |

### Adjacent systems

- [SUPG](https://doi.org/10.14778/3407790.3407804) adaptively spends labels over a fully proxy-scored population.
- [AQUAPRO: On Efficient Approximate Queries over Machine Learning Models](https://arxiv.org/abs/2206.02845) combines cheap proxies and expensive oracles for precision/recall targets.
- [ThalamusDB](https://doi.org/10.1145/3654989), [author PDF](https://saehanjo.github.io/assets/files/thalamusdb.pdf), prioritizes multimodal processing/labels under error, time, and labeling objectives.
- [MIRIS](https://doi.org/10.1145/3318464.3389692) performs query-specific sparse tracking/refinement; [DIVA](https://www.usenix.org/conference/atc21/presentation/xu) performs cheap-to-expensive video passes with validation and continuous results.
- [TASTI](https://doi.org/10.1145/3514221.3517897) is the only identifiable likely expansion of the prompt's ambiguous “T*”; if another work was intended, this report does not invent a citation.
- [TSGSV](https://arxiv.org/abs/2308.07102) addresses causal no-future-frame temporal grounding, but not expensive-action scheduling.
- [ProgressiveDB](https://doi.org/10.14778/3352063.3352073), [PDF](https://www.vldb.org/pvldb/vol12/p1814-berg.pdf), establishes incrementally improving database results as a systems goal.
- [Simple Adaptive Query Processing vs. Learned Query Optimizers](https://doi.org/10.14778/3611479.3611501) finds simple interpretable adaptive operators competitive with or better than learned optimizers, consistent with our fixed-policy evidence.

Engineering a bandit wrapper is reusable but ordinary. Enforcing exposure, completion deadlines, K3 deduplication, and durability is an incremental systems adaptation. The only defensible paper-level hypothesis is narrower: incomplete evidence is created at query time; deterministic coverage and confirmation share one physical clock; only causally exposed, confirmed events become durable. The MAB is neither the novel nor the supported part.

## 7. Mechanistic Interpretation of Existing Results

### Why B wins

1. **Temporal spread — supported.** B reaches cell 34 as its 14th completed SCAN. It runs at `207.3598–215.1089 s`; chronological A completes only an early contiguous prefix and never exposes unit 346.
2. **Exposure timing — supported.** Cell 34 exposes unit 346 with OpenCV mean difference `0.2248153`; it becomes rank 1 among exposed unattempted candidates.
3. **Prompt interleaving — supported.** B immediately starts `VERIFY:346` at `215.1109 s` and durably completes positive at `224.6838 s`. The repeat completes at `224.2006 s`.
4. **Why C misses — supported.** C reaches cell 34 only around `232.15–240.57 s`, scans all 43 cells, and unit 346 is then rank 11. Its second VERIFY (`308`) starts at `299.5311 s` and completes positive at `308.7692 s`, so it is excluded.
5. **Latency accident — unsupported as main cause.** Same-unit timing repeats within about half a second.
6. **Single-event luck — material limitation.** B's entire advantage is one of 21 reference positives. It is repeatable on one source, not generalized.

B versus A cleanly supports **order** because both are fixed 1:1. B versus C suggests **interleaving**, but also changes phase structure and queue competition. Adaptive control remains unsupported.

### Why adaptation fails

B already alternates coverage with the highest-ranked exposed VERIFY. Alternatives either spend more time on a lower-ranked candidate or replace an immediately available verification with a cheaper SCAN that has no immediate EventRelation delta. The seven opportunities were selected for cost, not semantic value.

Fixed-B continuation then re-imposes the 1:1 schedule. Four savings dissipate through later latency/action stopping and two treatments worsen; extra time matters only if it changes which positive is durably verified. The sole conversion occurs because control spends about `10.10 s` on negative `VERIFY:299`, while treatment spends about `8.22 s` on `SCAN:34`, exposes positive unit 346, and reaches the same event `10.54 s` earlier. This is a mechanistic example of coverage-before-negative-verification, not a learnable rule: runtime cannot know that 299 is negative or cell 34 positive.

## 8. Reviewer Debate

### Best case FOR MAB

The legal action model exists; cached states contain both SCAN-better and VERIFY-better cases; Guangzhou is order-sensitive; seven alternatives initially save cost; and one reachable override converts cost to earlier utility. A safe `{SCAN_NEXT, VERIFY_TOP}` sleeping contextual bandit could use queue pressure and time and fall back to B. Candidate-value work shows some runtime features carry semantic signal.

### Best case AGAINST MAB

The prerequisite is learnable repeatable headroom above B, not one favorable hindsight transition. Evidence is `0/18` immediate and `1/7` timing-only conversion, while learned action models are near-random and worse than fixed behavior. Logs cannot support honest closed-loop evaluation. SCAN creates future arms and delayed reward; VERIFY consumes them, so MAB is the wrong abstraction. LAVA already uses MAB video sampling and a dense prior-art neighborhood removes novelty.

### PI adjudication

Reviewer B wins. Reviewer A shows only that adaptation can be formulated. It does not establish empirical necessity, learnability, faithful evaluation, or novelty. The sole conversion is already captured by the simpler mechanism to retain: expose temporally distant evidence before costly negative verification, via temporal-bisection plus fixed interleaving.

## 9. Final Algorithm Direction

### Opportunity-cost adjudication

| Direction | Evidence-backed upside now | Main risk | Priority |
|---|---|---|---|
| MAB controller | One timing-only converted pair | Wrong abstraction, weak learnability, unsupported evaluation, crowded novelty | Stop |
| Deterministic temporal coverage/order | Two physical B runs recover the same deadline-safe event; mechanism is trace-identifiable | Single-source/single-event scope | **Primary** |
| Better VERIFY candidate ordering | Stage-A candidate AUPRC shows ranking potential | Model is exploratory/uncalibrated and does not establish closed-loop gain | Secondary analysis only |
| Cost-aware fixed scheduling | Directly addresses observed overruns without action learning | Conservative bounds may stop early | Required systems hardening |
| Event materialization/boundary recovery | Central to the durable EventRelation contract | Broad novelty is limited by ARC/MIRIS/DIVA | Required contract component |
| Precision-constrained early release | Potentially useful output contract | Current Guangzhou evidence tests confirmed release, not speculative release | Do not make current mainline |
| Other historical controller/proxy routes | Existing code and diagnostics | Repeated no-go/absent signals | Close |

The highest-value use of the next cycle is therefore deterministic temporal coverage plus completion-safe execution and evidence packaging. It converts already established behavior into an auditable contribution; MAB would consume the cycle rebuilding missing support for a weaker claim.

### Deadline-Aware Temporal-Bisection SCAN/VERIFY (DATB-SV)

```text
INPUT:
  immutable 10-second cells C[0..n-1], hard deadline D
  deterministic temporal-bisection permutation P(n)
  frozen query/SCAN/VERIFY/K3, action-cost upper bounds U
  durable-commit reserve R_commit

STATE:
  cursor := 0
  exposed := priority queue by frozen runtime-visible proxy score,
             then unit ID for deterministic ties
  attempted := empty; EventRelation := empty
  next_operator := SCAN

while monotonic_clock() < D:
  if next_operator == SCAN and cursor < n:
      a := SCAN(P(n)[cursor])
  else if exposed contains an unattempted candidate:
      a := VERIFY_TOP(exposed - attempted)
  else if cursor < n:
      a := SCAN(P(n)[cursor])
  else:
      break

  if now + U[type(a)] + R_commit > D:
      a := deterministic_safe_other_operator_or_STOP(state)
      if a == STOP: break

  start := monotonic_clock()
  outcome := execute(a)
  complete := durable_visibility_clock(outcome)
  append_full_trace(a, start, complete, outcome)

  if complete <= D:
      if a is SCAN:
          expose only candidates produced by this completed SCAN
          cursor += 1
      else:
          attempted.add(candidate)
          if outcome is accepted positive:
              EventRelation := K3_materialize_deduplicate(EventRelation, outcome)
          durable_atomic_commit(EventRelation)
  else:
      mark_post_deadline_diagnostic_only(outcome)
      break

  next_operator := VERIFY if a is SCAN else SCAN

durable_atomic_commit(EventRelation)
return EventRelation, trace
```

The safety bounds/reserve use existing physical profiles and are fixed, not learned. If no trustworthy bound exists near deadline, STOP. This conservative production admission is distinct from the exploratory runner's start-before-deadline rule.

This algorithm preserves the repeated mechanism, is causally auditable, avoids off-policy support problems, and does not learn sparse delayed rewards on evidence where learned selection already loses.

Defensible contributions:

1. A hard-deadline event-query contract in which candidate creation, causal exposure, expensive confirmation, K3 deduplication, and durable completion share one physical clock.
2. A deterministic temporal-coverage executor whose earlier event recovery versus chronological and scan-then-verify is demonstrated in the audited Guangzhou regime and same-source runtime repeat.
3. A causal controller audit/negative design result: after a strong fixed schedule, targeted legal alternatives mostly fail to convert lower cost to event utility. This is workload-scoped, not a universal theorem.

## 10. Paper Positioning

| Item | Frozen positioning |
|---|---|
| Research problem | Recover a durable semantic EventRelation from a long initially unscanned video under a hard wall-clock deadline |
| Core mechanism | Deterministic temporal spread creates diverse candidates early; fixed prompt verification avoids full-scan queue delay |
| Algorithm | DATB-SV: bisection SCAN + top-exposed VERIFY + fixed 1:1 interleaving + conservative admission + durable K3 |
| Baselines | Chronological 1:1, scan-then-verify, equal-call diagnostic, deadline-safe last-durable/empty state |
| Main claimed advantage | Earlier deadline-safe confirmed-event visibility under a fully charged clock |
| Do not claim | MAB efficacy, generalization, adaptive validation, first proxy/oracle video system, first progressive sampling, strict confirmatory Gate-O success |

Relative positioning:

- Seiden uses a partial oracle index and interpolation; DATB-SV begins without query evidence and publishes only confirmed events under the first-query clock.
- LAVA already owns the obvious MAB traffic-video segment-selection claim; DATB-SV's narrower distinction is deterministic incomplete evidence plus durable EventRelation visibility.
- ARC exhaustively generates proxy scores before refinement; DATB-SV co-schedules incomplete SCAN and VERIFY under an enforced clock.
- ExSample adapts chunks for distinct objects; DATB-SV fixes temporal coverage and separates candidate from semantic confirmation.
- SUPG/AQUAPRO/ThalamusDB optimize preexisting populations/plans rather than endogenous candidate exposure.
- MIRIS/DIVA/FiGO/Zeus/Aero make learned/profiled/adaptive choices and preclude broad optimizer novelty.
- ProgressiveDB motivates progressive answers broadly; this work's narrow issue is causal, confirmed, durable temporal-event output.

The honest paper is a **physical-anytime event-query systems and design-evidence paper**, not a MAB paper.

## 11. What To Do With MAB

```text
REJECTED_DESIGN_AND_FUTURE_WORK
```

Mention MAB once in the design-space/negative-results section: it was rejected because reachable gain was rare, runtime action value was not learnable, the process was stateful/delayed, and logs could not support credible closed-loop evaluation. Preserve the 18+7 results. Do not implement, tune, or headline a MAB. “Future work” records a claim boundary; it is not a recommendation for another experiment in this project cycle.

## 12. Concrete Next 2 Weeks

### Day 1–3

1. Freeze one DATB-SV spec separating demonstrated B behavior from conservative production admission.
2. Unify fixed-B order, tie-breaking, legal exposure, completion time, and durable visibility in one authoritative code path.
3. Add property tests for arbitrary-size bisection permutations, causal exposure, deterministic queues, post-deadline immutability, commit reserve, and fail-closed STOP.
4. Add a no-inference provenance command hashing algorithm, config, input, reference, traces, and results.

### Day 4–7

1. Build a read-only trace analysis for the original/repeat cell-34 → unit-346 timeline.
2. Generate existing-data figures: equal-time curves, exposure/queue timeline, and 18+7 outcome funnel.
3. Consolidate candidate-value versus action-value metrics, separating AUPRC from regret/sign accuracy.
4. Turn H0/one-step/continuation artifacts into a causal-support appendix retaining negative and post-deadline records.
5. Add an integrity test for every hash cited here and the strict Gate-O verifier.

### Week 2

1. Draft contract, algorithm, evaluation semantics, mechanism, related work, limitations, and negative-controller sections.
2. Create a `SUPPORTED / EXPLORATORY / NOT_SUPPORTED` claim ledger and lint prohibited adaptive/generalization wording.
3. Extend the related-work matrix with LAVA and Aero alongside existing ARC/Seiden/ExSample/SUPG/MIRIS/DIVA/FiGO audits.
4. Package deterministic replay that recomputes tables from JSON and never imports semantic runtime.
5. Remove MAB from roadmaps, diagrams, and the implementation queue; archive its scaffolds as non-mainline evidence.

## 13. Final Research Freeze

```text
MAB decision:
DO_NOT_DO_MAB

Primary algorithm:
Deadline-Aware Temporal-Bisection SCAN/VERIFY (DATB-SV): deterministic
temporal coverage, top-exposed verification, fixed 1:1 interleaving,
conservative admission, and durable K3 EventRelation commit.

Role of temporal-bisection:
Core scheduling mechanism and strongest fixed policy; supported on Guangzhou
with a same-source physical runtime repeat.

Role of adaptive SCAN/VERIFY:
Rejected as current mainline. Causal probes show rare weak conversion above B,
without a learnable runtime decision rule.

Role of MAB in paper:
REJECTED_DESIGN_AND_FUTURE_WORK

Main contribution:
A causally legal, hard-deadline physical-anytime event-query contract and a
deterministic temporal-coverage/verification algorithm with durable output.

Strongest evidence:
B alone recovers one deadline-safe event at about 224 s in both Guangzhou runs;
the trace ties it to early cell-34 exposure and immediate VERIFY:346, while
targeted adaptation gives 0/18 immediate gains and only 1/7 timing conversion.

Largest remaining limitation:
The positive algorithm result is exploratory, single-source, and single-event;
it supports a scoped systems/design claim, not generalization or confirmation.

What I should implement next:
Unify and harden DATB-SV, conservative completion-safe admission, provenance,
read-only trace analysis, and the paper artifact.

What I should stop doing:
Stop MAB/controller implementation, policy search, counterfactual expansion,
clairvoyant-oracle promotion, and claims that candidate ranking implies
adaptive action selection.
```
