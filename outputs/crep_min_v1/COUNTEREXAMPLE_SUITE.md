# CREP-Min v1 — Minimal Counterexample Suite (C1-C8)

Each witness: two worlds agreeing on the observable log L, differing only in the hidden component; the policy ranking flips -> the claim is NOT identifiable from L.

## C1 [ACTION_SUPPORT] unlogged action outcomes
- shared log: `{"recorded_actions": ["A1", "A3", "A5"], "outcomes_of_recorded": [1, 1, 1]}`
- W1: `{"hidden": "B_unlogged_outcomes", "B_actions_unlogged_outcome": [1, 1, 1], "V_pi_A": 3, "V_pi_B": 4}` -> V(pi_A)=3 < V(pi_B)=4
- W2: `{"hidden": "B_unlogged_outcomes", "B_actions_unlogged_outcome": [0, 0, 0], "V_pi_A": 3, "V_pi_B": 0}` -> V(pi_A)=3 > V(pi_B)=0
- real-world instance: MAB gate: physical probes (0/18) had no logged propensities; branch outcomes for non-selected actions unlogged in behavior logs

## C2 [CANDIDATE_CREATION] same SCAN -> different candidate sets
- shared log: `{"scan_observations": [{"t": 0, "obs": "X"}, {"t": 1, "obs": "X"}]}`
- W1: `{"candidates_created": ["c1"], "outcome(c1)": 1, "V_pi_A_verifies_c1": 1, "V_pi_B_verifies_c2": 0}` -> pi_A wins (1>0)
- W2: `{"candidates_created": ["c2"], "outcome(c1)": null, "V_pi_A_verifies_c1": 0, "V_pi_B_verifies_c2": 1}` -> pi_B wins (1>0)
- real-world instance: endogenous SCAN never instantiated locally (P4 NOT_STARTED); fixed-candidate replay cannot certify any endogenous candidate-creation claim

## C3 [LEGAL_ACTION_TRANSITION] VERIFY legal in one world, illegal in another
- shared log: `{"actions": [["step0", "SCAN(r)"], ["step1", "SCAN(r)"]]}`
- W1: `{"c_legal_at_step2": true, "outcome(c)": 1, "V_pi_A": 2, "V_pi_B": 1}` -> pi_A wins (2>1)
- W2: `{"c_legal_at_step2": false, "outcome(c)": null, "V_pi_A": 1, "V_pi_B": 2}` -> pi_B wins (2>1)
- real-world instance: INTENDED_VS_ACTUAL_CONTRACT: VERIFY legality gated on scanned-only exposure is emulated, not endogenously created

## C4 [COMPLETION_CLOCK] identical outcome, completion before/after deadline
- shared log: `{"actions": [{"a": "VERIFY(x)", "start": 290.0, "duration_observed": "?"}], "deadline": 300.0}`
- W1: `{"finish": 298.0, "included": true, "V_pi_A": 1, "V_pi_B": 0}` -> pi_A wins (1>0)
- W2: `{"finish": 308.0, "included": false, "V_pi_A": 0, "V_pi_B": 1}` -> pi_B wins (1>0)
- real-world instance: Guangzhou: B's event at 224.68s counts; C's at 308.77s excluded -> A/C zero deadline utility

## C5 [INFORMATION_FLOW] cache peek unobservable from log
- shared log: `{"actions": ["q1", "q2", "q3"], "verified_outcomes": [0, 1, 0]}`
- W1: `{"sandbox": true, "peeked_unqueried": false, "V_pi_A": 2, "V_pi_B": 2}` -> tie (2=2)
- W2: `{"sandbox": false, "peeked_unqueried": true, "V_pi_A": 4, "V_pi_B": 2}` -> leaked pi_A wins (4>2)
- real-world instance: partial_scan_pilot: POLICY_INFORMATION_ISOLATION = FAIL (policy code could read evaluator state) -> benchmark BLOCKED

## C6 [HIDDEN_GROUPING_TRANSITION] same outcomes, different EventRelation
- shared log: `{"unit_outcomes": [["u1", "relevant", 0, 10], ["u2", "relevant", 15, 25], ["u3", "relevant", 30, 40]]}`
- W1: `{"materializer": "C1_gap10", "events": [[0, 10], [15, 40]], "V_pi_A": 1, "V_pi_B": 0}` -> pi_A wins (1>0)
- W2: `{"materializer": "gap20", "events": [[0, 40]], "V_pi_A": 0, "V_pi_B": 1}` -> pi_B wins (1>0)
- real-world instance: ERAEA E4GAP: relation_greedy - top_proxy = 0.0001 (gap5) vs 0.0016 (gap10/15) vs 0.0014 (gap20)

## C7 [VERSION] identical trace, different materializer -> ranking reversal
- shared log: `{"trace": ["q1..qN"], "outcomes": "identical"}`
- W1: `{"evaluator": "C1", "V_pi_A": 0.1455, "V_pi_B": 0.1406}` -> pi_A > pi_B
- W2: `{"evaluator": "K0", "V_pi_A": 0.0345, "V_pi_B": 0.0345}` -> tie (K0 collapses)
- real-world instance: ERAEA E4: reversal_rate_across_materializers = 0.2222; K0 mean AUC 0.0396 vs C1 0.1618

## C8 [FUTURE_IDENTITY_LEAKAGE] candidate identity encodes future truth
- shared log: `{"candidate_ids": ["c0", "c1", "c2", "c3"], "actions": ["c1", "c3"]}`
- W1: `{"id_encodes_outcome": false, "V_pi_A": 1, "V_pi_B": 1}` -> tie (1=1)
- W2: `{"id_encodes_outcome": true, "V_pi_A": 2, "V_pi_B": 1}` -> leaked pi_A wins (2>1)
- real-world instance: candidate_order in frozen tables is chronological; no outcome-encoded ids observed locally (guard for future endogenous substrates)

## Checker result: 0 errors