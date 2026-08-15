# Proposed state-of-truth update (pending human review)

This is a proposal only. It does not modify any root-level state file. It
records what this audit can and cannot add to the project state.

## Proposed additions (pending confirmation)

1. A root-cause audit was requested against a claimed
   `outputs/endogenous_scan_preflight_v1/` artifact set. The artifact set is
   absent from the repository, so the audit is blocked at the fact-check gate.

2. No change to any empirical claim status is warranted by this audit. In
   particular:
   - C-B (true costly/incomplete SCAN benefits from state-dependent allocation)
     remains NOT ESTABLISHED.
   - C-K (endogenous SCAN adaptation works) remains NOT ESTABLISHED.
   - Controller remains CLOSED / NO-GO; MAB/RL remain unauthorized.

3. The only new project-level fact this audit adds is a provenance flag:
   "referenced endogenous-scan preflight artifacts are not present in the
   current repository; a path/environment discrepancy exists between
   `/root/charm/GVAQP` (prompt), `/root/charm/GVAQP_side_rcsem` (manifest), and
   `/Users/charmcheen/FDU/入学前/GVAQP` (actual)."

## Proposed no-ops (do not change)

- Do NOT convert NOT ESTABLISHED into DISFAVORED or FALSIFIED on the basis of an
  unverifiable 0/36 result.
- Do NOT reopen the controller or authorize MAB/RL.
- Do NOT alter the human P1 status (WAITING_HUMAN_REFERENCE) or any P1 frozen
  component.
- Do NOT create a new experiment ledger row implying a faithful endogenous-scan
  preflight completed, because no such artifact exists here.

## Condition that would change this proposal

If `outputs/endogenous_scan_preflight_v1/` is located and its hashes verified,
this proposal should be superseded by a full root-cause audit over those
artifacts, and only then should any claim-status or gate change be considered.
