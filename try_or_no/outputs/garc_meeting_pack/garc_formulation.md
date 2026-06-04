# G-ARC Minimal Formulation

## 1. Video and Frame Predicate

A video V is a sequence of N frames: V = <f_1, f_2, ..., f_N>.

Each frame f_i has an **oracle predicate** O(f_i) in {0, 1} that is expensive to evaluate. The oracle is the ground-truth label.

Each frame f_i also has a **proxy score** A(f_i) that is cheap and available for all frames. The proxy is a noisy, inexpensive approximation of the oracle.

**Example:** O(f_i) = 1 iff count_vehicle(f_i) >= K, where count_vehicle requires a large detection model or human annotation. A(f_i) is the output of a lightweight detector, normalized to [0, 1].

---

## 2. True Relevant Clip

A **true relevant clip** is a maximal consecutive run of frames where O(f_i) = 1 and the run length is at least tau frames.

Formally, a true clip c = [s, e] satisfies:
- O(f_i) = 1 for all i in [s, e]
- e - s + 1 >= tau
- Either s = 1 or O(f_{s-1}) = 0
- Either e = N or O(f_{e+1}) = 0

The set of all true relevant clips is denoted C*.

---

## 3. Candidate Clip

The algorithm returns a set of candidate clips C_hat = {c_hat_1, c_hat_2, ..., c_hat_M}.

Each candidate clip c_hat_j = [s_j, e_j] is a variable-length temporal interval with e_j - s_j + 1 >= tau.

---

## 4. Candidate Hit

Given an IoU threshold theta, a candidate clip c_hat **hits** a true clip c if:

IoU(c_hat, c) >= theta

where IoU for intervals is defined as:

IoU([s1, e1], [s2, e2]) = |[s1, e1] intersect [s2, e2]| / |[s1, e1] union [s2, e2]|

For MVP, a true clip c is counted as **recalled** if at least one candidate clip in C_hat has IoU >= theta with c.

---

## 5. Clip Recall

ClipRecall(C_hat, C*) = (number of true clips hit by at least one candidate clip) / (number of true clips)

Formally:

ClipRecall(C_hat, C*) = |{c in C* : exists c_hat in C_hat s.t. IoU(c_hat, c) >= theta}| / |C*|

If C* is empty, ClipRecall is defined as 1.0.

---

## 6. Target Guarantee

Given recall target gamma in [0, 1] and failure probability delta in (0, 1):

**Pr[ClipRecall(C_hat, C*) >= gamma] >= 1 - delta**

The probability is over the randomness of the sampling strategy (which frames are selected for oracle evaluation).

---

## 7. Oracle Budget

The algorithm can call the oracle O on at most B frames total.

The proxy A can be evaluated on all frames at negligible cost.

B is specified as either an absolute count or a fraction of N.

---

## 8. Why Existing Frame Guarantees Do Not Directly Apply

### 8.1 Frame recall does not imply clip recall

A method can achieve 95% frame-level recall but 0% clip-level recall if the 5% missed frames are contiguous and happen to fall at clip boundaries, fragmenting clips below the tau threshold.

### 8.2 Boundary errors can break IoU

Even small boundary errors (shifting a clip start or end by a few frames) can reduce IoU below theta, causing the clip to be counted as missed.

### 8.3 Fragmentation can split clips

If oracle noise causes a few frames in the middle of a true clip to be labeled negative, the clip may be split into two sub-tau segments, both of which are discarded.

### 8.4 Merging can distort IoU

If two nearby true clips are merged into one candidate, the IoU with each individual true clip may be poor, even if the merged candidate covers both.

### 8.5 tau can remove short predicted segments

Predicted positive segments shorter than tau are discarded. This means that even if frame-level recall is high, many short predicted segments may not survive the tau filter, reducing clip recall.

---

## 9. First Mechanism: Verification Sampling Layer

The proposed approach adds a verification / certification layer on top of ARC-style candidate generation.

### Step 1: ARC-Style Candidate Generation

Use proxy thresholding and temporal clustering to generate an initial set of candidate clips. This is the ARC-style pipeline: proxy pruning, temporal merging, oracle refinement on a subset of frames.

### Step 2: Partition the Timeline

Partition the video timeline into three regions:
- **Candidate regions**: frames inside candidate clips
- **Boundary regions**: frames near candidate clip boundaries (within a window of w frames)
- **Non-candidate regions**: all other frames

### Step 3: Verify Candidates and Boundaries

Draw oracle samples from candidate regions and boundary regions. Use these samples to verify that candidates are genuine and boundaries are accurate.

### Step 4: Audit Non-Candidate Regions

Draw oracle samples from non-candidate regions. Use these samples to estimate how many oracle-positive frames exist outside the candidates. This is the key step that addresses the candidate-side blind spot.

### Step 5: Estimate Conservative Missed-Clip Upper Bound

From the non-candidate oracle samples, estimate the total mass of oracle-positive frames in non-candidate regions. Convert this frame-level mass to a conservative upper bound on the number of missed true clips (clips entirely in non-candidate regions).

### Step 6: Derive Clip Recall Lower Bound

ClipRecall_lower_bound = 1 - (estimated_missed_clips_upper_bound / total_true_clips_estimate)

If ClipRecall_lower_bound >= gamma, issue a certificate: Pr[ClipRecall >= gamma] >= 1 - delta.

### Step 7: Adaptive Budget or Insufficient Budget

If the certificate cannot be issued with the current budget, either:
- Allocate more oracle calls to non-candidate regions (adaptive), or
- Report insufficient budget to certify the target.

---

## 10. Open Technical Problems

### 10.1 Missed frame mass to missed clip count conversion

Observing that X% of sampled non-candidate frames are oracle-positive does not directly tell us how many clips were missed. A region with many positive frames may contain one long clip or many short clips. The conversion requires assumptions or additional sampling.

### 10.2 Temporal dependence

Frame labels are temporally correlated. Standard sampling bounds (Hoeffding, CLT) assume independence. Temporal dependence requires either:
- Blocking / batching (treat windows as independent units), or
- Concentration inequalities for Markov chains or mixing processes.

### 10.3 Stratified sampling by proxy score and temporal region

The verification sampling should be stratified by:
- Proxy score (high-proxy non-candidate regions are more likely to contain missed clips)
- Temporal region (near candidates vs. far from candidates)

Optimal stratification is an open problem.

### 10.4 Boundary verification

How many oracle samples are needed near a candidate boundary to certify that the boundary is accurate within epsilon frames? This depends on the local transition rate of the oracle predicate.

### 10.5 Certificate tightness

The conservative bound may be much tighter than the true recall. Measuring and reporting bound tightness (true recall vs. certified lower bound) is important for practical utility.

### 10.6 Adaptive budget allocation

How to allocate the remaining budget between candidate verification, boundary refinement, and non-candidate auditing? This is an exploration-exploitation trade-off.
