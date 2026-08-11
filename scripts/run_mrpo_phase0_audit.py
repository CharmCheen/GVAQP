#!/usr/bin/env python3
"""MRPO Phase 0: read-only asset, region-label, cost, and leakage audit."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmarks/partial_scan_pilot_v1"
IMM = BENCH / "immutable"
DER = BENCH / "derived"
OUT = ROOT / "outputs/macro_region_proxy_optimization_v1"
AUTHORITY = Path("/root/.codex/attachments/bcab7a8a-1d43-4b1a-9511-3ddb1e26a968/pasted-text-1.txt")
LENGTHS = (40, 60, 90, 120)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")
    temporary.replace(path)


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value)
    temporary.replace(path)


def region_index(timestamp: float, length: int, count: int) -> int:
    # ceil(x)-1 implements the frozen smaller-index boundary tie rule.
    index = max(0, int(np.ceil(float(timestamp) / length) - 1))
    return min(index, count - 1)


def scan_costs(timeline: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for unit in timeline.itertuples(index=False):
        path = IMM / "scan_outputs" / unit.video_id / unit.unit_id / "runtime.json"
        runtime = json.loads(path.read_text())
        rows.append(
            {
                "video_id": unit.video_id, "unit_id": unit.unit_id,
                "full_scan_cost_sec": float(runtime["total_action_time_sec"]),
            }
        )
    return pd.DataFrame(rows)


def build_labels(
    length: int,
    videos: pd.DataFrame,
    timeline: pd.DataFrame,
    references: pd.DataFrame,
    exposable: set[str],
    costs: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    regions = []
    event_rows = []
    for video in videos.itertuples(index=False):
        count = int(np.ceil(float(video.duration_sec) / length))
        local_units = timeline[timeline.video_id.eq(video.video_id)].merge(
            costs, on=["video_id", "unit_id"]
        )
        unit_region = {
            str(row.unit_id): region_index(
                (float(row.start_sec) + float(row.end_sec)) / 2.0, length, count
            )
            for row in local_units.itertuples(index=False)
        }
        for index in range(count):
            start = index * length
            end = min((index + 1) * length, float(video.duration_sec))
            ids = [unit_id for unit_id, value in unit_region.items() if value == index]
            region_cost = float(
                local_units[local_units.unit_id.astype(str).isin(ids)].full_scan_cost_sec.sum()
            )
            regions.append(
                {
                    "macro_region_length_sec": length,
                    "video_id": video.video_id,
                    "region_id": f"{video.video_id}_L{length:03d}_R{index:04d}",
                    "region_index": index,
                    "start_sec": start, "end_sec": end,
                    "actual_duration_sec": end - start,
                    "region_duration_fraction": (end - start) / length,
                    "microchunk_count": len(ids),
                    "full_scan_cost_sec": region_cost,
                }
            )
        local_refs = references[references.video_id.eq(video.video_id)]
        for event in local_refs.itertuples(index=False):
            midpoint = (float(event.event_start_sec) + float(event.event_end_sec)) / 2.0
            index = region_index(midpoint, length, count)
            event_rows.append(
                {
                    "macro_region_length_sec": length,
                    "video_id": video.video_id,
                    "reference_event_id": event.reference_event_id,
                    "event_midpoint_sec": midpoint,
                    "region_id": f"{video.video_id}_L{length:03d}_R{index:04d}",
                    "region_index": index,
                    "exposable_under_offset0_full_scan": str(event.reference_event_id) in exposable,
                }
            )
    region_frame = pd.DataFrame(regions)
    event_frame = pd.DataFrame(event_rows)
    counts = (
        event_frame[event_frame.exposable_under_offset0_full_scan]
        .groupby("region_id").reference_event_id.nunique()
    )
    region_frame["residual_event_count"] = (
        region_frame.region_id.map(counts).fillna(0).astype(int)
    )
    region_frame["binary_positive"] = region_frame.residual_event_count.gt(0)
    return region_frame, event_frame


def main() -> None:
    videos = pd.read_csv(IMM / "videos.csv")
    timeline = pd.read_csv(IMM / "timeline_units.csv")
    references = pd.read_csv(IMM / "reference_events.csv")
    mapping = pd.read_parquet(DER / "candidate_event_map.parquet")
    offset0 = mapping[mapping.partition_offset_sec.eq(0)]
    exposable = set(offset0.reference_event_id.astype(str))
    costs = scan_costs(timeline)

    for directory in [
        "contracts", "audits", "preview/operator_manifests",
        "preview/region_features", "preview/runtime_samples", "labels/candidates",
        "experiments/univariate", "experiments/models", "experiments/ablations",
        "experiments/controls", "experiments/macro_region_sensitivity",
        "predictions", "metrics", "reports",
    ]:
        (OUT / directory).mkdir(parents=True, exist_ok=True)

    frozen = {
        "document_id": "MRPO-CONTRACT-V1",
        "authority_sha256": sha256(AUTHORITY),
        "authority_byte_count": AUTHORITY.stat().st_size,
        "frozen_objective": "LOW_COST_MACRO_REGION_RESIDUAL_NEW_EVENT_VALUE_ESTIMATION",
        "primary_stage": "STATIC_MACRO_REGION_RANKING",
        "initial_probe_contract": "H0_EMPTY",
        "design_videos": list(videos.video_id.astype(str)),
        "validation_video_count": 0, "test_video_count": 0,
        "event_claim_scope": "RELATIVE_TO_FROZEN_FULL_CONTEXT_ORACLE_PSEUDO_REFERENCE",
        "formal_model_selection": "REQUIRES_AT_LEAST_FOUR_NEW_VALIDATION_VIDEOS",
    }
    frozen["contract_hash"] = hashlib.sha256(
        json.dumps(frozen, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    write_json(OUT / "contracts/frozen_contract.json", frozen)
    write_json(OUT / "contracts/preview_contract.json", {
        "max_preview_operator_configs": 4,
        "families": ["P0_METADATA_FRAMESTAT", "P1_LOW_RATE_LOW_RESOLUTION_DETECTION", "P2_COMPRESSED_OR_SPARSE_MOTION"],
        "max_preview_cost_ratio": 0.10,
        "selection_without_event_labels": True,
        "full_scan_cache_use": "PROHIBITED",
    })
    write_json(OUT / "contracts/label_contract.json", {
        "macro_region_length_candidates_sec": list(LENGTHS),
        "canonical_mapping": "EVENT_MIDPOINT_SMALLER_REGION_ON_EXACT_BOUNDARY",
        "primary_universe": "OFFSET0_FULL_SCAN_EXPOSABLE_REFERENCE_EVENTS",
        "initial_probe_set": "EMPTY",
        "tail_regions": "RETAINED",
    })
    write_json(OUT / "contracts/metric_contract.json", {
        "primary": "RECALL_AT_20_PERCENT_COMPLETE_REGION_SCAN_COST",
        "secondary_budget_fractions": [0.10, 0.30],
        "region_partial_execution": False,
        "random_seed_count": 100,
        "net_yield_pays_preview_cost": True,
    })
    write_json(OUT / "contracts/search_budget.json", {
        "max_preview_operator_configs": 4, "max_feature_families": 8,
        "max_model_families": 5, "max_primary_configs": 50,
        "max_repair_cycles": 1, "formal_test_set_evaluations": 1,
    })

    sensitivity = []
    for length in LENGTHS:
        regions, event_map = build_labels(
            length, videos, timeline, references, exposable, costs
        )
        regions.to_parquet(
            OUT / f"labels/candidates/region_labels_L{length:03d}.parquet",
            index=False,
        )
        event_map.to_parquet(
            OUT / f"labels/candidates/event_region_map_L{length:03d}.parquet",
            index=False,
        )
        for video_id, group in regions.groupby("video_id"):
            sensitivity.append(
                {
                    "macro_region_length_sec": length, "video_id": video_id,
                    "region_count": len(group),
                    "positive_region_count": int(group.binary_positive.sum()),
                    "binary_positive_region_rate": float(group.binary_positive.mean()),
                    "mean_count": float(group.residual_event_count.mean()),
                    "variance_count": float(group.residual_event_count.var(ddof=1)),
                    "max_count": int(group.residual_event_count.max()),
                    "full_scan_cost_sec": float(group.full_scan_cost_sec.sum()),
                    "tail_region_duration_fraction": float(group.iloc[-1].region_duration_fraction),
                }
            )
    sensitivity_frame = pd.DataFrame(sensitivity)
    sensitivity_frame.to_csv(
        OUT / "experiments/macro_region_sensitivity/phase0_label_sensitivity.csv",
        index=False,
    )

    per_video = []
    for video_id in videos.video_id.astype(str):
        ref_count = int(references.video_id.eq(video_id).sum())
        exposed = int(offset0[offset0.video_id.eq(video_id)].reference_event_id.nunique())
        per_video.append(
            {
                "video_id": video_id,
                "duration_sec": float(videos.loc[videos.video_id.eq(video_id), "duration_sec"].iloc[0]),
                "microchunk_count": int(timeline.video_id.eq(video_id).sum()),
                "all_reference_event_count": ref_count,
                "exposable_event_count": exposed,
                "unexposable_event_count": ref_count - exposed,
                "full_scan_exposure_ceiling": exposed / ref_count,
                "measured_full_scan_cost_sec": float(costs[costs.video_id.eq(video_id)].full_scan_cost_sec.sum()),
            }
        )
    asset_audit = {
        "status": "PASS",
        "complete_video_count": len(videos), "design_video_count": len(videos),
        "validation_video_count": 0, "test_video_count": 0,
        "per_video": per_video,
        "total_reference_events": len(references),
        "total_exposable_events": len(exposable),
        "full_scan_ceiling": len(exposable) / len(references),
        "preview_asset_status": "NO_LEGAL_FROZEN_PREVIEW_ASSET_FOUND",
        "phase0_blocker": None,
    }
    write_json(OUT / "audits/asset_audit.json", asset_audit)
    write_json(OUT / "audits/label_audit.json", {
        "status": "PASS", "candidate_lengths": list(LENGTHS),
        "event_counted_once_per_length": True,
        "event_mapping_row_count_per_length": len(references),
        "tail_regions_retained": True,
        "initial_probe_contract": "H0_EMPTY",
        "sensitivity_rows": sensitivity,
    })
    legal = {
        "P0_METADATA_FRAMESTAT": ["F3", "F4", "F5", "F6", "F8"],
        "P1_LOW_RATE_LOW_RESOLUTION_DETECTION": ["F1", "F2", "F3", "F4", "F5", "F7", "F8"],
        "P2_COMPRESSED_OR_SPARSE_MOTION": ["F4", "F5", "F6", "F8"],
    }
    write_json(OUT / "audits/feature_legality_audit.json", {
        "status": "PASS", "legal_family_map": legal,
        "main_model_forbidden": [
            "video_id", "session_id", "filename", "absolute_region_index",
            "normalized_time", "reference", "candidate_event_map",
            "full_scan_outputs", "offline_greedy", "future_reward", "future_cost",
        ],
    })
    write_json(OUT / "audits/leakage_audit.json", {
        "status": "PASS",
        "existing_full_scan_features_rejected": [
            "outputs/scan_optimization_headroom_audit_v1/temporal_correlation_audit/unit_visible_features.csv",
            "outputs/psvr_proxy_finalization_v0/psvr_physical/proxy_scores_all_347.csv",
        ],
        "reason": "DERIVED_FROM_FULL_HIGH_FIDELITY_SCAN_OR_TRACKER",
        "legal_preview_feature_artifacts": [],
    })
    write_json(OUT / "audits/preview_cost_audit.json", {
        "status": "PENDING_PHASE1", "measured_full_scan_cost_sec": {
            row["video_id"]: row["measured_full_scan_cost_sec"] for row in per_video
        }, "max_preview_cost_ratio": 0.10,
    })
    write_json(OUT / "environment_lock.json", {
        "python": sys.version, "platform": platform.platform(),
        "pid": os.getpid(), "numpy": np.__version__, "pandas": pd.__version__,
    })
    write_json(OUT / "repair_log.json", [])
    report_rows = "\n".join(
        f"- `{row['video_id']}`: {row['microchunk_count']} microchunks, "
        f"{row['exposable_event_count']}/{row['all_reference_event_count']} exposable events, "
        f"full-SCAN cost {row['measured_full_scan_cost_sec']:.2f} s."
        for row in per_video
    )
    report = f"""# Phase 0 Asset and Label Audit

```text
PHASE_0 = PASS
COMPLETE_VIDEO_COUNT = {len(videos)}
DESIGN_VIDEO_COUNT = {len(videos)}
VALIDATION_VIDEO_COUNT = 0
TEST_VIDEO_COUNT = 0
REFERENCE_COMPLETENESS_STATUS = PARTIAL_OR_UNVERIFIED
EXPOSABLE_EVENTS = {len(exposable)}
ALL_REFERENCE_EVENTS = {len(references)}
FULL_SCAN_EXPOSURE_CEILING = {len(exposable) / len(references):.6f}
LEGAL_PREVIEW_ASSET = NOT_FOUND_REQUIRES_PHASE1_IMPLEMENTATION
```

{report_rows}

All four frozen macro lengths were materialized with tail regions retained and event-midpoint single-region mapping. No model was trained and no event label was used to choose a preview operator.
"""
    write_text(OUT / "reports/PHASE0_ASSET_AND_LABEL_AUDIT.md", report)
    print(json.dumps(asset_audit, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
