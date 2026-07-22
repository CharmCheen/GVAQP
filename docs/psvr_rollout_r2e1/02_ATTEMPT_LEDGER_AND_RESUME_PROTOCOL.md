# Ledger and resume

Ledger is append-only JSONL and records public identity, sealed-seed hash,
method, state, attempt ordinal, timestamp, trace path/hash, failure class, and
recovery status. Valid transitions are PREPARED → STARTED → COMMITTED, or
PREPARED/FAILED_INFRASTRUCTURE → RECOVERY_STARTED → RECOVERY_COMMITTED.

COMMITTED paths are immutable. A STARTED or infrastructure-failed identity is
recoverable only with the same sealed identity and frozen hashes, recorded as a
new recovery transition. No seed substitution, selective rerun, or overwrite is
permitted. Deterministic failure remains a terminal recorded outcome; hash
mismatch invalidates the attempt rather than permitting a silent rerun.
