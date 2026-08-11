# Task: Complete and validate the ARC physical baseline

## Repository state

- Base branch: dspro
- The ARC adaptation implementation was merged in commit:
  97d3412a9 Implement ARC baseline adaptation
- Work only inside the current git worktree.
- Existing unrelated changes belong to the user and must not be overwritten.

## Goal

Complete, audit, and validate the ARC baseline needed for comparison with the
current accelerated event-query method.

The final baseline identity is:

ARC-UNIT-INSPIRED-PHYS-v1

This task is not a new algorithm-design exercise. First determine what commit
97d3412a9 already implemented, then repair only concrete missing or incorrect
parts.

## Read before modifying code

Read all applicable AGENTS.md files first.

Then inspect:

1. outputs/mf_psvr_publication_program/
   cycle_00_integrity_and_literature/ARC_FULLTEXT_AUDIT.md

2. outputs/mf_psvr_publication_program/
   cycle_00_integrity_and_literature/BASELINE_ADAPTATION_SPEC.md

3. BSEC_AQP_Development_Gate_v1/scripts/run_native_arc_vs_pstr.py

4. Historical ARC source and adapters, including whichever of these exist:
   - refe_repos/ARC-main/
   - refe_repos/adapter/arc_baseline/
   - try_or_no/arc_source/

5. The implementation introduced by commit 97d3412a9:
   - inspect with git show --stat and git show
   - identify every new or changed ARC/SMDP/runtime/test file

6. The current accelerated event-query runtime:
   - SCAN
   - VERIFY
   - controller/SMDP state
   - deadline admission
   - K3 or EventRelation materialization
   - durable snapshot and atomic commit
   - evaluator and experiment runner

Do not assume historical cached-replay code is a valid physical baseline.

## Required ARC adaptation contract

The implementation must satisfy all of the following:

1. Use the benchmark's 10-second units as ARC records.

2. Map a calibrated unit relevance probability p_i(q) to:
   [1 - p_i(q), p_i(q)]

3. Require a complete online proxy pass before ARC refinement starts.

4. Use fixed Jensen-Shannon temporal clustering.

5. Set native ARC tau to one unit.
   K3 defines event bridging and event materialization.

6. ARC label propagation may update:
   - scheduling posterior
   - uncertainty
   - native ARC candidate diagnostics

   Propagated or proxy-only positives must never enter the strict EventRelation.

7. Only physically verified positive units may become EventRelation anchors.

8. Timeout, parse_failure, ambiguous, abstain, unknown, or unusable oracle
   results:
   - are charged to the physical budget;
   - remain unobserved/unknown;
   - must not be coerced to negative;
   - must not be propagated.

9. Proxy initialization, model loading, warm-up, decode, SCAN, calibration,
   clustering, selection, VERIFY, K3, serialization, fsync, atomic rename,
   commit, and final synchronization must share the same monotonic wall-clock
   deadline.

10. Before admitting VERIFY, reserve a complete action path plus durable commit.
    Do not start an action that predictably causes a deadline miss.

11. Keep two separate output views:
    - native ARC candidate intervals and confidence diagnostics;
    - oracle-confirmed EventRelation used for comparison.

12. Do not claim ARC's native confidence guarantee for the adapted EventRelation.

## Stage 1: audit and CPU-only completion

Perform the following now:

1. Inspect the repository and commit 97d3412a9.

2. Build a requirement-to-code matrix covering every contract item above.

3. Identify:
   - already satisfied requirements;
   - partially implemented requirements;
   - missing requirements;
   - incorrect behavior;
   - unverified assumptions.

4. Make minimal code changes needed to satisfy the contract.

5. Preserve the vendored ARC implementation as read-only unless a compatibility
   repair is strictly necessary. Prefer wrappers and adapters.

6. Run all relevant CPU-only tests, including tests for:
   - historical ARC synthetic parity under fixed arrays, clusters, seed, tau=1;
   - no oracle/reference leakage;
   - empty candidate handling without NaN;
   - duplicate VERIFY deduplication;
   - timeout and parse-failure semantics;
   - propagated positives excluded from EventRelation;
   - identical K3 output for identical physical oracle traces;
   - deterministic replay;
   - SMDP state causality;
   - deadline admission;
   - durable snapshot visibility and recovery.

7. Run available formatting, lint, type checks, and targeted pytest suites.
   Do not claim skipped checks passed.

8. Create:

   reports/ARC_BASELINE_READINESS.md

   It must contain:
   - inspected files and implementation map;
   - requirement-to-code matrix;
   - exact changes made;
   - exact commands executed;
   - test results and failures;
   - remaining scientific and engineering uncertainties;
   - whether the baseline is ready for a physical smoke run;
   - the exact proposed smoke command;
   - expected input/output files;
   - estimated GPU/model actions that command would perform.

## Restrictions for Stage 1

Do not:

- run GPU inference;
- launch YOLO, 8B, or 32B model inference;
- download models or datasets;
- access the network;
- kill or alter existing processes;
- change CUDA_VISIBLE_DEVICES;
- modify files outside this worktree;
- delete existing outputs;
- alter frozen prompts, parsers, oracle labels, references, or evaluation rules;
- commit, merge, push, or publish;
- launch the full experiment matrix.

You may run CPU-only tests and inspect existing files.

## Completion behavior

Work through the task rather than only proposing a plan.

At the end, report:

1. what was already implemented;
2. what you changed;
3. tests that passed;
4. tests that failed or were skipped;
5. whether physical smoke is authorized technically;
6. the exact next command requiring user approval.

Stop before executing any GPU or physical baseline command.
