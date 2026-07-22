# R2 confirmatory execution contract review

## Decision

`R2_CONFIRMATORY_STATE = BLOCKED_COMMAND_SPEC_MISMATCH`.

The 55-file freeze is hash-consistent, all 48 toy tests pass, development smoke
is unchanged, no relevant process is active, and no confirmatory master seed,
attempt ledger, episode output, aggregate, or completion marker exists.

Launching is nevertheless unsafe because the frozen runner cannot satisfy the
authorized execution contract:

- It evaluates B0/B1/B2/B3/B4/M1 but not required C0 Clairvoyant/DP ceiling;
  the frozen R2 preregistration also omits C0.
- It writes private generic JSON artifacts, not the required `CONFIRMATORY_*`
  seed/ledger/raw/task/regime/paired/recomputation/Gate/decision/failure set or
  the four required confirmatory reports.
- Its verifier checks only file count and ledger completion; it does not
  recompute raw-trace D1 metrics, pairing, regimes, Gate, commitment/split
  integrity, or duplicate/missing identities.
- It does not emit a preregistered final decision branch.
- An interruption after `STARTED` cannot resume: the generator rejects an
  existing root, there is no resume mode, and no failure/uncertain-nonretriable
  record is written.
- The frozen command requires `PYTHONPATH=src`; a bare `python runner --help`
  does not satisfy the stated CLI preflight.

Generating a master seed now would permanently consume a confirmatory universe
for a run known in advance to be nonconforming. The user prohibits modifying the
frozen runner in this execution turn. Therefore no one-shot command was run.

Independent review: `NOT_SAFE_TO_LAUNCH`.
