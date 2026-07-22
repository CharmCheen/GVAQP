# R2 split isolation

Fixtures use a public static sublibrary. Development uses only the retained
development seed file and exposes opaque development ids. Confirmatory seeds are
not materialized until the one-shot runner starts an attempt ledger. The
confirmatory generator is in a separate module imported only by that runner;
tests and development code must not import it. Legacy held-out path/hash/ids
raise `ContaminatedHeldoutUniverseError`.
