# REALCARTEST Oracle-Relative Full-Video Validation V13.5

## 0. Purpose

This document defines the V13.5 validation protocol for using:

```text
/qiuyeqing/llama_prl/G-ARC/try_or_no/videos/realcartest.mp4
```

as an internal full-video benchmark for CASQ / G-ClipAQP.

This document is subordinate to:

```text
/qiuyeqing/llama_prl/G-ARC/CASQ_CODEX_BRIEF_V12_1.md
```

Codex / Claude Code must read and follow `CASQ_CODEX_BRIEF_V12_1.md` first. This document only specifies the realcartest-specific protocol.

The main purpose is to answer:

```text
Did V13 fail because Nexar-derived labels are misaligned with O_enter_ego_path_v0,
or because full-video semantic candidate generation is intrinsically weak?
```

This validation must not be used to claim human-truth recall. All labels produced by VLM are:

```text
VLM_ORACLE_RELATIVE
```

not human-adjudicated ground truth.

## 1. Video and Query

Target video:

```text
/qiuyeqing/llama_prl/G-ARC/try_or_no/videos/realcartest.mp4
```

Target predicate:

```text
O_enter_ego_path_v0
```

Operational meaning:

```text
An object starts outside or not clearly inside the ego vehicle's future path,
then enters, overlaps, or creates a potential conflict with the ego path,
such that ego attention or reaction would be needed.
```

The predicate should be judged conservatively. Dense traffic, normal following, parked roadside objects, visible but non-interacting vehicles, and general traffic complexity are not positives unless there is a clear ego-path conflict.

## 2. Output Directory

All outputs must be written under:

```text
/qiuyeqing/llama_prl/G-ARC/test_vlm/outputs/v13_5_realcartest_oracle_relative_v1
```

Required structure:

```text
reports/
tables/
logs/
scripts/
figures/
clips/
contact_sheets/
raw_vlm_responses/
```

Required final summary:

```text
/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/v13_5_realcartest_oracle_relative_v1_summary.md
```

Do not overwrite prior experiment outputs.

## 3. Global Restrictions

Do not train models.

Do not download large datasets.

Do not modify previous experiment outputs.

Do not run certificate simulation in V13.5.

Do not claim human-truth labels.

Do not claim full paper-level benchmark validity from one video.

Do not use VLM labels, event boundaries, or oracle outputs during candidate generation.

Full or near-full VLM scanning is allowed only as offline benchmark construction for this one internal video. It must be clearly separated from online AQP query execution.

## 4. Stages

V13.5 has six stages.

```text
Stage 0: Protocol and filesystem setup
Stage 1: Video preflight
Stage 2: Full-video cheap proxy feature extraction
Stage 3: VLM oracle pilot
Stage 4: Conditional full coarse VLM oracle construction
Stage 5: Conditional boundary refinement and VLM-oracle event construction
Stage 6: Conditional candidate evaluation
```

AQP simulation is not part of V13.5 unless explicitly requested later. Certificate simulation is not part of V13.5.

## 5. Stage 0 — Protocol and Setup

Claude Code must confirm that it read:

```text
/qiuyeqing/llama_prl/G-ARC/CASQ_CODEX_BRIEF_V12_1.md
/qiuyeqing/llama_prl/G-ARC/docs/clip_aqp/REALCARTEST_ORACLE_RELATIVE_VALIDATION_V13_5.md
```

The final report must state both file paths.

Create:

```text
reports/PROTOCOL_README.md
tables/run_manifest.csv
```

The run manifest must include:

```text
run_id
date
project_root
brief_path
realcartest_protocol_path
video_path
output_dir
git_status_start
```

## 6. Stage 1 — Video Preflight

Objective: determine whether `realcartest.mp4` is readable and suitable for full-video validation.

Run `ffprobe` and store metadata:

```text
tables/video_metadata.json
```

Extract frames every 30 seconds and create a contact sheet:

```text
contact_sheets/realcartest_contact_sheet_30s.jpg
tables/scene_overview_30s.csv
```

`scene_overview_30s.csv` must include:

```text
timestamp
frame_path
scene_type
traffic_density_low_medium_high
ego_motion_static_slow_moving
visibility_good_bad
notes
```

Create a 5s non-overlapping coarse clip grid:

```text
tables/coarse_5s_clip_grid.csv
```

Fields:

```text
clip_id
video_id
source_video_path
start_time
end_time
duration
split
```

Stage 1 decision:

```text
PREFLIGHT_PASS
PREFLIGHT_FAIL
```

Fail if the video is unreadable, mostly corrupted, mostly non-driving, or cannot produce a stable clip grid.

## 7. Stage 2 — Full-Video Cheap Proxy Feature Extraction

Objective: compute proxy features before any VLM labels are used.

Input:

```text
tables/coarse_5s_clip_grid.csv
```

Required proxy features:

```text
motion_energy
vehicle_count_mean
vehicle_count_max
object_count_mean
object_count_max
bbox_area_sum_mean
bbox_area_sum_max
max_bbox_area_mean
center_roi_vehicle_count_mean
bottom_roi_vehicle_count_mean
```

Use locally available YOLO if possible:

```text
/qiuyeqing/llama_prl/G-ARC/models/yolo/yolov8n.pt
```

If YOLO GPU inference fails, report the failure clearly and continue with motion features only.

Output:

```text
tables/proxy_features_5s.csv
reports/PROXY_FEATURE_EXTRACTION_REPORT.md
```

Hard invariant:

```text
proxy_features_5s.csv must not contain VLM labels, event labels, oracle labels, event_start, event_end, or any field derived from future VLM outputs.
```

## 8. Stage 3 — VLM Oracle Pilot

Objective: determine whether this video contains enough O_enter_ego_path_v0 positives to justify full oracle construction.

Sample 100 clips from `coarse_5s_clip_grid.csv` using mixed sources:

```text
25 uniform temporal samples
25 random samples
25 high motion_energy samples
25 high YOLO / high traffic proxy samples
```

If YOLO is unavailable, replace the last group with high proxy fusion or medium motion samples, and report this substitution.

Output sample table:

```text
tables/vlm_pilot_sample_100.csv
```

Fields:

```text
clip_id
start_time
end_time
sample_source
sample_rank
used_for_pilot
```

VLM output schema:

```json
{
  "conservative_positive": "yes/no/abstain",
  "risk_level": "L0/L1/L2/L3/L4",
  "affected_ego": true,
  "event_type": "cut_in/crossing/approach/hard_brake/dense_traffic/other/none",
  "starts_outside_ego_path": true,
  "enters_ego_path": true,
  "requires_ego_attention": true,
  "evidence": "...",
  "confidence": "low/medium/high"
}
```

Positive rule:

```text
conservative_positive = yes
AND starts_outside_ego_path = true
AND enters_ego_path = true
AND requires_ego_attention = true
AND confidence != low
```

Output:

```text
tables/vlm_pilot_labels.csv
reports/VLM_ORACLE_PILOT_REPORT.md
raw_vlm_responses/pilot/
```

Report:

```text
num_pilot_clips
positive_count
negative_count
abstain_count
positive_rate
positive_by_sample_source
avg_vlm_runtime_seconds
failed_calls
gpu_name_if_available
peak_gpu_memory_if_logged
```

Stage 3 decision:

```text
PROCEED_FULL_ORACLE
REVISE_QUERY_OR_VIDEO
PILOT_UNSTABLE
```

Decision rules:

```text
PROCEED_FULL_ORACLE:
  positive_count >= 5
  OR positive_rate >= 0.03
  AND abstain_rate <= 0.30

REVISE_QUERY_OR_VIDEO:
  positive_count < 3
  AND no clear event evidence

PILOT_UNSTABLE:
  abstain_rate > 0.30
  OR VLM call failures make the pilot unreliable
```

If Stage 3 is not `PROCEED_FULL_ORACLE`, stop after Stage 3 and write final report.

## 9. Stage 4 — Conditional Full Coarse VLM Oracle Construction

Run only if Stage 3 decision is `PROCEED_FULL_ORACLE`.

Run VLM on all 5s non-overlapping coarse clips.

Expected scale for 1h video:

```text
about 720 clips
```

Output:

```text
tables/vlm_coarse_5s_labels.csv
reports/FULL_COARSE_ORACLE_REPORT.md
raw_vlm_responses/coarse/
```

Every row must include:

```text
clip_id
video_id
start_time
end_time
oracle_model
prompt_version
conservative_positive
risk_level
event_type
starts_outside_ego_path
enters_ego_path
requires_ego_attention
confidence
evidence
raw_response_path
runtime_seconds
vlm_call_status
```

The report must include:

```text
total_clips
successful_calls
failed_calls
positive_count
negative_count
abstain_count
positive_rate
runtime_total
runtime_mean
gpu_memory_if_logged
```

## 10. Stage 5 — Conditional Boundary Refinement and Event Construction

Run only if Stage 4 produces at least one positive coarse region.

Construct coarse positive regions by merging adjacent positive 5s clips.

For each coarse positive region, create a refinement window:

```text
region_start - 10s
region_end + 10s
```

clamped to video bounds.

Run refinement VLM on:

```text
2s window
1s stride
```

only inside these refinement regions.

Outputs:

```text
tables/refinement_2s_grid.csv
tables/vlm_refinement_2s_labels.csv
tables/vlm_oracle_events.csv
reports/BOUNDARY_REFINEMENT_REPORT.md
raw_vlm_responses/refinement/
```

Event stitching rule:

```text
1. medium/high confidence positive 2s windows define event cores.
2. adjacent positive windows separated by <= 2s are merged.
3. abstain windows between positives may be included as boundary_uncertain.
4. event_start is the earliest positive/refined-positive start.
5. event_end is the latest positive/refined-positive end.
6. each event records evidence and supporting windows.
```

`vlm_oracle_events.csv` fields:

```text
event_id
video_id
event_start
event_end
duration
event_type
risk_level_max
confidence_aggregate
num_supporting_positive_windows
num_abstain_boundary_windows
evidence_summary
label_source
```

`label_source` must be:

```text
VLM_ORACLE_RELATIVE
```

## 11. Stage 6 — Conditional Candidate Evaluation

Run only if Stage 5 creates at least 5 VLM-oracle events.

Objective: test whether full-video candidate generators can retrieve VLM-oracle events without seeing VLM labels.

Candidate generation must use the full video timeline and proxy features only.

Forbidden during candidate generation:

```text
VLM labels
event_start
event_end
event_id
conservative_positive
risk_level
event_type from VLM
oracle outputs
```

Candidate methods:

```text
fixed_uniform_multiscale
random_multiseed
motion_energy
yolo_count
yolo_geometry
motion_yolo_fusion
representation_candidate_if_available
```

Candidate windows:

```text
window_size: 2s, 4s, 6s, 10s
stride: window_size / 2
```

Returned duration budgets:

```text
0.05, 0.10, 0.20, 0.35, 0.50
```

Merge gaps:

```text
0s, 2s, 5s
```

Metrics:

```text
IoU theta = 0.3 primary
IoU theta = 0.1 diagnostic
event-moment hit diagnostic
```

Outputs:

```text
tables/candidate_results.csv
tables/candidate_per_event_hits.csv
tables/candidate_per_method_summary.csv
reports/CANDIDATE_EVALUATION_REPORT.md
```

Required fields in `candidate_results.csv`:

```text
candidate_name
window_size
stride
returned_duration_fraction
merge_gap
theta
event_hit_count
event_total_count
event_recall
total_returned_duration
mean_returned_clips
runtime_seconds
uses_oracle_annotation_for_generation
uses_event_boundary_for_generation
claim_scope
```

Hard invariants:

```text
uses_oracle_annotation_for_generation=false
uses_event_boundary_for_generation=false
```

If either invariant is false, mark the candidate invalid and exclude it from final decision.

Stage 6 decision:

```text
CANDIDATE_STRONG_PASS
CANDIDATE_PASS
CANDIDATE_FLAT
CANDIDATE_FAIL
```

Decision rules:

```text
CANDIDATE_STRONG_PASS:
  returned_duration_fraction <= 0.35
  AND at least one non-oracle candidate reaches event_recall >= 0.75
  AND beats fixed_uniform/random_mean by >= 0.10 absolute recall

CANDIDATE_PASS:
  returned_duration_fraction <= 0.35
  AND at least one non-oracle candidate reaches event_recall >= 0.60
  AND beats fixed_uniform/random_mean by >= 0.10 absolute recall

CANDIDATE_FLAT:
  all non-oracle candidates are within 0.05 of fixed/random
  OR best event_recall < 0.50

CANDIDATE_FAIL:
  leakage, video processing, event construction, or hit evaluation fails
```

## 12. Final Report

Final report path:

```text
reports/FINAL_REPORT.md
```

Final report must include:

```text
1. exact commands run
2. brief and protocol files read
3. git status summary
4. video preflight summary
5. proxy feature summary
6. VLM pilot summary
7. full oracle construction summary, if run
8. boundary refinement summary, if run
9. candidate evaluation summary, if run
10. caveats
11. recommended next action
```

Final report must end with exactly one of:

```text
FINAL_DECISION: PREFLIGHT_FAIL
FINAL_DECISION: PILOT_REVISE_QUERY_OR_VIDEO
FINAL_DECISION: PILOT_UNSTABLE
FINAL_DECISION: FULL_ORACLE_CONSTRUCTED_NOT_ENOUGH_EVENTS
FINAL_DECISION: CANDIDATE_STRONG_PASS_READY_FOR_AQP_SIMULATION
FINAL_DECISION: CANDIDATE_PASS_READY_FOR_AQP_SIMULATION
FINAL_DECISION: CANDIDATE_FLAT_TRY_REPRESENTATION_OR_REVISE_PROXY
FINAL_DECISION: CANDIDATE_FAIL_FIX_PIPELINE
```

## 13. Interpretation Rules

If the run succeeds, the strongest allowed claim is:

```text
On one internal real driving video, under a fixed VLM oracle contract,
full-video candidate generation shows / does not show signal for O_enter_ego_path_v0.
```

Forbidden claims:

```text
human-truth recall
generalization to all dashcam videos
certified recall
Nexar label validity
final paper-level benchmark success
```

Certificate simulation is explicitly out of scope for V13.5.
