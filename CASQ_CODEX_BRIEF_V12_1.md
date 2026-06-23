# CASQ / G-ClipAQP Codex Brief V12.1

## Changelog: V12 -> V12.1

V12 added the Phase 1 external-data and candidate-feasibility constraints.
V12.1 keeps that structure but tightens several implementation details that
would otherwise cause Codex to run an outdated Phase-0-only protocol or
overstate Nexar-derived results.

Critical fixes:

```text
1. Section 0 no longer says the whole document is Phase-0-only.
2. Section 22 now instructs Codex to read V12.1 and distinguish Phase 0
   from Phase 1+ runs.
3. Section 26 now treats Nexar collision/alert metadata as a default
   LOOSE_APPROXIMATION unless a bounded audit supports a stronger mapping.
4. Section 27.5 now defines default thresholds for AGREES_WELL,
   PARTIAL_DISAGREEMENT, and UNRELIABLE.
5. Section 28.3 now states the Phase 0.6 power finding more accurately:
   around 200 events may begin to help, while roughly 500+ events were
   needed for consistently non-vacuous certificates in that simulation.
6. New Section 31 adds a Phase 1 candidate-feasibility v2 implementation
   prompt, including the required-if-local representation-based candidate.
```

---

## Changelog: V11 -> V12

V11 was written for Phase 0 only (local/synthetic data, VLM assumed as the
oracle). The project has since moved into Phase 1 (external datasets,
Nexar-derived labels, real video, advisor review). Several gaps surfaced
during that work were previously discussed only in chat or buried in
phase-specific reports, which means Codex had no way to enforce them — an
unwritten rule is not a rule. V12 makes these explicit.

Critical fixes (regression risk — apply to any new implementation,
including candidate feasibility v2):

```text
1. Section 23 now includes the UCB/LCB bound invariants found necessary
   during the Phase 0 repair pass.
2. Section 11 now requires row-level persistence of block-audit data,
   not trial-level aggregates only.
```

New constraints (Phase 1 external-data and candidate-feasibility scope):

```text
3. Section 9.9 adds a fourth oracle role: external label oracle.
4. New Section 26: External Label <-> Predicate Mapping Requirement.
5. New Section 27: Bounded VLM Micro-Audit Protocol.
6. New Section 28: Candidate Hyperparameter Selection Protocol
   (Design / Report Split).
7. New Section 29: Selectivity Stratification Requirement.
8. New Section 30: Single-Dataset Claim Scope Limitation.
```

All V11 content is otherwise unchanged. Where V11 says "Phase 0 only,"
that scope label is now historical — it describes what Phase 0 covered,
not a restriction on later phases. Phase 1+ protocols are layered on top
via the new sections below; the Phase-0-specific procedural sections
(10-20) are left as a record of that phase and do not need to be rewritten.

---

## 0. Purpose

This document is the fixed reference for Codex implementation.

The project target is a DB/AQP-style research direction:

> Clip-level approximate selection query with recall certificates over long videos.

The goal is not to design a stronger driving-event proxy. STRIVE-D, iFinder, LAVA, AVA, embedding retrieval, VLM zero-shot scoring, YOLO count, motion heuristics, and random ranking are all treated as candidate generators.

The core contribution is a proxy-agnostic statistical guarantee layer:

> Given any candidate generator, an expensive oracle, oracle budget B, target recall gamma, and failure probability delta, can the system return variable-length clips and provide a conservative clip-level recall certificate?

This document now covers both the historical Phase 0 protocol and the Phase 1+
external-data / real-video candidate-feasibility protocols. Phase-0-specific
procedural sections remain in the document for reproducibility, but they do not
limit later phases.

Codex must choose the applicable protocol according to the task:

```text
Phase 0 runs:
  follow Sections 10-20, plus the shared statistical constraints in
  Sections 3-9, 11.1, and 23.

Phase 1+ external-data or candidate-feasibility runs:
  follow Part II, especially Sections 26-31, plus the shared statistical
  constraints in Sections 3-9, 11.1, and 23.
```

Global restrictions remain in force unless a later section gives a bounded,
explicit exception:

Do not train models without explicit approval.
Do not build a new perception stack.
Do not run large-scale VLM.
Do not download large datasets without explicit approval.
Do not reuse diagnostic / pilot / repair samples for final certification.
Do not fabricate event boundaries.

---

## 1. Project Paths

The project root is expected to be:

```bash
/qiuyeqing/llama_prl/G-ARC
```

Existing VLM / proxy work is expected under:

```bash
/qiuyeqing/llama_prl/G-ARC/test_vlm
```

Phase 0 output directory:

```bash
/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase0_v1
```

Codex should create the following structure if missing:

```bash
/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase0_v1/
  data_audit/
  scripts/
  tables/
  figures/
  reports/
  logs/
```

The final report must be:

```bash
/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase0_v1/reports/PHASE0_REPORT.md
```

The report must end with exactly one of:

```text
FINAL_DECISION: GO
FINAL_DECISION: NO_GO
FINAL_DECISION: PARTIAL_GO_NEED_CLEAN_EVENT_BOUNDARIES
```

---

## 2. Existing Data to Inspect

Codex should first check whether these files or directories exist:

```bash
/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded/vlm_labels_conservative.csv

/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/roadclip_budget_v2/vlm_oracle_expanded/roadclip_v2_audit_package.tar.gz

/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/human_audit_conservative_vlm_68clips.tar.gz

/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/kinematic_proxy/clips

/qiuyeqing/llama_prl/G-ARC/test_vlm/focused_validation_outputs
```

If these paths do not exist, Codex should search under:

```bash
/qiuyeqing/llama_prl/G-ARC
```

using patterns:

```bash
*vlm_labels*.csv
*conservative*.csv
*budget*
*proxy*
*human_audit*
*clips*
*audit*
*event*
```

Codex must not assume files exist. It must audit the filesystem and report what is available.

---

## 3. Core Query Semantics: CASQ

CASQ means Clip-level Approximate Selection Query.

Example query:

```sql
SELECT clip
FROM   long_videos
MATCH  EVENT "object enters ego path and creates potential conflict"
USING  CANDIDATE_GENERATOR <pluggable>
WITH   IOU THRESHOLD theta
ORACLE <fixed oracle contract>
ORACLE COST BUDGET B
TARGET RECALL gamma
WITH   FAILURE PROBABILITY delta
CERTIFY BY BLOCK_EVENT_AUDIT;
```

Candidate generator can be any of:

```text
STRIVE-D-style symbolic retriever
YOLO count / motion score
embedding retriever
VLM zero-shot scorer
agentic video index
existing video analytics system
random baseline
```

Candidate generator quality affects cost-to-certificate, not certificate validity.

A weak proxy may make certification expensive or impossible under the given budget. It must not make a valid certificate incorrect.

If the system cannot certify recall under the budget, the correct output is:

```text
NO_CERTIFICATE
```

---

## 4. Data Model

Each video has a timeline.

A returned clip is an interval:

```text
C = [s, e]
```

Under a fixed oracle contract O, the oracle-enumerated event set is:

```text
E^O = {E_1^O, E_2^O, ..., E_m^O}
```

Each oracle-enumerated event is also an interval:

```text
E_j^O = [s_j, e_j]
```

A returned clip R_k hits event E_j^O if:

```text
IoU(R_k, E_j^O) >= theta
```

Oracle-relative clip-level recall:

```text
Recall^O(R) =
|{E_j^O : exists R_k in R, IoU(R_k, E_j^O) >= theta}| / |E^O|
```

The target certificate is:

```text
Pr[Recall^O(R_final) >= gamma] >= 1 - delta
```

The probability is over the system-controlled random audit sampling design.

All guarantees are oracle-relative unless a human-adjudicated gold set is explicitly used and oracle error is corrected.

---

## 5. Core Statistical Quantities

Partition each video timeline into auditable blocks:

```text
B = {B_1, ..., B_N}
```

For each block:

```text
Y_i^O = number of oracle-enumerated events in B_i
M_i^O = number of oracle-enumerated events in B_i missed by returned clips R
```

Global totals:

```text
Y^O = sum_i Y_i^O
M^O = sum_i M_i^O
Recall^O(R) = 1 - M^O / Y^O
```

The system estimates conservative bounds:

```text
UCB(M^O)
LCB(Y^O)
```

and outputs:

```text
LCB_recall^O = 1 - UCB(M^O) / LCB(Y^O)
```

Certification succeeds if:

```text
LCB_recall^O >= gamma
```

If `LCB(Y^O)` is zero or too small, the system must return no certificate.

Do not use the phrase “true event count” unless referring to human-adjudicated labels. Use:

```text
oracle-enumerated event count
oracle-positive event
event under fixed oracle contract
```

---

## 6. Design-based Finite-population View

The blocks are treated as a finite population.

Randomness comes from the system-controlled audit sampling design, not from assuming iid video data.

Block independence is not a core validity assumption. Temporal correlation affects variance, confidence-bound tightness, and cost-to-certificate.

If bounds are too loose, the system returns no certificate.

---

## 7. Statistical Validity Contract

This section contains hard constraints. Codex must implement these constraints in scripts and checks.

### 7.1 Sample Split Invariant

Every audited block must carry these fields:

```text
sample_split
used_for_design
used_for_repair
used_for_certificate
```

Allowed `sample_split` values:

```text
pilot
diagnostic
certification
gold_eval
```

A sample can be used for final certificate only if:

```text
sample_split == certification
used_for_design == false
used_for_repair == false
used_for_certificate == true
```

Any function computing final certificate must reject samples where:

```text
sample_split != certification
or used_for_design == true
or used_for_repair == true
```

### 7.2 No Reuse for Repair and Certification

Diagnostic / pilot samples may be used to:

```text
choose block size
choose strata
choose sampling allocation
discover missed-event patterns
decide repair rules
estimate oracle cost
```

Diagnostic / pilot samples must not be used to compute final:

```text
UCB(M^O)
LCB(Y^O)
LCB_recall^O
```

If repair is performed, the system must:

```text
1. use diagnostic samples to choose repair;
2. apply repair;
3. freeze R_final;
4. draw fresh certification samples;
5. compute final certificate only from certification samples.
```

Forbidden procedure:

```text
1. use sampled blocks to find missed events;
2. repair those exact missed events;
3. reuse the same sampled blocks to compute final certificate.
```

This creates optimistic bias and invalidates the failure probability delta.

### 7.3 Adaptive Sampling

Certified mode supports two safe designs.

First, non-adaptive certification design:

```text
freeze R_final, strata, inclusion probabilities, and audit budget before drawing certification samples.
```

Second, two-stage sample splitting:

```text
use S_pilot to choose design;
draw fresh S_cert after design is fixed;
compute final certificate only from S_cert.
```

Multi-round adaptive certified mode is not allowed in Phase 0 unless delta is explicitly allocated across rounds or an anytime-valid confidence sequence is implemented.

Phase 0 should avoid multi-round adaptive certification.

### 7.4 No Certificate Is Valid Output

If the system cannot certify recall under the given budget, it must output:

```text
NO_CERTIFICATE
```

It must not lower standards, reuse samples, or silently switch to empirical-only reporting.

---

## 8. Event Ownership, Padding, and Deduplication

Audit uses padded blocks:

```text
B_i^+ = [start(B_i) - p, end(B_i) + p]
```

Event counting uses the core block `B_i`.

Canonical event ownership:

```text
canonical_point(E^O) = midpoint(E^O)
E^O belongs to B_i iff canonical_point(E^O) in B_i
```

If padding overlap causes duplicate enumeration, deduplicate by stable event key:

```text
event_key = (
  video_id,
  event_type,
  involved_object_id_or_description,
  rounded_event_start,
  rounded_event_end
)
```

Padding `p` must be specified in the oracle contract.

Default conservative rule:

```text
p >= expected_max_event_duration
```

If an event is truncated or boundary is uncertain, the oracle must return:

```text
boundary_status = truncated / uncertain / abstain
```

Certified mode must handle such events conservatively or require adjudication.

---

## 9. Oracle Contract: O_enter_ego_path_v0

### 9.1 Query Name

```text
O_enter_ego_path_v0
```

### 9.2 Query Definition

Detect whether a road user enters the ego vehicle’s future driving path and creates potential spatial conflict or requires ego attention.

The guarantee is oracle-relative unless human adjudication is added.

### 9.3 Positive Criteria

Label positive if all conditions hold:

```text
1. A vehicle, pedestrian, cyclist, or other road user is visible.
2. The object starts outside or near the boundary of the ego path.
3. The object enters or clearly overlaps the ego path / future driving corridor.
4. The event is temporally localized within the audited clip or block.
5. The object is sufficiently close or trajectory-relevant to ego motion to require attention.
```

### 9.4 Negative Criteria

Label negative for:

```text
1. normal following traffic;
2. static roadside objects;
3. far-away crossing without ego-path conflict;
4. dense traffic with no identifiable entering event;
5. parked vehicles with no motion into ego path;
6. low-speed irrelevant maneuvers without spatial conflict.
```

### 9.5 Abstain Criteria

Return abstain if:

```text
1. camera view is too poor;
2. object is too occluded;
3. event boundary cannot be localized;
4. ego path is ambiguous;
5. clip truncation prevents reliable judgment.
```

### 9.6 Input

Input is one audited block or candidate clip with optional padding.

Default:

```text
core_block_length: 10s / 15s / 30s depending on experiment
padding: >= expected_max_event_duration
frame_sampling: fixed, e.g. 1 fps or uniformly sampled keyframes
```

The exact sampling policy must be logged.

### 9.7 Output Schema

Oracle must output:

```json
{
  "label": "positive | negative | abstain",
  "event_start": "seconds or null",
  "event_end": "seconds or null",
  "event_type": "enter_ego_path",
  "involved_object": "vehicle | pedestrian | cyclist | other | unknown",
  "ego_relevant": true,
  "boundary_status": "ok | uncertain | truncated | null",
  "confidence": "high | medium | low",
  "evidence": "short textual evidence"
}
```

### 9.8 Stability Audit

For a fixed oracle contract, report:

```text
same-clip disagreement rate
positive/negative flip rate
abstain rate
event boundary variance
VLM vs human agreement if available
```

If disagreement is high, the system must not emit human-truth guarantees.

### 9.9 Oracle Roles

```text
gold oracle:
  small human or human-adjudicated set for evaluation.

operational oracle:
  fixed VLM or human policy used under budget.

external label oracle:
  pre-existing third-party dataset annotations (e.g. Nexar collision /
  alert metadata) used as a surrogate for oracle-enumerated events when
  no VLM or human policy has been run on that data.
  Must report boundary_confidence and label provenance.
  Must not be treated as equivalent to operational oracle until a
  stability and predicate-mapping audit (Section 26) has been run.
  Any certificate computed against an external label oracle must be
  reported as "external-label-relative," not "oracle-relative," unless
  the predicate-mapping audit shows close equivalence to a defined
  query (e.g. O_enter_ego_path_v0).

proxy / candidate generator:
  any low-cost score, including VLM zero-shot score, STRIVE-D score, embedding score, YOLO count.
```

---

## 10. Phase 0 Protocol

### 10.1 Goal

Phase 0 determines whether the DB/AQP direction is viable.

It must answer:

```text
Q1: Does SUPG/window-level + stitch violate clip-level recall guarantees?
Q2: Can block/event audit produce conservative and non-vacuous recall lower bounds?
Q3: Is a fixed oracle contract stable enough for oracle-relative certification?
```

Phase 0 must not:

```text
build a new perception stack
train proxy models
run large-scale VLM
download large datasets without approval
```

---

## 11. Required Unified Table

Codex should construct:

```bash
/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/clip_aqp_phase0_v1/data_audit/phase0_units.csv
```

Preferred columns:

```text
unit_id
video_id
clip_id
start_time
end_time
duration
proxy_score
proxy_source
oracle_label
oracle_source
human_label
event_id
event_start
event_end
source_path
has_event_boundary
```

If `event_start / event_end` are missing, results are pseudo-event or oracle-relative only. Codex must not fabricate boundaries.

### 11.1 Block Audit Tables Must Be Row-Level

In addition to `phase0_units.csv`, any block/event audit (Experiment B1,
B2, and later candidate-feasibility certificate runs) must persist one
row per audited block, not only trial-level aggregates. Each row must
include at minimum:

```text
trial_id
block_id
sample_split
used_for_design
used_for_repair
used_for_certificate
Y_i^O
M_i^O
inclusion_probability
```

Found necessary during Phase 0.5 diagnostics: an earlier implementation
saved only trial-level aggregate statistics, which made it impossible to
verify whether `UCB(M^O)` and `LCB(Y^O)` had been computed correctly, or
to recompute trial-level aggregates independently from raw block data.
Any new certificate implementation must support recomputing trial-level
aggregates from the persisted per-block rows as a sanity check.

---

## 12. Experiment A: SUPG/window-level + Stitch

Purpose:

```text
Test whether record/window-level selection implies clip-level event recall.
```

Procedure:

```text
1. Treat windows or units as records.
2. Simulate SUPG-style thresholding or selection.
3. Stitch selected adjacent windows into returned clips.
4. Evaluate event-level IoU recall.
5. Repeat trials and report guarantee violation rate.
```

Metrics:

```text
window_recall
clip_event_recall
GVR
budget
delta
gamma
```

Expected support for the research problem:

```text
SUPG/window-level + stitch has GVR > delta at clip-level.
```

If no event boundaries exist, Codex may construct pseudo-events by merging adjacent oracle-positive units, but must label the result as pseudo-boundary / oracle-relative.

---

## 13. Experiment B1: No-repair Block/Event Audit

Purpose:

```text
Test whether block/event audit gives conservative recall lower bounds.
```

Procedure:

```text
1. Fix candidate generator and returned clips R.
2. Draw certification samples S_cert only.
3. Audit sampled blocks.
4. Compute Y_i^O and M_i^O.
5. Estimate UCB(M^O), LCB(Y^O), LCB_recall^O.
6. Compare with full-data oracle/pseudo-oracle recall.
```

No diagnostic or repair samples are allowed in B1.

Metrics:

```text
true_oracle_recall
LCB_recall^O
coverage
GVR
tightness = true_oracle_recall - LCB_recall^O
cost_to_certificate
```

---

## 14. Experiment B2: Repair + Fresh Certification

Run only after B1 passes.

Procedure:

```text
1. Draw diagnostic samples S_diag.
2. Use S_diag to identify missed-event patterns and choose repair.
3. Apply repair and freeze R_final.
4. Draw fresh certification samples S_cert.
5. Compute final certificate only on S_cert.
6. Report diagnostic cost, repair cost, certification cost, total cost.
```

Forbidden:

```text
using S_diag to compute final certificate
```

If the method only works when diagnostic samples are reused, the result is invalid.

---

## 15. Experiment C: Oracle Stability Audit

Use existing repeated labels if available. Do not run large-scale VLM.

Report:

```text
label source pair
num comparable clips
agreement rate
positive rate source A
positive rate source B
positive -> negative flip
negative -> positive flip
abstain rate
boundary variance if available
human agreement if available
```

If fixed oracle protocol is unstable, final report should say:

```text
Current oracle labels are not stable enough for human-truth guarantee; only oracle-relative certification is currently defensible.
```

---

## 16. Default Experimental Parameters

Default grid:

```text
gamma in {0.8, 0.9}
delta in {0.05, 0.1}
IoU theta in {0.3, 0.5}
block_size in {10s, 15s, 30s}
num_trials = 100
```

Codex may reduce the grid if data is too small, but it must report why.

---

## 17. Phase 0 Scripts Required

Codex should implement:

```bash
scripts/00_audit_existing_data.py
scripts/01_build_phase0_table.py
scripts/10_supg_stitch_simulation.py
scripts/20_block_audit_simulation.py
scripts/30_oracle_stability_audit.py
scripts/40_generate_report.py
scripts/run_phase0.sh
```

`run_phase0.sh` must use:

```bash
set -euo pipefail
```

Logs should be saved to:

```bash
logs/run_phase0.log
```

---

## 18. Data Audit Output

`00_audit_existing_data.py` should output:

```bash
data_audit/existing_data_inventory.csv
reports/DATA_AUDIT.md
```

It should report for each discovered file:

```text
file path
row count
columns
whether video_id exists
whether start_time/end_time exists
whether proxy_score exists
whether oracle_label exists
whether event_id/event_start/event_end exists
whether human_label exists
```

---

## 19. Phase 0 Report Structure

Final report:

```bash
reports/PHASE0_REPORT.md
```

Required structure:

```markdown
# Phase 0 Report: Clip-level AQP Guarantee Feasibility

## 1. Goal
## 2. Existing Data Inventory
## 3. Unified Phase0 Table
## 4. Experiment A: SUPG/window-level + Stitch
## 5. Experiment B1: No-repair Block/Event Audit
## 6. Experiment B2: Repair + Fresh Certification
## 7. Experiment C: Oracle Stability
## 8. Findings
## 9. Limitations
## 10. Next Action
## 11. Final Decision
```

The report must end with exactly one of:

```text
FINAL_DECISION: GO
FINAL_DECISION: NO_GO
FINAL_DECISION: PARTIAL_GO_NEED_CLEAN_EVENT_BOUNDARIES
```

---

## 20. Go / No-Go Criteria

### GO

Use GO only if:

```text
1. SUPG/window-level + stitch clearly violates clip-level guarantee;
2. no-repair block/event audit covers oracle-relative recall;
3. repair + fresh certification, if run, still satisfies GVR <= delta;
4. LCB_recall is not vacuous;
5. cost-to-certificate is below full oracle scan;
6. fixed oracle contract supports oracle-relative analysis.
```

### PARTIAL_GO_NEED_CLEAN_EVENT_BOUNDARIES

Use this if pseudo experiments support the direction but clean event boundaries are missing.

### NO_GO

Use NO_GO if:

```text
1. SUPG/window-level + stitch does not fail;
2. block/event audit overestimates recall;
3. repair only works with sample reuse;
4. LCB is almost always zero;
5. oracle is unstable;
6. event boundaries cannot be obtained.
```

---

## 21. External Data Policy

Do not download large public datasets unless explicitly approved.

If existing data lacks event boundaries, write:

```bash
reports/EXTERNAL_DATA_NEEDED.md
```

Recommended external datasets:

```text
DoTA
DADA-2000 / LOTVS-DADA
Nexar Dashcam Collision Prediction
```

If download scripts are prepared, use:

```bash
/qiuyeqing/llama_prl/G-ARC/datasets/casq_external
```

Suggested subdirectories:

```bash
/qiuyeqing/llama_prl/G-ARC/datasets/casq_external/dota
/qiuyeqing/llama_prl/G-ARC/datasets/casq_external/dada2000
/qiuyeqing/llama_prl/G-ARC/datasets/casq_external/nexar
```

Do not download data into `test_vlm/outputs`.

---

## 22. Codex Implementation Prompt

Codex should follow this general instruction for all new runs:

```text
You are working in /qiuyeqing/llama_prl/G-ARC.

First read CASQ_CODEX_BRIEF_V12_1.md.

Determine whether the requested task is:
1. a historical Phase 0 reproduction / repair run; or
2. a Phase 1+ external-data, real-video, candidate-feasibility,
   bounded VLM micro-audit, or certificate-validation run.

For every run, enforce the shared statistical constraints:
- Sections 3-9 for CASQ semantics, oracle roles, event ownership,
  and oracle-relative / external-label-relative terminology;
- Section 11.1 for row-level block-audit persistence;
- Section 23 for sample-split assertions and UCB/LCB bound invariants.

For Phase 0 runs, follow Sections 10-20.

For Phase 1+ external-data / candidate-feasibility runs, follow Part II
(Sections 26-31) in addition to the shared constraints above. Do not use
the Phase 0-only report template or decision labels unless the task is
explicitly a Phase 0 run.

Do not train models without explicit approval.
Do not build a new perception stack.
Do not run large-scale VLM. Use Section 27 only for bounded micro-audits.
Do not download large datasets unless approved.
Do not fabricate event boundaries.
Do not reuse diagnostic / pilot / repair samples for final certification.

Final certificate code must reject samples where:
sample_split != certification
or used_for_design == true
or used_for_repair == true.

Any report using external dataset labels must state whether its numbers are
external-label-relative, oracle-relative, or human-truth-relative before the
Final Decision.
```

Historical note: earlier Phase 0 prompts referred to
`CASQ_CODEX_BRIEF_V11.md` and said the whole task was Phase 0 only. Those
prompts are obsolete for Phase 1+ work.

---

## 23. Implementation Hard Assertions

Codex should implement assertions wherever possible.

### 23.1 Sample Split Assertions

Certificate computation must fail if input contains any row used for repair or design:

```python
assert (df["sample_split"] == "certification").all()
assert (df["used_for_design"] == False).all()
assert (df["used_for_repair"] == False).all()
```

If these assertions fail, the script should stop and explain the statistical validity violation.

Phase 0 must not produce a certificate from mixed sample splits.

### 23.2 Bound Invariant Assertions

Found necessary during the Phase 0 repair pass: a pre-fix formula
silently capped `UCB(M^O)` by `LCB(Y^O)`, producing an invalid bound
without raising an error. Every implementation of the certificate
computation — Phase 0, Phase 1, candidate feasibility v2, and any
later phase — must include these checks before `LCB_recall^O` is
computed, regardless of whether the code descends from `repair_v1`:

```python
assert UCB_M_O >= M_hat_O - 1e-9, "UCB(M^O) below point estimate: invalid upper confidence bound"
assert LCB_Y_O <= Y_hat_O + 1e-9, "LCB(Y^O) above point estimate: invalid lower confidence bound"
```

A synthetic formula test (construct a case where the pre-fix formula is
known to fail and the fixed formula is known to pass) should accompany
any new implementation of this computation.

---

## 24. Minimal Success Interpretation

Even a PARTIAL_GO can be useful if it says:

```text
Existing data lacks clean event boundaries, but pseudo-event experiments suggest that
record-level selection does not transfer cleanly to clip-level recall and that block/event audit
can produce conservative oracle-relative lower bounds.
```

But Codex must not overstate pseudo-event results as human-truth results.

---

## 25. Current Research Position

The clean research claim is:

> Record-level approximate selection guarantees do not directly solve variable-length semantic clip queries. G-ClipAQP adds a proxy-agnostic block/event audit layer that estimates missed oracle-enumerated events and returns a conservative clip-level recall certificate under a fixed oracle contract.

The work should remain centered on:

```text
clip-level query semantics
missed-event estimation
oracle budget
recall lower bound
guarantee violation rate
cost-to-certificate
sample-splitting validity
oracle-relative guarantee
```

Avoid drifting into:

```text
better driving-event proxy design
training learned proxy
full perception stack engineering
large VLM benchmarking
general dangerous-event definition without event boundaries
exhaustive full-video VLM ground-truth construction
  (use the bounded micro-audit protocol, Section 27, instead)
```

---

# Part II — Phase 1 Extensions (Added in V12)

These sections govern work using external datasets (Nexar, DoTA,
DADA-2000) and real-video candidate generators. They extend, and do not
replace, Part I. Where Part I's Phase-0-specific sections (10-20)
describe local/synthetic procedure, treat them as historical; the
statistical machinery they define (Sections 5-9, 23) still applies.

## 26. External Label <-> Predicate Mapping Requirement

When an experiment uses an external dataset's existing labels as a
stand-in for oracle-enumerated events (an "external label oracle,"
Section 9.9), the experiment report must include a short mapping
statement before any recall or certificate numbers are reported. The
statement must say one of:

```text
EQUIVALENT:
  the external label's positive criteria are judged equivalent to
  the defined oracle contract (e.g. O_enter_ego_path_v0). State why.

SUBSET:
  the external label only captures a subset of the defined predicate.
  Example: a human-verified label for "object entered ego path and
  collided with ego" may be a subset of "object enters ego path and
  creates potential conflict," because non-collision conflicts are
  excluded. State what is excluded.

LOOSE_APPROXIMATION:
  the external label is a different but related signal used for
  practical reasons. State the known or suspected mismatch and its
  likely direction (over-counting or under-counting events).
```

For Nexar collision / alert metadata specifically, the default mapping is
`LOOSE_APPROXIMATION`: collision or alert labels may under-count
non-collision conflicts and may include collision types that do not match
`O_enter_ego_path_v0`. A stronger mapping (`SUBSET` or `EQUIVALENT`) may be
used only if a bounded audit under Section 27 supports it.

If this statement is missing, the report's recall/certificate numbers
must be treated as provisional, and the report must not claim
"oracle-relative recall" in its Final Decision — it must say
"external-label-relative recall" instead.

Where possible, validate the mapping with a small number of targeted
oracle checks rather than assumption alone (Section 27).

---

## 27. Bounded VLM Micro-Audit Protocol

The blanket rule "do not run large-scale VLM" (Section 0, Section 10)
remains in force. This section defines a narrow, explicitly bounded
exception for validating an external label oracle (Section 9.9,
Section 26) — not for general-purpose oracle labeling or candidate
scoring.

### 27.1 When This Protocol Applies

Use this protocol only to answer a specific question, such as: "does
the external label's positive/negative flag agree with the defined
oracle contract near its boundary, and at what rate does it miss
events away from its boundary?" Do not use it to construct a full
VLM-based ground truth for an entire benchmark.

### 27.2 Call Budget

A single micro-audit run must specify and respect:

```text
max_total_vlm_calls   (hard ceiling, e.g. <= 200)
max_calls_per_video    (e.g. <= 3)
clip_length_seconds    (e.g. 5-15s, not full video)
```

A run that would require scanning an entire video end-to-end at the
candidate clip length, or that has no stated ceiling, is "large-scale
VLM" and is forbidden under Section 0.

### 27.3 Sampling Design

```text
near_label sample:
  windows drawn near each external-label-positive event boundary,
  used to check whether the label's timing/positivity agrees with
  the oracle contract.

random_negative sample:
  windows drawn at random from segments the external label marks
  negative, used to estimate a miss rate for the external label.
```

Both samples must carry the same `sample_split` / `used_for_*`
provenance fields as any other audited block (Section 7.1).

### 27.4 Engineering Constraints

To stay within GPU memory limits, any VLM micro-audit must log:

```text
model_name
quantization (e.g. none / int8 / int4 / awq)
frames_per_clip or fps
max_pixels or resolution setting
peak_gpu_memory_observed
calls_completed / calls_planned
```

If peak GPU memory approaches the device limit, the run must reduce
frame rate, resolution, or apply quantization before increasing call
volume — not request additional GPUs to raise call volume at the same
per-call memory footprint. Additional GPUs may be used to parallelize
independent calls (throughput), not to make a single call fit that
does not fit in one device's memory.

### 27.5 Output

The micro-audit report must state, in addition to whatever was being
checked:

```text
EXTERNAL_LABEL_AUDIT_RESULT: AGREES_WELL / PARTIAL_DISAGREEMENT / UNRELIABLE
```

Default interpretation thresholds:

```text
AGREES_WELL:
  positive-window agreement with the target oracle contract >= 0.85;
  random-negative estimated miss rate <= 0.10;
  abstain rate <= 0.15;
  boundary median absolute error <= one audited clip length, if boundary
  error is evaluated.

PARTIAL_DISAGREEMENT:
  there is usable alignment signal, but one or more AGREES_WELL thresholds
  fail and the UNRELIABLE conditions are not met.

UNRELIABLE:
  positive-window agreement < 0.65;
  or random-negative estimated miss rate > 0.25;
  or abstain rate is too high to interpret the audit.
```

If the run is too small for these thresholds to be stable, the report must
say `AUDIT_UNDERPOWERED` and avoid promoting the external label mapping beyond
`LOOSE_APPROXIMATION`.

The audit result must feed back into the mapping statement required by
Section 26.

---

## 28. Candidate Hyperparameter Selection Protocol (Design / Report Split)

This section governs sweeps over candidate-generator hyperparameters
(e.g. top_k, duration_fraction, merge_gap, IoU theta, embedding
threshold) — a different kind of sample reuse than Section 7, which
governs reuse of audited blocks for the certificate itself.

### 28.1 The Problem

Section 7 prevents reusing diagnostic samples to compute the final
certificate. It does not, by itself, prevent a different form of
optimistic bias: sweeping many candidate configurations over the same
evaluation videos and reporting the best-performing configuration's
numbers as if they were obtained from a single pre-specified
configuration.

### 28.2 Rule

Any report that sweeps more than one candidate-generator configuration
must do one of the following, and must say which:

```text
HELD_OUT_REPORT:
  videos are split into a development subset (used for the sweep) and
  a held-out report subset (used only to report final numbers for the
  configuration chosen on the development subset). State the split
  and its sizes.

PRE_REGISTERED:
  the configuration(s) to be reported were fixed before seeing any
  evaluation results on this dataset, e.g. carried over from Section 16
  defaults or an earlier phase. State the source of the configuration.

EXPLORATORY_ONLY:
  the sweep results are explicitly labeled exploratory / not for the
  paper's headline numbers. Best-of-sweep numbers from this category
  must not appear in the Final Decision section of the report.
```

If none of these is stated, the report's best-configuration numbers
must be treated as exploratory only, regardless of how the report
itself characterizes them.

### 28.3 Interaction With Sample Size

A held-out split reduces the number of videos/events available to the
certificate (Section 5, Section 16). If the held-out report subset is
too small to produce a non-vacuous `LCB_recall^O`, the report must say
so explicitly rather than reporting the sweep's best development-set
numbers as if they were certified.

Phase 0.6 power-simulation interpretation:

```text
~200 events:
  may begin to improve bound tightness, but certificates can still be
  weak or vacuous depending on recall, sample fraction, and event density.

~500+ events:
  were needed in that simulation for consistently non-vacuous certificates
  (fraction_vacuous = 0 in the reported power run).
```

Do not summarize this as simply "200+ events are enough."

---

## 29. Selectivity Stratification Requirement

If the oracle-enumerated event population has identifiable subtypes
(event type, severity, or other available metadata field), pooled
recall and certificate numbers can hide poor performance on a
rare-but-important stratum.

### 29.1 Requirement

When subtype/severity metadata is available for oracle-enumerated
events, the report must compute and present, in addition to the pooled
number:

```text
per_stratum_event_count
per_stratum_true_recall
per_stratum_LCB_recall (if certifiable; NO_CERTIFICATE per stratum if not)
```

### 29.2 When Subtype Metadata Is Unavailable

If no subtype/severity field exists in the current data (this is the
current state for the Nexar collision/normal labels, which carry no
severity or collision-type field), the report must say so explicitly,
rather than implying that pooled recall represents uniform performance
across event severities. This is a known limitation to be revisited if
richer external-label metadata or VLM-derived subtype tags become
available.

### 29.3 Small-Stratum Vacuity

A rare stratum may not have enough sampled events to support a
non-vacuous per-stratum certificate even when the pooled certificate is
non-vacuous. This must be reported as `NO_CERTIFICATE` for that stratum
rather than omitted from the report.

---

## 30. Single-Dataset Claim Scope Limitation

### 30.1 Rule

Any finding obtained on a single external dataset must be labeled with
that dataset's name and its boundary type everywhere the finding is
stated, e.g.:

```text
"Nexar-200, derived-boundary, single-dataset: true_derived_recall = 0.06"
```

not:

```text
"true recall = 0.06"
```

### 30.2 Promotion to a General Claim

A finding may be stated as a general claim (without the dataset
qualifier) only after the same direction of result has been observed on
at least one additional, independently sourced external dataset (e.g.
DoTA or DADA-2000, per Section 21).

### 30.3 Effect on Final Decision

Any `*_DECISION:` line produced by a report based on a single external
dataset must include the dataset name, e.g.:

```text
NEXAR_CANDIDATE_DECISION: CANDIDATE_STILL_TOO_WEAK (Nexar-200 only, derived boundary)
```

rather than a dataset-agnostic decision label.

---

## 31. Phase 1 Candidate Feasibility v2 Implementation Prompt

This section governs the next Nexar candidate-feasibility run and any
analogous Phase 1+ candidate-feasibility run.

Codex should follow this instruction:

```text
You are working in /qiuyeqing/llama_prl/G-ARC.

First read CASQ_CODEX_BRIEF_V12_1.md.

Task: run Phase 1 candidate feasibility v2, not Phase 0.

Use the available external-data benchmark only within its stated claim scope.
For Nexar-200, report every main result as Nexar-200, derived-boundary,
single-dataset unless and until another independent dataset confirms the
same direction of result.

Before reporting recall or certificate numbers, state the external-label
<-> predicate mapping required by Section 26. For Nexar collision / alert
metadata, the default mapping is LOOSE_APPROXIMATION unless a bounded
micro-audit under Section 27 supports a stronger mapping.

Do not run large-scale VLM. If VLM is used, it must be only for the bounded
micro-audit protocol in Section 27, with explicit max_total_vlm_calls,
max_calls_per_video, clip_length_seconds, frame sampling, resolution,
quantization, and peak GPU memory logging.

Do not use event_start, event_end, alert_time, event_moment, or any derived
boundary field to generate candidates. These fields may be used only for
evaluation after candidate clips are frozen.

Candidate feasibility v2 must include:
1. fixed or random baseline;
2. at least one cheap handcrafted candidate if available (e.g. motion energy
   or YOLO count);
3. at least one representation-based candidate if local model assets are
   already available (e.g. CLIP, SigLIP, existing visual embeddings, or a
   local embedding retriever).

If no representation-based model or embedding assets are locally available
and no download is approved, the report must state:

REPRESENTATION_CANDIDATE_NOT_AVAILABLE

In that case, failure of fixed / motion / YOLO candidates must be stated as
failure of cheap handcrafted candidates, not failure of candidate generation
in general.

Any sweep over top_k, duration_fraction, merge_gap, IoU theta, embedding
threshold, score fusion, or related candidate hyperparameters must follow
Section 28 and declare one of:
HELD_OUT_REPORT, PRE_REGISTERED, or EXPLORATORY_ONLY.

If HELD_OUT_REPORT is used, report the development and held-out subset sizes
and event counts. If the held-out subset is too small for a non-vacuous
certificate, say so explicitly.

If PRE_REGISTERED is used, state exactly where the reported configuration
was fixed before seeing this run's evaluation results.

If EXPLORATORY_ONLY is used, do not put best-of-sweep numbers in the Final
Decision.

If subtype, severity, event source, or other stratum metadata exists, report
pooled and per-stratum recall / LCB according to Section 29. If no such
metadata exists, state that pooled recall may hide heterogeneous performance
and mark selectivity stratification as unavailable for that dataset version.

Certificate validation may be run only after returned clips are frozen.
Final certificate code must enforce:
- sample_split == certification;
- used_for_design == false;
- used_for_repair == false;
- row-level audited block persistence;
- UCB(M^O) >= M_hat_O - 1e-9;
- LCB(Y^O) <= Y_hat_O + 1e-9.

The report must end with exactly one dataset-scoped decision line, for
example:

NEXAR_CANDIDATE_DECISION: CHEAP_CANDIDATE_SUFFICIENT (Nexar-200 only, derived boundary)
NEXAR_CANDIDATE_DECISION: NEED_REPRESENTATION_CANDIDATE (Nexar-200 only, derived boundary)
NEXAR_CANDIDATE_DECISION: REPRESENTATION_CANDIDATE_NOT_AVAILABLE (Nexar-200 only, derived boundary)
NEXAR_CANDIDATE_DECISION: CANDIDATE_STILL_TOO_WEAK (Nexar-200 only, derived boundary)
NEXAR_CANDIDATE_DECISION: VIDEO_MAPPING_OR_READABILITY_FAILED (Nexar-200 only, derived boundary)
NEXAR_CANDIDATE_DECISION: CODE_REVIEW_NEEDED (Nexar-200 only, derived boundary)
```

Recommended minimum report sections:

```markdown
# Phase 1 Candidate Feasibility v2 Report

## 1. Goal
## 2. Data and Claim Scope
## 3. External Label <-> Predicate Mapping
## 4. Optional Bounded VLM Micro-Audit
## 5. Candidate Generators
## 6. Hyperparameter Selection Protocol
## 7. Candidate Recall / Duration / Runtime Results
## 8. Representation-Based Candidate Availability
## 9. Certificate Validation, if applicable
## 10. Selectivity Stratification
## 11. Limitations
## 12. Final Decision
```

