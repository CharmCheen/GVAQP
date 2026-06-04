# Method Positioning: SUPG / ABae / ARC / G-ARC

## Comparison Table

| Dimension | SUPG | ABae | ARC | G-ARC (Proposed) |
|-----------|------|------|-----|------------------|
| **Output type** | Record / frame set | Scalar / group aggregate | Relevant clips | Candidate clips + recall certificate |
| **Main query type** | Approximate selection | Aggregation with expensive predicates | Relevant clip query | Guaranteed approximate relevant clip query |
| **Quality target** | Precision or recall of selected set | Estimation error / confidence interval | Candidate confidence, recall, efficiency | Clip recall lower bound, GVR, oracle cost |
| **Guarantee type** | High-probability precision / recall target | Confidence interval | Confidence estimate for candidate clips | Target: high-probability clip-level recall certificate |
| **Clip query support** | No | No | Yes | Yes (target) |
| **Clip-level recall guarantee** | No | No | No explicit Pr[ClipRecall >= gamma] >= 1-delta | Target contribution |
| **Distribution-free?** | Sampling-based; proxy quality affects efficiency not validity | Valid under sampling assumptions | Relies on proxy-oracle probabilistic semantics / estimated reliability | Long-term target may be distribution-free; MVP should be stated as finite-population / sampling-based certificate unless assumptions are added |
| **Limitation for G-ARC** | No temporal continuity, IoU, tau, merge/split | Aggregation, not retrieval | Candidate-side confidence does not certify missed clips outside candidates | Not yet validated |

## Detailed Notes

### SUPG

- **What it does:** Given a proxy, an oracle, and a budget, SUPG returns a set of records satisfying a high-probability precision or recall target.
- **Guarantee form:** Pr[Recall >= gamma] >= 1 - delta (or precision variant).
- **Why it does not solve G-ARC:** SUPG's output is a frame set. It does not model temporal continuity, variable-length clips, IoU-based hit semantics, minimum duration tau, merge/split operations, or fragmentation. Frame-level recall does not imply clip-level recall: a method can recall 95% of positive frames but miss entire clips if the missed frames are contiguous at clip boundaries.

### ABae

- **What it does:** Given an aggregation query with an expensive predicate, ABae uses proxy-stratified sampling to estimate the aggregate with a confidence interval.
- **Guarantee form:** Pr[|estimate - truth| <= epsilon] >= 1 - delta.
- **Why it does not solve G-ARC:** ABae targets aggregation (AVG, SUM, COUNT), not retrieval. It returns a scalar estimate, not a set of clips. Clip retrieval is a fundamentally different query type.

### ARC

- **What it does:** ARC supports relevant clip query. Its pipeline includes proxy pruning, temporal clustering, oracle refinement, and label propagation. ARC reports a candidate-side confidence that measures the quality of returned candidates.
- **Confidence interpretation:** ARC's confidence is candidate-side / precision-like. It estimates the fraction of oracle samples inside the candidate region that are positive. This measures "are the returned candidates pointing at real things?" but not "did we find all the real things?"
- **Why it does not solve G-ARC:** ARC optimizes recall empirically but does not provide an explicit guarantee of the form Pr[ClipRecall >= gamma] >= 1 - delta. The P1 smoke experiment shows that candidate-side confidence can be high (0.95-1.00) while actual clip recall is low (0.00-0.31). This is because the confidence metric does not audit non-candidate regions for missed true clips.

### G-ARC (Proposed)

- **What it targets:** Relevant clip query + clip-level recall certification.
- **Target guarantee:** Pr[ClipRecall(C_hat, C*) >= gamma] >= 1 - delta.
- **How it differs from ARC:** G-ARC adds a verification / certification layer that audits non-candidate regions using oracle samples, estimates a conservative upper bound on missed clips, and derives a clip recall lower bound. If the bound certifies the target, the result is returned with a certificate; otherwise, more budget is requested or insufficient budget is reported.
- **Current status:** Not yet validated. The formulation is proposed, the verification sampling idea is initial, and no complete method exists.
