from __future__ import annotations

import csv
import hashlib
import json
import random
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
PILOT = ROOT / "benchmarks/safety_critical_driving_event_reference_pilot_v1"
V1 = ROOT / "benchmarks/partial_scan_pilot_v1"
DERIVED = PILOT / "derived"
SEED = 20260729
V1_EXPECTED_HASHES = {
    "immutable/contracts/query_contract.yaml": "6965be01d0a6424025c13282979fe5730d8eaef55a43d39117df3c3c02e3bced",
    "immutable/reference_events.csv": "ca25d34744cb231dbc7dc48811fe56e7e42ecc59f2aa1b2b98c4949f11f55642",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def verify_v1() -> dict[str, str]:
    observed = {relative: sha256_file(V1 / relative) for relative in V1_EXPECTED_HASHES}
    if observed != V1_EXPECTED_HASHES:
        raise RuntimeError(f"frozen v1 hash mismatch: {observed}")
    return observed


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def overlaps_reference(window: dict[str, Any], references: list[dict[str, str]]) -> bool:
    start, end = float(window["start_sec"]), float(window["end_sec"])
    return any(
        row["video_id"] == window["video_id"]
        and min(end, float(row["event_end_sec"])) > max(start, float(row["event_start_sec"]))
        for row in references
    )


def load_legacy_candidates() -> dict[str, list[dict[str, Any]]]:
    references = read_csv(V1 / "immutable/reference_events.csv")
    videos = {row["video_id"]: row for row in read_csv(V1 / "immutable/videos.csv")}
    raw_root = V1 / "derived/reference_construction/raw"
    pools = {
        "legacy_cut_in_positive": [],
        "legacy_cut_in_hard_negative": [],
        "legacy_boundary_disagreement": [],
        "normal_traffic_control": [],
    }
    for path in sorted(raw_root.glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("parse_status") != "ok":
            continue
        events = record.get("parsed", {}).get("events", [])
        base = {
            "video_id": record["video_id"],
            "video_path": videos[record["video_id"]]["video_path"],
            "start_sec": float(record["start_sec"]),
            "end_sec": float(record["end_sec"]),
            "source_window_id": record["window_id"],
            "expected_sample_fps": 2.0,
        }
        boundary = any(
            float(event["start_sec"]) <= 0.5
            or float(event["end_sec"]) >= float(record["duration_sec"]) - 0.5
            for event in events
        )
        if boundary:
            pools["legacy_boundary_disagreement"].append({
                **base, "selection_reason": "legacy event touches a window boundary",
            })
        elif events:
            pools["legacy_cut_in_positive"].append({
                **base, "selection_reason": "legacy cut-in pseudo-reference positive",
            })
        elif overlaps_reference(base, references):
            pools["legacy_cut_in_hard_negative"].append({
                **base,
                "selection_reason": "legacy empty window overlaps an event reported by another context window",
            })
        else:
            pools["normal_traffic_control"].append({
                **base, "selection_reason": "legacy empty window with no overlapping cut-in reference",
            })
    return pools


def deterministic_selection(pools: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    targets = {
        "legacy_cut_in_positive": 10,
        "legacy_cut_in_hard_negative": 5,
        "legacy_boundary_disagreement": 5,
        "normal_traffic_control": 10,
    }
    rng = random.Random(SEED)
    selected: list[dict[str, Any]] = []
    used: set[str] = set()
    for stratum, target in targets.items():
        candidates = list(pools[stratum])
        rng.shuffle(candidates)
        by_video: dict[str, list[dict[str, Any]]] = {}
        for candidate in candidates:
            by_video.setdefault(candidate["video_id"], []).append(candidate)
        ordered: list[dict[str, Any]] = []
        while any(by_video.values()):
            for video_id in sorted(by_video):
                if by_video[video_id]:
                    ordered.append(by_video[video_id].pop())
        for candidate in ordered:
            if candidate["source_window_id"] in used:
                continue
            selected.append({**candidate, "selection_stratum": stratum})
            used.add(candidate["source_window_id"])
            if sum(row["selection_stratum"] == stratum for row in selected) == target:
                break
    # Prevent monotonically assigned sample IDs from revealing the selection stratum.
    rng.shuffle(selected)
    for index, row in enumerate(selected, 1):
        row["sample_id"] = f"SCDE_REF_{index:03d}"
    return selected


def audit_alternative_assets() -> dict[str, Any]:
    manifest = (
        ROOT
        / "outputs/mf_psvr_publication_program/cycle_01_training_pool/candidates/UNIT_MANIFEST.csv"
    )
    if not manifest.is_file():
        return {"status": "ABSENT", "manifest": str(manifest.relative_to(ROOT))}
    rows = read_csv(manifest)
    locators = sorted({row["local_locator"] for row in rows if row.get("local_locator")})
    available = [locator for locator in locators if (ROOT / locator).is_file()]
    tags: dict[str, int] = {}
    for locator in locators:
        matching = next(row for row in rows if row.get("local_locator") == locator)
        tag = matching.get("sampling_tag_only", "") or "unknown"
        tags[tag] = tags.get(tag, 0) + 1
    return {
        "status": "METADATA_ONLY_NO_LOCAL_VIDEO_BYTES" if not available else "LOCAL_VIDEO_BYTES_PRESENT_REQUIRES_INDEPENDENCE_REVIEW",
        "manifest": str(manifest.relative_to(ROOT)),
        "unique_video_locator_count": len(locators),
        "locally_available_video_count": len(available),
        "sampling_tag_video_counts": tags,
        "human_adjudicated": False,
        "disposition": (
            "Do not use metadata-only collision/near-collision tags to claim the four missing "
            "semantic strata; derived labels are provenance, not human event truth."
        ),
    }


def main() -> None:
    observed_hashes = verify_v1()
    pools = load_legacy_candidates()
    selected = deterministic_selection(pools)
    private_fields = [
        "sample_id", "video_id", "video_path", "start_sec", "end_sec",
        "expected_sample_fps", "selection_stratum", "selection_reason", "source_window_id",
    ]
    blinded_fields = [
        "sample_id", "video_id", "video_path", "start_sec", "end_sec",
        "expected_sample_fps",
    ]
    write_csv(DERIVED / "private/sample_selection_manifest.csv", selected, private_fields)
    write_csv(DERIVED / "blinded/annotation_manifest.csv", selected, blinded_fields)

    required_external = {
        "longitudinal_conflict_candidate": 5,
        "vulnerable_road_user_crossing_candidate": 5,
        "road_hazard_candidate": 5,
        "intersection_conflict_candidate": 5,
    }
    observed_counts = {name: len(rows) for name, rows in pools.items()}
    selected_counts = {
        name: sum(row["selection_stratum"] == name for row in selected)
        for name in pools
    }
    missing_external = sorted(required_external)
    selected_video_paths = sorted({row["video_path"] for row in selected})
    available_selected_video_paths = [
        path for path in selected_video_paths if Path(path).is_file()
    ]
    missing_selected_video_paths = sorted(
        set(selected_video_paths) - set(available_selected_video_paths)
    )
    blockers = []
    if missing_external:
        blockers.append("MISSING_INDEPENDENT_SEMANTIC_POOLS")
    if missing_selected_video_paths:
        blockers.append("MISSING_SELECTED_SOURCE_VIDEO_BYTES")
    audit = {
        "status": "BLOCKED_" + "_AND_".join(blockers),
        "v1_hashes_verified": observed_hashes,
        "available_legacy_pool_counts": observed_counts,
        "selected_legacy_counts": selected_counts,
        "selected_sample_count": len(selected),
        "target_total_range": [45, 55],
        "required_external_pool_counts": required_external,
        "missing_external_pools": missing_external,
        "selected_unique_video_count": len(selected_video_paths),
        "available_selected_video_count": len(available_selected_video_paths),
        "missing_selected_video_paths": missing_selected_video_paths,
        "alternative_asset_audit": audit_alternative_assets(),
        "vlm_launch_allowed": False,
        "reason": (
            "Legacy provenance supports cut-in and control selection metadata only. The selected "
            "source video bytes are absent in this checkout, and selecting other hazard families "
            "without an independent pool would fabricate semantic coverage."
        ),
    }
    (DERIVED / "audits").mkdir(parents=True, exist_ok=True)
    (DERIVED / "audits/sample_availability_audit.json").write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
