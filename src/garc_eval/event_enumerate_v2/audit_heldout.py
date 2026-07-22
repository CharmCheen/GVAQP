"""Audit existing local video/reference families for the held-out data gate."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[3]
OUTPUT = (
    ROOT
    / "AQP_Algorithm_Invention_Sprint_v1/operator_validation/event_enumerate_v2"
)
DATA = OUTPUT / "data"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _count_mp4(path: Path) -> int:
    return sum(1 for _ in path.rglob("*.mp4")) if path.exists() else 0


def candidate_rows() -> list[dict[str, object]]:
    nexar = ROOT / "datasets/casq_external/nexar"
    nexar_positive = _count_mp4(nexar / "videos_hf/train/positive")
    nexar_negative = _count_mp4(nexar / "videos_hf/train/negative")
    driving_zip = ROOT / "datasets/DrivingDojo-mini/drivingdojo_mini.zip"
    driving_sequences = 0
    if driving_zip.exists():
        with zipfile.ZipFile(driving_zip) as archive:
            metadata = json.loads(
                archive.read("drivingdojo_mini/mini_dataset.json").decode("utf-8")
            )
            driving_sequences = len(metadata)
    probe_template = ROOT / "outputs/probe_set_v1/probe_set_human_labels_template.csv"
    probe_human_rows = 0
    if probe_template.exists():
        with probe_template.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if str(row.get("final_reviewed_label", "")).strip():
                    probe_human_rows += 1
    strict_video = ROOT / "data/realcam/long_video_data/long_video_dataset3.mp4"
    return [
        {
            "candidate_family": "strict_dataset3_and_derived_clips",
            "local_video_evidence": str(strict_video.relative_to(ROOT)),
            "video_count": 1,
            "reference_evidence": "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict/frozen_inputs/event_reference.csv",
            "disjoint_from_strict_video": False,
            "unused_for_vera_selection": False,
            "trusted_event_level_reference": True,
            "same_or_formally_mapped_predicate": True,
            "empty_single_multi_coverage_proven": True,
            "gate_result": "REJECT",
            "decisive_reason": "explicitly forbidden strict video; derived dataset3/probe clips share this source",
        },
        {
            "candidate_family": "Nexar_collision_prediction_train",
            "local_video_evidence": "datasets/casq_external/nexar/videos_hf/train/{positive,negative}",
            "video_count": nexar_positive + nexar_negative,
            "reference_evidence": "datasets/casq_external/nexar/hf_metadata_probe/train/{positive,negative}/metadata.csv",
            "disjoint_from_strict_video": True,
            "unused_for_vera_selection": True,
            "trusted_event_level_reference": "PARTIAL",
            "same_or_formally_mapped_predicate": False,
            "empty_single_multi_coverage_proven": False,
            "gate_result": "REJECT",
            "decisive_reason": f"{nexar_positive} positive and {nexar_negative} negative clips are local, but labels describe one collision/near-collision alert-to-event interval, not every enter_ego_path event; multi-event completeness is absent",
        },
        {
            "candidate_family": "DrivingDojo_mini",
            "local_video_evidence": "datasets/DrivingDojo-mini/drivingdojo_mini.zip",
            "video_count": driving_sequences,
            "reference_evidence": "mini_dataset.json plus per-frame ego next-position vectors",
            "disjoint_from_strict_video": True,
            "unused_for_vera_selection": True,
            "trusted_event_level_reference": False,
            "same_or_formally_mapped_predicate": False,
            "empty_single_multi_coverage_proven": False,
            "gate_result": "REJECT",
            "decisive_reason": "contains frame sequences, camera data, ego-motion vectors, and scenario remarks but no target-event intervals or exhaustive negatives",
        },
        {
            "candidate_family": "DoTA",
            "local_video_evidence": "datasets/casq_external/dota",
            "video_count": _count_mp4(ROOT / "datasets/casq_external/dota"),
            "reference_evidence": "README_CASQ_MAPPING.md only",
            "disjoint_from_strict_video": True,
            "unused_for_vera_selection": True,
            "trusted_event_level_reference": False,
            "same_or_formally_mapped_predicate": False,
            "empty_single_multi_coverage_proven": False,
            "gate_result": "REJECT",
            "decisive_reason": "raw videos and anomaly metadata are absent locally; class-to-predicate adjudication is also required",
        },
        {
            "candidate_family": "DADA_2000",
            "local_video_evidence": "datasets/casq_external/dada2000",
            "video_count": _count_mp4(ROOT / "datasets/casq_external/dada2000"),
            "reference_evidence": "README_CASQ_MAPPING.md only",
            "disjoint_from_strict_video": True,
            "unused_for_vera_selection": True,
            "trusted_event_level_reference": False,
            "same_or_formally_mapped_predicate": False,
            "empty_single_multi_coverage_proven": False,
            "gate_result": "REJECT",
            "decisive_reason": "raw videos and accident-boundary annotations are absent locally; accident class is not the frozen predicate",
        },
        {
            "candidate_family": "Micro_CASQ_v0",
            "local_video_evidence": "datasets/casq_external/micro_casq_v0",
            "video_count": _count_mp4(ROOT / "datasets/casq_external/micro_casq_v0"),
            "reference_evidence": "micro_casq_events_template.csv",
            "disjoint_from_strict_video": "UNKNOWN",
            "unused_for_vera_selection": True,
            "trusted_event_level_reference": False,
            "same_or_formally_mapped_predicate": True,
            "empty_single_multi_coverage_proven": False,
            "gate_result": "REJECT",
            "decisive_reason": "schema template is empty and no raw videos are present",
        },
        {
            "candidate_family": "realcartest_protocol_pseudo_references",
            "local_video_evidence": "try_or_no/videos/realcartest.mp4 (missing); realcartest_5k and exported clips",
            "video_count": _count_mp4(ROOT / "datasets/clips"),
            "reference_evidence": "outputs/late_aqp_frozen_cross_segment_v1 and outputs/real_video_protocol_pilot_v1",
            "disjoint_from_strict_video": "UNPROVEN",
            "unused_for_vera_selection": False,
            "trusted_event_level_reference": False,
            "same_or_formally_mapped_predicate": "PARTIAL",
            "empty_single_multi_coverage_proven": False,
            "gate_result": "REJECT",
            "decisive_reason": "source video is missing for the main universe and references are explicitly VLM-defined pseudo-events already used in prior development",
        },
        {
            "candidate_family": "probe_set_v1",
            "local_video_evidence": "outputs/probe_set_v1/probe_media/clips",
            "video_count": _count_mp4(ROOT / "outputs/probe_set_v1/probe_media/clips"),
            "reference_evidence": "probe_set_human_labels_template.csv and VLM oracle files",
            "disjoint_from_strict_video": False,
            "unused_for_vera_selection": "UNKNOWN",
            "trusted_event_level_reference": False,
            "same_or_formally_mapped_predicate": "PARTIAL",
            "empty_single_multi_coverage_proven": False,
            "gate_result": "REJECT",
            "decisive_reason": f"clips are exported from dataset3; human template has {probe_human_rows} completed rows and VLM outputs cannot define held-out truth",
        },
        {
            "candidate_family": "experiment_video_exports",
            "local_video_evidence": "experiments/* and outputs/* clip exports",
            "video_count": _count_mp4(ROOT / "experiments") + _count_mp4(ROOT / "outputs"),
            "reference_evidence": "mixed selection/oracle development artifacts",
            "disjoint_from_strict_video": "MIXED",
            "unused_for_vera_selection": False,
            "trusted_event_level_reference": False,
            "same_or_formally_mapped_predicate": False,
            "empty_single_multi_coverage_proven": False,
            "gate_result": "REJECT",
            "decisive_reason": "exports are derived from strict/realcartest or Nexar development clips and lack an exhaustive independently frozen enter_ego_path event relation",
        },
    ]


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_requirements() -> None:
    requirements = """# Held-out data requirements

Decision: `HELDOUT_DATA_REQUIRED`.

## Decisive evidence

The local search found thousands of video files but no population satisfying
all gate conditions.  `HELDOUT_CANDIDATE_AUDIT.csv` separates availability
from validity.  The strongest candidate, Nexar, has disjoint positive and
negative clips with collision times, but it does not exhaustively annotate the
frozen `object enters ego path` predicate and cannot establish multi-event
recall.  DrivingDojo has disjoint imagery but no target-event relation.  The
remaining references are absent, pseudo-oracle-derived, development-used, or
derived from the forbidden strict video.

No physical call is permitted or spent under this decision.

## Minimum acceptable population

A future population must provide:

1. one or more videos byte-disjoint from
   `data/realcam/long_video_data/long_video_dataset3.mp4` and from its exported
   clips;
2. provenance showing the videos and reference were not used to select VERA,
   its prompt, sampling rule, parser, or thresholds;
3. an independently frozen, exhaustive event-level reference for the exact
   v1 prompt definition of `enter_ego_path`, or a documented one-to-one
   predicate mapping reviewed before sampling;
4. explicit reviewed negative coverage, not merely absence of a positive
   dataset label;
5. enough continuous duration to form empty, one-event, and multi-event
   operator intervals, plus events crossing proposed ownership boundaries;
6. both short and long events and multiple actor types where the source
   population contains them;
7. source FPS/frame count and a license/provenance record;
8. evaluator-only storage isolated from inference inputs; and
9. a frozen adjudication protocol with at least two independent reviewers for
   positives, hard negatives, and disputed boundaries.

## Reference creation prohibition

VERA outputs, EVENT_ENUMERATE v2 outputs, and prompt-specific Qwen responses
must not create or repair the reference.  Existing VLM pseudo-labels may help
locate candidate media for human annotation only if selection provenance is
recorded and annotators review the full sampled population; they cannot be
accepted as truth.

## Next gate

After a compliant reference is delivered, validate its schema and provenance,
freeze `HELDOUT_SAMPLE.csv`, keep
`HELDOUT_REFERENCE_EVALUATOR_ONLY.csv` inaccessible to inference, then replace
the proposed matrix with a hash-sealed call matrix.  Processor tests must be
rerun against the unchanged frozen source before any GPU call.
"""
    (DATA / "HELDOUT_DATA_REQUIREMENTS.md").write_text(requirements, encoding="utf-8")

    schema = """# Required annotation schema

## Video table

Required fields:

| Field | Meaning |
|---|---|
| `population_id` | immutable annotation-population ID |
| `video_id` | stable video ID |
| `video_path` | evaluator-resolvable path; not exposed as a label carrier |
| `video_sha256` | full file hash |
| `source_dataset` | provenance and license family |
| `source_split` | split fixed before this gate |
| `fps` | verified source FPS |
| `total_frames` | verified frame count |
| `duration_seconds` | container duration |
| `used_for_vera_or_operator_development` | must be false |
| `provenance_review_status` | must be `PASS` |

## Event relation

One row per true event:

| Field | Constraint |
|---|---|
| `population_id`, `video_id`, `event_id` | unique composite key |
| `event_start`, `event_end` | finite absolute video seconds, `0 <= start < end <= duration` |
| `event_type` | exactly `enter_ego_path` after any frozen mapping |
| `involved_object` | `vehicle`, `pedestrian`, `cyclist`, `other`, or `unknown` |
| `object_identity` | reviewer-visible distinguishing description |
| `ego_relevant` | true |
| `boundary_confidence` | high/medium/low |
| `predicate_mapping_id` | exact predicate or prereviewed formal mapping |
| `annotator_ids` | at least two independent annotators for accepted events |
| `adjudicator_id` | required for disagreement |
| `reference_frozen_at` | timestamp before operator inference |
| `source_evidence` | frames/timestamps used by reviewers |

## Reviewed coverage intervals

To prove emptiness and exhaustiveness, a separate table must partition every
eligible video into reviewed intervals with fields
`coverage_id, video_id, start, end, review_complete, visibility_status,
annotator_ids, adjudication_status`.  An empty operator interval is valid only
when fully contained in coverage marked complete and containing no reference
event.  Unreviewable time must be excluded, never treated as negative.

## Evaluator-only derived fields

After reference freeze, the evaluator may derive event duration, actor/type,
empty/single/multi count, boundary-straddling status, and proposed sample
strata.  These fields must not be passed to inference.  All derivations and
the final reference hash must be reproducible.
"""
    (DATA / "REQUIRED_ANNOTATION_SCHEMA.md").write_text(schema, encoding="utf-8")

    matrix = [
        {
            "primary_stratum": "empty_reviewed",
            "enumeration_intervals": 3,
            "matched_dense_10s_calls": 15,
            "deterministic_repeat_calls": 2,
            "required_content": "fully reviewed hard and ordinary negatives",
            "selection_uses_reference_only_in_evaluator": True,
        },
        {
            "primary_stratum": "single_event",
            "enumeration_intervals": 3,
            "matched_dense_10s_calls": 15,
            "deterministic_repeat_calls": 2,
            "required_content": "short and long events; actor diversity",
            "selection_uses_reference_only_in_evaluator": True,
        },
        {
            "primary_stratum": "multi_event",
            "enumeration_intervals": 3,
            "matched_dense_10s_calls": 15,
            "deterministic_repeat_calls": 2,
            "required_content": "at least two distinct true events per interval",
            "selection_uses_reference_only_in_evaluator": True,
        },
        {
            "primary_stratum": "ownership_boundary_straddle",
            "enumeration_intervals": 2,
            "matched_dense_10s_calls": 10,
            "deterministic_repeat_calls": 2,
            "required_content": "event midpoint or extent near a frozen core boundary",
            "selection_uses_reference_only_in_evaluator": True,
        },
        {
            "primary_stratum": "final_partial_interval",
            "enumeration_intervals": 1,
            "matched_dense_10s_calls": 2,
            "deterministic_repeat_calls": 2,
            "required_content": "short final input with reviewed coverage",
            "selection_uses_reference_only_in_evaluator": True,
        },
    ]
    for row in matrix:
        row["proposed_total_physical_calls"] = (
            int(row["enumeration_intervals"])
            + int(row["matched_dense_10s_calls"])
            + int(row["deterministic_repeat_calls"])
        )
        row["status"] = "PROPOSAL_ONLY_NOT_FROZEN"
    _write_csv(DATA / "PROPOSED_SAMPLE_MATRIX.csv", matrix)


def audit() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    rows = candidate_rows()
    _write_csv(DATA / "HELDOUT_CANDIDATE_AUDIT.csv", rows)
    if any(row["gate_result"] == "ACCEPT" for row in rows):
        raise RuntimeError("audit code found an accepted family; manual gate update required")
    write_requirements()
    summary = {
        "decision": "HELDOUT_DATA_REQUIRED",
        "candidate_families_audited": len(rows),
        "accepted_families": 0,
        "physical_calls_permitted": False,
        "physical_calls_spent": 0,
        "candidate_audit_sha256": sha256_file(DATA / "HELDOUT_CANDIDATE_AUDIT.csv"),
    }
    (DATA / "HELDOUT_GATE.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    audit()


if __name__ == "__main__":
    main()
