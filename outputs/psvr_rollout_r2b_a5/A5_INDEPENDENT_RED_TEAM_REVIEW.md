# A5 independent result-blind red-team review

Verdict: `BLOCKED_POSTHOC_CONFIGURATION`.

The reviewer inspected only frozen core/IC1 documents, the original registry
and universe specification, the runner, A5 artifacts, and attempt ledger
timestamps/identity counts.  It did not inspect utilities, agreement, regret,
LCB, success rates, resources, traces, or development-performance outputs.

## Evidence

- The core requires four error forms and magnitudes `0`, `.05`, `.10`, `.20`.
  The 13-row original registry has only systematic optimism/pessimism and
  `0`, `.05`, `.10`.
- The original Cartesian product is exactly `6 × 13 × 5 = 390`; A5 materializes
  390 unique, hash-bound identities from precisely `cfg-00` through `cfg-12`.
- Each of `ic1-cfg-13` … `ic1-cfg-18` is an
  `UNAUTHORIZED_POSTHOC_CONFIGURATION`.  The runner calls them extensions that
  complete previously unexercised axes, which is a registry change.
- `development_attempt_v9/DEVELOPMENT_ATTEMPT_LEDGER.jsonl` was modified at
  `2026-07-21T05:25:03.688703787Z`; the runner carrying the append was modified
  at `2026-07-21T05:54:30.574975Z`.  The untracked worktree has no first-
  introduction commit or a pre-result authorization artifact.  Result-driven
  selection is not proved, but cannot be excluded; that fails the requirement
  to establish pre-result authorization.

The reviewer found no independent hash failure.  The provenance failure is
decisive: a 390 identity subset cannot claim complete frozen-grid coverage,
and a 570 set cannot be retroactively authorized by a runtime append.

Minimum remedy: a new explicit, result-blind scientific-grid amendment.  Do
not relabel the runtime set, backdate the registry, resume V2, or run IC1.
