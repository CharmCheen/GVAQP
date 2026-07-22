# Stage-A execution difference audit

## Conclusion

The physical run itself is exact and independently reproducible: 96 STARTED attempts, 96 durable accepted calls, zero uncertain calls, 96 raw artifacts, 96 parsed artifacts, 96 call rows, 192 query-projected label rows, and zero parse failures. The frozen completion marker binds every artifact.

The frozen verifier nevertheless remains failed. Its default pandas CSV parse rounds call 001's textual runtime `19.338814230635762` to `19.33881423063576`, then compares that value bit-for-bit with the raw JSON float. Python's round-trip `float()` conversion of the same CSV text equals the raw value. No frozen evidence was edited to make the check pass.

## Independent resolution

The first independent reporter reconciled identities, universe counts, completion-marker bindings, cost, hashes, and held-out gates, but it did not itself rerun raw parsing/projection/K3 construction. It is retained as a partial reconciliation with audit hash `2fe6caea6b86f8c688a9b86c8e76306b8eb065cb762a313e5c74c49f8df892eb`.

The full resolution is recorded separately in `STAGE_A_ORACLE_ROUNDTRIP_VERIFICATION_AUDIT.json`: a source-hash-bound wrapper runs the unchanged frozen verifier with only its module-local pandas `read_csv` default set to `float_precision="round_trip"`. That original full verification path recomputes raw parsing, projections, manifests, K3 groups, support, cost, and completion and must return `VERIFIED_COMPLETE_COMMIT`.

The frozen runner also omitted the writer for a cost artifact that it requires during finalization. An independent, pre-finalization cost builder reconstructed it only from immutable preparation, model-validation, inference-receipt, attempt-log, and raw-envelope evidence. The completion marker now binds that artifact at SHA-256 `60ae9bc2453312c388b8fac7004fb4770be223daa5f781f471d4b08c31846760`.

## Decision

Record `PASS_WITH_RECORDED_FROZEN_VERIFIER_DEFECT`, not an unqualified runner-verify pass. Continue the required dataset and grouped-model phases because they consume the independently verified immutable manifests. Do not run V0/V1, and do not treat the oracle support decision as evidence that a learned representation is ready for a physical pilot.
