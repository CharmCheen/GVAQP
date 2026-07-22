# BCM-AQP Phase-0 Blocker Audit Reproduction

Run all commands from `/qiuyeqing/llama_prl/G-ARC`.

This reproduction is intentionally limited to source inspection and read-only
video-frame provenance hashing.  It does not load a model, call a VLM,
implement BCM, or run any benchmark/baseline/ceiling/ablation/synthetic suite.

## 1. Verify authoritative source hashes

```bash
sha256sum \
  Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v1/scripts/benchmark_lib.py \
  Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v1/scripts/run_clean_benchmark.py \
  Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v1/scripts/replay_baseline_acquisition.py \
  src/garc_eval/outputs/event_native_aqp_autonomous_research_sprint_v1/scripts/stage2_full_center10_oracle.py \
  src/garc_eval/outputs/event_native_aqp_p1_dataset3_semantic_pilot_v1/scripts/run_pilot_oracle.py \
  src/garc_eval/outputs/event_native_aqp_p1_dataset3_semantic_pilot_v1/scripts/build_anchor_plan.py \
  outputs/video_feature_precompute_v1/scripts/precompute_video_features.py
```

Expected hashes are recorded in `EXPERIMENT_MANIFEST.json` and the two audit
reports.

## 2. Confirm the duration-field discrepancy

```bash
ffprobe -v error -select_streams v:0 \
  -show_entries stream=duration,avg_frame_rate,r_frame_rate,nb_frames,start_time \
  -show_entries format=duration,start_time -of json \
  data/realcam/long_video_data/long_video_dataset3.mp4
```

The relevant values are video-stream duration `3462.866000`, MP4 format
duration `3462.930499`, and `103886` frames.

## 3. Reproduce the frame audit

```bash
python -m py_compile \
  Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/bcm_aqp_experiment_v1/audit/reproduce_oracle_provenance.py

python \
  Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/bcm_aqp_experiment_v1/audit/reproduce_oracle_provenance.py
```

The second command reads the source MP4 using the exact recovered OpenCV
selection loop.  It hashes 347 cache-interval sequences and the corresponding
frozen sequences (identical intervals are decoded once).  It writes:

- `audit/oracle_cache_interval_audit.csv`;
- `audit/unit346_frame_equivalence.csv`;
- `audit/provenance_reproduction_manifest.json`.

It imports `cv2` but not `torch`, `transformers`, or model code.  The manifest
must report `vlm_loaded=false`, `vlm_calls=0`, and
`formal_experiment=false`.

## 4. Verify the decisive invariants

```bash
python - <<'PY'
import collections
import csv

path = (
    "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/"
    "bcm_aqp_experiment_v1/audit/oracle_cache_interval_audit.csv"
)
rows = list(csv.DictReader(open(path, encoding="utf-8")))
assert len(rows) == 347
assert collections.Counter(r["same_frame_indices"] for r in rows) == {"True": 346, "False": 1}
assert collections.Counter(r["same_frame_content"] for r in rows) == {"True": 346, "False": 1}
different = [r for r in rows if r["same_frame_content"] == "False"]
assert [r["unit_id"] for r in different] == ["346"]
assert different[0]["decision"] == "ORACLE_PROVENANCE_BLOCKED_REQUIRES_BENCHMARK_V2"
assert different[0]["frozen_num_frames"] == "10"
assert different[0]["cache_num_frames"] == "11"
assert all(r["video_sha256_match"] == "True" for r in rows)
assert all(r["raw_response_hash_match"] == "True" for r in rows)
print("PASS: 347 units audited; unit 346 alone has different frame indices/content")
PY
```

## 5. Validate blocker deliverables and frozen-input integrity

Before the integrity check, reproduce the unit-346 frozen-trace usage table:

```bash
python \
  Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/bcm_aqp_experiment_v1/audit/reproduce_unit346_query_usage.py
```

This reads the existing aggregate current/baseline action traces and writes
`audit/unit346_query_usage.csv`; it does not replay a planner or oracle.

```bash
python -m json.tool \
  Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/bcm_aqp_experiment_v1/EXPERIMENT_MANIFEST.json \
  >/dev/null

sha256sum \
  Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v1/frozen_inputs/unit_table.csv \
  Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v1/frozen_inputs/evaluator_config.json
```

Expected physical hashes are respectively
`50e8c454d8de02c89c2ffd6ff9fada134d9c566366e3132ad22518ebe495faa4`
and `2466f38a74c65e56a2c52a99b033f81a5dee80cad33a31433a1a1b7219f01aa5`,
as frozen in the existing benchmark manifest.

Do not run `run_clean_benchmark.py`, any VLM script, or any BCM command as part
of this blocker reproduction.
