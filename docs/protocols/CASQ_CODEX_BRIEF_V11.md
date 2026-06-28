# CASQ / G-ClipAQP Codex Brief V11

## 0. Purpose

This document is the fixed reference for Codex implementation.

The project target is a DB/AQP-style research direction:

> Clip-level approximate selection query with recall certificates over long videos.

The goal is not to design a stronger driving-event proxy. STRIVE-D, iFinder, LAVA, AVA, embedding retrieval, VLM zero-shot scoring, YOLO count, motion heuristics, and random ranking are all treated as candidate generators.

The core contribution is a proxy-agnostic statistical guarantee layer:

> Given any candidate generator, an expensive oracle, oracle budget B, target recall gamma, and failure probability delta, can the system return variable-length clips and provide a conservative clip-level recall certificate?

The current task for Codex is Phase 0 only:

1. audit existing data;
2. build a unified intermediate table;
3. test whether window-level / record-level selection plus stitching fails at clip-level recall;
4. test whether block/event audit produces conservative recall lower bounds;
5. audit oracle stability;
6. generate a final Phase 0 report.

Do not train models.
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

Codex should follow this instruction:

```text
You are working in /qiuyeqing/llama_prl/G-ARC.

First read CASQ_CODEX_BRIEF_V11.md.

Your task is Phase 0 only:
1. audit existing data;
2. build phase0_units.csv;
3. run SUPG/window-level + stitch simulation;
4. run no-repair block/event audit simulation;
5. optionally run repair + fresh certification, with strict sample splitting;
6. run oracle stability audit;
7. generate PHASE0_REPORT.md.

Do not train models.
Do not build a new perception stack.
Do not run large-scale VLM.
Do not download large datasets unless approved.
Do not fabricate event boundaries.
Do not reuse diagnostic / pilot / repair samples for final certificate.

Final certificate code must reject samples where:
sample_split != certification
or used_for_design == true
or used_for_repair == true.

The final report must end with exactly one final decision:
FINAL_DECISION: GO
FINAL_DECISION: NO_GO
FINAL_DECISION: PARTIAL_GO_NEED_CLEAN_EVENT_BOUNDARIES.
```

---

## 23. Implementation Hard Assertions

Codex should implement assertions wherever possible.

Certificate computation must fail if input contains any row used for repair or design:

```python
assert (df["sample_split"] == "certification").all()
assert (df["used_for_design"] == False).all()
assert (df["used_for_repair"] == False).all()
```

If these assertions fail, the script should stop and explain the statistical validity violation.

Phase 0 must not produce a certificate from mixed sample splits.

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
```
