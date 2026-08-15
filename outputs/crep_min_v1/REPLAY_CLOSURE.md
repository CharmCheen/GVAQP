# CREP-Min v1 — Replay Closure Conditions (Phase 2)

A claim `(π_A, π_B, metric M, log L)` is **replay-certifiable** only if all
six closures hold. Each closure is stated as a predicate; a missing closure
maps 1:1 to a counterexample in `COUNTEREXAMPLE_SUITE` (C1–C8).

## A. Action support closure
For every history `h` reachable under the target policies, every action
`a ∈ Γ(h)` has a logged occurrence or a verifiable model of its outcome law.
Failure witness: **C1** (unlogged action outcomes differ across two
log-consistent worlds).

## B. Outcome closure
The outcome law `P(outcome | h, a)` is identifiable from the log for every
target action (cached full-grid outcomes satisfy this under the frozen
verifier; behavior logs with propensities do not, without recording
propensities).
Failure witness: **C2** (same SCAN observation → different candidate sets in
two worlds).

## C. Candidate / capability closure
The candidate set and the legal-action set after each action are exactly
reconstructible from the log.
Failure witness: **C3** (a VERIFY legal in one world, illegal in another,
with identical logs).

## D. Clock closure
`start`, `finish`, `materialize`, `commit` and `deadline` are reconstructible
with the same semantics used at execution.
Failure witness: **C4** (identical outcome, completion before vs after
deadline).

## E. Information-flow closure
No policy input can read unqueried outcomes, reference, ambient cache, or
future candidates. Enforced by a sandbox; leakage = invalid replay.
Failure witness: **C5** (peeking at unqueried outcomes produces spurious
advantage). Local real-world instance: partial_scan_pilot
`POLICY_INFORMATION_ISOLATION = FAIL`.

## F. Version closure
proxy / verifier / materializer / evaluator / reference versions frozen and
hashed; replay under a different version is a different claim.
Failure witness: **C7** (identical trace, different materializer → policy
ranking reversal). Local real-world instance: ERAEA E4 reversal rate 0.2222.

## G (derived). Hidden-grouping transition guard
Same unit outcomes → same EventRelation must hold under the pinned
materializer. If grouping is not deterministic from outcomes, ranking is not
replay-certifiable.
Failure witness: **C6**.

## H (derived). Future-identity leakage guard
Candidate identity must not encode future truth (e.g., ids ordered by
outcome). Failure witness: **C8**.
