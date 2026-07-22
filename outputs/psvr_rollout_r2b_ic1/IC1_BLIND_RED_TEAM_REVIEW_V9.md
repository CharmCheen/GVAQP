# Blind red-team review — v9

**Verdict: FAIL — H1B development evidence is unsuitable to support a future confirmatory protocol.**

The review found critical defects: planning time is omitted from primary D1 utility and approximate/exact values; model-error axes are not implemented as generative transitions; the verifier reuses production execution; post-planning safety is incomplete; evaluator ordering is not commit-first; the expected development universe is partly code-derived; source closure is incomplete; and v9 lacks a reconciled resource report. v9 remains `DEBUG_ONLY_NONCONFIRMATORY` and `INVALID_FOR_H1B_DEVELOPMENT_GATE`.

## Raw reviewer findings

| ID | Severity | Finding | Gate blocker |
|---|---|---|---:|
| RT-01 | Critical | Planning time changes `_elapsed` but is absent from D1 utility/timeline. | Yes |
| RT-02 | Critical | Approximate Q estimates omit post-planning elapsed time. | Yes |
| RT-03 | Critical | Error mechanisms are payoff adjustments, not generative transitions; base is unperturbed. | Yes |
| RT-04 | High | Joint-corner semantics omit common JOINT sign. | Yes |
| RT-05 | Critical | Verifier re-runs production execution rather than independently recomputing. | Yes |
| RT-06 | High | Existing verifier/final reports are stale or prior-attempt artifacts. | Yes |
| RT-07 | High | Post-planning action safety minima are all zero. | Yes |
| RT-08 | High | Exact sidecar runs before action is durably committed. | Yes |
| RT-09 | High | Six IC1 development rows are code-added rather than committed in the coverage artifact. | Yes |
| RT-10 | High | Source/dependency freeze closure is incomplete. | Yes |
| RT-11 | High | Reconciled v9 resource report is absent. | Yes |

## Original complete report

Overall verdict: `FAIL — H1B development evidence is unsuitable to support a future confirmatory protocol.` I found multiple independent blocking defects. The strongest is not a documentation issue: planning time is omitted from the primary D1 utility and from the approximate/exact action values.

Observed positive evidence:

- v9 has 570 latest ledger identities, all `COMMITTED`, with 570 compact traces and 570 sidecars.
- All v9 traces are multi-step: 22–30 decisions; zero are one-action traces.
- The current 14 local H1B tests pass, but they do not exercise the defects below.

| ID | Severity | Finding | Evidence | Blocks H1B development gate? |
|---|---|---|---|---|
| RT-01 | Critical | Planning time changes `_elapsed` but is absent from the time-weighted D1 utility. | `ic1.py:262-273` applies planning time via `env._elapsed += ...`; `r2.py:235-242` computes utility solely from action-observation durations. In v9 trace `00ad…90b`, three commits have stored utility 4675, while summing \(1600-\) actual elapsed time including prior planning yields 4015. Across v9, 408/570 traces disagree; aggregate overstatement 236,502 utility ticks, max 2,300. | Yes |
| RT-02 | Critical | Approximate rollout Q estimates also omit post-planning elapsed time. | The planner passes a post-planning state to `IC1PairedModel`, but `_return(world, action)` at `ic1.py:140-154` replays only visible history and never applies `state.remaining_ticks` / elapsed gap. It calls the same planning-unaware `env.utility()`. Thus planning affects threshold and feasibility but not simulated return. | Yes |
| RT-03 | Critical | The six frozen model-error mechanisms are not implemented as generative transitions; the baseline half of each paired comparison is unperturbed. | A2 requires candidate retention, confirm positivity, novelty, grouping, duration, and materialization transforms in planner’s generative model. `ic1.py:156-176` instead adds a fixed post-hoc payoff adjustment: probability perturbation around `0.5` × 200, duration perturbation hard-coded 100. It never modifies candidates, observations, grouping, duration, tokens, continuation dynamics. `paired_returns`/`paired_summary` perturb only action_values (`:190-193`, `:207-209`); base_values remain true-model. | Yes |
| RT-04 | High | Joint-corner error semantics do not use mandated common `k=JOINT` sign. | A1 requires a single common JOINT sign across mechanisms. `ic1.py:160-175` loops mechanisms each with own `ErrorContext`, retains own mechanism names and ordinary form. | Yes |
| RT-05 | Critical | “Independent verifier” is circular and does not independently recompute required quantities. | verifier imports and re-runs production `execute_full_horizon`, `ExactReferenceEvaluator`, `identity_hash`; shared bug reproduces. It does not reconstruct expected universe coverage, recompute D1, LCB/sample arrays, planning time, fallback, overrides, source closure independently. | Yes |
| RT-06 | High | Recorded verifier PASS stale/prior attempt claim. Existing outputs before v9. | Yes |
| RT-07 | High | Postplanning legal action safety not encoded in policy state. `ic1.py:91-95` all `minimum_remaining_ticks=0`; actual R2 requires SCAN 703/CONFIRM138. | Yes |
| RT-08 | High | Exact sidecar ordering violates: sidecar runs after selection but before actual action is durable. Sidecar error aborts pre-commit. | Yes |
| RT-09 | High | Expected v9 universe not reconstructible from declared coverage: frozen coverage 13 rows/390; runner silently adds six rows. | Yes |
| RT-10 | High | source/dependency closure incomplete: source hashes omit approximate_rollout, errors, posterior sampling, CRN, planning/fallback/utility/R2 kernel etc. | Yes |
| RT-11 | High | resource evidence stale before v9 (now v9 raw sample exists but no reconcile profile). | Yes |

Main alternative considered: planning cost might only be threshold+feasibility. A1 explicitly says same-horizon SMDP and primary metric “net D1 after SMDP planning time”; trace demonstrates contradiction.

Recommended disposition: preserve v9 as DEBUG_ONLY_NONCONFIRMATORY and set current gate BLOCKED_EXECUTION_INTEGRITY (also resource unresolved). Do not use v9 agreement/regret/utility/resource/error summaries for confirmatory authorization.
