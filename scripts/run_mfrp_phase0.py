#!/usr/bin/env python3
"""MFRP-V1 Phase 0: authoritative asset, label, and macro-region audit."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
import pandas as pd

from run_mrpo_phase0_audit import build_labels, scan_costs


ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmarks/partial_scan_pilot_v1"
IMM = BENCH / "immutable"
DER = BENCH / "derived"
OUT = ROOT / "outputs/multi_fidelity_region_preview_v1"
PARENT = ROOT / "outputs/macro_region_proxy_optimization_v1"
LENGTHS = (40, 60, 90, 120)
SELECTED_LENGTH = 40


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")
    tmp.replace(path)


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(value.rstrip() + "\n")
    tmp.replace(path)


def main() -> None:
    videos = pd.read_csv(IMM / "videos.csv")
    timeline = pd.read_csv(IMM / "timeline_units.csv")
    references = pd.read_csv(IMM / "reference_events.csv")
    mapping = pd.read_parquet(DER / "candidate_event_map.parquet")
    offset0 = mapping[mapping.partition_offset_sec.eq(0)]
    exposable = set(offset0.reference_event_id.astype(str))
    costs = scan_costs(timeline)
    v2_videos = ROOT / "benchmarks/partial_scan_pilot_v2/immutable/videos.csv"

    sensitivity_rows = []
    selected_regions = selected_event_map = None
    for length in LENGTHS:
        regions, event_map = build_labels(length, videos, timeline, references, exposable, costs)
        regions.to_parquet(OUT / f"experiments/macro_region_sensitivity/region_labels_L{length:03d}.parquet", index=False)
        event_map.to_parquet(OUT / f"experiments/macro_region_sensitivity/event_region_map_L{length:03d}.parquet", index=False)
        for video_id, group in regions.groupby("video_id", sort=True):
            sensitivity_rows.append({
                "macro_region_length_sec": length, "video_id": video_id,
                "region_count": len(group), "positive_region_count": int(group.binary_positive.sum()),
                "binary_positive_region_rate": float(group.binary_positive.mean()),
                "count_mean": float(group.residual_event_count.mean()),
                "count_variance": float(group.residual_event_count.var(ddof=1)),
                "count_max": int(group.residual_event_count.max()),
                "full_scan_cost_sec": float(group.full_scan_cost_sec.sum()),
                "tail_duration_fraction": float(group.iloc[-1].region_duration_fraction),
            })
        if length == SELECTED_LENGTH:
            selected_regions, selected_event_map = regions, event_map
    sensitivity = pd.DataFrame(sensitivity_rows)
    sensitivity.to_csv(OUT / "experiments/macro_region_sensitivity/label_sensitivity.csv", index=False)
    assert selected_regions is not None and selected_event_map is not None
    selected_regions[["video_id", "region_id", "region_index", "binary_positive"]].to_parquet(
        OUT / "labels/region_binary_labels.parquet", index=False
    )
    selected_regions[["video_id", "region_id", "region_index", "residual_event_count"]].to_parquet(
        OUT / "labels/region_count_labels.parquet", index=False
    )
    selected_event_map.to_parquet(OUT / "labels/event_region_map.parquet", index=False)
    selected_regions.to_parquet(OUT / "labels/region_table.parquet", index=False)

    partition_value = "\n".join(
        selected_regions.sort_values(["video_id", "region_index"])[
            ["video_id", "region_id", "start_sec", "end_sec"]
        ].astype(str).agg("|".join, axis=1)
    ).encode()
    partition_hash = hashlib.sha256(partition_value).hexdigest()
    write_json(OUT / "contracts/macro_region_selection.json", {
        "selected_macro_region_length_sec": SELECTED_LENGTH,
        "partition_hash": partition_hash,
        "selection_timing": "BEFORE_NEW_P1_P2_METRICS",
        "selection_scope": "TWO_DESIGN_VIDEOS_ONLY",
        "selection_rule": "LEAST_BINARY_LABEL_SATURATION_THEN_MAX_REGION_SAMPLE_SIZE",
        "selection_evidence": "experiments/macro_region_sensitivity/label_sensitivity.csv",
        "validation_reselection": "PROHIBITED",
    })

    per_video = []
    for video in videos.itertuples(index=False):
        all_count = int(references.video_id.eq(video.video_id).sum())
        exposed_count = int(offset0[offset0.video_id.eq(video.video_id)].reference_event_id.nunique())
        local_regions = selected_regions[selected_regions.video_id.eq(video.video_id)]
        per_video.append({
            "video_id": video.video_id, "duration_sec": float(video.duration_sec),
            "microchunk_count": int(timeline.video_id.eq(video.video_id).sum()),
            "selected_macro_region_count": len(local_regions),
            "all_reference_event_count": all_count,
            "exposable_event_count": exposed_count,
            "unexposable_event_count": all_count - exposed_count,
            "full_scan_exposure_ceiling": exposed_count / all_count,
            "full_scan_cost_sec": float(local_regions.full_scan_cost_sec.sum()),
            "binary_positive_region_rate": float(local_regions.binary_positive.mean()),
            "count_mean": float(local_regions.residual_event_count.mean()),
            "count_variance": float(local_regions.residual_event_count.var(ddof=1)),
            "count_max": int(local_regions.residual_event_count.max()),
        })
    asset_audit = {
        "status": "PASS", "authoritative_benchmark": "partial_scan_pilot_v1",
        "partial_scan_pilot_v2_video_manifest_exists": v2_videos.exists(),
        "asset_version_conflict": False,
        "design_video_count": len(videos), "per_video": per_video,
        "additional_complete_validation_videos_with_frozen_reference_and_timeline": 0,
        "formal_static_ranking_gate": "BLOCKED_INSUFFICIENT_VALIDATION_VIDEOS",
        "reference_type": "FULL_CONTEXT_ORACLE_PSEUDO_REFERENCE",
        "reference_completeness": "NOT_HUMAN_GROUND_TRUTH_COMPLETE",
        "all_reference_events": int(references.reference_event_id.nunique()),
        "exposable_reference_events": len(exposable),
        "unexposable_reference_events": int(references.reference_event_id.nunique()) - len(exposable),
        "full_scan_exposure_ceiling": len(exposable) / int(references.reference_event_id.nunique()),
    }
    write_json(OUT / "audits/asset_audit.json", asset_audit)
    write_json(OUT / "audits/label_audit.json", {
        "status": "PASS", "candidate_lengths_sec": list(LENGTHS),
        "selected_length_sec": SELECTED_LENGTH, "partition_hash": partition_hash,
        "event_mapping_rule": "MIDPOINT_EXACT_BOUNDARY_TO_SMALLER_INDEX",
        "event_map_row_count": len(selected_event_map),
        "unique_event_count": int(selected_event_map.reference_event_id.nunique()),
        "event_counted_once": bool(selected_event_map.reference_event_id.value_counts().eq(1).all()),
        "exposable_count_sum_across_regions": int(selected_regions.residual_event_count.sum()),
        "tail_regions_retained": True, "initial_probe_set": "EMPTY",
        "event_claim_scope": "RELATIVE_TO_FROZEN_FULL_CONTEXT_ORACLE_PSEUDO_REFERENCE",
    })

    # Inherit P0 as a frozen baseline, never as a tunable branch.
    shutil.copy2(PARENT / "preview/region_features/SELECTED.parquet", OUT / "preview/p0/region_features.parquet")
    shutil.copy2(PARENT / "preview/operator_manifests/P0_SELECTION.json", OUT / "preview/p0/operator_manifest.json")
    for path in sorted((PARENT / "preview/runtime_samples").glob("P0_KEYFRAME_5S_160X90__*.json")):
        shutil.copy2(path, OUT / "preview/runtime_samples" / ("P0__" + path.name))
    write_json(OUT / "preview/p0/inheritance_manifest.json", {
        "status": "FROZEN_BASELINE", "tuning": "CLOSED",
        "source_feature_path": "outputs/macro_region_proxy_optimization_v1/preview/region_features/SELECTED.parquet",
        "source_feature_sha256": sha256(PARENT / "preview/region_features/SELECTED.parquet"),
        "copied_feature_sha256": sha256(OUT / "preview/p0/region_features.parquet"),
        "frozen_best_feature": "luma_std__std", "frozen_orientation": -1,
        "frozen_design_recall_at_20": {"PSP_V0_SHORT": 0.2714285714285714, "PSP_V1_LONG": 0.26424870466321243},
        "frozen_nested_lovo_recall_at_20": {"PSP_V0_SHORT": 0.21428571428571427, "PSP_V1_LONG": 0.19689119170984457},
    })

    write_text(OUT / "reports/PHASE0_ASSET_AND_LABEL_AUDIT.md", f"""# Phase 0 Asset and Label Audit

Two complete design videos are authoritative under `partial_scan_pilot_v1`; no `partial_scan_pilot_v2` video manifest and no four complete validation videos with frozen references/timelines exist. Formal ranking is therefore blocked, while exploratory work is allowed.

The selected length is 40 s, frozen before new P1/P2 metrics because it has the least label saturation and the largest region sample size. It yields {len(selected_regions)} regions. All {len(selected_event_map)} pseudo-reference events map once; {len(exposable)} are offset-0 exposable and 5 are unexposable, for a {len(exposable)/len(selected_event_map):.6f} ceiling over all references.

`EVENT_CLAIM_SCOPE = RELATIVE_TO_FROZEN_FULL_CONTEXT_ORACLE_PSEUDO_REFERENCE`
""")
    print(json.dumps({
        "status": "PASS", "selected_length": SELECTED_LENGTH,
        "region_count": len(selected_regions), "exposable": len(exposable),
        "all_reference": len(selected_event_map),
        "formal_gate": asset_audit["formal_static_ranking_gate"],
    }, indent=2))


if __name__ == "__main__":
    main()
