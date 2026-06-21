#!/usr/bin/env python3
"""Create human audit package for roadclip_budget_v2."""

from __future__ import annotations

import argparse
import html
import random
import shutil
import tarfile
from pathlib import Path

from common import DEFAULT_CONFIG, ensure_output_dir, load_config, read_csv, to_float, validate_base_paths, write_blocked, write_csv


FIELDS = [
    "clip_id",
    "video_id",
    "segment_id",
    "start_time",
    "end_time",
    "clip_path",
    "local_clip_filename",
    "sample_reason",
    "conservative_positive",
    "risk_level",
    "affected_ego",
    "event_type",
    "negative_reason",
    "confidence",
    "evidence",
    "score_count",
    "score_naive",
    "score_kinematic",
    "human_label",
    "human_event_type",
    "human_reason",
    "human_confidence",
    "error_type",
]


def top_by(rows: list[dict], score: str, n: int) -> list[str]:
    return [r["clip_id"] for r in sorted(rows, key=lambda r: -to_float(r[score]))[:n]]


def temporal_nms(rows: list[dict], score: str, n: int, gap: float = 4.0) -> list[str]:
    selected = []
    for r in sorted(rows, key=lambda x: -to_float(x[score])):
        st = to_float(r["start_time"])
        if all(r["video_id"] != s["video_id"] or abs(st - to_float(s["start_time"])) > gap for s in selected):
            selected.append(r)
        if len(selected) >= n:
            break
    return [r["clip_id"] for r in selected]


def expansion(rows: list[dict], anchors: list[str], n: int, radius: int = 2) -> list[str]:
    by_video = {}
    pos = {}
    for r in rows:
        by_video.setdefault(r["video_id"], []).append(r)
    for video_rows in by_video.values():
        video_rows.sort(key=lambda r: to_float(r["start_time"]))
        for i, r in enumerate(video_rows):
            pos[r["clip_id"]] = (video_rows, i)
    selected = []
    for cid in anchors:
        if cid in pos and cid not in selected:
            selected.append(cid)
        if len(selected) >= n:
            break
        if cid not in pos:
            continue
        video_rows, idx = pos[cid]
        for d in range(1, radius + 1):
            for j in [idx - d, idx + d]:
                if 0 <= j < len(video_rows):
                    nid = video_rows[j]["clip_id"]
                    if nid not in selected:
                        selected.append(nid)
                        if len(selected) >= n:
                            return selected
    return selected[:n]


def add_reason(selected: dict[str, set[str]], cid: str, reason: str) -> None:
    selected.setdefault(cid, set()).add(reason)


def main() -> None:
    parser = argparse.ArgumentParser(description="Make audit package.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    cfg = load_config(args.config)
    validate_base_paths(cfg)
    output_dir = ensure_output_dir(cfg)
    labels_path = output_dir / "vlm_labels_conservative.csv"
    proxy_path = output_dir / "proxy_scores.csv"
    if not labels_path.is_file() or not proxy_path.is_file():
        path = write_blocked(output_dir, "BLOCKED_audit_missing_inputs.md", "BLOCKED: Audit Missing Inputs", ["Need vlm_labels_conservative.csv and proxy_scores.csv."])
        print(f"blocked_report={path}")
        return
    labels = {r["clip_id"]: r for r in read_csv(labels_path)}
    proxies = {r["clip_id"]: r for r in read_csv(proxy_path)}
    rows = []
    for cid, p in proxies.items():
        if cid in labels:
            rows.append({**p, **labels[cid]})
    rows.sort(key=lambda r: (r["video_id"], to_float(r["start_time"])))
    positives = [r for r in rows if r["conservative_positive"] == "yes"]
    negatives = [r for r in rows if r["conservative_positive"] != "yes"]
    rng = random.Random(42)
    selected: dict[str, set[str]] = {}
    for r in positives:
        add_reason(selected, r["clip_id"], "all_conservative_positive")
    for r in rng.sample(negatives, min(30, len(negatives))):
        add_reason(selected, r["clip_id"], "random_conservative_negative")
    for cid in top_by(negatives, "score_count", min(20, len(negatives))):
        add_reason(selected, cid, "top_count_high_score_negative")
    for cid in temporal_nms(rows, "score_naive", min(20, len(rows))):
        add_reason(selected, cid, "temporal_nms_naive_sample")
    for cid in expansion(rows, top_by(rows, "score_count", len(rows)), min(20, len(rows)), 2):
        add_reason(selected, cid, "proxy_then_expansion_count_sample")

    pkg_dir = output_dir / "audit_package"
    clips_dir = pkg_dir / "clips"
    if pkg_dir.exists():
        shutil.rmtree(pkg_dir)
    clips_dir.mkdir(parents=True, exist_ok=True)
    by_id = {r["clip_id"]: r for r in rows}
    manifest = []
    for cid in sorted(selected, key=lambda x: (by_id[x]["video_id"], to_float(by_id[x]["start_time"]))):
        r = by_id[cid]
        src = Path(r["clip_path"])
        local_name = src.name
        shutil.copy2(src, clips_dir / local_name)
        manifest.append(
            {
                "clip_id": cid,
                "video_id": r["video_id"],
                "segment_id": r["segment_id"],
                "start_time": r["start_time"],
                "end_time": r["end_time"],
                "clip_path": r["clip_path"],
                "local_clip_filename": f"clips/{local_name}",
                "sample_reason": ";".join(sorted(selected[cid])),
                "conservative_positive": r["conservative_positive"],
                "risk_level": r["risk_level"],
                "affected_ego": r["affected_ego"],
                "event_type": r["event_type"],
                "negative_reason": r["negative_reason"],
                "confidence": r["confidence"],
                "evidence": r.get("evidence", ""),
                "score_count": r["score_count"],
                "score_naive": r["score_naive"],
                "score_kinematic": r["score_kinematic"],
                "human_label": "",
                "human_event_type": "",
                "human_reason": "",
                "human_confidence": "",
                "error_type": "",
            }
        )
    write_csv(pkg_dir / "audit_manifest.csv", manifest, FIELDS)
    readme = [
        "# Roadclip V2 Human Audit Package",
        "",
        f"- clips in package: {len(manifest)}",
        f"- all conservative positives included: {len(positives)}",
        "",
        "Fill these columns in `audit_manifest.csv`:",
        "",
        "- `human_label`: 1 = true ego-relevant risk/path conflict, 0 = not ego-relevant risk, -1 = uncertain.",
        "- `human_event_type`: cut_in/crossing/sudden_braking/lane_conflict/normal_following/dense_traffic_only/roadside_static/other.",
        "- `human_reason`: brief reason.",
        "- `human_confidence`: low/medium/high.",
        "- `error_type`: optional, e.g. false_positive, false_negative, ambiguous_prompt, bad_scene.",
        "",
        "VLM labels are pseudo-GT and not human ground truth.",
    ]
    (pkg_dir / "README_AUDIT.md").write_text("\n".join(readme) + "\n", encoding="utf-8")
    cards = ["<html><body><h1>Roadclip V2 Audit</h1><table border='1'><tr><th>clip</th><th>reason</th><th>label</th><th>video</th></tr>"]
    for r in manifest:
        cards.append(
            f"<tr><td>{html.escape(r['clip_id'])}<br><video width='360' controls src='{html.escape(r['local_clip_filename'])}'></video></td>"
            f"<td>{html.escape(r['sample_reason'])}</td><td>{html.escape(r['conservative_positive'])}/{html.escape(r['event_type'])}</td><td>{html.escape(r['evidence'][:300])}</td></tr>"
        )
    cards.append("</table></body></html>")
    (pkg_dir / "index.html").write_text("\n".join(cards), encoding="utf-8")
    tar_path = output_dir / "roadclip_v2_audit_package.tar.gz"
    if tar_path.exists():
        tar_path.unlink()
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(pkg_dir, arcname="audit_package")
    print(f"audit_package={pkg_dir}")
    print(f"audit_tar={tar_path}")
    print(f"audit_clips={len(manifest)}")


if __name__ == "__main__":
    main()
