# Runtime-added configuration audit

The IC1 runner appends `ic1-cfg-13` through `ic1-cfg-18` in source rather than
reading them from the frozen registry.  Every one is classified
`UNAUTHORIZED_POSTHOC_CONFIGURATION` for scientific execution.

This is based on provenance, not performance: the v9 development ledger was
written before the runner file's current modification time.  The worktree has
no commit history for this untracked source, so it cannot supply an earlier
pre-result authorization.  The runner's self-description as “result-blind” is
an implementation claim, not authorization evidence.

The row-by-row evidence is retained in `A5_RUNTIME_6_ROW_AUDIT.json`.
