# Controller estimand mapping audit (local scientific audit, v1)

Audit type: static read + stdlib-only (csv/json) deterministic analysis. No model was
run, no training, no MAB/RL experiment, no human-labeled file was read.

Scope of this audit: map every controller / action-selection experiment to its exact
estimand (Q definition, state population, continuation, threshold), and reconcile the
two well-known 108-state number sets:

- cached branch table: **SCAN_BETTER=25 / VERIFY_BETTER=26 / TIED=57** (tie tolerance 1e-12)
- identifiability audit: **BENEFICIAL=5 / HARMFUL=5 / INDIFFERENT=98** (practical delta=0.005)

**Verdict on the 108-state numbers: RECONCILED.** They are two threshold + orientation
views of the *same* per-state one-step Q difference on the *same* 108 states, not
contradictory results (see §c and §b). All numbers below were re-derived from frozen
artifacts; the learning metrics reproduce the cached SUMMARY to ~1e-11.

---

## a. Exact Q definition per controller experiment

Frozen controller Q (shared by the 108-state cached branch table and the identifiability
audit; source: `controller_dynamic_headroom_cached_v1/SUMMARY.json` field
`q_definition`, echoed by `Q_OBJECTIVE_DISCONTINUITY_AUDIT.md`):

```
Q = 0.5*terminal_event_recall + 0.5*anytime_event_recall_auc - 1[nonempty output precision < 0.8]
```

- `terminal_event_recall` and `anytime_event_recall_auc` are computed against an *older
  cached pseudo-reference* under **strict K3** grouping (`CONTROLLER_OBJECTIVE_LINEAGE.csv`
  row `controller_dynamic_headroom`: optimized_score = "Q terminal recall + recall AUC -
  hard precision penalty"; `INTENDED_VS_ACTUAL_CONTRACT.csv` row 11: "0.5 terminal
  pseudo-event recall + 0.5 recall AUC, hard precision penalty").
- The `-1` term is a hard penalty applied when a nonempty output violates precision>=0.8
  (a discontinuity). Verified on branch records: e.g. state `a25acad7...` q =
  0.5*0.15384615 + 0.5*0.08826923 = 0.12105769 with `precision_constraint_satisfied=true`
  (no penalty). Two states cross the precision boundary and their deviation value is
  penalty-dominated (see §c).
- Per-state **branch delta**: `delta_q = Q(scan_branch) - Q(verify_branch)`, both branches
  rolled out under the same fixed continuation. This is the quantity stored in
  `STATE_ACTION_BRANCHES.jsonl` and used as the learning target in
  `public_state_predictability_cached_v3` (verified: `predictions.csv` `delta_q` column is
  byte-identical to the branch table values, e.g. 0.007596153846153836 for
  `a06a9cb0...`).
- **Identifiability audit delta**: `delta_original = delta_deviation = Q(alternative
  action) - Q(default 1:1 action)` at each state (confirmed in
  `scripts/run_original_theory_identifiability_audit.py` lines 148-153). The default
  action is the one the fixed 1:1 continuation would take at that state; the alternative
  is the other legal action. This is a *default-referenced* contrast, not the
  symmetrized SCAN-vs-VERIFY contrast (see §b).
- **Offline smooth variant** (`Q_OBJECTIVE_DISCONTINUITY_AUDIT.md`): remove only the `-1`
  penalty, no refitting/relabeling. Classes become 5/4/99; original-vs-smooth delta
  Spearman = 0.899.

Other experiments use **different** objectives (not this Q):

| Experiment | Objective |
|---|---|
| `binary_smdp_value_v1` | Conditioned SMDP state-action value (terminal events + AnytimeAUC) under a beam oracle; distinct contract, executed width ≤16, unsafe admission |
| `psvr_bottleneck_research` | Macro AnytimeAUC / F1 / TTFC under physical deadline (Macro AnytimeAUC 0.04755, 3 unique confirmed events) |
| Guangzhou order (`RESULTS_DEADLINE_SAFE.json`) | Deadline-safe event Recall/F1 at 300 s and AUC over [0,300] under strict completion accounting |
| Physical probes | Local event delta (one-step) or cost-to-utility conversion under fixed-B (continuation) |

## b. "Q(SCAN)-Q(VERIFY)" vs "deviation-from-default regret": same estimand?

**Not the same estimator in orientation/reference, but the same underlying quantity:**
both are one-step conditional action-value differences with the *identical* fixed
continuation (FIXED_SCAN1_VERIFY1, i.e. one forced action then fixed 1:1 to budget).

- `delta_q = Q(scan) - Q(verify)`: a **symmetrized** contrast between the two legal
  actions. It does not reference any default policy. This is what the cached branch
  table (`25/26/57`) and the learning screen (`public_state_predictability`) use.
- `delta_deviation = Q(alternative) - Q(default)`: an **asymmetric, default-referenced**
  contrast. The default is the action the fixed 1:1 schedule takes at that state (derived
  from the behavior-trajectory scan/verify parity). This is what the identifiability
  audit's BENEFICIAL/HARMFUL/INDIFFERENT (5/5/98) uses.
- Relationship (verified exhaustively over all 108 states): `|delta_q| =
  |delta_deviation|` for **every** state; the sign differs on **26/108** states (exactly
  the states where the default action is SCAN and delta != 0, i.e.
  `delta_deviation = -delta_q`). Under the 1:1 alternation, default = VERIFY when
  scan_count > verify_count, else SCAN — this rule reproduces the diagnostic CSV
  **0/108 mismatches**.
- Practical consequence: a state can be "SCAN-better" in the branch table (delta_q > 0)
  yet "HARMFUL" in the audit when SCAN is already the default (deviation toward VERIFY
  would be the harmful move). Example: `4d01d6d4...` delta_q=+0.0123 (SCAN better),
  default=SCAN -> delta_deviation=-0.0123 -> HARMFUL. Conversely `a06a9cb0...`
  delta_q=+0.0076 (SCAN better), default=VERIFY -> BENEFICIAL.
- "Regret" framing: the learning screen's `decision_regret` = per-fold mean over
  held-out states of the expected loss vs the oracle-best action under `delta_q`
  (`expected_metrics` in `experiments/public_state_predictability.py`); always-VERIFY
  regret 0.000885 is the best fixed policy. The identifiability "practical deviation
  value" is the same one-step delta measured against the 1:1 default. Both answer
  "does deviating from a fixed action improve the frozen Q", just anchored differently
  (oracle-best vs schedule-default).

## c. Reconciling 25/26/57 with 5/5/98 — RECONCILED

Same 108 states (state hashes match 1:1 between `STATE_ACTION_BRANCHES.jsonl` and
`Q_OBJECTIVE_STATE_DIAGNOSTIC.csv`; set difference = 0), same frozen Q, same fixed 1:1
continuation. The two number sets differ only along two axes:

1. **Threshold.** Branch table: `|delta| <= 1e-12` -> TIED (exact tie). Diagnostic:
   `|delta| <= 0.005` -> INDIFFERENT (practical delta). Distribution of `delta_q`
   (verified with stdlib): 57 states |delta| <= 1e-12; 51 nonzero; 44 states with
   1e-12 < |delta| <= 0.005 (small but non-zero margins); only **10** states with
   |delta| > 0.005. So 41 of the 51 non-tied states are practically indifferent.
2. **Orientation.** The diagnostic classifies `delta_deviation` (default-referenced),
   not `delta_q`. Re-derivation: applying the practical 0.005 threshold to
   `delta_deviation` reproduces **BENEFICIAL 5 / HARMFUL 5 / INDIFFERENT 98** exactly,
   and matches `original_class` in the diagnostic CSV for all 108 states. Applying the
   same threshold naively to `delta_q` instead gives 3/7/98 — the 6-state difference is
   exactly the states where the better action *is* the default (so the deviation is
   harmful), which is why the audit uses the default-referenced estimand.

The 10 practical states: BENEFICIAL = {a06a9cb0 (+0.0076), cb4cf580 (+0.0344),
56d221f7 (+0.0299), ca56f044 (+0.9986), 24013180 (+1.0408)}; HARMFUL = {d1209c9f
(-0.0303), 4d01d6d4 (-0.0123), 9a884e7d (-0.0288), 70877366 (-0.9858), 94a576c6
(-0.0058)} — all with |delta| > 0.005, all cross-checked against the branch records'
scan/verify counts. The two huge positive states (ca56f044, 24013180) are precision-
penalty crossings and contribute 96.6% of the positive deviation value (2.0394/2.1113,
verified); the smooth (penalty-removed) classes are 5/4/99.

**Conclusion:** 25/26/57 and 5/5/98 measure the same 108 states' same one-step delta_q
under two thresholds (1e-12 vs 0.005) and two orientations (symmetrized vs
default-referenced). No contradiction. Both should be quoted with their threshold and
orientation; the practical, decision-relevant statement is 5/5/98 (only ~9% of states
have |delta| > 0.005), while 25/26/57 describes the raw sign structure of the
clairvoyant ceiling.

## d. Where do the 108 states come from?

- **Behavior policies (4):** CURRENT_TWO_STAGE_RAW (18 states), FIXED_SCAN1_VERIFY1 (27),
  FIXED_SCAN1_VERIFY3 (34), DYNAMIC_ADAPTIVE_K3_VALUE_V3 (29) — all are *prior cached
  policies*, not a randomized/coverage-rich behavior policy.
- **Source videos (2 independent):** `long_video_dataset3` (36 states) and `realcartest`
  (72 states across two segments/domains `realcartest_0_1570`, `realcartest_2000_3200`).
  `STATE_SUPPORT_AUDIT.csv` reports `source_video_count=2` for every archetype row;
  `SAMPLING_VS_PREVALENCE_ANALYSIS.md` and the cached SUMMARY state "only two independent
  source videos across three cached domains".
- **Sampling:** dual-legal states reached by the four behavior policies, deduplicated,
  then **capped at 12 per domain-budget cell by evenly spaced indices** (3 domains x 3
  budgets 20/50/100 = 9 cells x 12 = 108). **Not population-weighted**: `SAMPLING_VS_PREVALENCE
  = NOT_IDENTIFIABLE` — "not a probability sample from a true online cheap-sensing
  process"; rare high-regret visitation cannot be distinguished from coverage gaps.
  Natural prevalence cannot be inferred; the minimum evidence would be prospective
  endogenous SCAN logging with randomized/coverage-rich behavior on independent videos.

## e. Continuations: cached 108-state branches vs physical probes

- **108-state cached branches:** continuation = `FIXED_SCAN1_VERIFY1` for all 108
  records (verified `continuation_policy` counter = 108), i.e. one forced action
  (SCAN or VERIFY) then fixed 1:1 interleaving to budget, with **abstract costs**
  (scan=0.1, verify=1.0), cached maps/reference, 1 rollout, no deadline. Per
  `INTENDED_VS_ACTUAL_CONTRACT.csv` row 14: "one forced action then fixed 1:1 to
  budget ... valid one-step estimand, not adaptive closed loop". It is a
  **clairvoyant cached ceiling** (both branches simulated with oracle access); the H0
  audit classifies it `CLAIRVOYANT_DIAGNOSTIC_CEILING_ONLY` and
  `FAIL_CURRENT_H0_APPLICABILITY` as a Guangzhou exact-state registry.
- **Physical probes (0/18, 1/7):** from `counterfactual_probe_v1` (18 one-step
  alternatives over 12 label-blind B states; verdicts: 0 STRONG_LOCAL_POSITIVE, 7
  POTENTIAL_FUTURE_HEADROOM/cost-only, 2 NEUTRAL, 9 WORSE) and
  `counterfactual_continuation_v1` (7 paired continuations: 1 CONVERTED_HEADROOM, 4
  DISSIPATED, 2 WORSE, rate 1/7). Their continuation per contract is
  "**temporal-bisection fixed SCAN1:VERIFY1**" with max 6 additional completed actions /
  60 physical seconds, start-before-deadline admission, measured physical costs,
  Qwen3-VL-8B verifier.
- **Are they the same?** Same *1:1 fixed SCAN:VERIFY interleaving family* (operator
  ratio 1:1, fixed schedule after the deviation), but **not identical**: the cached
  table uses chronological FIXED_SCAN1_VERIFY1 to budget with abstract costs and a
  clairvoyant cached reference; the probes use the temporal-bisection order (B's
  schedule), a bounded horizon (<=6 actions / 60 s), measured physical cost, and the
  real verifier. Both share the "deviate one step, then fixed continuation" design,
  which is why the cached 5/5/98 headroom and the physical 0/18+1/7 agree in direction
  (headroom is rare) without being the same measurement.

## f. Evidence classes (A-E) and scope

No project-standard A-E evidence-class vocabulary exists in the repo (verified by grep);
this is an audit-local scheme, defined operationally and applied in
`CONTROLLER_ESTIMAND_MAP.csv`:

- **A** = frozen direct result artifact with hashes, valid for its exact declared scope.
- **B** = cached/abstract-cost deterministic replay over frozen inputs (reproducible, but
  reduced fidelity: abstract costs, cached oracle, sampled states).
- **C** = static stdlib re-derivation/audit over frozen artifacts (this audit).
- **D** = exploratory physical probe or single-source exploratory run (selected states,
  label-blind, hash-stamped; high internal validity, narrow scope).
- **E** = non-authorizing diagnostic / ceiling / insufficient-evidence decision (oracle
  upper bound, unsafe or incomplete SMDP, terminal no-go).

| Experiment | Class | Scope statement |
|---|---|---|
| controller_dynamic_headroom_cached_v1 (+ reproduction) | B | Headroom ceiling over 108 cached states; abstract costs; not physical/confirmatory; gate passed only as cached headroom |
| original_theory_identifiability_audit_v1 | C | Read-only re-derivation; sets C-B and C-K to NOT ESTABLISHED; does not replace frozen Q |
| public_state_predictability_cached_v3 | B | LOVO screen over 2 sources; learned selection worse than always-VERIFY; gate FAILED; predictive ≠ closed-loop |
| binary_smdp_value_v1 | E | INSUFFICIENT_EVIDENCE / NOT_AUTHORIZED; unsafe deadline admission; not cross-video |
| psvr_bottleneck_research | E | COMPLETE_NO_GO; all controller signals ABSENT; physical safety PASS; two-video search terminal |
| exploratory_temporal_order_guangzhou_v1 | D | Single-source exploratory order signal; B repeatable same-source; supports fixed bisection executor, not adaptation |
| counterfactual_probe_v1 | D | 0/18 immediate positives; selected subset, not a logged-bandit dataset |
| counterfactual_continuation_v1 | D | 1/7 conversion under fixed-B; sole conversion is coverage-before-negative-verification, not a learnable rule |

Cross-cutting scope facts (from `PROJECT_STATE_OF_TRUTH.md`, `FINAL_IDENTIFIABILITY_REPORT.md`):
SCAN is a dictionary lookup of precomputed proxy rows (0/108 new raw observations, 0/108
online proxy computations, 0/108 new candidate identities, 108/108 precomputed releases,
108/108 future-legal-VERIFY expansions); costs are abstract; reference is model-relative
(pseudo-reference / strict K3), human-valid utility absent; state prevalence not natural.
MAB/RL/controller work is therefore NO-GO on the current substrate per the frozen
decision (`MAB_RESEARCH_DIRECTION_DECISION.md`: DO_NOT_DO_MAB).

## Unresolved / caveats

- The learning screen's exact per-fold aggregation was recovered by re-derivation from
  `predictions.csv` + `experiments/public_state_predictability.py` (macro = mean of the
  two LOVO-fold metrics; all SUMMARY values reproduced to ~1e-11). No discrepancy.
- `delta_deviation` default-action rule (VERIFY if scan_count>verify_count else SCAN)
  was inferred and verified 108/108 against the diagnostic CSV; the original
  `default_action` column lives in `selective_deviation_predictability_v1/` (older
  artifact, not re-read here beyond the identifiability script's usage).
- The 1/7 continuation "actions_completed=7" counts the parent action + 6 additional
  completed actions under the contract's max_additional_completed_actions=6.
