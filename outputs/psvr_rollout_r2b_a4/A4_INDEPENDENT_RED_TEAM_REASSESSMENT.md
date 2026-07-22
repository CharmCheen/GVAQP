# A4 Independent Blind Reassessment — FAIL

Verdict:

```text
A4_FREEZE_GATE = FAIL
BLOCKED_INDEPENDENT_VERIFIER
```

The reviewer inspected the frozen BASE/A1/A2/A3/A4 material, current source, tests, registries, A4 transition evidence, and the independent verifier without using the original finding list as a checklist. No files were edited by the reviewer. Focused tests and `py_compile` passed, but they do not establish Freeze.

## Direct reproducible counterexamples

From a fresh `execute_full_horizon(identity, 101).trace`, the verifier accepts both of the following after the affected local hashes/commitment are recomputed.

1. A transition post-state is replaced with `committed=["FORGED_EVENT"]` and an empty frontier. `verify_episode_evidence` returns `PASS` with no errors. The verifier checks local draw realization and self-consistent hash but does not independently derive post-state, legal successor action, or transition continuity.
2. Every action return in one persisted pair is increased by `1000.0`; paired differences, mean, variance, LCB and trace commitment are recomputed. `verify_episode_evidence` returns `PASS` with no errors. The verifier recomputes arithmetic over persisted return scalars but does not reconstruct continuation returns from evidence.

Thus the current path does not establish:

```text
canonical identity + visible history + compact evidence/replay keys
→ transition → continuation → paired samples → mean/variance/LCB
→ selection → utility timeline
```

It validates local consistency of untrusted records instead.

## Original finding reassessment

| Finding | Assessment |
| --- | --- |
| RT-A4-01 | Production/docs/artifact agreement appears repaired; not independently closed globally. |
| RT-A4-02 | Production retains generated same-source pair draws and lexical ranks; not independently replay-verified. |
| RT-A4-03 | Canonical hypothesis fields exist; forged post-state PASS proves no independent closure. |
| RT-A4-04 | Synthetic duplicate token exists; not independently replay-verified. |
| RT-A4-05 | Completion ticks and focused fixture exist; not independently full-history verified. |
| RT-A4-06 | Shared key/uniform records exist; not independently closed through continuation replay. |
| RT-A4-07 | Evidence is retained, but forged post-states/returns pass. |
| RT-A4-08 | Schedule is explicit; not independently replay-verified. |
| RT-A4-09 | Operator/realization order is explicit; not independently replay-verified. |
| RT-A4-10 | **OPEN — BLOCKED_INDEPENDENT_VERIFIER.** |
| RT-A4-11 | Static evidence improved; no independent full-boundary proof. |
| RT-A4-12 | Focused tests omit adversarial post-state and continuation-return forgery checks. |

## Required rejection criterion

Do not freeze A4 or resume IC1 until an independent verifier reconstructs and validates post-state and successor continuity, continuation returns, paired samples/LCB/fallback/tie-break selection, utility timeline, and commitments; both described forgeries must fail after all affected hashes are recomputed.
