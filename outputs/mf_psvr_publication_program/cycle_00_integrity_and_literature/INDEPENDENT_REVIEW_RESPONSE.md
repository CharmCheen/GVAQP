# Independent Cycle-0 Review and Response

`REVIEW_STATUS = BLOCKERS_IDENTIFIED_AND_SPEC_CORRECTED`

## Review provenance

- Reviewer role: independent integrity/adversarial reviewer (`Herschel`)
- Scope: full-text audit, assumption matrix, baseline adaptation, novelty
  boundary, and source manifest
- Review behavior: read-only; the reviewer modified no files
- Review date: 2026-07-18 UTC

## Reviewer verdict

The original narrow hypothesis was structurally falsifiable but not yet
publication-defensible. Priority and superiority were unestablished, important
nearest priors were absent, and several proposed comparators removed defining
mechanisms from the prior systems they named.

## Findings and dispositions

| Severity | Finding | Disposition |
|---|---|---|
| P0 | Zeus was missing despite directly learning resolution, segment length, and sampling rate for temporal action queries; FiGO and Boggart were also close omitted priors. | Complete primary papers for Zeus, FiGO, and Boggart were acquired, hashed, and added to the source manifest, assumption matrix, novelty boundary, rejection hypothesis, and baseline plan. |
| P0 | Independent-pool `MIRIS-PHYS` changed native target-video preprocessing/planning and added Qwen after MIRIS's native endpoint. | Split into `MIRIS-FIRSTQUERY`, `MIRIS-AMORTIZED`, and `MIRIS-XFER`; only native-cost views characterize MIRIS, and Qwen is labeled an added benchmark confirmation view. |
| P0 | The proposed DIVA comparator removed landmarks, query-specific operator bootstrap, and online upgrades. | Renamed the generic row `FIXED-MULTIPASS`; added separate `DIVA-FIRSTQUERY` and `DIVA-LANDMARK-AMORTIZED` specifications. Generic cascade results cannot support "beats DIVA." |
| P0 | ARC lacked a common proxy/oracle probability domain, temporal mapping, and adapter validation. | Declared native fidelity impossible under the unit oracle; specified `ARC-UNIT-INSPIRED` with a binary unit domain, calibrated probabilities, abstention behavior, JSD clustering, `tau=1`, unit dedup, full costs, and synthetic equivalence test. |
| P1 | Track-bearing opportunity identity could be misread as track confirmation even though the oracle is unit-level. | Split immutable `opportunity_id` from unit `verification_key`; deduplicate by verification key and prohibit track-attribution claims in committed output. |
| P1 | The matrix mixed paper contracts with released-artifact behavior. | Expanded the CSV schema with separate `paper_contract` and `audited_artifact_behavior` fields for every method; paper-only rows say so explicitly. |
| P1 | Terms such as "matches," "meaningful," and component loss lacked fixed estimands and margins. | Preregistered intention-to-run failure handling, paired task-level estimands, development/noninferiority/equivalence margins, minimum REFINE effect, third-source gate, and task-only bootstrap procedure. |
| Claim correction | The wording implied exhaustive literature coverage. | Replaced it with "the literature audited so far" and retained the mandatory broader citation-chain review. |
| Claim correction | Code-tested clock/identity repairs were combined with physical validity. | Split implementation-tested status from unestablished end-to-end physical validity. |

## Remaining uncertainty

- Zeus, FiGO, and Boggart code behavior has not been audited; the current rows
  support paper-contract conclusions only.
- The new adapters are specifications, not validated implementations or
  reproductions.
- A broader systematic database/citation-chain search remains mandatory before
  paper submission.
- No result yet shows that strict durability/accounting changes method rankings,
  that a refiner adds causal value, or that MF-PSVR beats Zeus/FiGO/simple
  controls within the preregistered margins.

## Review-controlled decision

Cycle 0 may close as an integrity/literature gate after its machine audit passes,
but no novelty or superiority claim is promoted. The next discriminating action
remains measuring query-aligned class support in an independent training pool.
