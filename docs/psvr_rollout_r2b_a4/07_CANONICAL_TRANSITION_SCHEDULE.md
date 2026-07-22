# A4 canonical transition schedule

SCAN realizes duration, candidate yield, witness ordering, grouping, coverage,
and then atomically writes its observation. CONFIRM realizes duration, Oracle
outcome, then (only if positive) novelty and materialization, updates commit
and frontier state, and atomically writes its observation. Canonical records
use sorted object keys, stable list order, IEEE-754 JSON numbers, lower-case
hex SHA-256 IDs, and explicit JSON `null`.
