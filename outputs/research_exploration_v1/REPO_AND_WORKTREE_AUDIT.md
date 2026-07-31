# Repository and worktree audit

Snapshot: 2026-07-30 12:28 UTC.

## Authoritative locations

- Main Git repository: `/root/charm/GVAQP`, branch `dspro`, commit
  `35d4829280166a30fbd130cfb43ab3aae163463d`.
- RC-SEM side package: `/root/charm/GVAQP_side_rcsem`. It has no `.git`
  metadata and is therefore an exported/staged package, not a Git worktree.
- ARC adaptation: `/root/charm/GVAQP-arc-phys-baseline`, branch
  `arc-phys-baseline`, commit `dc5c507605f603f01d2a7f07e5b492ad0ca06280`.

## Dirty state and ownership boundary

The main repository had 13 untracked paths, all under the active full-grid
execution/preregistration lineage. The ARC adaptation had 12 modified or
untracked entries. These are treated as user-owned. Nothing was reset,
cleaned, deleted, overwritten, committed, or pushed.

The main repository's registered worktrees were:

1. `/root/charm/GVAQP` at `35d482928` (`dspro`);
2. `/root/charm/GVAQP-arc-phys-baseline` at `dc5c50760`;
3. `/tmp/garc_runtime_contract_source` detached at `5047241b0`.

The requested `exp/scan-event-value`, `exp/verify-escalation`,
`exp/controller-headroom`, and `infra/evaluation-harness` branches/worktrees
did not exist. They were not created because the side package is not a Git
repository and the main sealed source tree is being used by an active formal
execution. Creating competing worktrees before release would not make the
missing reference/cost contracts available and would add ambiguous lineage.

## Formal execution outcome

The sealed Oracle V3 full-grid subsequently fail-stopped with 136 completed
units and `DALI_u0136` in flight. Its coordinator measured that call at
23.754265 seconds against the sealed 23.579961-second hard reservation, an
overrun of 0.174304 seconds. `GLOBAL_EXECUTION_STATE.json` records
`status=STOPPED` and `stop_trigger=cost_envelope_exceeded`; the supervisor and
worker exited. HANGZHOU and WUHAN were never activated.

The frozen decision mapping assigns any cost/runtime failure the
higher-priority decision `FULL_GRID_ABORTED_RUNTIME`. An authoritative
finalizer decision artifact has not appeared, but the run cannot satisfy its
1,475-terminal-record gate and the failure policy forbids retries, continuation
under the same approval, a unit-label table, formal K3 relation, or downstream
access. A continuation would be a newly sealed and explicitly authorized
experiment.

No partial raw label or partial parsed-label table was opened during this
exploration. Only coordinator state, cost, and ledger-transition metadata were
audited.

## Test-data access

The older cached study's `dataset3_development` “primary_heldout” fold has
already been evaluated and appears in preserved reports; it is no longer an
untouched final test set. The two realcartest slices were development folds and
share one source video. The new DALI/HANGZHOU/WUHAN V3 grid is frozen, but its
complete reference does not yet exist, so no released final test relation was
available or opened.

## Query contract discrepancy

The pasted task describes a broader attention/preparedness semantic. The
sealed V3 prompt is narrower: a noticeable slowdown, braking action, or
avoidance maneuver due to visible conditions. The frozen prompt was not
modified; claims in this directory are relative to its exact hash.
