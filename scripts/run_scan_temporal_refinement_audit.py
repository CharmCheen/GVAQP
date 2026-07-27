#!/usr/bin/env python3
"""Temporal correlation and visible-trigger neighbor-gain audit."""
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
DER = BENCH / "derived"
OUT = ROOT / "outputs/scan_optimization_headroom_audit_v1/temporal_correlation_audit"
FEATURES = (
    "detection_count", "track_count", "mean_center_occupancy",
    "mean_bbox_area", "trigger_count", "bbox_growth_signal",
    "lateral_motion_signal", "center_entry_signal", "late_track_entry_signal",
)


def unit_event_map() -> dict[str, set[str]]:
    mapping = pd.read_parquet(DER / "candidate_event_map.parquet")
    mapping = mapping[mapping.partition_offset_sec.eq(0)]
    result: dict[str, set[str]] = {}
    for row in mapping.itertuples(index=False):
        for unit_id in json.loads(row.source_unit_ids):
            result.setdefault(str(unit_id), set()).add(str(row.reference_event_id))
    return result


def unit_features(timeline: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for unit in timeline.itertuples(index=False):
        directory = IMM / "scan_outputs" / unit.video_id / unit.unit_id
        detections = pd.read_parquet(directory / "detections.parquet")
        tracks = pd.read_parquet(directory / "tracks.parquet")
        triggers = json.loads((directory / "triggers.json").read_text())
        raw = json.loads((directory / "raw_candidates.json").read_text())
        if len(detections):
            width = 1280.0
            height = 720.0
            center_x = ((detections.x1 + detections.x2) / 2.0) / width
            area = ((detections.x2 - detections.x1) / width) * (
                (detections.y2 - detections.y1) / height
            )
            occupancy = float(((center_x >= 0.3) & (center_x <= 0.7)).mean())
            mean_area = float(area.mean())
        else:
            occupancy = 0.0
            mean_area = 0.0

        center_entry = False
        late_entry = False
        if len(tracks):
            first_frame = int(tracks.frame_index.min())
            for _, group in tracks.groupby("track_id"):
                group = group.sort_values("frame_index")
                centers = ((group.x1 + group.x2) / 2.0) / 1280.0
                inside = (centers >= 0.3) & (centers <= 0.7)
                center_entry |= bool((inside & ~inside.shift(fill_value=inside.iloc[0])).any())
                late_entry |= int(group.frame_index.min()) > first_frame
        bbox_growth = any(float(row.get("box_growth", 0.0)) > 0 for row in raw)
        lateral = any(
            float(row.get("path_directed_lateral_motion", 0.0)) > 0
            for row in raw
        )
        rows.append(
            {
                "video_id": unit.video_id, "unit_id": unit.unit_id,
                "unit_index": int(unit.unit_index),
                "detection_count": len(detections),
                "track_count": int(tracks.track_id.nunique()) if len(tracks) else 0,
                "mean_center_occupancy": occupancy,
                "mean_bbox_area": mean_area,
                "trigger_count": len(triggers),
                "candidate_trigger": bool(raw),
                "bbox_growth_signal": float(bbox_growth),
                "lateral_motion_signal": float(lateral),
                "center_entry_signal": float(center_entry),
                "late_track_entry_signal": float(late_entry),
                "composite_visible_trigger": bool(
                    raw or bbox_growth or lateral or center_entry or late_entry
                ),
            }
        )
    return pd.DataFrame(rows)


def lagged_observation_curve(features: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for video_id, group in features.groupby("video_id"):
        group = group.sort_values("unit_index").reset_index(drop=True)
        standardized = group[list(FEATURES)].astype(float)
        standardized = (standardized - standardized.mean()) / standardized.std(ddof=0).replace(0, 1)
        for distance in range(1, min(25, len(group))):
            left = standardized.iloc[:-distance].to_numpy()
            right = standardized.iloc[distance:].to_numpy()
            feature_products = left * right
            correlations = feature_products.mean(axis=0)
            payload = {
                "video_id": video_id, "distance_units": distance,
                "distance_sec": distance * 10.0,
                "pair_count": len(left),
                "K_obs_mean_feature_autocorrelation": float(np.mean(correlations)),
            }
            payload.update(
                {f"autocorr_{name}": float(value) for name, value in zip(FEATURES, correlations)}
            )
            rows.append(payload)
    return pd.DataFrame(rows)


def event_and_neighbor_curves(features: pd.DataFrame, events: dict[str, set[str]]) -> tuple[pd.DataFrame, pd.DataFrame]:
    continuation_rows = []
    neighbor_rows = []
    trigger_names = (
        "candidate_trigger", "bbox_growth_signal", "lateral_motion_signal",
        "center_entry_signal", "late_track_entry_signal", "composite_visible_trigger",
    )
    for video_id, group in features.groupby("video_id"):
        group = group.sort_values("unit_index").reset_index(drop=True)
        for distance in range(1, min(13, len(group))):
            for index in range(len(group) - distance):
                current = group.iloc[index]
                neighbor = group.iloc[index + distance]
                current_events = events.get(str(current.unit_id), set())
                neighbor_events = events.get(str(neighbor.unit_id), set())
                continuation_rows.append(
                    {
                        "video_id": video_id, "distance_units": distance,
                        "distance_sec": distance * 10.0,
                        "current_has_event": bool(current_events),
                        "same_event_continues": bool(current_events & neighbor_events),
                        "neighbor_event_count": len(neighbor_events),
                        "duplicate_event_fraction": len(current_events & neighbor_events) / max(1, len(neighbor_events)),
                    }
                )
                for trigger_name in trigger_names:
                    neighbor_rows.append(
                        {
                            "video_id": video_id, "distance_units": distance,
                            "trigger_name": trigger_name,
                            "trigger_present": bool(current[trigger_name]),
                            "neighbor_has_any_event": bool(neighbor_events),
                            "neighbor_has_first_new_event_vs_current": bool(neighbor_events - current_events),
                            "new_neighbor_event_count": len(neighbor_events - current_events),
                        }
                    )
    continuation = pd.DataFrame(continuation_rows)
    neighbor = pd.DataFrame(neighbor_rows)
    return continuation, neighbor


def summarize_continuation(frame: pd.DataFrame) -> pd.DataFrame:
    positive = frame[frame.current_has_event].copy()
    return positive.groupby(["video_id", "distance_units", "distance_sec"], as_index=False).agg(
        event_pair_count=("same_event_continues", "size"),
        same_event_continuation_probability=("same_event_continues", "mean"),
        candidate_duplicate_fraction=("duplicate_event_fraction", "mean"),
    )


def summarize_neighbor(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    keys = ["video_id", "distance_units", "trigger_name"]
    for key, group in frame.groupby(keys):
        present = group[group.trigger_present]
        absent = group[~group.trigger_present]
        p1 = float(present.neighbor_has_first_new_event_vs_current.mean()) if len(present) else np.nan
        p0 = float(absent.neighbor_has_first_new_event_vs_current.mean()) if len(absent) else np.nan
        rows.append(
            {
                "video_id": key[0], "distance_units": key[1],
                "distance_sec": key[1] * 10.0, "trigger_name": key[2],
                "trigger_pair_count": len(present), "no_trigger_pair_count": len(absent),
                "p_new_neighbor_event_given_trigger": p1,
                "p_new_neighbor_event_given_no_trigger": p0,
                "absolute_neighbor_gain": p1 - p0,
                "neighbor_gain_risk_ratio": p1 / p0 if p0 > 0 else np.inf if p1 > 0 else np.nan,
                "mean_new_neighbor_events_given_trigger": float(present.new_neighbor_event_count.mean()) if len(present) else np.nan,
                "mean_new_neighbor_events_given_no_trigger": float(absent.new_neighbor_event_count.mean()) if len(absent) else np.nan,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    timeline = pd.read_csv(IMM / "timeline_units.csv")
    events = unit_event_map()
    features = unit_features(timeline)
    observation = lagged_observation_curve(features)
    continuation_raw, neighbor_raw = event_and_neighbor_curves(features, events)
    continuation = summarize_continuation(continuation_raw)
    neighbor = summarize_neighbor(neighbor_raw)
    transition = pd.read_csv(DER / "cost_calibration/transition_cost_samples.csv")
    transition_summary = transition.groupby("transition_class", as_index=False).actual_action_cost_sec.agg(
        ["count", "mean", "median", lambda values: values.quantile(.9)]
    ).reset_index().rename(columns={"<lambda_0>": "q90_action_cost_sec"})

    OUT.mkdir(parents=True, exist_ok=True)
    atomic_csv(OUT / "unit_visible_features.csv", features)
    atomic_csv(OUT / "K_obs_curve.csv", observation)
    atomic_csv(OUT / "same_event_and_duplicate_decay.csv", continuation)
    atomic_csv(OUT / "trigger_neighbor_gain.csv", neighbor)
    atomic_csv(OUT / "transition_cost_by_path.csv", transition_summary)

    primary = neighbor[neighbor.distance_units.eq(1)].copy()
    trigger_gates = []
    for trigger_name, group in primary.groupby("trigger_name"):
        trigger_success = float(
            (group.p_new_neighbor_event_given_trigger * group.trigger_pair_count).sum()
        )
        no_trigger_success = float(
            (group.p_new_neighbor_event_given_no_trigger * group.no_trigger_pair_count).sum()
        )
        pooled_p1 = trigger_success / max(1, int(group.trigger_pair_count.sum()))
        pooled_p0 = no_trigger_success / max(1, int(group.no_trigger_pair_count.sum()))
        pooled_ratio = pooled_p1 / pooled_p0 if pooled_p0 > 0 else None
        per_video_positive = bool((group.absolute_neighbor_gain > 0).all())
        passed = bool(
            per_video_positive
            and (pooled_ratio is None or pooled_ratio >= 1.25)
        )
        trigger_gates.append(
            {
                "trigger_name": trigger_name,
                "per_video_positive_neighbor_gain": per_video_positive,
                "pooled_p_new_neighbor_event_given_trigger": pooled_p1,
                "pooled_p_new_neighbor_event_given_no_trigger": pooled_p0,
                "pooled_neighbor_gain_risk_ratio": pooled_ratio,
                "gate": "PASS" if passed else "STOP",
            }
        )
    passing_triggers = [
        row["trigger_name"] for row in trigger_gates if row["gate"] == "PASS"
    ]
    gate = bool(passing_triggers)

    observation_mean = observation.groupby("distance_units").K_obs_mean_feature_autocorrelation.mean()
    below = observation_mean[observation_mean <= 0.10]
    redundancy_horizon = int(below.index.min()) if len(below) else int(observation_mean.index.max())
    continuation_mean = continuation.groupby("distance_units").same_event_continuation_probability.mean()
    supported = continuation_mean[continuation_mean >= 0.10]
    refinement_radius = int(supported.index.max()) if len(supported) else 0
    decision = {
        "status": "PASS",
        "reference_semantics": "FROZEN_FULL_CONTEXT_ORACLE_PSEUDO_REFERENCE",
        "effective_observation_redundancy_horizon_units": redundancy_horizon,
        "effective_observation_redundancy_horizon_sec": redundancy_horizon * 10,
        "maximum_empirical_refinement_radius_units": refinement_radius,
        "maximum_empirical_refinement_radius_sec": refinement_radius * 10,
        "distance_1_trigger_neighbor_results": json.loads(
            primary.replace([np.inf, -np.inf], np.nan).to_json(orient="records")
        ),
        "trigger_gates": trigger_gates,
        "passing_predeclared_triggers": passing_triggers,
        "FIXED_REFINEMENT_GATE": "PASS" if gate else "STOP",
    }
    atomic_json(OUT / "temporal_refinement_decision.json", decision)
    composite = primary[primary.trigger_name.eq("composite_visible_trigger")]
    details = "\n".join(
        f"- `{row.video_id}` composite: P(new neighbor event | trigger)={row.p_new_neighbor_event_given_trigger:.4f}, "
        f"without trigger={row.p_new_neighbor_event_given_no_trigger:.4f}, "
        f"absolute gain={row.absolute_neighbor_gain:.4f}."
        for row in composite.itertuples(index=False)
    )
    gate_details = "\n".join(
        f"- `{row['trigger_name']}`: {row['gate']}, pooled RR={row['pooled_neighbor_gain_risk_ratio']}."
        for row in trigger_gates
    )
    report = f"""# Temporal Correlation and Refinement Audit

All event quantities are empirical structure relative to the frozen full-context Oracle pseudo-reference, not ground-truth event prevalence.

## Composite visible-trigger neighbor result

{details}

Component-wise preregistered trigger gates:

{gate_details}

```text
EFFECTIVE_OBSERVATION_REDUNDANCY_HORIZON = {redundancy_horizon} units ({redundancy_horizon * 10} s)
MAXIMUM_EMPIRICAL_REFINEMENT_RADIUS = {refinement_radius} units ({refinement_radius * 10} s)
FIXED_REFINEMENT_GATE = {'PASS' if gate else 'STOP'}
PASSING_TRIGGER_SET = {', '.join(passing_triggers) if passing_triggers else 'NONE'}
```

Each component gate requires positive gain on both videos and pooled RR >= 1.25 (or an undefined ratio caused by a zero no-trigger base rate). Passing the association gate permits only fixed-baseline testing; it does not establish scheduling value.
"""
    atomic_text(OUT / "TEMPORAL_REFINEMENT_REPORT.md", report)
    print(json.dumps(decision, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
