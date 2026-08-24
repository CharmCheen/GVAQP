# T0 Endogenous Scan Provenance Decision

## Verdict

`RETIRED_FOR_CLAIM_USE`

## Scope

This decision applies only to the historical endogenous-scan preflight claims and
their alleged physical-cost evidence. It does not say that endogenous scanning is
algorithmically impossible.

## Directly observed local evidence

- The claimed `outputs/endogenous_scan_preflight_v1/` evidence bundle is absent.
- None of the 13 artifacts required by the recovery manifest is locally available.
- The audited local substrate contains precomputed candidates for all 1,475 of
  1,475 units, giving exposure recall 1.0 by construction. It therefore cannot
  reproduce or validate natural candidate misses.
- The historical numbers for SCAN/VERIFY cost, candidate counts, state counts, and
  all-zero public states have no recoverable local trace, command, environment, or
  hash chain.
- Searches of the project, likely local parent roots, Downloads, and Codex
  attachments did not recover the missing bundle.

## Consequence

The historical physical-cost and endogenous-exposure numbers must not be used as
paper evidence, cost calibration, baseline evidence, or justification for a
deadline-safe claim. They may be mentioned only as unrecoverable historical leads.

No numbers were regenerated, inferred, or repaired. Any future physical-cost claim
requires a newly authorized, independently logged C3 measurement run.

