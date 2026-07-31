# Post-failure recovery draft audit

Status: `REVISE_BEFORE_BUILD_OR_RESEAL`.

An uncommitted main-repository draft proposes a fresh output root, a 35-second
per-call reservation, and a 29 A100-hour envelope. Its arithmetic is internally
plausible: the all-operation hard bound is 28.743889 A100-hours, leaving
0.256111 hours below the proposed envelope; adding the failed run's 1.428403
hours remains below the broader 64-hour authorization. The draft also forbids
reusing the 136 partial labels and starts again at unit zero.

However, direct source audit found the following release blockers.

1. `oracle_v3_full_grid_dry_run.py` still constructs coordinators with the old
   23.579961-second call reservation and 19.4-hour envelope. Therefore the
   complete mock and fault suite do not exercise the proposed contract.
2. Existing supervisor/control tests likewise hard-code the old values. All
   150 focused tests pass, but no test references
   `FULL_GRID_CALL_RESERVATION_DERIVATION` or the new prior-failure binding.
   The green suite is not coverage evidence for the revision.
3. The physical analyzer and finalizer still reject actual usage above 19.4
   hours, while admission permits up to 29.0. Runner, analyzer, finalizer,
   preregistration, and approval thus do not share one cost contract.
4. Documentation requires a fresh execution ID, but the bound
   `EXPERIMENT_ID` remains `AEQ_MODEL_RELATIVE_ORACLE_V3_FULL_GRID`. A new
   directory and seal distinguish files, but the formal lineage identifier is
   not new as claimed.
5. The authorization assertion checks only `new envelope < 64`; it does not
   bind `prior actual cost + new envelope <= cumulative authorization`.
   Current numbers happen to fit, but the invariant is absent.
6. The cost regression uses tokenizer re-encoding of decoded raw response text,
   not the actual generated-token count. Re-encoding is a proxy because decode
   and encode need not preserve token cardinality. The derivation must validate
   this measurement or conservatively account for its error.
7. Runtime-tail calibration uses outputs from the same frozen evaluation
   videos after a formal failure. This may be acceptable for safety diagnosis,
   but it is post-outcome adaptation. The new preregistration and independent
   review must explicitly decide whether the resulting run remains
   confirmatory, and must not conceal this as independent calibration.

No package was built, no seal was generated, no model was loaded, and none of
the user-owned draft files were modified by this audit.

Minimum repair gate: parameterize one cost contract across runner, dry-run,
tests, analyzer, finalizer, seal and approval; add derivation/failure-binding
tests; bind cumulative authorization and a genuinely new execution identity;
then run the complete no-inference mock and independent adversarial review.
Only an exact new approval may authorize physical execution.
