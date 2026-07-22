# PSVR rollout interruption recovery audit

Audit timestamp: `2026-07-20T01:48:39+00:00`.

The unique recovery state is `HELDOUT_CONTAMINATION_DETECTED`. No relevant
process was active and no held-out policy runner, result directory, completion
marker, ranking table, or result artifact was found. The held-out runner is
gated by `--confirm-heldout` and an unauthorized preregistration state; it was
not executed.

The decisive contrary evidence is direct seed visibility: the required focused
test suite includes `test_unfrozen_invariants.py`, which calls `read_text()` on
`TOY_HELDOUT_SEEDS.json`. The suite was run in this audit (36 passed, 1 xfailed).
This is seed-visibility contamination even though no policy comparison occurred.
The exposed universe must be frozen permanently and cannot support H-ROLLOUT1A.

Durable completed work: the D2 split amendment and D2-T exact support binding are
present; all 9 updated-freeze and all 16 code-manifest hashes recompute exactly.
The amendment records result blindness and D2-P remains calibration-blocked.

The distinct non-held-out blocker is also durable: the rebound preregistration
is `REBOUND_BUT_BLOCKED_INTERNAL_INCONSISTENCY`, and the freeze manifest lists a
missing nonclairvoyant visible-history conditional kernel plus three prototype
defects. Syntax compilation passed; focused toy tests passed, but neither result
makes the simulator scientifically frozen. Development smoke has not run.

Git revision and worktree status could not be read because Git refused the
directory's ownership; this audit did not alter global Git configuration.

The only safe next command is recorded in `NEXT_EXACT_COMMAND.md`:
`NONE_HELDOUT_CONTAMINATION_REQUIRES_NEW_PREREGISTRATION`.

Terminal condition: `AUDIT_COMPLETE_HELDOUT_CONTAMINATION`.
