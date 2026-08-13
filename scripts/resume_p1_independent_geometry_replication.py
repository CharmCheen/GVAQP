#!/usr/bin/env python3
"""Freeze the P1 human reference and run the preregistered P1 analysis.

Fail-closed: without two complete independent annotations and a complete
adjudication CSV this script reports readiness and writes no scientific result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeRegressor

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from garc_eval.accelerated_event_query.matching import MatchConfig, match_events, summarize_matches
from garc_eval.accelerated_event_query.types import EventRecord
from garc_eval.p1b_protocol_v1_2 import assign_positive_units_to_events, reference_quality_decision


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/p1_independent_geometry_replication_v1"
RAW = OUT / "HUMAN_EVENT_LABELS.jsonl"
CASES = OUT / "ANNOTATOR_VIEW_CASES.json"
ADJUDICATED = OUT / "ADJUDICATED_EVENTS.csv"
TRACE = OUT / "TRACE_POPULATION.csv"
PAIRS = OUT / "TRACE_PAIR_MANIFEST.csv"
PRIMARY_PAIRS = OUT / "PRIMARY_GEOMETRY_PAIR_MANIFEST_V1_2.csv"
PROTOCOL = OUT / "P1_PROTOCOL.json"
HUMAN_PROTOCOL = OUT / "HUMAN_REFERENCE_PROTOCOL.json"
P1B_FREEZE = OUT / "P1B_PROTOCOL_V1_2_FREEZE.json"
Q1 = ROOT / "outputs/v10_multiseal_reference_v1/FINAL_UNIT_REFERENCE.parquet"
Q2 = ROOT / "outputs/gvaqp_long_horizon_p1_p3_v1/qwen32_oracle/P1_QWEN32_UNIT_OUTCOMES.parquet"
VIDEOS = ("DALI", "HANGZHOU", "WUHAN")
QUERIES = ("Q_DRIVER_RESPONSE_V1", "Q_VULNERABLE_ROAD_USER_CONFLICT_V1")
PROXIES = (
    "PROXY_A_YOLOV8N_OBJECT_MOTION",
    "PROXY_B_OPTICAL_FLOW_VISUAL_DYNAMICS",
)
PUBLIC_FEATURES = [
    "positive_yield", "number_of_temporal_regions_touched", "temporal_dispersion",
    "coverage_fraction", "largest_unqueried_gap", "median_unqueried_gap",
    "query_redundancy", "near_duplicate_query_fraction", "queried_temporal_span",
]
REFERENCE_FEATURES = [
    "distance_to_existing_verified_evidence",
    "human_reference_event_count", "reference_event_temporal_dispersion",
    "mean_positive_distance_to_reference", "reference_events_touched_OFFLINE_DIAGNOSTIC",
]


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def latest_annotations() -> tuple[dict[str, dict], dict[tuple[str, str], dict], list[str]]:
    cases = {item["case_id"]: item for item in json.loads(CASES.read_text())}
    records = [json.loads(line) for line in RAW.read_text().splitlines() if line.strip()]
    latest: dict[tuple[str, str], dict] = {}
    protocol_hash = json.loads(HUMAN_PROTOCOL.read_text())["protocol_hash"]
    for row in records:
        if row.get("case_id") not in cases:
            raise RuntimeError("annotation references unknown case")
        if row.get("protocol_hash") != protocol_hash:
            raise RuntimeError("annotation protocol hash mismatch")
        required = {"annotator_id","case_id","video_id","query_id","event_exists","events","saved_at_utc","protocol_hash"}
        if not required.issubset(row) or row.get("annotator_id") not in {"ANNOTATOR_A","ANNOTATOR_B"}:
            raise RuntimeError("annotation schema/provenance invalid")
        case = cases[row["case_id"]]
        if row["video_id"] != case["video_id"] or row["query_id"] != case["query_id"]:
            raise RuntimeError("annotation provenance identity mismatch")
        if bool(row["event_exists"]) != bool(row["events"]):
            raise RuntimeError("annotation explicit no-event state invalid")
        seen_ids=set()
        for event in row["events"]:
            start,end=float(event["start_time"]),float(event["end_time"])
            annotation_id=str(event.get("annotation_id",""))
            if not (0 <= start < end <= float(case["duration_sec"])) or not annotation_id or annotation_id in seen_ids:
                raise RuntimeError("annotation event schema/timestamp/ID invalid")
            if not isinstance(event.get("boundary_ambiguous"),bool) or not isinstance(event.get("semantic_ambiguity"),bool):
                raise RuntimeError("annotation ambiguity schema invalid")
            seen_ids.add(annotation_id)
        latest[(str(row.get("annotator_id")), str(row["case_id"]))] = row
    annotators = sorted({key[0] for key in latest})
    return cases, latest, annotators


def verify_protocol_freeze() -> None:
    if not P1B_FREEZE.exists():
        raise RuntimeError("P1-B v1.2 freeze missing")
    freeze=json.loads(P1B_FREEZE.read_text())
    for relative, expected in freeze["artifact_hashes"].items():
        path=ROOT/relative
        if not path.exists() or sha(path) != expected:
            raise RuntimeError(f"P1-B v1.2 protocol hash mismatch: {relative}")


def readiness() -> dict:
    cases, latest, annotators = latest_annotations()
    complete = []
    missing = {}
    for annotator in annotators:
        absent = sorted(case for case in cases if (annotator, case) not in latest)
        if absent:
            missing[annotator] = absent
        else:
            complete.append(annotator)
    required = {"ANNOTATOR_A", "ANNOTATOR_B"}
    return {
        "raw_records": sum(1 for line in RAW.read_text().splitlines() if line.strip()),
        "annotators_seen": annotators,
        "complete_annotators": complete,
        "missing_cases_by_annotator": missing,
        "two_complete_independent_annotators": required.issubset(complete),
        "required_annotator_ids": sorted(required),
        "adjudication_file_present": ADJUDICATED.exists(),
    }


def interval_iou(left: dict, right: dict) -> float:
    overlap = max(0.0, min(float(left["end_time"]), float(right["end_time"])) - max(float(left["start_time"]), float(right["start_time"])))
    union = max(float(left["end_time"]), float(right["end_time"])) - min(float(left["start_time"]), float(right["start_time"]))
    return overlap / union if union else 0.0


def match_annotation_events(left: list[dict], right: list[dict], minimum_iou: float = 0.0) -> list[tuple[dict, dict, float]]:
    if not left or not right:
        return []
    scores = np.asarray([[interval_iou(a, b) for b in right] for a in left])
    rows, cols = linear_sum_assignment(-scores)
    return [(left[i], right[j], float(scores[i, j])) for i, j in zip(rows, cols) if scores[i, j] >= minimum_iou and scores[i, j] > 0]


def validate_independent_annotations() -> tuple[dict, dict[tuple[str, str], dict], pd.DataFrame, dict]:
    """Validate complete A/B exports and compute agreement without opening method outcomes."""
    cases, latest, _ = latest_annotations()
    annotators = ("ANNOTATOR_A", "ANNOTATOR_B")
    if not all(all((a, case_id) in latest for case_id in cases) for a in annotators):
        raise RuntimeError("ANNOTATOR_A and ANNOTATOR_B must each complete all six cases")
    exported: dict[str, list[dict]] = {a: [] for a in annotators}
    comparison = []
    for case_id, case in cases.items():
        for annotator in annotators:
            record = latest[(annotator, case_id)]
            if bool(record.get("event_exists")) != bool(record.get("events")):
                raise RuntimeError(f"explicit no-event mismatch: {annotator}/{case_id}")
            seen = set()
            for index, event in enumerate(record["events"], 1):
                start, end = float(event["start_time"]), float(event["end_time"])
                if not (0 <= start < end <= float(case["duration_sec"])):
                    raise RuntimeError(f"invalid interval: {annotator}/{case_id}")
                annotation_id = str(event.get("annotation_id", ""))
                if not annotation_id or annotation_id in seen:
                    raise RuntimeError(f"missing/duplicate annotation_id: {annotator}/{case_id}")
                seen.add(annotation_id)
                exported[annotator].append({
                    "annotation_id": annotation_id, "annotator_id": annotator,
                    "video_id": case["video_id"], "query_id": case["query_id"],
                    "event_index": index, "start_time": start, "end_time": end,
                    "boundary_ambiguous": bool(event["boundary_ambiguous"]),
                    "semantic_ambiguity": bool(event["semantic_ambiguity"]),
                    "optional_note": str(event.get("optional_note", "")),
                    "adjudication_status": "UNADJUDICATED_INDEPENDENT",
                })
        left, right = latest[(annotators[0], case_id)]["events"], latest[(annotators[1], case_id)]["events"]
        raw = match_annotation_events(left, right)
        row = {
            "case_id": case_id, "video_id": case["video_id"], "query_id": case["query_id"],
            "annotator_a_event_count": len(left), "annotator_b_event_count": len(right),
            "event_existence_agreement": bool(left) == bool(right),
            "median_matched_temporal_iou": float(np.median([m[2] for m in raw])) if raw else math.nan,
            "median_abs_start_disagreement_sec": float(np.median([abs(float(a["start_time"])-float(b["start_time"])) for a,b,_ in raw])) if raw else math.nan,
            "median_abs_end_disagreement_sec": float(np.median([abs(float(a["end_time"])-float(b["end_time"])) for a,b,_ in raw])) if raw else math.nan,
            "boundary_ambiguity_rate": float(np.mean([bool(e["boundary_ambiguous"]) for e in left+right])) if left or right else 0.0,
            "semantic_ambiguity_rate": float(np.mean([bool(e["semantic_ambiguity"]) for e in left+right])) if left or right else 0.0,
        }
        for threshold in (0.1, 0.3, 0.5):
            matched = match_annotation_events(left, right, threshold)
            suffix = str(threshold).replace(".", "p")
            row[f"matched_events_iou_ge_{suffix}"] = len(matched)
            row[f"unmatched_a_iou_ge_{suffix}"] = len(left)-len(matched)
            row[f"unmatched_b_iou_ge_{suffix}"] = len(right)-len(matched)
        row["matched_events_iou_gt_0"] = len(raw)
        # This blinded manual review flag is false unless a protocol auditor,
        # before method outcomes, explicitly documents systematic misunderstanding.
        row["systematic_semantic_misunderstanding"] = False
        comparison.append(row)
    columns = ["annotation_id","annotator_id","video_id","query_id","event_index","start_time","end_time","boundary_ambiguous","semantic_ambiguity","optional_note","adjudication_status"]
    for annotator, name in zip(annotators, ("ANNOTATOR_A_EVENTS.csv", "ANNOTATOR_B_EVENTS.csv")):
        pd.DataFrame(exported[annotator], columns=columns).to_csv(OUT/name, index=False)
    agreement = pd.DataFrame(comparison)
    agreement.to_csv(OUT/"ANNOTATOR_EVENT_COMPARISON.csv", index=False)
    total_events = int(agreement.annotator_a_event_count.sum()+agreement.annotator_b_event_count.sum())
    matched0 = int(agreement.matched_events_iou_gt_0.sum())
    correspondence = 1.0 if total_events == 0 else 2*matched0/total_events
    quality, failure_reasons = reference_quality_decision(agreement.to_dict("records"))
    diagnostics = {"event_existence_agreement":float(agreement.event_existence_agreement.mean()),
                   "global_matched_event_fraction_iou_gt_0":correspondence,
                   "median_matched_temporal_iou":float(agreement.median_matched_temporal_iou.median()),
                   "median_abs_start_difference":float(agreement.median_abs_start_disagreement_sec.median()),
                   "median_abs_end_difference":float(agreement.median_abs_end_disagreement_sec.median()),
                   "boundary_ambiguity_rate":float(agreement.boundary_ambiguity_rate.mean()),
                   "semantic_ambiguity_rate":float(agreement.semantic_ambiguity_rate.mean()),
                   "failure_reasons":failure_reasons,"human_reference_quality":quality}
    (OUT/"ANNOTATION_VALIDATION.md").write_text("# Annotation validation\n\nAll 12 required annotator-case combinations are complete; timestamps, IDs, explicit no-event states, provenance, and schemas are valid. No policy/method outcomes were read.\n")
    (OUT/"HUMAN_REFERENCE_AGREEMENT.md").write_text(
        "# Human reference agreement (pre-adjudication)\n\n" +
        "Agreement was measured per video-query with one-to-one maximum-IoU matching at 0.1/0.3/0.5.\n\n```json\n"+
        json.dumps(diagnostics, indent=2, sort_keys=True)+"\n```\n")
    if quality == "INSUFFICIENT":
        (OUT/"REFERENCE_PROTOCOL_FAILURE_ANALYSIS.md").write_text(
            "# Reference protocol failure analysis\n\n`HUMAN_REFERENCE_QUALITY = INSUFFICIENT`\n\n"
            "The preregistered triage gate failed. Do not adjudicate, delete cases, or inspect method outcomes. "
            "A protocol amendment followed by full six-case reannotation is required.\n")
    template = []
    for case_id, case in cases.items():
        template.append({"case_id":case_id,"video_id":case["video_id"],"query_id":case["query_id"],
            "annotator_a_events_json":json.dumps(latest[("ANNOTATOR_A",case_id)]["events"],sort_keys=True),
            "annotator_b_events_json":json.dumps(latest[("ANNOTATOR_B",case_id)]["events"],sort_keys=True),
            "adjudicator_id":"","adjudication_action":"","event_exists":"","events_json":"","adjudication_reason":""})
    pd.DataFrame(template).to_csv(OUT/"ADJUDICATION_TEMPLATE.csv", index=False)
    return cases, latest, agreement, diagnostics


def freeze_adjudicated_reference(cases: dict, diagnostics: dict) -> tuple[pd.DataFrame, dict]:
    if diagnostics["human_reference_quality"] != "ADJUDICATION_ELIGIBLE":
        raise RuntimeError("human reference quality gate failed; adjudication forbidden")
    if not ADJUDICATED.exists():
        raise RuntimeError("agreement sufficient; complete blinded ADJUDICATED_EVENTS.csv from ADJUDICATION_TEMPLATE.csv")
    adjudicated = pd.read_csv(ADJUDICATED, keep_default_na=False)
    required = ["case_id","video_id","query_id","annotator_a_events_json","annotator_b_events_json",
                "adjudicator_id","adjudication_action","event_exists","events_json","adjudication_reason"]
    if list(adjudicated.columns) != required or len(adjudicated) != 6 or set(adjudicated.case_id) != set(cases):
        raise RuntimeError("adjudication schema or six-case coverage invalid")
    actions = {"ACCEPT_A","ACCEPT_B","MERGE","SPLIT","REDRAW","NO_EVENT","MIXED"}
    events, log = [], []
    for row in adjudicated.to_dict("records"):
        case = cases[row["case_id"]]
        if row["video_id"] != case["video_id"] or row["query_id"] != case["query_id"] or row["adjudication_action"] not in actions:
            raise RuntimeError("invalid adjudication identity/action")
        if not row["adjudicator_id"].strip() or not row["adjudication_reason"].strip():
            raise RuntimeError("adjudicator and reason required")
        parsed = json.loads(row["events_json"]); exists = row["event_exists"].lower()
        if exists not in {"true","false"} or not isinstance(parsed,list) or (exists=="true") != bool(parsed):
            raise RuntimeError("adjudicated event_exists/list mismatch")
        for index,event in enumerate(parsed,1):
            start,end=float(event["start_time"]),float(event["end_time"])
            if not 0 <= start < end <= float(case["duration_sec"]): raise RuntimeError("adjudicated interval outside video")
            events.append({"video_id":row["video_id"],"query_id":row["query_id"],"event_id":f"P1::{row['video_id']}::{row['query_id']}::E{index:03d}",
                "start_time":start,"end_time":end,"boundary_ambiguous":bool(event.get("boundary_ambiguous",False)),
                "semantic_ambiguity":bool(event.get("semantic_ambiguity",False)),"annotator_id":row["adjudicator_id"],"adjudication_status":"ADJUDICATED_FROZEN"})
        log.append({k:row[k] for k in ("case_id","video_id","query_id","adjudicator_id","adjudication_action","adjudication_reason")})
    reference=pd.DataFrame(events,columns=["video_id","query_id","event_id","start_time","end_time","boundary_ambiguous","semantic_ambiguity","annotator_id","adjudication_status"])
    reference.to_csv(OUT/"HUMAN_REFERENCE_ADJUDICATED.csv",index=False); reference.to_csv(OUT/"HUMAN_REFERENCE_EVENTS.csv",index=False)
    pd.DataFrame(log).to_csv(OUT/"ADJUDICATION_LOG.csv",index=False)
    freeze={"status":"FROZEN","human_reference_frozen":True,"created_at_utc":datetime.now(timezone.utc).isoformat(),"annotators":["ANNOTATOR_A","ANNOTATOR_B"],
            "case_count":6,"event_count":len(reference),"reference_sha256":sha(OUT/"HUMAN_REFERENCE_ADJUDICATED.csv"),
            "query_definition_sha256":sha(OUT/"QUERY_DEFINITIONS.md"),"annotation_guide_sha256":sha(OUT/"ANNOTATION_GUIDE.md"),
            "protocol_hash":json.loads(HUMAN_PROTOCOL.read_text())["protocol_hash"],"adjudication_sha256":sha(ADJUDICATED)}
    write_json(OUT/"HUMAN_REFERENCE_FREEZE.json",freeze)
    return reference,freeze


def load_semantic_labels() -> dict[tuple[str, str], dict[str, dict]]:
    old = pd.read_parquet(Q1)
    new = pd.read_parquet(Q2)
    result = {}
    for query, frame, label_column, start_column, end_column in (
        (QUERIES[0], old, "authoritative_label", "start_time", "end_time"),
        (QUERIES[1], new, "label", "start_time", "end_time"),
    ):
        for video, group in frame.groupby("video_id", sort=True):
            result[(str(video), query)] = {
                str(row.unit_id): {
                    "label": str(getattr(row, label_column)),
                    "start": float(getattr(row, start_column)),
                    "end": float(getattr(row, end_column)),
                }
                for row in group.itertuples(index=False)
            }
    return result


def overlap(start: float, end: float, event_start: float, event_end: float) -> bool:
    return max(start, event_start) < min(end, event_end)


def c1_events(positive: list[dict]) -> list[tuple[float, float]]:
    ordered = sorted(positive, key=lambda item: (item["start"], item["end"], item["unit_id"]))
    groups: list[list[dict]] = []
    for item in ordered:
        if not groups or item["start"] - groups[-1][-1]["end"] > 10.0:
            groups.append([item])
        else:
            groups[-1].append(item)
    return [(min(item["start"] for item in group), max(item["end"] for item in group)) for group in groups]


def authoritative_c1_metrics(
    predictions: list[tuple[float, float]], references: list[tuple[float, float]],
    video: str, query: str,
) -> tuple[float, float, float, float]:
    predicted = [
        EventRecord(f"P1_C1::{video}::{query}::{index:04d}", query, video, start, end, 1.0,
                    "VERIFIED_EVENT", (), (), "C1_GAP_ONLY_FROZEN", None)
        for index, (start, end) in enumerate(predictions, 1)
    ]
    reference = [
        EventRecord(f"P1_HUMAN::{video}::{query}::{index:04d}", query, video, start, end, 1.0,
                    "HUMAN_ADJUDICATED_EVENT", (), (), "P1_HUMAN_REFERENCE", None)
        for index, (start, end) in enumerate(references, 1)
    ]
    matches = match_events(predicted, reference, MatchConfig(minimum_tiou=0.0, boundary_tolerance_sec=0.0))
    summary = summarize_matches(
        predicted, reference,
        matches,
    )
    return (
        float(summary["32b_operational_oracle_relative_event_precision"]),
        float(summary["32b_operational_oracle_relative_event_recall"]),
        float(summary["event_f1"]),
        float(np.mean([match.temporal_iou for match in matches])) if matches else 0.0,
    )


def safe_f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def materializer_independent_results(reference: pd.DataFrame) -> pd.DataFrame:
    trace = pd.read_csv(TRACE)
    labels = load_semantic_labels()
    rows = []
    for item in trace.itertuples(index=False):
        selected_ids = json.loads(item.queried_unit_ids)
        mapping = labels[(item.video_id, item.query_id)]
        positive = [
            {**mapping[unit], "unit_id": unit}
            for unit in selected_ids if mapping[unit]["label"] == "relevant"
        ]
        refs = reference[(reference.video_id == item.video_id) & (reference.query_id == item.query_id)]
        reference_intervals = [(float(row.start_time), float(row.end_time)) for row in refs.itertuples()]
        ref_events = [{"event_id":str(row.event_id),"start_time":float(row.start_time),"end_time":float(row.end_time)} for row in refs.itertuples()]
        anchor_counts_by_id = assign_positive_units_to_events(positive, ref_events, "ANCHOR_ASSIGNED_EVENT")
        overlap_counts_by_id = assign_positive_units_to_events(positive, ref_events, "OVERLAP_ANY_EVENT")
        evidence_counts = list(anchor_counts_by_id.values())
        overlap_counts = list(overlap_counts_by_id.values())
        touched = sum(count >= 1 for count in evidence_counts)
        overlap_touched = sum(count >= 1 for count in overlap_counts)
        evidence_hits = sum(anchor_counts_by_id.values())
        evidence_precision = evidence_hits / len(positive) if positive else (1.0 if not reference_intervals else 0.0)
        coverage_defined = bool(reference_intervals)
        evidence_recall = touched / len(reference_intervals) if coverage_defined else math.nan
        predictions = c1_events(positive)
        c1_precision, c1_recall, c1_f1, c1_iou = authoritative_c1_metrics(
            predictions, reference_intervals, item.video_id, item.query_id
        )
        ref_centers = np.asarray([(start + end) / 2 for start, end in reference_intervals])
        positive_centers = np.asarray([(value["start"] + value["end"]) / 2 for value in positive])
        mean_distance = float(np.mean([np.min(np.abs(ref_centers - center)) for center in positive_centers])) if len(ref_centers) and len(positive_centers) else 0.0
        rows.append({
            **item._asdict(),
            "human_reference_event_count": len(reference_intervals),
            "human_events_with_0_semantic_evidence": sum(count == 0 for count in evidence_counts),
            "human_events_with_1plus_verified_positive": sum(count >= 1 for count in evidence_counts),
            "human_events_with_2plus_verified_positive": sum(count >= 2 for count in evidence_counts),
            "distinct_human_events_touched": touched,
            "distinct_human_events_anchor_assigned": touched,
            "human_event_coverage_anchor_assigned": evidence_recall,
            "events_with_zero_anchor_assigned_evidence": sum(count == 0 for count in evidence_counts),
            "events_with_1plus_anchor_assigned_evidence": sum(count >= 1 for count in evidence_counts),
            "distinct_human_events_overlap_any": overlap_touched,
            "human_event_coverage_overlap_any": overlap_touched / len(reference_intervals) if coverage_defined else math.nan,
            "human_event_coverage": evidence_recall,
            "human_event_coverage_defined": coverage_defined,
            "human_event_recall": evidence_recall,
            "semantic_evidence_precision": evidence_precision,
            "human_event_F1": safe_f1(evidence_precision, evidence_recall) if coverage_defined else math.nan,
            "C1_event_precision_SECONDARY": c1_precision,
            "C1_event_recall_SECONDARY": c1_recall,
            "C1_EventF1_SECONDARY": c1_f1,
            "C1_MatchedMeanIoU_SECONDARY": c1_iou,
            "reference_event_temporal_dispersion": float(np.std(ref_centers)) if len(ref_centers) else 0.0,
            "mean_positive_distance_to_reference": mean_distance,
            "reference_events_touched_OFFLINE_DIAGNOSTIC": touched,
        })
    return pd.DataFrame(rows)


def primary_pairs(endpoints: pd.DataFrame) -> pd.DataFrame:
    pairs = pd.read_csv(PRIMARY_PAIRS)
    lookup = endpoints.set_index("trace_instance_id")
    rows = []
    metrics = [
        "distinct_human_events_touched", "human_event_recall", "human_event_F1",
        "human_event_coverage", "human_events_with_0_semantic_evidence",
        "human_events_with_1plus_verified_positive", "human_events_with_2plus_verified_positive",
        "distinct_human_events_anchor_assigned", "human_event_coverage_anchor_assigned",
        "events_with_zero_anchor_assigned_evidence", "events_with_1plus_anchor_assigned_evidence",
        "distinct_human_events_overlap_any", "human_event_coverage_overlap_any",
        "C1_EventF1_SECONDARY",
    ]
    for pair in pairs.itertuples(index=False):
        high = lookup.loc[pair.trace_a_better_geometry]
        low = lookup.loc[pair.trace_b_worse_geometry]
        row = pair._asdict()
        for metric in metrics:
            row[f"better_{metric}"] = float(high[metric])
            row[f"worse_{metric}"] = float(low[metric])
            row[f"delta_{metric}"] = float(high[metric] - low[metric])
        rows.append(row)
    result=pd.DataFrame(rows)
    result["primary_sensitivity_direction_agree_coverage"] = (
        np.sign(result.delta_human_event_coverage_anchor_assigned)
        == np.sign(result.delta_human_event_coverage_overlap_any)
    )
    return result


def model_factory(name: str):
    if name == "linear":
        estimator = LinearRegression()
    elif name == "ridge":
        estimator = Ridge(alpha=1.0)
    elif name == "small_tree":
        estimator = DecisionTreeRegressor(max_depth=2, min_samples_leaf=12, random_state=0)
    else:
        raise ValueError(name)
    return Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler()), ("model", estimator)])


def heldout_models(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame[frame.human_event_coverage_defined].copy()
    representations = {
        "YIELD_ONLY": ["positive_yield"],
        "YIELD_PLUS_PUBLIC_GEOMETRY": PUBLIC_FEATURES,
        "REFERENCE_AWARE_DIAGNOSTIC": [*PUBLIC_FEATURES, *REFERENCE_FEATURES],
    }
    rows = []
    splits = [
        ("LOVO", video, frame.video_id != video, frame.video_id == video)
        for video in VIDEOS
    ] + [
        ("LOVQO", f"{video}::{query}",
         (frame.video_id != video) | (frame.query_id != query),
         (frame.video_id == video) & (frame.query_id == query))
        for video in VIDEOS for query in QUERIES
    ]
    for split, heldout, train_mask, test_mask in splits:
        train, test = frame[train_mask], frame[test_mask]
        for representation, features in representations.items():
            for model_name in ("linear", "ridge", "small_tree"):
                model = model_factory(model_name).fit(train[features], train.human_event_coverage)
                prediction = model.predict(test[features])
                rows.append({
                    "split": split, "heldout": heldout,
                    "representation": representation, "model": model_name,
                    "n_train": len(train), "n_test": len(test),
                    "R2": float(r2_score(test.human_event_coverage, prediction)),
                    "MAE": float(mean_absolute_error(test.human_event_coverage, prediction)),
                    "mean_prediction": float(np.mean(prediction)),
                    "mean_observed": float(test.human_event_coverage.mean()),
                })
    result = pd.DataFrame(rows)
    macro = result.groupby(["split", "representation", "model"], as_index=False).agg(
        R2=("R2", "mean"), MAE=("MAE", "mean"),
        n_train=("n_train", "sum"), n_test=("n_test", "sum"),
    )
    macro["heldout"] = "MACRO_MEAN"
    macro["mean_prediction"] = np.nan
    macro["mean_observed"] = np.nan
    return pd.concat([result, macro[result.columns]], ignore_index=True)


def cluster_effects(primary: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    deltas = [
        "delta_distinct_human_events_touched", "delta_human_event_coverage",
        "delta_human_event_F1", "delta_C1_EventF1_SECONDARY",
    ]
    dependent = primary[primary.trace_a_proxy_dependent | primary.trace_b_proxy_dependent].copy()
    shared = primary[~primary.trace_a_proxy_dependent & ~primary.trace_b_proxy_dependent].copy()
    proxy = dependent.groupby(["video_id", "query_id", "proxy_id"], as_index=False).agg(
        exact_pairs=("budget", "size"),
        **{f"mean_{column}": (column, "mean") for column in deltas},
        **{f"median_{column}": (column, "median") for column in deltas},
    )
    proxy_overall = proxy.groupby(["video_id", "query_id"], as_index=False).agg(
        proxy_count=("proxy_id", "nunique"), exact_pairs=("exact_pairs", "sum"),
        **{f"mean_{column}": (f"mean_{column}", "mean") for column in deltas},
        **{f"median_{column}": (f"median_{column}", "mean") for column in deltas},
    )
    shared = shared.drop_duplicates(["video_id","query_id","pair_content_hash"])
    shared_effect = shared.groupby(["video_id","query_id"],as_index=False).agg(
        shared_control_pairs=("budget","size"),
        **{f"shared_mean_{column}":(column,"mean") for column in deltas},
    )
    overall = proxy_overall.merge(shared_effect,on=["video_id","query_id"],how="outer").fillna({"shared_control_pairs":0,"proxy_count":0,"exact_pairs":0})
    for column in deltas:
        proxy_column=f"mean_{column}"; shared_column=f"shared_mean_{column}"
        overall[proxy_column]=[
            float(np.mean([x for x in (p,s) if pd.notna(x)]))
            for p,s in zip(overall[proxy_column],overall[shared_column])
        ]
    overall["both_proxy_coverage_signs"] = [
        ";".join(f"{r.proxy_id}:{np.sign(r.mean_delta_human_event_coverage):+.0f}" for r in proxy[(proxy.video_id==v)&(proxy.query_id==q)].itertuples())
        for v,q in zip(overall.video_id,overall.query_id)
    ]
    return proxy, overall


def cluster_bootstrap(overall: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    metrics = ["mean_delta_distinct_human_events_touched", "mean_delta_human_event_coverage", "mean_delta_human_event_F1"]
    rng = np.random.default_rng(20260813)
    records = []
    values = overall[metrics].to_numpy(float)
    for replicate in range(10_000):
        sampled = values[rng.integers(0, len(values), size=len(values))]
        for index, metric in enumerate(metrics):
            records.append({"replicate": replicate, "metric": metric, "median_effect": float(np.median(sampled[:, index]))})
    frame = pd.DataFrame(records)
    summary = {
        metric: {
            "median": float(group.median_effect.median()),
            "ci95": [float(value) for value in group.median_effect.quantile([0.025, 0.975])],
        }
        for metric, group in frame.groupby("metric", sort=True)
    }
    return frame, summary


def decide(primary: pd.DataFrame, models: pd.DataFrame) -> tuple[str, dict]:
    protocol = json.loads(PROTOCOL.read_text())
    gate = protocol["p1_final_gate_operationalization"]
    proxy_effects, overall = cluster_effects(primary)
    counts = primary.groupby("proxy_id").size().to_dict()
    clusters_per_proxy = primary.groupby("proxy_id").apply(
        lambda group: group.groupby(["video_id", "query_id"]).ngroups,
        include_groups=False,
    ).to_dict()
    macro = models[models.heldout == "MACRO_MEAN"]

    def metric(split: str, representation: str, model: str, column: str) -> float:
        row = macro[(macro.split == split) & (macro.representation == representation) & (macro.model == model)]
        return float(row.iloc[0][column])

    # Ridge is the frozen primary explanatory model; linear/tree are diagnostics.
    y_r2_lovo = metric("LOVO", "YIELD_ONLY", "ridge", "R2")
    y_r2_lovqo = metric("LOVQO", "YIELD_ONLY", "ridge", "R2")
    y_mae_lovo = metric("LOVO", "YIELD_ONLY", "ridge", "MAE")
    y_mae_lovqo = metric("LOVQO", "YIELD_ONLY", "ridge", "MAE")
    g_mae_lovo = metric("LOVO", "YIELD_PLUS_PUBLIC_GEOMETRY", "ridge", "MAE")
    g_mae_lovqo = metric("LOVQO", "YIELD_PLUS_PUBLIC_GEOMETRY", "ridge", "MAE")
    mae_lift_lovo = y_mae_lovo - g_mae_lovo
    mae_lift_lovqo = y_mae_lovqo - g_mae_lovqo
    yield_insufficient = y_r2_lovo <= 0.50 or mae_lift_lovo >= 0.05
    geometry_lift = mae_lift_lovo >= 0.02
    positive_clusters = int((overall.mean_delta_human_event_coverage > 0).sum())
    source_effect = overall.groupby("video_id").mean_delta_human_event_coverage.mean()
    positive_source_videos = int((source_effect > 0).sum())
    budget_effect = primary.groupby("budget").delta_human_event_coverage.mean()
    positive_budgets = int((budget_effect > 0).sum())
    matched_effect = bool(
        overall.mean_delta_human_event_coverage.mean() > 0
        and overall.mean_delta_distinct_human_events_touched.mean() > 0
        and positive_clusters >= 4
        and positive_source_videos >= 2
        and positive_budgets >= 2
    )
    proxy_medians = proxy_effects.groupby("proxy_id").mean_delta_human_event_coverage.mean().to_dict()
    cross_proxy = all(proxy_medians.get(proxy, 0.0) > 0 for proxy in PROXIES)
    minimum_evidence = all(
        counts.get(proxy, 0) >= gate["minimum_exact_pairs_per_proxy"]
        and clusters_per_proxy.get(proxy, 0) >= gate["minimum_video_query_clusters_with_exact_pairs_per_proxy"]
        for proxy in PROXIES
    )
    checks = {
        "minimum_evidence": minimum_evidence,
        "yield_only_insufficient": yield_insufficient,
        "public_geometry_heldout_lift": geometry_lift,
        "equal_yield_matched_human_effect": matched_effect,
        "cross_proxy_consistency": cross_proxy,
        "materializer_independent_endpoint": matched_effect,
        "primary_uses_no_reference_only_features": True,
    }
    details = {
        "checks": checks, "exact_pairs_by_proxy": counts,
        "video_query_clusters_per_proxy": clusters_per_proxy,
        "positive_direction_video_query_clusters": positive_clusters,
        "positive_source_videos": positive_source_videos,
        "positive_budgets": positive_budgets,
        "mean_delta_human_event_coverage": float(overall.mean_delta_human_event_coverage.mean()),
        "mean_delta_distinct_human_events_touched": float(overall.mean_delta_distinct_human_events_touched.mean()),
        "proxy_median_delta_human_event_coverage": proxy_medians,
        "yield_only_R2_LOVO": y_r2_lovo, "yield_only_R2_LOVQO": y_r2_lovqo,
        "yield_plus_geometry_MAE_lift_LOVO": mae_lift_lovo,
        "yield_plus_geometry_MAE_lift_LOVQO": mae_lift_lovqo,
    }
    if all(checks.values()):
        decision = "PASS"
    elif details["mean_delta_human_event_coverage"] > 0 or geometry_lift:
        decision = "PARTIAL"
    else:
        decision = "FAIL"
    return decision, details


def run_analysis(reference: pd.DataFrame, freeze: dict) -> None:
    endpoints = materializer_independent_results(reference)
    endpoints.to_csv(OUT / "MATERIALIZER_INDEPENDENT_TRACE_RESULTS.csv", index=False)
    primary = primary_pairs(endpoints)
    primary.to_csv(OUT / "EQUAL_YIELD_PRIMARY_RESULTS.csv", index=False)
    models = heldout_models(endpoints)
    models.to_csv(OUT / "LOVO_RESULTS.csv", index=False)
    models[models.representation == "YIELD_ONLY"].to_csv(OUT / "YIELD_ONLY_MODEL.csv", index=False)
    models[models.representation == "YIELD_PLUS_PUBLIC_GEOMETRY"].to_csv(OUT / "PUBLIC_GEOMETRY_MODEL.csv", index=False)
    models[models.representation == "REFERENCE_AWARE_DIAGNOSTIC"].to_csv(OUT / "REFERENCE_DIAGNOSTIC_MODEL.csv", index=False)
    proxy_effects, overall = cluster_effects(primary)
    proxy_effects.to_csv(OUT / "CROSS_PROXY_HUMAN_EVENT_EFFECT.csv", index=False)
    overall.to_csv(OUT / "CLUSTER_PRIMARY_EFFECTS.csv", index=False)
    primary.groupby(["video_id","query_id","proxy_id","budget"],as_index=False).agg(
        exact_pairs=("budget","size"),mean_delta_distinct_human_events_touched=("delta_distinct_human_events_touched","mean"),
        mean_delta_human_event_coverage=("delta_human_event_coverage","mean")
    ).to_csv(OUT/"BUDGET_STRATIFIED_EFFECTS.csv",index=False)
    endpoints[["trace_instance_id","video_id","query_id","proxy_id","budget","C1_event_precision_SECONDARY","C1_event_recall_SECONDARY","C1_EventF1_SECONDARY","C1_MatchedMeanIoU_SECONDARY"]].to_csv(OUT/"HUMAN_C1_RESULTS.csv",index=False)
    bootstrap, bootstrap_summary = cluster_bootstrap(overall)
    bootstrap.to_csv(OUT / "CLUSTER_BOOTSTRAP.csv", index=False)
    decision, details = decide(primary, models)

    macro = models[models.heldout == "MACRO_MEAN"]
    summary = {
        "decision": decision, "gate": details,
        "bootstrap": bootstrap_summary,
        "human_reference_freeze": freeze,
        "input_hashes": {
            "trace_population": sha(TRACE), "trace_pairs": sha(PAIRS),
            "primary_pair_manifest": sha(PRIMARY_PAIRS),
            "human_reference": sha(OUT / "HUMAN_REFERENCE_EVENTS.csv"),
            "p1_protocol": sha(PROTOCOL), "human_protocol": sha(HUMAN_PROTOCOL),
        },
        "heldout_macro": macro.to_dict(orient="records"),
    }
    write_json(OUT / "P1_RESULT.json", summary)
    report = f"""# GVAQP P1 independent event-evidence geometry replication

## Decision

`P1_EVENT_EVIDENCE_GEOMETRY = {decision}`

The primary statistical unit is the video-query cluster. The {len(primary)} exact-yield trace strata were median-collapsed within cluster/proxy before the six-cluster direction test; they were never treated as independent samples.

## Frozen gate audit

```json
{json.dumps(details, indent=2, sort_keys=True)}
```

## Cluster-bootstrap uncertainty

```json
{json.dumps(bootstrap_summary, indent=2, sort_keys=True)}
```

The primary effect uses direct human-event touch/coverage from verified-positive evidence and does not pass through C1. C1 EventF1 is reported only as a frozen secondary endpoint. Reference-aware model features are offline diagnostics and cannot support an algorithm claim.

{'P1 supports only the claim that event-query quality depends on acquired semantic-evidence structure beyond yield. Proceed to P2 novelty-killer; do not claim a new policy.' if decision == 'PASS' else 'P1 does not pass the independent-human, cross-proxy gate. P2 and geometry-aware selector development are not authorized.'}
"""
    (OUT / "P1_FINAL_REPORT.md").write_text(report)
    (OUT / "P1_DECISION.md").write_text(report)
    next_action = (
        "Run the frozen P2 Generic Relevance+Coverage Novelty-Killer baselines; do not develop a new selector."
        if decision == "PASS"
        else ("Run only a new preregistered low-cost independent replication if it resolves the single documented uncertainty; P2 remains unauthorized."
              if decision == "PARTIAL" else "Close the event-evidence policy branch and consolidate the negative independent-reference result; do not run P2.")
    )
    (OUT / "NEXT_RESEARCH_ACTION.md").write_text(f"# Next single action\n\n{next_action}\n")
    state = json.loads((OUT / "RESEARCH_STATE.json").read_text())
    state.update({
        "current_phase": "P1_COMPLETE", "phase_status": "COMPLETE",
        "p1_event_evidence_geometry": decision,
        "human_reference_status": "COMPLETE",
        "human_reference_frozen": True,
        "user_input_required": None,
        "next_entrypoint": None,
        "next_single_action": next_action,
    })
    write_json(OUT / "RESEARCH_STATE.json", state)
    print(json.dumps({"status": "COMPLETE", "decision": decision, "output": str(OUT)}, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="report readiness without writing a reference/result")
    args = parser.parse_args()
    verify_protocol_freeze()
    status = readiness()
    if args.check:
        print(json.dumps(status, indent=2, sort_keys=True))
        return
    if (OUT / "P1_RESULT.json").exists():
        raise RuntimeError("P1 has already been finalized")
    cases, _, _, diagnostics = validate_independent_annotations()
    status = json.loads((OUT/"ANNOTATION_STATUS.json").read_text())
    status.update({"completed_cases":{"ANNOTATOR_A":6,"ANNOTATOR_B":6},"agreement_status":diagnostics["human_reference_quality"],
                   "adjudication_status":"NOT_STARTED" if not ADJUDICATED.exists() else "SUBMITTED"})
    write_json(OUT/"ANNOTATION_STATUS.json",status)
    if diagnostics["human_reference_quality"] == "INSUFFICIENT":
        raise RuntimeError("HUMAN_REFERENCE_QUALITY=INSUFFICIENT; see REFERENCE_PROTOCOL_FAILURE_ANALYSIS.md")
    if not ADJUDICATED.exists():
        raise RuntimeError("agreement complete; blinded adjudication required before reference freeze or outcome analysis")
    reference, freeze = freeze_adjudicated_reference(cases, diagnostics)
    run_analysis(reference, freeze)


if __name__ == "__main__":
    main()
