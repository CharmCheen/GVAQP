# Decision Ledger

## Cycle 00 — 2026-07-29 — OBSERVE / CONTRACT FREEZE

- Decision: `CONTINUE`; run oracle-adequacy preflight before a full 1,475-unit oracle pass.
- Decisive evidence: the old complete Dali/Wuhan oracle uses different query semantics; the prior 32B Hangzhou probe includes a qualitatively unsupported positive; direct prior 32B latency implies a full pass is substantial.
- Rejected action: reuse old Q1/Q2 labels as the new operational reference. Reason: semantic mismatch would change the frozen objective.
- Rejected action: train a controller from existing binary-SMDP pilot rows. Reason: only four formally ineligible rows exist, with no VERIFY-better states and unsafe latency support.
- Preserved failure evidence: binary-SMDP `INSUFFICIENT_EVIDENCE`, V0 imputed costs, overrun counts, 32B disagreement, parse/unknown policies, and all historical result directories remain unchanged.
- Next highest-value action: materialize and verify the frozen grid, then preregister the smallest cross-video 32B stability sample.
- Revision trigger: if H1 fails, stop the full oracle launch and revise/declare insufficient evidence; if H1 passes, run the full oracle and test H2 before controller work.

## Cycle 01 — 2026-07-29 — PRE-OUTCOME ADVERSARIAL FREEZE

- Decision: `CONTINUE`; freeze the qualitative contradiction screen before spending oracle budget.
- Observed evidence: all twelve deterministic 2 fps contact sheets were generated and content-hashed while zero new-query 32B output artifacts existed. The blinded review contains four qualitative positives, five negatives, and three unknowns.
- Interpretation limit: the reviewer is the research agent, not an independent human adjudicator; sparse visual frames do not measure ego braking or steering. The review is a falsification screen, not semantic truth.
- Preregistered discriminator: only two identical high-confidence 2 fps oracle positives against a medium/high frozen `not_relevant` review form a contradiction candidate. One candidate requires independent adjudication; at least two candidates across at least two videos fail as a systematic pattern. Frozen `unknown` cannot count as a contradiction.
- Verification: the manifest is hash-bound from the review, the analyzer fails closed on a manifest or clip-ID mismatch, and 21 targeted tests pass.
- Remaining blocker: the 30 physical 32B calls are a substantial compute/oracle action and remain unexecuted pending explicit approval (expected 30, observed 0).
- Next highest-value action: after approval, run the three frozen video shards and evaluate the preregistered gates; do not extrapolate to the full oracle if the result fails or requires adjudication.

## Cycle 02 — 2026-07-29 — INDEPENDENT PREFLIGHT FALSIFICATION / PROTOCOL REVISION

- Decision: `REVISE_ORACLE_PROTOCOL`; do not run V1.
- Decisive evidence: independent review directly demonstrated exact-frame mismatch (20 review frames versus 21 model frames), nominal 4 fps drift to about 4.286 fps, permissive label-inconsistent parsing, unauthenticated raw inputs, and false passes for degenerate oracle outputs.
- Alternative explanation rejected: these are not merely low-power concerns; they make the measurement internally inconsistent even before considering sample representativeness.
- Preserved failure: V1 remains at commit `3cf559648`, its expected/observed call count is 30/0, and `PREFLIGHT_V1_INVALIDATION_AUDIT.json` records the rejection without fabricating an outcome.
- V2 evidence: exact precomputed RGB identities now cover 12 base and six sensitivity frame sets; two reviewers independently re-inspected exact sheets and agreed on 10/12 labels. Disagreements remain unknown.
- Key uncertainty: V2's physical runner and analyzer do not yet enforce the new bindings and gates; H1 remains untested.
- Next action: implement authenticated execution/analysis and obtain another independent code-level review before requesting the 32-call budget.

### Cycle 02 implementation update

- Implemented evidence: all three CPU-only runner shards authenticate their frozen bindings and exact frames, yielding the preregistered 10/11/11-call schedule and 32 total inputs.
- Fail-closed evidence: the analyzer rehashes raw records, reparses raw text, compares exact frames/model-input identities, validates GPU provenance and attempt chains, rejects mixed runner commits, requires three disjoint GPU pairs, and cannot emit final pass before positive-claim grounding.
- Falsification tests: synthetic all-unknown, all-negative, and all-positive oracles fail class support; raw and frame tampering fail authentication; a valid mixed result remains pending claim review. The focused suite has 38 passing tests.
- Remaining uncertainty: these claims require independent code inspection; no physical oracle call has occurred.

## Cycle 03 — 2026-07-29 — FIRST V2 IMPLEMENTATION REVIEW / FAIL-CLOSED REPAIR

- Decision: retain `REVISE_ORACLE_PROTOCOL`; do not request or spend oracle compute yet.
- Decisive evidence: independent review rejected the first V2 runner/analyzer because schedule and source execution were not sealed, model provenance was insufficiently direct, accepted ledgers were not exact triples, physical retries and crash ambiguity were possible, sensitivity positives escaped grounding, duplicate JSON keys were accepted, and no frozen final PASS path existed.
- Main competing explanation: the 32-call arithmetic and raw self-hashes looked sufficient under normal completion. This was rejected because mutation and crash cases could still change the physical experiment or admit unauthenticated evidence.
- Repair evidence: an explicit self-hashed 32-call manifest now fixes 24/6/2 calls across 10/11/11 shards; all 19 model files (35,532,291,229 bytes) were directly rehashed; source/protocol hashes are execution-sealed; ledger transitions distinguish pre-inference preparation from physical generation; a started call can never be automatically retried; and every unique positive, including 4 fps output, is routed through a frozen review/finalizer.
- Falsification evidence: mutated call totals, stale model-audit status, wrong accepted triples, concurrent shard launch, interrupted generation, post-generation crash recovery, duplicate JSON keys, sensitivity boundary/response failures, systematic semantic contradictions, incomplete/unsupported grounding, and malformed compute approval were tested. The focused suite has 49 passing tests.
- Key uncertainty: the repaired seal has not yet received an independent GO, and physical oracle calls remain 0/32.
- CPU-only verification: the sealed DALI/HANGZHOU/WUHAN schedules passed at 10/11/11 calls; all current model, video, exact-frame, and call identities matched. This consumes no oracle calls and does not test H1.
- Next action: return the exact seal to the independent reviewer. Any material defect requires a new seal; only GO permits a user compute-approval request.
