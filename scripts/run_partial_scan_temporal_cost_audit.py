#!/usr/bin/env python3
"""Development-only temporal, event, and controlled-warm cost audit.

This consumes only frozen V1 derived inputs and emits no method ranking.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from partial_scan_pilot_common import atomic_csv, atomic_json, atomic_text  # noqa: E402

BENCH = ROOT / "benchmarks/partial_scan_pilot_v1"
IMM = BENCH / "immutable"
DERIVED = BENCH / "derived"
OUT = ROOT / "outputs/partial_scan_method_development_v1/temporal_cost_audit"


def unit_features(timeline: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for unit in timeline.itertuples(index=False):
        directory = IMM / "scan_outputs" / unit.video_id / unit.unit_id
        detections = pd.read_parquet(directory / "detections.parquet")
        tracks = pd.read_parquet(directory / "tracks.parquet")
        triggers = json.loads((directory / "triggers.json").read_text())
        # Histograms are compact observable summaries for distance similarity.
        classes = detections.class_id.value_counts(normalize=True).to_dict()
        areas = ((detections.x2 - detections.x1) * (detections.y2 - detections.y1))
        rows.append({
            "video_id": unit.video_id, "unit_id": unit.unit_id,
            "unit_index": unit.unit_index, "detection_count": len(detections),
            "track_count": int(tracks.track_id.nunique()), "trigger_count": len(triggers),
            "mean_bbox_area": float(areas.mean()) if len(areas) else 0.0,
            "class_histogram": json.dumps(classes, sort_keys=True),
            "trigger_types": json.dumps(sorted({x["trigger"] for x in triggers})),
        })
    return pd.DataFrame(rows)


def jaccard(left: set[str], right: set[str]) -> float:
    return len(left & right) / len(left | right) if left or right else 1.0


def redundancy_curve(features: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    by_unit = candidates.groupby("unit_id").candidate_id.apply(lambda x: set(x.astype(str))).to_dict()
    rows = []
    for video_id, group in features.groupby("video_id"):
        group = group.sort_values("unit_index").reset_index(drop=True)
        for distance in range(1, min(25, len(group))):
            pairs = []
            for i in range(len(group) - distance):
                a, b = group.iloc[i], group.iloc[i + distance]
                pairs.append({
                    "candidate_jaccard": jaccard(by_unit.get(a.unit_id, set()), by_unit.get(b.unit_id, set())),
                    "detection_count_ratio": min(a.detection_count, b.detection_count) / max(1, max(a.detection_count, b.detection_count)),
                    "track_count_ratio": min(a.track_count, b.track_count) / max(1, max(a.track_count, b.track_count)),
                    "trigger_count_ratio": min(a.trigger_count, b.trigger_count) / max(1, max(a.trigger_count, b.trigger_count)),
                })
            rows.append({"video_id": video_id, "distance_units": distance, "distance_sec": distance * 10.0,
                         "pair_count": len(pairs), **pd.DataFrame(pairs).mean().to_dict()})
    return pd.DataFrame(rows)


def event_curves(timeline: pd.DataFrame, references: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    source = timeline.merge(
        references[["video_id", "reference_event_id", "event_start_sec", "event_end_sec"]],
        on="video_id",
    )
    source = source[(source.start_sec < source.event_end_sec) & (source.end_sec > source.event_start_sec)]
    memberships = source.groupby(["video_id", "reference_event_id"]).unit_index.apply(set)
    duration = memberships.apply(lambda x: len(x)).rename("unit_count").reset_index()
    rows = []
    for (video, event), indices in memberships.items():
        for d in range(1, 13):
            rows.append({"video_id": video, "reference_event_id": event, "distance_units": d,
                         "same_event_continues": any((i + d) in indices or (i - d) in indices for i in indices)})
    curve = pd.DataFrame(rows).groupby("distance_units").same_event_continues.agg(["mean", "count"]).reset_index()
    curve = curve.rename(columns={"mean": "continuation_probability", "count": "event_count"})
    return duration, curve


def costs() -> pd.DataFrame:
    frame = pd.read_csv(DERIVED / "cost_calibration/transition_cost_samples.csv")
    return frame.groupby("transition_class").actual_action_cost_sec.agg(["count", "mean", "median", lambda x: x.quantile(.9)]).reset_index().rename(columns={"<lambda_0>": "q90_action_cost_sec"})


def main() -> None:
    timeline = pd.read_csv(IMM / "timeline_units.csv")
    candidates = pd.concat([pd.read_parquet(p) for p in sorted((DERIVED / "visible_subset_candidates").glob("*_offset0_full.parquet"))])
    references = pd.read_csv(IMM / "reference_events.csv")
    features = unit_features(timeline)
    redundancy = redundancy_curve(features, candidates)
    duration, continuation = event_curves(timeline, references)
    cost = costs()
    OUT.mkdir(parents=True, exist_ok=True)
    for name, frame in [("unit_observation_features.csv", features), ("observation_redundancy_curve.csv", redundancy), ("event_duration_distribution.csv", duration), ("same_event_continuation_curve.csv", continuation), ("transition_cost_summary.csv", cost)]:
        atomic_csv(OUT / name, frame)
    horizon = int(redundancy.groupby("distance_units").candidate_jaccard.mean().pipe(lambda x: x[x <= .05].index.min() or 24))
    qualifying_radius = continuation.loc[
        continuation.continuation_probability >= .10, "distance_units"
    ]
    radius = int(qualifying_radius.max()) if not qualifying_radius.empty else 0
    atomic_json(OUT / "frozen_development_structure.json", {
        "scope": "DEVELOPMENT_ONLY_RELATIVE_TO_FROZEN_FULL_CONTEXT_ORACLE_PSEUDO_REFERENCE",
        "OBSERVATION_REDUNDANCY_CURVE": "observation_redundancy_curve.csv",
        "EFFECTIVE_REDUNDANCY_HORIZON": {"units": horizon, "seconds": horizon * 10},
        "COVERAGE_PROBE_SPACING": {"units": max(1, horizon), "seconds": max(10, horizon * 10)},
        "EVENT_DURATION_DISTRIBUTION": "event_duration_distribution.csv",
        "SAME_EVENT_CONTINUATION_CURVE": "same_event_continuation_curve.csv",
        "MAX_REFINEMENT_RADIUS": {"units": radius, "seconds": radius * 10},
        "PATH_COST_STRATA": "transition_cost_summary.csv",
        "FORMAL_METHOD_RANKING": "BLOCKED_PENDING_EXTERNAL_RUNTIME_ATTESTATION",
    })
    atomic_text(OUT / "TEMPORAL_COST_AUDIT.md", "# Development temporal and cost audit\n\nAll event findings are relative to the frozen full-context Oracle pseudo-reference. This is development analysis only; no formal ranking is asserted.\n")


if __name__ == "__main__":
    main()
