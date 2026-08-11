# Minimum Decisive Experiments

## P0 — Independent event-continuity check (paper deciding)

- **Hypothesis:** The P0 C1 continuity-gain reflects event continuity that independent human reviewers would endorse, rather than agreement with a K3-defined model-relative reference.
- **Design:** Before inspecting the annotation outcomes, freeze 36–48 temporal neighborhoods across DALI/HANGZHOU/WUHAN by a timestamp-only stratified rule. Reviewers see the original clips and frozen query, not K3/K0 predictions or model labels. Collect whether relevant activity exists and whether pre-specified adjacent units belong to one event. Compare C0, C1, and current K3 only after labels are frozen.
- **Falsifier:** C1/K3 does not improve agreement with human continuity over C0, or reviewers cannot define a reproducible continuity judgment.
- **Support:** C1 improves agreement while K3 provides no additional effect; then the contribution must be framed as a simple continuity operator/contract, not negative-barrier K3.
- **Cost/VOI:** Small human effort; high. This directly resolves the largest circularity and novelty risk and can change the paper decision.

## P1 — Predicate/domain replication with a frozen non-K3 reference

- **Hypothesis:** Sparse verification → continuity-constrained relation materialization is not peculiar to one driving-response predicate.
- **Design:** One additional preregistered predicate or independent video domain, one frozen candidate universe, full reference unit labels, and event reference constructed independently of method-side K3. Reuse exactly C0/C1/current-K3 and the P0 same-trace matrix.
- **Falsifier:** C1 effect is near zero/inconsistent once the reference is not K3-defined.
- **Support:** Positive multi-selector effect with the same direction and a disclosed regime boundary.
- **Cost/VOI:** Moderate/high VLM or annotation work; do it only if P0 supports the continuity hypothesis.

## P2 — Physical deadline validation of the selected final story

- **Hypothesis:** The final relation-materialization contract preserves the quality conclusion under measured completion-based wall-clock deadlines.
- **Design:** Only after P0/P1 are positive, run the frozen executor on at least three sources with measured scan, oracle, materialization, commit, and late-exclusion times. Plot quality-vs-query-budget separately from quality-vs-wall-clock.
- **Falsifier:** the effect vanishes or late/durable semantics reverse it.
- **Support:** the same qualitative C0/C1 result under legal deadline admission.
- **Cost/VOI:** High. It cannot rescue a circular/non-novel materializer, so it is deliberately P2.
