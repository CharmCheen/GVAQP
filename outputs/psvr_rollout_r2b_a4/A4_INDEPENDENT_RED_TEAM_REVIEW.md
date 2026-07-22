# Independent A4 blind red-team review — initial report

Verdict: `FAIL — A4 is not freezeable and IC1 must not resume development execution.`

I inspected BASE/A1/A2/A3, current A4 docs/artifacts, `a4.py`, IC1 integration, verifier, and A4 tests. This review did not rely on the prior ambiguity proof as a checklist.

Positive findings:

- `a4.py` now uses typed JSON hashing internally, avoiding the earlier delimiter collision in the source implementation.
- Candidate iteration, action ranks, and SCAN state-dependent maximum are now explicitly computed in source.
- SCAN grouping is now sequential within a scan rather than the earlier batch-local stale-frontier behavior.
- The approximate A4 module does not import the exact evaluator or `R2Environment`.

Those repairs do not remove the blockers below.

| ID | Severity | Finding | Direct evidence | Gate impact |
|---|---|---|---|---|
| RT-A4-01 | Critical | The frozen keyed-realization specification, A4 counterexample artifact, and implementation define different random experiments. | [03_KEYED_PROBABILITY_REALIZATION.md] declares pipe-delimited bytes; `A4_KEYED_REALIZATION_SPEC.json` says the same. `a4.py:38-44` instead hashes canonical JSON bytes. For A4 key `("H1B_A4","development-0000",1,0,2,"confirm_outcome","CONFIRM|h00_0|w00_0")` and `p=.3833333333`, pipe encoding gives `U=.0022878357` and `True`; source JSON gives `U=.6088243547` and `False`. `A4_COUNTEREXAMPLE_RESOLUTION.json` records the former U and `true`, so its claimed A4 outcome disagrees with the code. | Blocks keyed realization, counterexample resolution, replay, and canonical serialization. |
| RT-A4-02 | Critical | Current grouping implementation changes the A2-frozen target/draw semantics instead of merely supplying the missing post-state semantics. | A2 § target registry requires one draw for every same-hypothesis unordered pair: `GROUP|h|min(wi,wj)|max(wi,wj)`, lexical pair rank. `a4.py:315-324` substitutes one self-pair per emitted witness, `GROUP|h|w|w`, with witness rank. No A4 document specifies a deterministic mapping from A2 pair outcomes to the new three-category per-witness transition. This changes independent-variance signs and keyed draws, not just a post-state representation. | `BLOCKED_SCIENTIFIC_CONFLICT` unless a result-blind, hierarchy-respecting mapping is specified. |
| RT-A4-03 | Critical | The required complete grouping/hypothesis post-state is not implemented or frozen. | `A4BranchState` (`a4.py:153-172`) stores only a flat witness list. It has no hypothesis objects or canonical `ordered_witness_ids`, `verified_witness_ids`, `pending_witness_ids`, `resolved`, `suppressed`, or committed-ref state required by the A4 schema. CONFIRM merely deletes matching flat members (`a4.py:376`), with no resolved/suppressed state or specified related-hypothesis suppression rule. | Blocks grouping post-state uniqueness and replay of future legal actions/utility. |
| RT-A4-04 | Critical | A modeled “novel” duplicate can produce `NEW_COMMIT` utility without materializing a distinct new token. | At `a4.py:364-371`, when an already committed latent event receives `novel=True`, the code re-adds the same `event` to a set, sets `committed=True`, and reports `NEW_COMMIT`. The set/post-state is unchanged but rollout adds D1 reward. A2 defines novelty as mapping to a new token; no deterministic synthetic-token transition/ID exists. | Allows incompatible committed sets, duplicate classification, and utility under the same semantic transition. |
| RT-A4-05 | High | Historical grouping ordering is not reconstructible correctly. | `_hydrate_history` assigns every historical emitted witness `created_at=self.state.elapsed` (`a4.py:205-215`), i.e. the current time rather than that SCAN’s completion time. The frozen grouping rule selects the first hypothesis by `(created_at, hypothesis_id)`. A correct replay and the current implementation can therefore choose different `H_same`/`H_diff` targets. Past planning times are also not represented per historical action. | Blocks grouping ordering and deterministic replay after nonempty history. |
| RT-A4-06 | High | Baseline–perturbed shared-uniform coupling is documented but not operationally generated or auditable. | `a4.py` computes only `P_error` outcomes. It never realizes/stores `Y0=F^-1_{P0}(U)` alongside `Y_error`; `IC1PairedModel._incremental_return` consumes only perturbed rollout value (`ic1.py:172-175`). The coupling test only asserts two manual inequalities, not kernel-level paired outcomes. | Coupling claim is unproven; baseline/perturbed semantic divergence remains possible. |
| RT-A4-07 | High | Canonical transition records are incomplete, and IC1 discards them. | Required records must bind pre-state, draw keys, probabilities, outcomes, and post-state. Current draw rows omit the complete A4 key, canonical transition index, A1 sign key/sign, and several baseline/transformed values; duration rows contain no transform metadata (`a4.py:302`, `354`). Then IC1 explicitly discards all records (`ic1.py:172-175`). | Blocks lossless evidence and independent recomputation of approximate Q/LCB. |
| RT-A4-08 | High | The branch-transition-index mapping is source-only and not frozen in A4 artifacts. | `a4.py:228-236` uses `action_ordinal*10_000_000 + family_ordinal*1_000_000 + entity_ordinal`. Neither keyed-realization document nor JSON registry specifies this formula, bounds, action ordinal semantics, or how it relates across paired branches. | Two otherwise compliant implementations can derive different U for the same variable. |
| RT-A4-09 | High | A4’s written operator order conflicts with its written transition schedule and source behavior. | Operator-order documentation/JSON says `candidate_yield → grouping → … → duration` and says JOINT transforms finish before realization. Transition schedule says duration first. Source realizes duration first and then realizes candidate/grouping draws (`a4.py:291-341`). | Operator/order and JOINT semantics are not uniquely frozen. |
| RT-A4-10 | High | The claimed independent IC1 verifier is still circular. | `scripts/verify_psvr_rollout_h1b_ic1_development.py` imports production `execute_full_horizon`, `identity_hash`, `ContinuationReturnCache`, and `ExactReferenceEvaluator` (`lines 7-9`) and treats rerunning them as independent verification (`lines 36-41`). Shared A4, SMDP, evidence, and exact-reference defects reproduce identically. | Blocks IC1 independent verification and Gate condition G. |
| RT-A4-11 | Medium | Static leakage audit is inadequate for the claimed boundary. | It checks only source-string import absence. Yet `A4BranchState.canonical()` serializes `latent_event_id` (`a4.py:165-169`). The production planner currently discards records, so this is not proven active policy leakage; however the audit does not establish that latent values cannot reach a policy/evidence consumer. | Information-boundary PASS is unsupported. |
| RT-A4-12 | Medium | Required A4 grouping fixtures are absent. | `test_h1b_a4.py` has only six shallow tests. It does not test CORRECT attach/create, UNDER_MERGE with `H_same`, OVER_MERGE attach/fallback, canonical frontier ordering, over-merge opportunity loss, under-merge duplicate path, suppression, historical hydration, source/artifact serialization agreement, or full transition replay. | The fixture PASS artifact is materially overclaimed. |

Main competing explanation considered: A4 may be intended to supersede A2’s pair-level grouping target with a new per-witness categorical target. That is not supported by the stated hierarchy or A4’s limited authority: A2 explicitly froze grouping target identities/draw indexes, while A4 is authorized to supply previously undefined generative/post-state semantics without changing frozen scientific fields. A valid repair needs an explicit, result-blind composition from the A2 pair-level draws to A4’s grouping outcome, or a clearly authorized scientific-conflict disposition.

Recommended disposition:

```text
H1B_A4_GENERATIVE_TRANSITION_SEMANTICS = FAIL
H1B_DEVELOPMENT_GATE = BLOCKED_SCIENTIFIC_CONFLICT
```

Minimum repair sequence:

1. Select one key serialization, bind exact bytes and transition-index formula in docs/JSON/source, then regenerate the counterexample artifact and fixtures.
2. Reconcile A2’s pair-level grouping registry with a deterministic A4 grouping-state transition; do not silently replace its target keys.
3. Implement canonical hypothesis state, completion/suppression rules, deterministic new-token materialization, and history hydration timestamps.
4. Emit lossless transition records including full keys/signs/probabilities and retain compact commitments sufficient for independent Q/LCB replay.
5. Replace the circular verifier with an independently implemented replay/evaluator path.
6. Re-run a genuinely complete A4 fixture suite and a new blind review before any development execution.

## Repair status

This original report is immutable historical review evidence. Its findings RT-A4-01 through RT-A4-05 and RT-A4-08/09 were repaired after the review and require fresh independent reassessment. RT-A4-06/07/10/12 remain active until individually verified closed.
