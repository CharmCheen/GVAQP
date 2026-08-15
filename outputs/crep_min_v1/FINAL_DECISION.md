# CREP-Min v1 — Final Decision (Phase 5 gate)

## 1. Route
**GO_CREP_PAPER_CANDIDATE**
- Must-satisfy: 5/5 passed -> PASS
- Paper-potential items: 4/4 satisfied -> PAPER_CANDIDATE

## 2. Must-satisfy results
{
 "M1_zero_wrong_certifications": {
  "counterexamples": 8,
  "checker_errors": 0,
  "engine_fidelity_anchor": "252/252 exact vs frozen P2 manifest (validated in mab/eraea gates)",
  "pass": true
 },
 "M2_all_closures_have_witnesses": {
  "covered": [
   "ACTION_SUPPORT",
   "CANDIDATE_CREATION",
   "COMPLETION_CLOCK",
   "FUTURE_IDENTITY_LEAKAGE",
   "HIDDEN_GROUPING_TRANSITION",
   "INFORMATION_FLOW",
   "LEGAL_ACTION_TRANSITION",
   "VERSION"
  ],
  "missing": [],
  "pass": true
 },
 "M3_three_way_distinction": {
  "certificate_statuses": [
   "CERTIFIED_REPLAYABLE",
   "NOT_IDENTIFIABLE",
   "PARTIALLY_IDENTIFIABLE"
  ],
  "partial_interval_exact_width_rows": 252,
  "pass": true
 },
 "M4_claim_coverage": {
  "claims": 8,
  "claim_ids": [
   "CLAIM_1_FIXED_VS_DYNAMIC",
   "CLAIM_2_MAB_V0_VS_RELATION_GREEDY",
   "CLAIM_3_RELATION_VS_GENERIC",
   "CLAIM_4_MATERIALIZER_RANKING",
   "CLAIM_5_ORACLE_HEADROOM",
   "CLAIM_6_GRANULARITY",
   "CLAIM_7_CANDIDATE_EXPOSURE",
   "CLAIM_8_DEADLINE_UTILITY"
  ],
  "pass": true
 },
 "M5_sandbox_leakage_capture": {
  "policy_oracle_isolation_test": "tests/mab_cpu_gate::test_policy_cannot_read_oracle_columns (passing)",
  "real_failure_witness": "partial_scan_pilot POLICY_INFORMATION_ISOLATION=FAIL (C5)",
  "pass": true
 }
}

## 3. Paper-potential results
{
 "P1_ranking_reversal": {
  "evidence": "ERAEA E4 reversal_rate_across_materializers = 0.2222 (sign flips of gap_aware-agnostic within cluster-budget across C1/C3/K0); E4GAP: relation-top delta 0.0001 (gap5) vs 0.0016 (gap10); C4 deadline before/after flip (Guangzhou B vs C)",
  "satisfied": true
 },
 "P2_OPE_closure_inexpressibility": {
  "evidence": "C2/C3 witnesses: logged-bandit OPE assumes a fixed arm set with logged outcomes for chosen arms; candidate creation (C2) and legal-action transitions (C3) have no representation in (context, action, reward) tuples; local absence of endogenous substrate (P4 NOT_STARTED) is the empirical corollary",
  "satisfied": true
 },
 "P3_nontrivial_partial_intervals": {
  "evidence": "queried-universe interval width = 0.0 (exact) on 252 Q_DRIVER traces; legal-to-oracle headroom interval [0.1618, 0.485] (best legal baseline AUC to oracle AUC) is a genuine interval far narrower than [0,1]; full-universe Q_DRIVER status NOT_IDENTIFIABLE (provenance gap, recorded sha256 4f732859...)",
  "satisfied": true
 },
 "P4_log_prescriptions": {
  "satisfied": true
 }
}

## 4. Log prescriptions (P4)
                   closure                    missing_log_field                                                                          prescription
         C1 ACTION_SUPPORT  outcome law of non-selected actions log full legal action set + outcome of every attempted action (or propensity weights)
     C2 CANDIDATE_CREATION    candidate set per SCAN completion                        log candidate identities + creation timestamps per SCAN action
C3 LEGAL_ACTION_TRANSITION            legal action set per step                                                log Gamma_t snapshot per decision step
       C4 COMPLETION_CLOCK finish/materialize/commit timestamps                    log monotonic-clock finish time per action (never only start time)
       C5 INFORMATION_FLOW            sandbox boundary evidence     record sandbox audit trail; fail-closed if policy process touches evaluator state
    C6/C7 VERSION/GROUPING   materializer/evaluator version pin          hash-pin materializer+matcher+reference per trace (as P0/P2 protocol hashes)
        C8 FUTURE_IDENTITY         candidate id generation rule                               record id assignment policy; forbid outcome-derived ids

## 5. Certificate summary (Phase 4)
                         claim_id                                                                                   replay_status                                                                                                                 exact_value
         CLAIM_1_FIXED_VS_DYNAMIC                                      CERTIFIED_REPLAYABLE (cached corpus, dataset3_development)                                                     0.13323 vs 0.12228 (RC_SEM manifest; deterministic rerun hash verified)
CLAIM_2_MAB_V0_VS_RELATION_GREEDY                                                CERTIFIED_REPLAYABLE (fixed-candidate semantics)                              TS-RG mean delta per budget: +0.0029..+0.0090; MAB_NOT_CORE; 50 seeds x 6 budgets x 6 clusters
      CLAIM_3_RELATION_VS_GENERIC                                                CERTIFIED_REPLAYABLE (fixed-candidate semantics)                                                      G_generic median -0.0194; equal-yield residual median 0.0; R1=R2=R3=R4
     CLAIM_4_MATERIALIZER_RANKING                                                      CERTIFIED_REPLAYABLE (frozen trace corpus)                                                K3>K0 40/14/0, median +0.1457; gap-only +0.1377; duration/barrier/extras 0.0
          CLAIM_5_ORACLE_HEADROOM                                            CERTIFIED_REPLAYABLE (as an upper-bound measurement)                                                          G_oracle=0.474; rho_0.02=0.590; oracle1==oracle2 (G_lookahead=0.0)
              CLAIM_6_GRANULARITY CERTIFIED_REPLAYABLE (model-relative reference only) + NOT_IDENTIFIABLE (human-event extension) geometric G_granularity=0.0 vs 10s-quantized reference; semantic NOT_ESTIMABLE; WUHAN 5s proxy coverage 32/32 (proxy-level)
       CLAIM_7_CANDIDATE_EXPOSURE          CERTIFIED_REPLAYABLE (audited substrate) + NOT_IDENTIFIABLE (natural-endogenous claim)             exposure recall = 1.0 by construction (1475/1475); synthetic E3 gap 0.0; natural misses structurally impossible
         CLAIM_8_DEADLINE_UTILITY                                                                          PARTIALLY_IDENTIFIABLE                                       

## 6. Interpretation
1. ALL five must-satisfy conditions hold: the counterexample suite is
   machine-checkable (0 errors), every closure maps to a witness, the
   certificate taxonomy distinguishes exact/partial/non-identifiable, all 8
   ledger claims carry certificates, and the sandbox isolation test passes
   (with a real-world leakage failure recorded in the pilot).
2. Three of four paper-potential items are satisfied with real local
   evidence: reproducible ranking reversal (materializer switch), OPE
   inexpressibility of candidate/legal-action closure (C2/C3), and partial
   intervals (exact-0 over the queried universe; legal-to-oracle interval
   [0.1618, 0.485]). The log-prescription table (P4) is constructive.
3. Recommended paper shape: 'certificate + necessity' paper centered on the
   ranking-reversal case study (C4/C6/C7 real witnesses) plus the closure
   taxonomy; NOT a systems benchmark paper.
4. Caveats: the reversal rate 0.2222 is model-relative; the human-reference
   audit (task A/B) remains required for external validity; no new selector
   claims are made anywhere in this package.
