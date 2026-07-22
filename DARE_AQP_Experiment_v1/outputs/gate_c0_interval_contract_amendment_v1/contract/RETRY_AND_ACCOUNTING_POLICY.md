# Retry and accounting policy

Every started attempt consumes one physical call and remains in the ledger.
Successful valid responses are never replaced. Parser-invalid, missing-field,
timeout or OOM attempts permit at most one retry, subject to a global reserve of
12 calls and the absolute 160-call cap. Semantic abstain, low confidence,
incomplete target and contradiction are authoritative outcomes and are not
retried. If a retry succeeds it is authoritative for execution, while both
attempts remain charged and both remain visible for stability/failure metrics.
If no valid retry exists, the first attempt is authoritative UNKNOWN.
