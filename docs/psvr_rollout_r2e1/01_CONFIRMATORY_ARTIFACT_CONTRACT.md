# Artifact contract

The immutable raw layer is `CONFIRMATORY_SEED_COMMITMENT.json`, the private
`sealed_seed_manifest.json`, `CONFIRMATORY_SEALED_UNIVERSE_MANIFEST.json`, the
append-only ledger, episode manifest, per-method raw JSON traces, execution
failure table, independent-verification record, and completion marker. Each
trace carries public identity, visible observations, evaluator-private truth
tokens/regime labels, source/config hashes, and a ledger-bound SHA-256.

The task/regime/paired tables and coordinator metric recomputation are published
inside one `CONFIRMATORY_DERIVED_BUNDLE` directory by atomic directory rename.
Independent verification, Gate output and decision branch are likewise
published as one atomic `CONFIRMATORY_DECISION_BUNDLE`. Reports are derived
products. They never substitute for raw trace evidence. A committed raw path
and published bundle are immutable; all writes stage then atomically rename.
