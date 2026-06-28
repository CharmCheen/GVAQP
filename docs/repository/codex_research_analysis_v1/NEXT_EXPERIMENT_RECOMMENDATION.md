# Next Experiment Recommendation

## Candidate Direction Comparison

### A. Ego-Path-Conditioned Geometric Proxy

- Purpose: Build a cheap predicate-conditioned proxy that scores whether object trajectories intersect the ego future path.
- Why it follows from current evidence: V13.9/V13.10 show raw vehicle count and motion energy mostly capture traffic density, not ego-path intrusion.
- Expected benefit: Better alignment with `O_enter_ego_path_v0` while staying in the cheap-proxy layer.
- Risk: Can become perception engineering; lane/path estimation may be brittle and time-consuming.
- Estimated cost: Medium. CPU analysis may be possible if existing detections/tracks exist; new detector runs may require GPU if tracks are missing.
- Required inputs: Center10 anchor grid, existing YOLO proxy features, object boxes if available, frame timestamps, optional lane/ego-path estimate.
- Proposed method: Reuse existing proxy CSV schemas; compute scores such as object center entering ego corridor, lateral motion toward center path, time-to-path-intersection, and near-field trajectory conflict. Do not use V13.8 labels for feature design beyond final evaluation.
- Metrics: Direct event-discovery recall, temporal-overlap recall, OracleBest efficiency, positive-anchor precision, recall-per-call, proxy uniqueness, leakage checks.
- Pass/fail criteria: Pass if B=20 event recall improves by at least +0.10 over random and exceeds current best static 0.137 by a meaningful margin; fail if it remains traffic-density-like or below uniform.
- AQP framing: Helps if treated as one candidate generator class under common AQP evaluation. Weakens framing if it becomes a bespoke driving-event detector.

### B. 8B VLM Cascade / Mid-Fidelity Oracle

- Purpose: Test whether a cheaper semantic scorer can rank anchors before 32B oracle verification.
- Why it follows from current evidence: Cheap nonsemantic proxies fail; the target predicate is semantic.
- Expected benefit: A natural multi-fidelity AQP story: cheap proxy, mid-cost semantic scorer, expensive oracle.
- Risk: Requires new VLM calls, likely GPU, and could be expensive. It also may reproduce 32B biases rather than provide an independent useful signal.
- Estimated cost: Medium to high.
- Required inputs: The 399 center10 anchors and a fixed 8B prompt/scoring rubric.
- Proposed method: Run a small pilot first, e.g. stratified subset only if explicitly authorized; compare 8B score/rank with 32B labels; simulate cascade budgets.
- Metrics: Rank correlation with V13.8 labels, event recall at B=10/20/40, cost-normalized recall, disagreement analysis, abstain/error rate.
- Pass/fail criteria: Pass if 8B-based ranking materially beats uniform and current YOLO/motion proxies at B=20 and has manageable disagreement. Fail if it collapses to traffic density or high disagreement.
- AQP framing: Strong if cast as multi-fidelity oracle allocation. Weak if it becomes model benchmarking without query-plan implications.

### C. RoI-SigLIP or CLIP Representation Scorer

- Purpose: Test whether visual embeddings can provide a semantic conflict score cheaper than VLM oracle calls.
- Why it follows from current evidence: A representation scorer may capture scene semantics missed by raw YOLO counts.
- Expected benefit: Could provide a reusable candidate generator without full VLM inference.
- Risk: If prototypes are selected from V13.8 positives, leakage can inflate results. Generic CLIP may still prefer traffic density or salient objects.
- Estimated cost: Medium. Depends on local model availability and GPU/CPU feasibility.
- Required inputs: Center10 clips or frames, local embedding model, leakage-safe positive/negative prompts or external exemplars.
- Proposed method: Use text prompts or external non-V13 examples for conflict-like scenes; optionally use RoI crops around tracked participants; evaluate scores against V13.8 only after scores are frozen.
- Metrics: Direct event-discovery recall, temporal-overlap recall, OracleBest efficiency, precision at top B, rank uniqueness, failure-case categories.
- Pass/fail criteria: Pass if it beats uniform and current proxies at B=20/B40 without label leakage; fail if top-ranked anchors are just dense traffic.
- AQP framing: Useful as an L1 candidate generator, but must avoid becoming representation-learning research.

### D. More Adaptive Query Execution

- Purpose: Improve allocation by updating future selections after observations.
- Why it follows from current evidence: Static methods stall, but V13.10 shows naive local adaptive expansion fails.
- Expected benefit: Could be the most DB/AQP-like method if it uses principled uncertainty, coverage, or posterior updates.
- Risk: More local expansion without a new signal is already contradicted by V13.10.
- Estimated cost: Low to medium for simulation, higher if it depends on new scores.
- Required inputs: Stronger base score or new runtime state signal; existing V13.8 labels for evaluation only.
- Proposed method: Defer until a better scorer exists. Then test adaptive rules based on uncertainty, cluster diversity, event-span posterior, or disagreement, not simple neighbor boost.
- Metrics: Event recall, efficiency ratio, redundant-call rate, calls per new event, same-base delta.
- Pass/fail criteria: Pass if adaptive beats its own static base at most budgets and improves best-static efficiency; fail if same-base hurts again.
- AQP framing: Strong only after a meaningful runtime update signal exists.

### E. Metric Reconciliation / Evaluation Cleanup

- Purpose: Ensure conclusions consistently distinguish temporal-overlap coverage from direct event discovery.
- Why it follows from current evidence: V13.10 resolved a V13.9/V13.10 mismatch and showed field-name mistakes can mislead conclusions.
- Expected benefit: Prevents future overclaiming and makes reports paper-ready.
- Risk: Low research upside; no new method.
- Estimated cost: Low.
- Required inputs: Existing V13.9/V13.10 tables and code.
- Proposed method: Standardize metric names in summaries; add validation tests comparing direct and overlap definitions where applicable.
- Metrics: Deterministic equality checks, table schema audit, report consistency.
- Pass/fail criteria: Pass if future reports cannot accidentally cite IoU-zero columns as primary recall.
- AQP framing: Necessary hygiene, but not an immediate research experiment unless inconsistencies remain.

### F. Broader Benchmark Construction / Second Video

- Purpose: Test whether V13.6/V13.8 observations generalize beyond `realcartest.mp4`.
- Why it follows from current evidence: All V13 results are single-video only.
- Expected benefit: Reduces the largest external-validity risk.
- Risk: Requires new VLM calls and possibly GPU; positive rate may be too low/high; dataset access can dominate.
- Estimated cost: High if full 32B oracle is needed; medium if starting with a small construction-sensitivity pilot.
- Required inputs: A second long driving video with temporal continuity and permissions.
- Proposed method: Repeat staged process: audit, center10 grid, small construction/prompt pilot, then full oracle only if nondegenerate.
- Metrics: Abstain rate, positive rate, stitched event count, event completeness, static baseline recall.
- Pass/fail criteria: Pass if prompt remains stable, event count is nontrivial, and selection evaluation is meaningful; fail if degenerate or inaccessible.
- AQP framing: Strong benchmark contribution, but not a method by itself.

### G. Human Sanity-Check Label Audit

- Purpose: Estimate whether Qwen3-VL-32B labels align with human judgment.
- Why it follows from current evidence: All current labels are VLM-oracle-relative; no human truth exists.
- Expected benefit: Calibrates the oracle and protects claims.
- Risk: Does not improve query execution recall; may expose oracle instability.
- Estimated cost: Medium human time, low compute.
- Required inputs: Small stratified set of V13.8 positives/negatives and a labeling rubric.
- Proposed method: Sample 20-50 clips across positives, high-proxy negatives, and random negatives; compare human labels to 32B labels.
- Metrics: Agreement, false positive/false negative categories, boundary disagreement.
- Pass/fail criteria: Pass if agreement is high enough to keep VLM-oracle-relative work credible; fail if label semantics diverge.
- AQP framing: Important later for claim calibration, but not the immediate blocker for budgeted AQP method development.

## Ranking

1. Ego-path-conditioned geometric proxy.
2. RoI-SigLIP or CLIP representation scorer.
3. 8B VLM cascade / mid-fidelity oracle.
4. Broader benchmark construction / second video.
5. Metric reconciliation / evaluation cleanup.
6. Human sanity-check label audit.
7. More adaptive query execution.

This ranking prioritizes finding a better selection signal before spending more effort on adaptive logic or certificates. It does not automatically choose 8B because cheap proxy failed: 8B is promising, but it requires new VLM calls and should follow or be paired with lower-cost signal tests. It does not automatically choose CLIP/SigLIP unless the scorer is designed to avoid traffic-density leakage. It does not recommend more simple local adaptive expansion because V13.10 already found that such mechanisms hurt under current signals.

## Concrete Plan for the Next 2-3 Experiments

### Experiment 1: EgoPathGeometryProxySmoke

- Goal: Test whether predicate-conditioned geometry beats traffic-density proxies.
- Inputs: Existing center10 anchor grid, available YOLO/object geometry features, frame timestamps, V13.8 labels for evaluation only.
- Method: Build a leakage-safe geometric score that approximates ego corridor entry or object motion toward ego path. Freeze scores before evaluation.
- Outputs: New independent output directory with manifest, schema, score table, event-recall tables, and report.
- Metrics: Direct event-discovery recall, temporal-overlap recall, OracleBest efficiency, precision at B=5/10/20/40, proxy score uniqueness.
- Pass criteria: B=20 event recall exceeds current best static 0.137 and beats random by at least +0.10; B=40 improves over 0.216 or has clearer efficiency/precision tradeoff.
- Fail criteria: Top anchors are dense traffic without ego-path entry; B=20 remains near uniform/random.
- Expected interpretation: A pass supports a cheap predicate-conditioned L0 proxy. A fail strengthens the case for semantic L1/L2 scoring.

### Experiment 2: RepresentationScorerLeakageSafePilot

- Goal: Test a representation-based candidate generator without reusing V13.8 labels for ranking design.
- Inputs: Center10 clips/frames; locally available CLIP/SigLIP-like model if present; external text prompts or non-V13 exemplars.
- Method: Compute frozen image/video or RoI embeddings; score anchors by similarity to ego-path conflict prompts or exemplars; evaluate only after scores are finalized.
- Outputs: Score table, leakage audit, budget curves, failure-case report.
- Metrics: Direct event-discovery recall, temporal-overlap recall, OracleBest efficiency, rank correlation with V13.8 labels, density-bias audit.
- Pass criteria: Beats uniform and existing proxies at B=20 and B=40 without selecting mostly dense traffic.
- Fail criteria: No improvement, low score uniqueness, or evidence that ranking is label-leaked.
- Expected interpretation: A pass provides an L1 candidate generator; a fail suggests a mid-fidelity semantic oracle may be needed.

### Experiment 3: 8BFirstPassCascadePilot

- Goal: Test whether mid-fidelity VLM scoring can support oracle allocation.
- Inputs: Center10 anchors and a fixed 8B prompt. This requires explicit authorization because it involves new VLM calls and likely GPU.
- Method: Start with a small stratified pilot rather than full 399-anchor inference. Compare 8B labels/scores to V13.8 32B labels and simulate top-B 32B verification.
- Outputs: Pilot labels, disagreement table, cascade simulation, cost-normalized recall report.
- Metrics: Agreement with 32B, direct event-discovery recall at simulated B, abstain/error rate, cost per recovered event.
- Pass criteria: 8B ranking materially improves over uniform/current proxies and disagreement is interpretable.
- Fail criteria: High disagreement, no rank signal, or cost not meaningfully below 32B full scan.
- Expected interpretation: A pass supports a multi-fidelity AQP story; a fail argues for benchmark expansion or certificate-focused work rather than VLM cascade.
