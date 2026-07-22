# Stage-A prelaunch difference audit

## Strongest supported conclusion

The recovered zero-call state is correct, but the recovery memo's Git-provenance statement is not. The live repository reports the Stage-A runners, core modules, and focused tests as untracked rather than tracked and unmodified.

This is primarily a provenance-record defect, not evidence of changed frozen behavior: direct SHA-256 checks match all applicable bindings in the pre-inference audit, acquisition protocol, and oracle execution spec. No paid GPU or oracle work was started before recording the initial difference.

An adversarial review subsequently identified a second, literal protocol issue: candidate preflight always atomically rewrites `UNIT_MANIFEST.csv`. The launch did so at 2026-07-19T04:40:14Z despite the instruction not to regenerate it. The SHA-256 remained exactly `28e72b6d9497d0f4a9278add3e1df00898585045fdb90520026e0f37747c3053`, so the operation changed metadata but no bytes, identities, anchors, or universe membership.

## Decisive observed evidence

- No candidate or Stage-A Python runner is active; the only `pgrep` hit was the inspection shell itself.
- `nvidia-smi` reports no compute process on the available NVIDIA A800-SXM4-80GB.
- Candidate state remains `PREFLIGHT_PASS_GPU_NOT_RUN` with 0/603 provider videos and no `UNIT_SCORES.csv`.
- Oracle call and label manifests are header-only; no attempt ledger, raw envelope, input identity, preparation marker, or completion marker exists.
- Candidate and oracle preflights pass without decoding semantic frames or loading the oracle model.
- `py_compile` passes and the three focused suites report 14 passed.
- The live hashes of the candidate runner, freeze runner, training-pool core, and selection core exactly match the pre-inference bindings.
- The freeze runner and selection core also exactly match the acquisition-protocol bindings.
- The oracle runner and oracle core exactly match the execution-spec bindings.

## Differences from the recovery report or requested launch procedure

1. The recovery report says the core Stage-A files are Git-tracked and unmodified. Git reports them as untracked. Commit-relative cleanliness therefore cannot establish their provenance.
2. The frozen sample-selection runner does not implement an argparse help path. Running it with `--help` enters its zero-argument main routine and fails closed because candidates are incomplete. Editing it to add help would violate its frozen hash; the exact frozen invocation after extraction is `python scripts/freeze_mf_psvr_stage_a_sample.py`.
3. Candidate preflight rewrites the frozen unit manifest byte-identically. This violates the literal no-regeneration rule even though it leaves the scientific universe unchanged.

## Competing explanation and residual uncertainty

The most plausible explanation is that this recovered workspace was reconstructed into an untracked tree while preserving byte-identical audited files. Direct hashes strongly support that explanation. Git history alone cannot establish how those untracked bytes arrived, so the launch relies on content-addressed frozen bindings rather than index status.

## Decision

`CONDITIONAL_PASS_REQUIRE_INDEPENDENT_COMPLETION_AUDIT`.

Allow the already-running authorized extraction to finish because stopping cannot undo the byte-identical rewrite and would discard useful in-scope compute. Do not freeze Stage-A from the runner's completion flag alone. First require independent recomputation of all provider, unit, query-key, numeric-content, source-hash, implementation-hash, and held-out gates. Reject if any source hash, proxy/config/weight/tracker hash, provider-video identity, unit identity, query key, numeric row, or held-out boundary diverges.
