# ARC vs G-ARC Concept Note

## 1. Problem: Relevant Clip Query

A video is a sequence of frames f_1, ..., f_N.

A frame predicate O(f_i) is a boolean condition evaluated by an oracle, such as count(vehicle) >= K.

A **true relevant clip** is a maximal consecutive run of oracle-positive frames with length >= tau. Formally, C = [f_s, f_e] where O(f_i) = 1 for all i in [s, e], e - s + 1 >= tau, and the run cannot be extended.

A **candidate clip** C_hat is a clip returned by the system. A candidate clip **hits** a true clip C_star if IoU(C_hat, C_star) >= theta, where theta is the IoU hit threshold (e.g., 0.5).

**Clip recall** is the fraction of true relevant clips that are hit by at least one candidate clip:

ClipRecall = |{C_star : exists C_hat s.t. IoU(C_hat, C_star) >= theta}| / |C_star|

## 2. ARC High-Level Idea

*This note describes ARC at a high level. It is not an exact implementation description.*

ARC targets relevant clip queries over large-scale video repositories. Its workflow can be described as:

1. **Proxy pruning:** Run a cheap proxy model over all frames. Use proxy outputs to identify regions unlikely to satisfy the predicate.
2. **Candidate clip formation:** Form initial candidate clips from proxy-positive regions, exploiting temporal clustering and continuity.
3. **Oracle refinement:** Use a stronger oracle model on candidate boundaries and uncertain regions to refine candidate clips.
4. **Candidate-side confidence:** Estimate a confidence score for each returned candidate clip, reflecting how likely it is to be a true hit.
5. **Return under budget:** Return candidate clips ranked by confidence, subject to an oracle call budget.

ARC's efficiency goal: minimize oracle cost while maintaining high confidence on returned candidates.

## 3. ARC's Limitation for Our Target

ARC's confidence is **candidate-side / precision-like**. It answers:

> "Are the returned candidate clips reliable?"

It does **not** answer:

> "How many true relevant clips were missed outside the candidate set?"

High candidate confidence can coexist with low clip-level recall. If the proxy has high precision but low recall, ARC may return a small set of high-confidence candidates while missing many true clips in regions where the proxy failed to fire.

This is the key blind spot for recall certification. ARC does not provide a mechanism to audit the non-candidate region for missed clips.

## 4. G-ARC Target

G-ARC targets high-probability clip-level recall certification:

**Pr[ClipRecall(C_hat, C_star; theta, tau) >= gamma] >= 1 - delta**

where:
- C_hat is the returned candidate clip set;
- C_star is the true relevant clip set under the oracle;
- theta is the IoU hit threshold;
- tau is the minimum clip length;
- gamma is the target clip recall;
- delta is the allowed failure probability.

This differs from candidate confidence in a fundamental way: candidate confidence says "the clips I returned are good"; recall certification says "I did not miss too many true clips." The former is about precision of returned results; the latter is about coverage of the true set.

## 5. Proposed G-ARC Mechanism

G-ARC adds a verification sampling layer on top of ARC-style candidate generation:

1. **ARC-style candidate generation:** Use proxy scores to generate initial candidate clips (same as ARC).
2. **Candidate verification:** Use limited oracle calls to verify whether candidate clips are true hits.
3. **Boundary verification:** Use oracle calls near candidate boundaries to check if clips extend further.
4. **Non-candidate audit:** Sample frames from non-candidate regions using verification sampling. Use oracle labels on sampled frames to estimate how many true clips may exist outside candidates.
5. **Missed clip upper bound:** From the audit, derive a conservative upper bound on the number of missed true clips.
6. **Recall lower bound:** Combine verified candidates and missed-clip upper bound to derive a clip recall lower bound.
7. **Return with certificate:** Return candidate clips with the recall lower bound, or report that the oracle budget is insufficient to certify the target gamma.

## 6. Role of video_to_supg_csv.py

The script `video_to_supg_csv.py` only builds real-video frame tables. It does not implement ARC or G-ARC. It enables later experiments by providing per-frame proxy and pseudo-oracle records.

## 7. Conservative Claims Allowed

- This pipeline enables real-video proxy/pseudo-oracle experiments.
- YOLOv8n and YOLOv8x show a real proxy/pseudo-oracle quality gap on test.mov.
- This gap can be amplified by tau-based clip constraints.
- The result motivates recall certification.

## 8. Claims Not Allowed

- This reproduces ARC.
- ARC fails.
- G-ARC is solved.
- YOLOv8x is human ground truth.
- The current experiment proves distribution-free guarantee.
