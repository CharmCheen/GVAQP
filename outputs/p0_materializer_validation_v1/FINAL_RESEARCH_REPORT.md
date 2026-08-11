# P0 Materializer Validation Report

# 1. Executive Decision

`MATERIALIZATION_MAINLINE_DECISION = PAUSED_INPUT_REQUIRED`.

The repository contains three independent V3 source videos, but no released
complete V3 model-relative reference package. Running a selector × materializer
matrix from partial fail-stop raw labels would violate the V3 publication policy
and could turn incomplete execution into pseudo-ground truth.

# 2. Experimental Contract

No quality experiment was run. `RUN_MANIFEST.json`, `VIDEO_INVENTORY.csv`,
`REFERENCE_PROVENANCE.csv`, and `EXPERIMENT_PROTOCOL.json` freeze the observed
repository state and the exact input gate. Budget semantics for the future
matrix are `QUERY_BUDGET`, not wall-clock deadline.

# 3. Controlled Matrix

Not executed: 0 valid controlled pairs. K0 was intentionally not implemented,
because no released V3 common trace/reference exists against which to enforce
same-trace identity.

# 4–9. Effects, Diagnostics, Generalization, Failure Cases

Not computed. The only finding is an input-evidence failure, not a negative
finding about K3.

# 10. Provenance / Leakage

`UNKNOWN_PROVENANCE` for a released main-evaluation reference because none was
found. The latest V3 protocol states that partial formal references are
forbidden; this report follows that constraint.

# 11. Historical Bridge

Not executed. Historical Stage-0 traces cannot establish the current V3
multi-video claim without a released V3 reference/evaluator binding.

# 12. Deadline Interpretation

No deadline experiment ran. The blocking condition is reference completeness,
not compute timing.

# 13. Paper Claim Allowed

No new materialization claim is supported by this P0 run.

# 14. Paper Claim NOT Allowed

Do not claim current-V3, cross-video, selector-robust materialization benefit.

# 15. Next Research Action

Complete or provide the frozen V3 full-grid reference package, then run the
same-trace K0/K3 controlled matrix without changing the protocol.
