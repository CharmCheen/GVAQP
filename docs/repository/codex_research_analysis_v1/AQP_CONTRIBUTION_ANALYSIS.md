# AQP Contribution Analysis

## Overall Assessment

The project currently has credible AQP infrastructure and a credible benchmark/evaluation problem, but it does not yet have a positive AQP method contribution. The strongest defensible claim is that a VLM-oracle-relative single-video event benchmark and evaluation harness now exist, and that cheap static proxies plus simple adaptive search fail under low oracle budgets. That is useful, but it is not yet a publishable database/AQP contribution by itself unless the paper is explicitly framed around benchmark construction and negative results.

The core AQP contribution promised by the project is a proxy-agnostic statistical guarantee layer. The audit evidence shows this layer is conceptually specified and historically prototyped, but it has not been validated on the current V13.8 full oracle. Current results therefore support `PROBLEM_AND_EVALUATION_ESTABLISHED` more strongly than `STRONG_AQP_STORY`.

## 1. Event-Level Approximate Selection Query Over Long Video

- Strength: Clear DB-style query abstraction: retrieve event-containing clips from long video under an expensive semantic predicate and budget.
- Weakness: Currently demonstrated on one 66.5-minute video only.
- Evidence from repository: V13.8 full oracle has 399 anchors and 51 stitched VLM-defined events; V13.9/V13.10 evaluate budgeted selection over these events.
- What is still missing: A second video or broader benchmark and a positive method that improves event discovery at practical budgets.
- Strong enough for DB/AQP paper: Not alone. Strong as problem setup and benchmark machinery.

## 2. Expensive Semantic Predicate Evaluation With VLM Oracle

- Strength: The expensive-oracle setting is concrete: Qwen3-VL-32B over 10s video anchors, about 74 minutes for 399 calls in V13.8.
- Weakness: The oracle is not human ground truth, and stability has not been audited on repeated clips.
- Evidence from repository: V13.8 final report; V13.6 prompt repair; V13.8 0% abstain and 399/399 successful calls.
- What is still missing: Human sanity labels or repeated-call stability audit; second-video prompt validation.
- Strong enough for DB/AQP paper: Moderate as an oracle-relative experimental setting, not as human-truth risk-event detection.

## 3. Clip Construction / Granularity Selection, Especially Center10

- Strength: V13.6 gives a clean engineering result: center10 halves full-video calls versus fixed 5s and improves positive yield on the construction sample.
- Weakness: This is a benchmark-construction contribution, not the main AQP statistical contribution.
- Evidence from repository: V13.6 final report: center10 56% positive rate versus fixed5 44%, 399 versus 798 full-video calls, 0% abstain, 100% complete events.
- What is still missing: Validation on another video and on more diverse event durations.
- Strong enough for DB/AQP paper: As a supporting design choice, yes. As the central contribution, probably too narrow.

## 4. Proxy-Oracle Alignment Audit

- Strength: The project has strong negative evidence that raw traffic-density proxies are misaligned with ego-path intrusion events.
- Weakness: The tested proxy family is narrow; no representation or mid-fidelity semantic proxy has been tested.
- Evidence from repository: V13.9 shows B=20 best method is uniform with event recall 0.137 and proxy delta +0.059 versus random; V13.10 static efficiency is 0.350 at B=20 and 0.275 at B=40.
- What is still missing: A more targeted proxy family and an alignment analysis that separates traffic density, object motion, ego path, and semantic conflict.
- Strong enough for DB/AQP paper: Useful as a diagnostic contribution, not yet sufficient as a method.

## 5. OracleBest@B and Efficiency-Ratio Evaluation

- Strength: V13.10 provides a clear upper-bound denominator for event discovery and a compact way to show wasted budget.
- Weakness: OracleBest is simple here because every positive anchor maps to exactly one stitched event; it may be less trivial on denser or overlapping event sets.
- Evidence from repository: V13.10 report and `oracle_upper_bound_v13_10.csv`; OracleBest@20 = 0.392 and best static efficiency at B=20 = 0.350.
- What is still missing: Generalization to multi-event anchors or overlapping events and use in a positive method comparison.
- Strong enough for DB/AQP paper: Good evaluation contribution if paired with a method or broader benchmark.

## 6. Static Proxy Failure as Motivating Evidence

- Strength: The failure is well documented and supersedes the earlier optimistic V13.7 replay.
- Weakness: Negative evidence does not itself establish a new AQP algorithm.
- Evidence from repository: V13.7 biased subset; V13.9 full-reference failure; V13.10 efficiency audit.
- What is still missing: A follow-up showing what kind of signal or allocation strategy can close part of the OracleBest gap.
- Strong enough for DB/AQP paper: Strong motivation; insufficient as the main contribution.

## 7. Multi-Fidelity Oracle Allocation

### L0 Cheap Proxy

- Strength: Existing YOLO/motion/geometry features are available for all 399 anchors.
- Weakness: Current L0 proxy is too weak for the predicate.
- Evidence: V13.9/V13.10.
- Missing: Better L0 features that are predicate-conditioned, especially ego-path geometry.
- Paper strength: Baseline layer only.

### L1 Representation Scorer

- Strength: Could bridge cheap perception and semantic oracle by ranking conflict-like regions without full VLM inference.
- Weakness: No local representation results are present; V12.1 reports representation candidate unavailable.
- Evidence: Audit recommendation and V12.1 representation availability report.
- Missing: CPU/GPU-feasible embedding pipeline, leakage-safe prompt/prototype construction, and full-reference evaluation.
- Paper strength: Potentially useful if it improves ranking without training on the oracle labels.

### L2 8B VLM

- Strength: More semantically aligned than YOLO and cheaper than 32B in principle.
- Weakness: No 8B labels or cascade results in the audited evidence; would require new VLM calls.
- Evidence: Recommended in agent loop and evidence pack as a next candidate, not as a result.
- Missing: Small controlled pilot and cost/quality comparison against 32B.
- Paper strength: Potentially strong for multi-fidelity AQP if budget and calibration are quantified.

### L3 32B VLM Oracle

- Strength: Current fixed operational oracle exists and is complete for realcartest center10.
- Weakness: Human calibration and stability are missing.
- Evidence: V13.8.
- Missing: Human sanity audit or repeated-call stability.
- Paper strength: Acceptable for oracle-relative AQP evaluation if carefully qualified.

## 8. Adaptive Query Execution

- Strength: The project has already tested adaptive mechanisms and diagnosed why they fail under current proxies.
- Weakness: The tested adaptive rules are simple local expansion/priority boost; they lack a new state update signal.
- Evidence from repository: V13.10 adaptive simulation and sensitivity addendum.
- What is still missing: A better base scorer or adaptive state, such as uncertainty, semantic disagreement, cluster coverage, or learned event-boundary likelihood.
- Strong enough for DB/AQP paper: Not currently. More adaptive search should not be the immediate next step without a new signal.

## 9. Recall Auditing / Certificate Layer

- Strength: This is the most database-native contribution: a conservative oracle-relative recall certificate independent of proxy quality.
- Weakness: It has not been run successfully on the current V13.8 reference, and previous certificate attempts were underpowered or pseudo-event-based.
- Evidence from repository: V12.1 report says `NO_CERTIFICATE_YET`; Phase 0.6 power report suggests hundreds of events are needed for non-vacuous certificates under its assumptions.
- What is still missing: A valid certificate run on a suitable benchmark, or an honest proof that the current benchmark is too small and a scaling plan is needed.
- Strong enough for DB/AQP paper: Conceptually yes, empirically not yet.

## 10. Avoiding Pure Video-Understanding Framing

- Strength: The audit and protocol clearly warn against turning the project into "build a better driving-event detector."
- Weakness: Many plausible next steps, including ego-path geometry, CLIP/SigLIP, and 8B cascades, can drift into perception engineering if not constrained.
- Evidence from repository: V12.1 protocol and open risks.
- What is still missing: Experiments should be framed as testing classes of candidate generators under the same AQP evaluation and certificate machinery, not as optimizing a domain detector.
- Strong enough for DB/AQP paper: This framing is essential. The contribution should be "oracle allocation and conservative evaluation under expensive semantic predicates," not "new traffic-event recognizer."

## Critical Judgment

The current project is not ready for a full method-development claim or paper outline. It is also not a dead end. The V13.8/V13.9/V13.10 chain provides an unusually clean negative result: a fixed VLM oracle exists; cheap proxies and naive adaptive search fail; an oracle upper bound shows there is recoverable structure if a better selection signal exists.

The immediate research need is a positive signal source or a rigorous benchmark expansion. Without one, the AQP story remains infrastructure plus negative evidence. With one, the OracleBest and certificate machinery can become a real DB/AQP contribution.
