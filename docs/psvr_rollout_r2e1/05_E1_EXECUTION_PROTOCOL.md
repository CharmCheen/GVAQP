# E1 execution protocol

The coordinator first verifies R2 and E1 freeze hashes and that the legacy
contaminated universe remains unchanged. An explicit guarded command creates
the sealed universe exactly once, then prepopulates every episode × frozen
method identity. It executes only uncommitted identities, writes raw traces by
atomic rename, appends ledger transitions, derives export tables, invokes the
independent verifier, and emits the frozen Gate/decision branch.

There is no default all-splits mode and no development/held-out mixing. E1
development validation uses a disposable temporary directory and a fixed
fixture identity, never an E1 confirmatory attempt root.
