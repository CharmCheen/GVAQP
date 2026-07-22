# Audit authority

This audit is read-only with respect to R2/E1 assets. Its primary evidence is the 4,608 immutable raw JSON traces, their ledger SHA-256 bindings, the sealed seed commitment, and frozen manifests. Derived reports were not used as numerical truth.

- R2 freeze: `f5ebab418a5bbae2ef98aedb514307578fd1cdf268543bf5626224853481bdc4`
- E1 freeze: `2d52ddabeeeb4c2bbd1131cfcf9e87d3eeecc65e64418383c8c6ddbbfeead35b`
- preregistration: `a6364084bb6dd14022b81ae241d56a06a2dea18771f411b0f7607ec967f24004`
- Raw identity universe: 4608 traces = 512 episodes × 9 methods.

The independent reference implementation is `run_r2_evidence_audit.py`; it imports no project metric, verifier, coordinator, or aggregation function.
