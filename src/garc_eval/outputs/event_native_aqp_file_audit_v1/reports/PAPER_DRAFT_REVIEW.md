# Paper Draft Review

Reviewing `paper_draft/PAPER_STYLE_RESEARCH_REPORT.md` (306 lines).

---

## Strengths

1. **Clear problem framing:** Positioned as AQP with expensive predicates (SUPG lineage), extending to video clips
2. **Empirical grounding:** Full oracle reference (347 anchors) provides solid data for all claims
3. **Honest limitations:** VLM-oracle-relative labels, templated boundaries, certificate as future work
4. **Structured claim categorization:** Strong/moderate/weak/unsafe — defensible
5. **Good coverage:** Introduction through Conclusion + Related Work + Experiments + Appendix

## Weaknesses

1. **Title too generic:** "Budgeted AQP for Semantic Event Clip Retrieval" doesn't highlight the innovation (weak proxy, audit, non-i.i.d.)
2. **Abstract too packed:** 250 words trying to cover everything. Should focus on 1-2 key contributions
3. **No formal problem definition for certificate:** Section 3 defines recall but not the certificate problem (Pr[R̂ ≥ γ] ≥ 1 − δ with non-i.i.d. structure)
4. **DCA is described but not validated:** Section 5 proposes DCA with specific fractions (40-40-20) but no evidence that these fractions are optimal. The algorithm description is aspirational, not empirical
5. **Results section conflates what IS vs what SHOULD BE:** RQ5 (boundary) and RQ6 (audit/certificate) mix empirical findings with design arguments
6. **No certificate algorithm at all:** Section 8 mentions certificate as future work but doesn't even sketch how it could work
7. **Experimental setup missing critical details:** Which GPU? Which CUDA version? How were random seeds set? What was the runtime variance?
8. **Related work matrix is in appendix but not integrated:** Section 4 references the matrix but doesn't synthesize the positioning argument
9. **Missing ablation on α, β fractions:** DCA's 40-40-20 split is arbitrary. No analysis of how different fractions would perform
10. **No comparison to realcartest results:** The paper mentions realcartest but doesn't systematically compare the two videos

## Recommendations for Revision

1. **Focus title on the novel mechanism:** "Budget Decomposition with Audit-Aware Allocation for Weak-Proxy Video AQP" or similar
2. **Cut Abstract to 150 words** focused on: (a) the problem (weak proxy + temporal clips), (b) the solution (DCA with audit), (c) the evidence (40% improvement at B=80)
3. **Add formal certificate problem definition** even if not solved: Pr[R̂ ≥ γ] ≥ 1 − δ, where the probability is over the oracle allocation and the clip-level label process
4. **Validate DCA fractions on replay data** before presenting 40-40-20 as fixed. Use sweep analysis
5. **Separate empirical findings from design proposals** into different sections
6. **Add a certificate feasibility section** describing the block bootstrap approach (E3)
7. **Add budgets comparison table** showing DCA expected performance vs best baselines
8. **Move related work matrix into the main text** (Section 4). The capability table is a strong positioning tool
9. **Add cross-video comparison table** (realcartest vs dataset3) showing proxy AUC, positive rate, temporal correlation, and method performance
10. **Strengthen the audit narrative** — "42.5% of positives are proxy-blind" is the strongest empirical finding; build the paper around this
