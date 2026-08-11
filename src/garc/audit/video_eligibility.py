from __future__ import annotations

import json
import random
import statistics
import subprocess
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any

from .provenance import audit_source, load_sidecar, sha256

VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}


def probe_video(path: Path) -> dict[str, Any]:
    command = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
               "format=duration:stream=width,height,avg_frame_rate,nb_frames", "-of", "json", str(path)]
    run = subprocess.run(command, capture_output=True, text=True)
    if run.returncode:
        return {"pass": False, "error": run.stderr[-2000:]}
    try:
        raw = json.loads(run.stdout)
        stream = raw["streams"][0]
        return {"pass": True, "duration_sec": float(raw["format"]["duration"]),
                "width": int(stream["width"]), "height": int(stream["height"]),
                "avg_frame_rate": stream.get("avg_frame_rate"), "nb_frames": stream.get("nb_frames")}
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as error:
        return {"pass": False, "error": f"probe_parse_error:{error}"}


def full_decode(path: Path) -> dict[str, Any]:
    run = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path),
                          "-map", "0:v:0", "-f", "null", "-"], capture_output=True, text=True)
    return {"pass": run.returncode == 0 and not run.stderr.strip(), "returncode": run.returncode,
            "stderr_tail": run.stderr[-4000:]}


def seek_audit(path: Path, digest: str, duration_sec: float, samples: int = 12) -> dict[str, Any]:
    rng = random.Random(int(digest[:16], 16))
    times = sorted(rng.uniform(1.0, max(1.001, duration_sec - 1.0)) for _ in range(samples))
    attempts = []
    for timestamp in times:
        run = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{timestamp:.6f}",
                              "-i", str(path), "-frames:v", "1", "-f", "null", "-"],
                             capture_output=True, text=True)
        attempts.append({"timestamp_sec": round(timestamp, 6),
                         "pass": run.returncode == 0 and not run.stderr.strip()})
    return {"pass": all(row["pass"] for row in attempts), "attempts": attempts}


def signatures(path: Path) -> list[dict[str, Any]]:
    run = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-vf",
                          "fps=1/30,scale=16:16,format=gray", "-f", "rawvideo", "-"], capture_output=True)
    if run.returncode:
        return []
    result = []
    for index in range(len(run.stdout) // 256):
        values = list(run.stdout[index * 256:(index + 1) * 256])
        median = statistics.median(values)
        bits = "".join("1" if value >= median else "0" for value in values)
        result.append({"timestamp_sec": index * 30.0, "signature": f"{int(bits, 2):064x}"})
    return result


def pairwise_overlap(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    reasons = []
    if left["sha256"] == right["sha256"]:
        reasons.append("EXACT_FILE_DUPLICATE")
    left_source, right_source = left["source"], right["source"]
    if left_source.get("capture_session_id") and left_source.get("capture_session_id") == right_source.get("capture_session_id"):
        reasons.append("SHARED_CAPTURE_SESSION_ID")
    left_names = {left["path"], Path(left["path"]).name, left["sha256"]}
    right_names = {right["path"], Path(right["path"]).name, right["sha256"]}
    if left_source.get("known_parent_video") in right_names or right_source.get("known_parent_video") in left_names:
        reasons.append("DECLARED_PARENT_RELATION")
    offsets: dict[int, int] = {}
    for a in left["signatures"]:
        for b in right["signatures"]:
            distance = (int(a["signature"], 16) ^ int(b["signature"], 16)).bit_count()
            if distance <= 4:
                offset = round((b["timestamp_sec"] - a["timestamp_sec"]) / 30.0)
                offsets[offset] = offsets.get(offset, 0) + 1
    support = max(offsets.values(), default=0)
    if support >= 3:
        reasons.append("OFFSET_CONSISTENT_CONTENT_OVERLAP")
    return {"left": left["path"], "right": right["path"],
            "max_offset_consistent_match_count": support, "failure_reasons": reasons,
            "pass": not reasons, "limitation": "Sparse perceptual sampling cannot prove absence of all overlap."}


def register_candidates(input_dir: Path, ledger_path: Path) -> list[dict[str, Any]]:
    prior = []
    if ledger_path.exists():
        prior = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    identities = {(row["path"], row["sha256"]) for row in prior}
    rows = list(prior)
    new_rows = []
    for path in sorted(item for item in input_dir.rglob("*") if item.is_file() and item.suffix.lower() in VIDEO_SUFFIXES):
        digest = sha256(path)
        identity = (str(path), digest)
        if identity not in identities:
            source = load_sidecar(path)
            declared = source.get("registration_utc")
            try:
                parsed = datetime.fromisoformat(str(declared).replace("Z", "+00:00"))
                normalized = parsed.astimezone(timezone.utc).isoformat() if parsed.tzinfo else None
            except ValueError:
                normalized = None
            new_rows.append({"path": str(path), "filename": path.name, "sha256": digest,
                             "bytes": path.stat().st_size, "declared_registration_utc": declared,
                             "normalized_registration_utc": normalized,
                             "semantic_information_opened": False})
            identities.add(identity)
    new_rows.sort(key=lambda row: (row["normalized_registration_utc"] or "9999-12-31T23:59:59+00:00",
                                   row["filename"], row["sha256"]))
    for row in new_rows:
        row["registration_order"] = len(rows) + 1
        rows.append(row)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    return rows


def audit_video_inputs(input_dir: Path, output_dir: Path, *, required_count: int = 4,
                       minimum_duration_sec: float = 1200.0) -> dict[str, Any]:
    """RESEARCH_SUPPORT technical/provenance Gate; it opens no semantic labels."""
    input_dir, output_dir = Path(input_dir), Path(output_dir)
    registry = register_candidates(input_dir, output_dir / "candidate_registration_ledger.jsonl")
    items = []
    for row in registry:
        path = Path(row["path"])
        source = load_sidecar(path)
        probe = probe_video(path)
        item = {"path": str(path), "sha256": row["sha256"], "source": source,
                "probe": probe, "signatures": signatures(path) if probe.get("pass") else []}
        if probe.get("pass"):
            item["decode"] = full_decode(path)
            item["seek"] = seek_audit(path, row["sha256"], probe["duration_sec"])
        else:
            item["decode"] = item["seek"] = {"pass": False}
        items.append(item)
    sessions = [item["source"].get("capture_session_id") for item in items
                if isinstance(item["source"].get("capture_session_id"), str)]
    provenance = [audit_source(Path(item["path"]), item["source"], sessions) for item in items]
    overlaps = [pairwise_overlap(a, b) for a, b in combinations(items, 2)]
    overlapped = {row[key] for row in overlaps if not row["pass"] for key in ("left", "right")}
    qualifying = []
    for item, source_audit in zip(items, provenance):
        technical = item["probe"].get("pass") and item["probe"].get("duration_sec", 0) >= minimum_duration_sec and item["decode"]["pass"] and item["seek"]["pass"]
        if technical and source_audit["pass"] and item["path"] not in overlapped:
            qualifying.append(item["path"])
    decision = {"INPUT_GATE": "PASS" if len(qualifying) >= required_count else "BLOCKED_INSUFFICIENT_INDEPENDENT_VIDEOS",
                "REQUIRED_NEW_VIDEO_COUNT": required_count, "QUALIFYING_NEW_VIDEO_COUNT": len(qualifying),
                "MISSING_NEW_VIDEO_COUNT": max(0, required_count - len(qualifying)),
                "QUALIFYING_VIDEOS": qualifying, "SEMANTIC_INFORMATION_OPENED": False,
                "research_support": True, "runtime_algorithm": False}
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, value in (("video_inventory.json", items), ("provenance_audit.json", provenance),
                        ("pairwise_content_independence.json", overlaps), ("input_gate_decision.json", decision)):
        (output_dir / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return decision
