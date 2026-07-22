# Contamination disposition

The old concrete held-out universe at
`outputs/psvr_rollout_preimplementation/TOY_HELDOUT_SEEDS.json` is retained
unchanged as audit evidence. It was directly read by
`tests/psvr_rollout_toy/test_unfrozen_invariants.py::test_seed_lists_are_frozen_and_disjoint`.

Its confirmatory status is permanently invalid. It may only be used as audit
evidence, a non-confirmatory regression/adversarial fixture, or non-confirmatory
debugging evidence. It must never be used for H-ROLLOUT1A-R1, any future
confirmatory comparison, a primary-paper held-out result, or model/policy
selection. It must not be renamed or rematerialized as a new confirmatory split.

No replacement confirmatory seeds were generated in this R1 assessment.
