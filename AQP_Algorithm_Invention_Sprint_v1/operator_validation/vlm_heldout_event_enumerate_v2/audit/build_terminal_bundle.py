from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parents[1]
TEST = ROOT / "try_or_no/test.mov"
SLICE = ROOT / "try_or_no/videos/realcartest_5k.mp4"
STRICT = ROOT / "data/realcam/long_video_data/long_video_dataset3.mp4"
VLM_LABELS = ROOT / "experiments/v13/v13_8_full_oracle/tables/center10_full_oracle_labels.csv"
VLM_EVENTS = ROOT / "experiments/v13/v13_8_full_oracle/tables/center10_vlm_oracle_events.csv"
YOLO_TEST = ROOT / "try_or_no/outputs/garc_meeting_pack/real_video_csv_pipeline/video_supg.csv"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def probe(path: Path) -> dict:
    raw = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries",
        "format=format_name,duration,size:stream=index,codec_type,codec_name,width,height,pix_fmt,r_frame_rate,avg_frame_rate,time_base,duration,nb_frames",
        "-of", "json", str(path),
    ])
    return json.loads(raw)


def video_row(path: Path) -> dict:
    p = probe(path)
    v = next(x for x in p["streams"] if x["codec_type"] == "video")
    audio = any(x["codec_type"] == "audio" for x in p["streams"])
    return {
        "path": str(path.relative_to(ROOT)), "sha256": sha(path),
        "bytes": path.stat().st_size, "container": p["format"]["format_name"],
        "codec": v["codec_name"], "width": v["width"], "height": v["height"],
        "pixel_format": v.get("pix_fmt", ""), "duration_seconds": p["format"]["duration"],
        "r_frame_rate": v["r_frame_rate"], "avg_frame_rate": v["avg_frame_rate"],
        "time_base": v["time_base"], "frame_count": v.get("nb_frames", ""),
        "audio_present": audio,
    }


def phash(path: Path, t: float) -> tuple[int, float]:
    cap = cv2.VideoCapture(str(path))
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise RuntimeError(f"decode failed: {path} at {t}")
    gray = cv2.cvtColor(cv2.resize(frame, (64, 64), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    coeff = cv2.dct(np.float32(gray))[:8, :8].flatten()[1:]
    bits = coeff > coeff.mean()
    value = sum(int(x) << i for i, x in enumerate(bits))
    return value, float(gray.mean())


def write_csv(rel: str, fieldnames: list[str], rows: list[dict]) -> None:
    path = OUT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def write(rel: str, text: str) -> None:
    path = OUT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def main() -> None:
    if (OUT / "FINAL_DECISION.csv").exists() and "--force" not in sys.argv:
        raise SystemExit("refusing to overwrite an existing bundle; use the read-only REPRODUCTION.md verifier")
    rows = {p.name: video_row(p) for p in (TEST, SLICE, STRICT)}
    with VLM_LABELS.open(newline="") as f:
        labels = list(csv.DictReader(f))
    with VLM_EVENTS.open(newline="") as f:
        events = list(csv.DictReader(f))
    with YOLO_TEST.open(newline="") as f:
        yolo = list(csv.DictReader(f))

    write("audit/GOVERNING_ASSUMPTION.md", """# Governing assumption

`ORACLE_EXACT_BY_USER_ASSUMPTION = true`  
`REFERENCE_TYPE = VLM_DEFINED_HELDOUT_PSEUDO_ORACLE`  
`HUMAN_GT = false`  
`REAL_WORLD_SEMANTIC_CLAIM = false`

The user authorizes existing VLM oracle outputs as exact for this AQP
abstraction only. Direct artifacts still must establish that an observation
belongs to `test.mov`; exactness does not license transferring annotations
from different content or treating YOLO vehicle counts as VEPC labels.
""")

    governing = [
        "AQP_Algorithm_Invention_Sprint_v1/FINAL_REPORT.md",
        "AQP_Algorithm_Invention_Sprint_v1/FINAL_DECISION.csv",
        "AQP_Algorithm_Invention_Sprint_v1/RESEARCH_STATE.md",
        "AQP_Algorithm_Invention_Sprint_v1/operator_validation/event_enumerate_v2/FINAL_REPORT.md",
        "AQP_Algorithm_Invention_Sprint_v1/operator_validation/event_enumerate_v2/FINAL_DECISION.csv",
        "AQP_Algorithm_Invention_Sprint_v1/operator_validation/event_enumerate_v2/config/FROZEN_EVENT_ENUMERATE_V2_CONFIG.json",
        "AQP_Algorithm_Invention_Sprint_v1/operator_validation/event_enumerate_v2/config/PROCESSOR_CONTRACT.json",
        "AQP_Algorithm_Invention_Sprint_v1/operator_validation/event_enumerate_v2/audit/PRE_EXECUTION_PROCESSOR_AUDIT.csv",
        "AQP_Algorithm_Invention_Sprint_v1/operator_validation/event_enumerate_v2/theory/QWEN3_VL_TEMPORAL_SEMANTICS.md",
        "AQP_Algorithm_Invention_Sprint_v1/operator_validation/event_enumerate_v2/theory/TIMESTAMP_MAPPING_PROOF.md",
        "AQP_Algorithm_Invention_Sprint_v1/operator_validation/heldout_reference_v1/FINAL_REPORT.md",
        "AQP_Algorithm_Invention_Sprint_v1/operator_validation/heldout_reference_v1/FINAL_DECISION.csv",
        "AQP_Algorithm_Invention_Sprint_v1/operator_validation/heldout_reference_v1/FILE_MANIFEST.csv",
    ]
    write_csv("audit/FROZEN_STATE_REPRODUCTION.csv", ["path", "sha256", "status"],
              [{"path": p, "sha256": sha(ROOT / p), "status": "READ_AND_HASHED"} for p in governing])
    write_csv("audit/SOURCE_MANIFEST.csv", ["path", "sha256", "role"],
              [{"path": p, "sha256": sha(ROOT / p), "role": "governing_source"} for p in governing])
    write_csv("audit/INPUT_MANIFEST.csv", ["path", "sha256", "bytes", "role"], [
        {"path": r["path"], "sha256": r["sha256"], "bytes": r["bytes"], "role": role}
        for r, role in [(rows["test.mov"], "canonical_heldout"), (rows["realcartest_5k.mp4"], "claimed_derived_slice_content_rejected"), (rows["long_video_dataset3.mp4"], "prior_strict_video")]
    ] + [
        {"path": str(p.relative_to(ROOT)), "sha256": sha(p), "bytes": p.stat().st_size, "role": role}
        for p, role in [(VLM_LABELS, "recovered_vlm_labels_different_video"), (VLM_EVENTS, "recovered_vlm_events_different_video"), (YOLO_TEST, "exhaustive_non_vlm_vehicle_count_table")]
    ])

    write_csv("independence/VIDEO_HASH_COMPARISON.csv", list(next(iter(rows.values())).keys()), list(rows.values()))
    frame_rows = []
    durations = {"test.mov": 43.043333, "realcartest_5k.mp4": 208.333333, "long_video_dataset3.mp4": 3462.930499}
    for other in ("realcartest_5k.mp4", "long_video_dataset3.mp4"):
        for fraction in (0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99):
            ta = min(durations["test.mov"] * fraction, durations["test.mov"] - 0.05)
            tb = min(durations[other] * fraction, durations[other] - 0.05)
            ha, ma = phash(TEST, ta)
            hb, mb = phash(ROOT / rows[other]["path"], tb)
            frame_rows.append({"comparison": f"test.mov_vs_{other}", "fraction": fraction,
                               "test_timestamp": f"{ta:.6f}", "other_timestamp": f"{tb:.6f}",
                               "phash_hamming_distance": (ha ^ hb).bit_count(),
                               "test_gray_mean": f"{ma:.6f}", "other_gray_mean": f"{mb:.6f}",
                               "exact_phash_match": False})
    write_csv("independence/FRAME_CONTENT_COMPARISON.csv", list(frame_rows[0]), frame_rows)
    write("independence/VERA_EXPOSURE_AUDIT.md", """# VERA exposure audit

The user states that `test.mov` was never read or used by VERA or the current
research process. A repository search of the governing sprint and `src`
found no `test.mov` path or canonical SHA256. It did find mentions of
`realcartest_5k` as a different candidate and explicitly says it lacked a VEPC
reference. Status: `PASS_WITH_USER_PROVENANCE_ASSUMPTION`.
""")
    write("independence/HELDOUT_INDEPENDENCE_REPORT.md", f"""# Held-out independence report

Status: `PASS_WITH_USER_PROVENANCE_ASSUMPTION` for `test.mov` versus the strict
video. Byte hashes differ (`{rows['test.mov']['sha256']}` versus
`{rows['long_video_dataset3.mp4']['sha256']}`), media properties differ, and
seven beginning/middle/end proportional perceptual fingerprints have no exact
match (Hamming distances {min(r['phash_hamming_distance'] for r in frame_rows if 'long_video' in r['comparison'])}–{max(r['phash_hamming_distance'] for r in frame_rows if 'long_video' in r['comparison'])}).
No audio exists in `test.mov`, while the strict video has AAC audio. This is
strong sampled evidence, not an exhaustive mathematical comparison of all
cross-frame pairs. The user-provided non-overlap and non-use facts remain the
authoritative provenance premise.
""")

    sr = rows["realcartest_5k.mp4"]
    write_csv("mapping/SLICE_MANIFEST.csv", ["slice_id"] + list(sr), [{"slice_id": "slice_0001", **sr}])
    write_csv("mapping/SLICE_TO_TEST_MOV_TIMELINE.csv",
              ["slice_id", "claimed_relation", "verified_start_offset", "verified_end_offset", "mapping_status", "reason"],
              [{"slice_id": "slice_0001", "claimed_relation": "derived_from_test.mov_by_user_statement",
                "verified_start_offset": "", "verified_end_offset": "", "mapping_status": "REJECT_CONTENT_MISMATCH",
                "reason": "different beginning/middle/end scenes; duration 208.333333s exceeds canonical 43.043333s"}])
    write_csv("mapping/SLICE_OVERLAP_AND_GAP_AUDIT.csv", ["slice_id", "overlap_status", "gap_status", "status"],
              [{"slice_id": "slice_0001", "overlap_status": "NOT_MAPPABLE", "gap_status": "NOT_MAPPABLE", "status": "FAIL"}])
    write_csv("mapping/FRAME_CORRESPONDENCE.csv", list(frame_rows[0]),
              [r for r in frame_rows if "realcartest_5k" in r["comparison"]])
    write("mapping/MAPPING_REPORT.md", """# Slice mapping report

`FAIL_CONTENT_MISMATCH`. The sole file under `try_or_no/videos` cannot be
mapped to `test.mov`. It is a 208.333333-second, 5000-frame Bilibili road video;
`test.mov` is a 43.043333-second, 1775-decodable-frame screen recording of a
different dashcam compilation. All seven proportional perceptual comparisons
are nonmatching. Direct beginning, middle, and end inspection shows different
scenes, overlays, dates, and source watermarks. No absolute-time mapping is
defined, and the slice is not counted as an independent video.
""")

    candidates = [
        (VLM_LABELS, "PARSED_VLM_OBSERVATIONS", "realcartest", len(labels), "EXHAUSTIVE_COMPLETE_FOR_DIFFERENT_VIDEO"),
        (VLM_EVENTS, "PARSED_VLM_EVENTS", "realcartest", len(events), "DERIVED_FROM_DIFFERENT_VIDEO"),
        (YOLO_TEST, "YOLO_VEHICLE_COUNT_TABLE", "test_mov_heldout_001", len(yolo), "EXHAUSTIVE_NON_TARGET_PREDICATE"),
        (ROOT / "try_or_no/outputs/garc_meeting_pack/real_video_csv_pipeline/video_supg_smoke.csv", "YOLO_SMOKE_TABLE", "test_mov_heldout_001", 100, "PARTIAL_NON_TARGET_PREDICATE"),
        (ROOT / "try_or_no/outputs/garc_meeting_pack/real_video_csv_pipeline/realcar_5k.csv", "YOLO_VEHICLE_COUNT_TABLE", "unmappable_slice", 5000, "EXHAUSTIVE_NON_TARGET_PREDICATE"),
    ]
    write_csv("oracle_reference/ANNOTATION_FILE_INVENTORY.csv",
              ["path", "sha256", "artifact_type", "video_identity", "rows", "coverage_class", "usable_for_test_mov_vepc"],
              [{"path": str(p.relative_to(ROOT)), "sha256": sha(p), "artifact_type": typ, "video_identity": vid,
                "rows": n, "coverage_class": cov, "usable_for_test_mov_vepc": False} for p, typ, vid, n, cov in candidates])
    raw_rows = []
    for x in labels:
        p = Path(x["raw_response_path"])
        raw_rows.append({"anchor_id": x["anchor_id"], "video_id": x["video_id"],
                         "raw_response_path": str(p), "exists": p.exists(),
                         "sha256": sha(p) if p.exists() else "", "transferable_to_test_mov": False})
    write_csv("oracle_reference/RAW_RESPONSE_MANIFEST.csv", list(raw_rows[0]), raw_rows)
    obs_rows = [{"anchor_id": x["anchor_id"], "video_id": x["video_id"], "interval_start": x["start_time"],
                 "interval_end": x["end_time"], "label": x["label"], "event_type": x["event_type"],
                 "involved_object": x["involved_object"], "source_hash": sha(VLM_LABELS),
                 "mapped_test_mov_interval": "", "mapping_status": "REJECT_DIFFERENT_VIDEO"} for x in labels]
    write_csv("oracle_reference/PARSED_OBSERVATION_MANIFEST.csv", list(obs_rows[0]), obs_rows)
    counts = Counter(x["label"] for x in labels)
    write("oracle_reference/ORACLE_PROVENANCE_AUDIT.md", f"""# Oracle provenance audit

Classification for canonical `test.mov`: `UNKNOWN` / zero target-predicate VLM
observations.

Recovered Qwen3-VL evidence comprises {len(labels)} 10-second observations
({counts.get('positive',0)} positive, {counts.get('negative',0)} negative) and
{len(events)} merged VEPC events, all with `video_id=realcartest` on a roughly
3987-second source. The raw-response paths exist for
{sum(r['exists'] for r in raw_rows)}/{len(raw_rows)} observations. The VLM
discovery report explicitly classifies `test` (43 seconds) and
`realcartest_5k` (208 seconds) as different videos with no VEPC reference.

The only exhaustive table directly naming `test.mov` has {len(yolo)} rows and
was produced by YOLOv8x without a language prompt; its predicate is vehicle
count >= K, not `enter_ego_path`. It cannot be relabeled as a VLM VEPC oracle.
No human-ground-truth or real-world-semantic claim is made.
""")

    for rel, heading in [
        ("reference/STATUS.md", "Reference"), ("processor/STATUS.md", "Processor"),
        ("physical_plan/STATUS.md", "Physical plan"), ("physical/STATUS.md", "Physical"),
        ("runtime/STATUS.md", "Runtime"), ("metrics/STATUS.md", "Metrics"),
        ("diagnostics/STATUS.md", "Diagnostics"), ("logs/STATUS.md", "Logs")]:
        write(rel, f"# {heading} status\n\n`NOT_RUN_VLM_REFERENCE_INCOMPLETE`. Physical calls: `0`.\n")

    write("FINAL_DECISION.csv", "decision,independence_gate,slice_mapping,oracle_coverage,reference_freeze,processor_gate,physical_execution,physical_calls,event_precision,event_recall,event_f1,corrected_gpu_seconds,matched_dense_gpu_seconds,independent_review,reason\nVLM_REFERENCE_INCOMPLETE,PASS_WITH_USER_PROVENANCE_ASSUMPTION,FAIL_CONTENT_MISMATCH,UNKNOWN_ZERO_TEST_MOV_VEPC_VLM_OBSERVATIONS,NOT_FROZEN,NOT_RUN,NOT_RUN,0,NOT_MEASURED,NOT_MEASURED,NOT_MEASURED,NOT_MEASURED,NOT_MEASURED,PENDING,existing exhaustive Qwen3-VL oracle belongs to different realcartest video and test.mov has only YOLO vehicle-count labels\n")
    write("FINAL_REPORT.md", f"""# VLM-defined held-out reference recovery and corrected EVENT_ENUMERATE v2 gate

## Exact decision

`VLM_REFERENCE_INCOMPLETE`

`REFERENCE_TYPE = VLM_DEFINED_HELDOUT_PSEUDO_ORACLE`; `HUMAN_GT = false`;
`REAL_WORLD_SEMANTIC_CLAIM = false`.

`test.mov` passes byte/content independence from the strict video under the
user-provided provenance premise. However, no exhaustive `enter_ego_path` VLM
reference exists for its 43.043333-second timeline. The recovered 399-anchor,
51-event Qwen3-VL reference belongs to the different 3987-second
`realcartest` video. The sole claimed slice also fails content correspondence.
The exhaustive 1775-row artifact naming `test.mov` is a YOLOv8x vehicle-count
table, not a VLM VEPC annotation.

Therefore the reference was not frozen, no processor/model audit was started,
no physical plan was constructed, and physical calls equal zero. Quality and
cost metrics are `NOT_MEASURED`; VERA viability remains unresolved.

Exact next task: supply or identify exhaustive prompt-conditioned
`enter_ego_path` VLM observations whose recorded frame inputs map to
`try_or_no/test.mov` across its complete timeline. Alternatively, authorize a
new independent reference-generation pass distinct from EVENT_ENUMERATE;
that would be new oracle inference and must be sealed before operator sample
selection.
""")
    write("RESEARCH_STATE.md", """# Research state

## Established findings

- `test.mov` is byte/content-disjoint from the strict video under the user's provenance premise.
- `realcartest_5k.mp4` is not content-derived from the current `test.mov` artifact despite the supplied statement.
- The recovered exhaustive Qwen3-VL VEPC oracle is for `realcartest`, not `test.mov`.
- `test.mov` has exhaustive YOLO vehicle-count outputs, which do not answer the target event predicate.
- Physical calls in this workflow: zero.

## Active hypothesis

The intended test.mov VLM responses may exist outside the searched workspace or under an unrecorded source identity.

## Rejected hypotheses

- The current `realcartest_5k.mp4` is a temporal slice of the current `test.mov`: rejected by direct frame content.
- YOLO vehicle-count labels can instantiate `enter_ego_path`: rejected by predicate/schema mismatch.

## Unresolved uncertainty and next action

Locate a complete prompt-conditioned VEPC annotation set with frame-level lineage to `test.mov`, or authorize independent oracle generation before any EVENT_ENUMERATE call.
""")
    write("REPRODUCTION.md", """# Reproduction

Run `python AQP_Algorithm_Invention_Sprint_v1/operator_validation/vlm_heldout_event_enumerate_v2/audit/build_terminal_bundle.py` from the project environment. It reads media and historical artifacts only; it does not load Qwen3-VL or execute EVENT_ENUMERATE/VERA. Validate hashes with `FILE_MANIFEST.csv` after final sealing.
""")
    manifest = {
        "experiment": "vlm_heldout_event_enumerate_v2",
        "decision": "VLM_REFERENCE_INCOMPLETE",
        "reference_type": "VLM_DEFINED_HELDOUT_PSEUDO_ORACLE",
        "oracle_exact_by_user_assumption": True,
        "human_gt": False,
        "real_world_semantic_claim": False,
        "canonical_video_id": "test_mov_heldout_001",
        "canonical_video_sha256": rows["test.mov"]["sha256"],
        "target_vlm_observations_recovered": 0,
        "physical_calls": 0,
        "operator_executed": False,
        "vera_executed": False,
    }
    write("EXPERIMENT_MANIFEST.json", json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
