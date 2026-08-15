# Provenance Conflicts (local audit findings)

Conflicts found between project sources, ranked by scientific severity. All
items were re-checked locally during this audit.

## CONFLICT-1 (dominant): claimed endogenous-SCAN preflight vs. project ledger

- Source A (prior discussion/prompt): `outputs/endogenous_scan_preflight_v1/`
  with SUBSTRATE_FIDELITY=PASS, costs 0.1071/18.4440 s, 57/36 states,
  5 natural misses, 0/36 regret at delta 0.02.
- Source B (local repo): directory absent; 0/13 artifacts; `P4_FAITHFUL_SCAN`
  = NOT_STARTED / NOT_AUTHORIZED; natural misses impossible on the audited
  substrate (exposure recall 1.0 by construction).
- Classification: **E (CONFLICTED) → resolved to C (REPORTED_REMOTE_UNVERIFIED)
  for the claim, F (NOT_FOUND) for the evidence.**
- Resolution action: recover artifacts (see REMOTE_ARTIFACT_RECOVERY_MANIFEST.md).
  Until then the 0/36 must not be cited, root-caused, or used to update any
  claim status.

## CONFLICT-2 (reconciled): 25/26/57 vs 5/5/98 on the same 108 states

- Source A: `controller_dynamic_headroom_cached_reproduction_v1/SUMMARY.json`
  — SCAN_BETTER 25, VERIFY_BETTER 26, EFFECTIVELY_TIED 57 (tie tolerance
  1e-12).
- Source B: `outputs/original_theory_identifiability_audit_v1/` —
  BENEFICIAL 5, HARMFUL 5, INDIFFERENT 98 (practical delta 0.005).
- Local re-verification: same 108 `delta_q` values, two thresholds.
  **RECONCILED — different estimand granularity, not a contradiction.**
- Residual note: `EXPERIMENT_DECISION_LEDGER.csv` cites only the 5/5/98 view
  for the identifiability row and `PROJECT_STATE_OF_TRUTH.md` cites only the
  25/26/57 view for the controller row. Readers can misread these as two
  different experiments; both files are correct in their own scope.

## CONFLICT-3 (resolved by hash evidence): pilot video names

- Prior audit (`endogenous_scan_root_cause_audit_v1/SOURCE_OF_TRUTH.md`)
  states the physical pilot used "PSP_V0_SHORT / PSP_V1_LONG (not
  DALI/HANGZHOU/WUHAN)".
- Local hash evidence: `PSP_V0_SHORT` sha256 `bad22900…` = WUHAN in the P1
  protocol; `PSP_V1_LONG` sha256 `64cb0cfa…` = DALI. The videos are the same
  sources under different names.
- Classification: **E → reconciled in favor of hash evidence.** Scientific
  impact low (the pilot is BLOCKED regardless), but provenance maps must not
  claim the pilot used different source videos.

## CONFLICT-4 (historical, resolved in state files): old narrative vs. frozen status

- Older roadmaps/design packs (e.g., `0714修改idea.md`,
  `BCM_AQP_MATHEMATICAL_REFERENCE.md`, `*_Design_Pack_v1`) describe a broad
  SCAN/VERIFY controller/materializer program with stronger language than
  the frozen ledgers now support.
- Resolution: `PROJECT_STATE_OF_TRUTH.md` §1 and §5 explicitly supersede
  older narrative. This is a documented, rule-governed supersession, not an
  unresolved conflict. Auditor concurs.

## CONFLICT-5 (terminology risk): "exposure degradation gap 0.0" reading

- The alignment report says exposure severe-vs-original median gap 0.0000;
  a naive reading might call exposure "irrelevant". The correct reading
  (confirmed by `SCAN_FALSE_NEGATIVE_AUDIT.md` and re-derived numbers) is
  that SYNTHETIC thinning under these policies/budgets does not change
  median EventF1, because the tested bottleneck is ranking. Natural exposure
  failure remains unmeasured. No contradiction, but high misreading risk —
  flagged for the proposed state-of-truth update.

## CONFLICT-6 (citation integrity): "DIVA" reference likely mislabeled

- `MAB_RESEARCH_DIRECTION_DECISION.md` §6 cites "DIVA" as a USENIX ATC'21
  cheap-to-expensive video-pass system. The independent literature audit
  could not resolve that DOI to any system named DIVA; the ATC'21 record
  resolves to "Video Analytics with Zero-Streaming Cameras"
  (arXiv 1904.12342). Recommend the project owner re-verify or remove this
  citation before any publication use.
- Also unresolvable in the same document: "EFS", "MEC" (abbreviation
  ambiguity). Not scored in `NOVELTY_CLAIM_MATRIX.csv`; flagged here for
  citation hygiene.

## Conflict register conclusion

- 1 unresolved dominant provenance conflict (endogenous preflight).
- 1 threshold-view reconciliation (108 states).
- 1 hash-evidence reconciliation (pilot videos).
- 1 rule-governed supersession (old narratives).
- 1 terminology hazard (exposure gap wording).
- 1 citation-integrity finding (DIVA/EFS/MEC references).
