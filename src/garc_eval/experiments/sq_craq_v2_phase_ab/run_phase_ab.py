#!/usr/bin/env python3
"""SQ-CRAQ v2 phase A/B.

Phase A builds an independent, frozen probe set. Phase B materializes cheap
track-interaction and inside/outside contrast features, then evaluates their
within-bin TP/FP separation on the available six true-interval reference.

This script intentionally does not compute certificate or guarantee quantities.
"""

from __future__ import annotations

import argparse
import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
PROBE_OUT = ROOT / "outputs/probe_set_v1"
CHEAP_OUT = ROOT / "outputs/cheap_signal_v2"

REQUESTED_VIDEO = ROOT / "try_or_no/videos/realcartest.mp4"
FALLBACK_VIDEO = ROOT / "data/realcam/long_video_data/long_video_dataset3.mp4"

REF_OUT = ROOT / "src/garc_eval/outputs/clean_interval_aqp_full_reference_v2_clean_no_leak"
TIEBREAK_OUT = ROOT / "src/garc_eval/outputs/within_bin_tiebreak_ablation_v1"
TRACK_OUT = ROOT / "src/garc_eval/outputs/track_transition_validation_v1"
EXPANDED_REF = ROOT / "src/garc_eval/outputs/true_interval_reference_expansion_execution_v1/reference_events_expanded_v1.csv"

IMG_W = 1920.0
IMG_H = 1080.0
SEED = 20260702


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_dirs() -> None:
    for p in [
        PROBE_OUT,
        PROBE_OUT / "probe_media",
        PROBE_OUT / "probe_media/clips",
        PROBE_OUT / "probe_media/centers",
        PROBE_OUT / "probe_media/sheets",
        PROBE_OUT / "config",
        PROBE_OUT / "data_manifest",
        PROBE_OUT / "logs",
        CHEAP_OUT,
        CHEAP_OUT / "config",
        CHEAP_OUT / "data_manifest",
        CHEAP_OUT / "logs",
        CHEAP_OUT / "tables",
        CHEAP_OUT / "reports",
        CHEAP_OUT / "figures",
        CHEAP_OUT / "scripts",
    ]:
        p.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def append_progress(out_dir: Path, checkpoint: str, result: str, command: str = "", next_action: str = "") -> None:
    path = out_dir / "logs/progress.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("# Progress\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as fh:
        fh.write(
            f"- {utc_now()} | checkpoint={checkpoint} | command={command or 'n/a'} "
            f"| result={result} | next={next_action or 'n/a'}\n"
        )


def md_table(df: pd.DataFrame, max_rows: int = 40) -> str:
    if df.empty:
        return "_No rows._"
    view = df.head(max_rows).copy()
    lines = ["| " + " | ".join(map(str, view.columns)) + " |", "| " + " | ".join(["---"] * len(view.columns)) + " |"]
    for _, row in view.iterrows():
        vals: list[str] = []
        for c in view.columns:
            v = row[c]
            if isinstance(v, float):
                vals.append("" if math.isnan(v) else f"{v:.6g}")
            else:
                vals.append(str(v).replace("|", "\\|").replace("\n", " "))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def run(cmd: list[str]) -> tuple[bool, str]:
    p = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    return p.returncode == 0, p.stdout[-1200:]


def ffprobe_duration(path: Path) -> float:
    ok, out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nk=1:nw=1", str(path)])
    if not ok:
        raise RuntimeError(out)
    return float(out.strip())


def reference_offset_seconds() -> float:
    ref_path = REF_OUT / "reference_events.csv"
    if not ref_path.exists():
        return 0.0
    ref = pd.read_csv(ref_path)
    if {"absolute_t_start", "t_start"}.issubset(ref.columns) and len(ref):
        delta = pd.to_numeric(ref["absolute_t_start"], errors="coerce") - pd.to_numeric(ref["t_start"], errors="coerce")
        delta = delta.dropna()
        if len(delta):
            return float(delta.median())
    return 0.0


def video_source() -> tuple[Path, str, float, float, float]:
    if REQUESTED_VIDEO.exists():
        dur = ffprobe_duration(REQUESTED_VIDEO)
        return REQUESTED_VIDEO, "requested_realcartest_path", 0.0, dur, dur
    if FALLBACK_VIDEO.exists():
        offset = reference_offset_seconds()
        dur = ffprobe_duration(FALLBACK_VIDEO)
        logical_dur = max(0.0, dur - offset)
        return FALLBACK_VIDEO, "fallback_dataset3_with_reference_absolute_offset", offset, dur, logical_dur
    raise FileNotFoundError(f"Neither {REQUESTED_VIDEO} nor {FALLBACK_VIDEO} exists")


def fmt_time(x: float) -> str:
    return f"{x:.1f}".replace(".", "p")


def build_probe_set(n: int = 25, clip_duration: float = 10.0) -> None:
    ensure_dirs()
    video, status, offset, media_duration, logical_duration = video_source()
    if logical_duration <= clip_duration:
        raise RuntimeError(f"Available logical duration is too short: {logical_duration:.3f}s")

    margin = clip_duration / 2.0
    centers = np.linspace(margin, logical_duration - margin, n)
    rows = []
    for i, center in enumerate(centers, start=1):
        local_start = max(0.0, float(center - margin))
        local_end = min(logical_duration, float(center + margin))
        media_start = local_start + offset
        media_end = min(media_duration, local_end + offset)
        duration = max(0.5, media_end - media_start)
        probe_id = f"probe_set_v1_{i:04d}"
        clip_name = f"{probe_id}_{fmt_time(local_start)}_{fmt_time(local_end)}.mp4"
        center_name = f"{probe_id}_center.jpg"
        sheet_name = f"{probe_id}_sheet.jpg"
        clip_path = PROBE_OUT / "probe_media/clips" / clip_name
        center_path = PROBE_OUT / "probe_media/centers" / center_name
        sheet_path = PROBE_OUT / "probe_media/sheets" / sheet_name

        if clip_path.exists() and clip_path.stat().st_size > 0:
            clip_status = "OK_EXISTING"
            clip_msg = ""
        else:
            ok, msg = run(
                [
                    "ffmpeg",
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-ss",
                    f"{media_start:.3f}",
                    "-t",
                    f"{duration:.3f}",
                    "-i",
                    str(video),
                    "-c",
                    "copy",
                    str(clip_path),
                ]
            )
            if not ok:
                ok, msg = run(
                    [
                        "ffmpeg",
                        "-y",
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-ss",
                        f"{media_start:.3f}",
                        "-t",
                        f"{duration:.3f}",
                        "-i",
                        str(video),
                        "-an",
                        "-c:v",
                        "mpeg4",
                        "-q:v",
                        "5",
                        str(clip_path),
                    ]
                )
            clip_status = "OK" if ok else "FAILED"
            clip_msg = "" if ok else msg
            if not ok and clip_path.exists() and clip_path.stat().st_size == 0:
                clip_path.unlink()

        center_t = media_start + duration / 2.0
        if center_path.exists() and center_path.stat().st_size > 0:
            center_status = "OK_EXISTING"
            center_msg = ""
        else:
            ok, msg = run(
                [
                    "ffmpeg",
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-ss",
                    f"{center_t:.3f}",
                    "-i",
                    str(video),
                    "-frames:v",
                    "1",
                    "-q:v",
                    "3",
                    str(center_path),
                ]
            )
            center_status = "OK" if ok else "FAILED"
            center_msg = "" if ok else msg

        if sheet_path.exists() and sheet_path.stat().st_size > 0:
            sheet_status = "OK_EXISTING"
            sheet_msg = ""
        elif clip_status.startswith("OK"):
            ok, msg = run(
                [
                    "ffmpeg",
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    str(clip_path),
                    "-vf",
                    "fps=1/2,scale=320:-1,tile=5x4",
                    "-frames:v",
                    "1",
                    "-q:v",
                    "3",
                    str(sheet_path),
                ]
            )
            sheet_status = "OK" if ok else "FAILED"
            sheet_msg = "" if ok else msg
        else:
            sheet_status = "CLIP_MISSING"
            sheet_msg = clip_msg

        rows.append(
            {
                "probe_id": probe_id,
                "review_id": probe_id,
                "candidate_id": "",
                "probe_set": "probe_set_v1",
                "video_id": "realcartest",
                "sampling_rule": "independent_equal_interval_time_grid_not_candidate_lattice",
                "video_source_status": status,
                "video_path": str(video),
                "local_to_media_offset_seconds": offset,
                "local_t_start": local_start,
                "local_t_end": local_end,
                "media_t_start": media_start,
                "media_t_end": media_end,
                "duration": local_end - local_start,
                "context_start": local_start,
                "context_end": local_end,
                "source": "probe_set_v1_independent_temporal_grid",
                "clip_path": str(clip_path),
                "center_frame_path": str(center_path),
                "sheet_path": str(sheet_path),
                "clip_export_status": clip_status,
                "center_export_status": center_status,
                "sheet_export_status": sheet_status,
                "export_notes": "; ".join(x for x in [clip_msg, center_msg, sheet_msg] if x),
                "do_not_use_for_tuning": True,
            }
        )

    manifest = pd.DataFrame(rows)
    manifest.to_csv(PROBE_OUT / "probe_set_manifest.csv", index=False)
    manifest.to_csv(PROBE_OUT / "data_manifest/probe_set_manifest.csv", index=False)

    review = manifest[
        [
            "review_id",
            "probe_id",
            "video_id",
            "probe_set",
            "local_t_start",
            "local_t_end",
            "duration",
            "context_start",
            "context_end",
            "source",
            "clip_path",
            "center_frame_path",
            "sheet_path",
            "do_not_use_for_tuning",
        ]
    ].copy()
    review["suggested_event_type"] = "enter_ego_path_or_near_conflict"
    for col in [
        "human_event_type",
        "human_is_true_interval",
        "human_is_point_anchor",
        "human_is_negative",
        "corrected_start",
        "corrected_end",
        "boundary_confidence",
        "keep_for_interval_eval",
        "exclusion_reason",
        "notes",
        "final_reviewed_label",
    ]:
        review[col] = ""
    review.to_csv(PROBE_OUT / "probe_set_review_sheet.csv", index=False)

    write_text(
        PROBE_OUT / "README.md",
        f"""# probe_set_v1

Purpose: independent Layer 0 probe set for read-only evaluation of SQ-CRAQ v2 and later stages.

Hard restriction: rows marked `probe_set_v1` must not be used for tuning, threshold selection,
selector choice, repair decisions, or candidate generation. They are a frozen evaluation-only
readout once annotated.

Sampling:
- Rule: equal-interval time grid, independent of candidate lattice, envelope, and prior review queues.
- Target count: `{n}`.
- Clip duration: `{clip_duration}` seconds.
- Requested video path exists: `{REQUESTED_VIDEO.exists()}`.
- Video source used: `{video}`.
- Video source status: `{status}`.
- Local-to-media offset seconds: `{offset}`.
- Media duration seconds: `{media_duration:.3f}`.
- Available logical duration seconds: `{logical_duration:.3f}`.

Outputs:
- `probe_set_manifest.csv`: media/export manifest.
- `probe_set_review_sheet.csv`: empty annotation sheet.
- `probe_media/clips`, `probe_media/centers`, `probe_media/sheets`: exported review media.

No VLM, oracle, detector, candidate lattice, or envelope logic was run to construct this probe set.
""",
    )
    write_text(
        PROBE_OUT / "config/probe_set_v1.yaml",
        f"""probe_set: probe_set_v1
seed: {SEED}
sampling_rule: independent_equal_interval_time_grid_not_candidate_lattice
target_count: {n}
clip_duration_seconds: {clip_duration}
video_source_status: {status}
video_path: {video}
local_to_media_offset_seconds: {offset}
requested_video_path: {REQUESTED_VIDEO}
fallback_video_path: {FALLBACK_VIDEO}
do_not_use_for_tuning: true
""",
    )
    ok_clips = int(manifest["clip_export_status"].astype(str).str.startswith("OK").sum())
    ok_sheets = int(manifest["sheet_export_status"].astype(str).str.startswith("OK").sum())
    append_progress(PROBE_OUT, "build_probe_set", f"probes={len(manifest)} clips_ok={ok_clips} sheets_ok={ok_sheets}", next_action="annotate read-only probe sheet")


def add_track_dynamics(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy().sort_values(["track_id", "timestamp_sec", "detection_id"]).reset_index(drop=True)
    df["cx_norm"] = pd.to_numeric(df["cx"], errors="coerce") / IMG_W
    df["cy_norm"] = pd.to_numeric(df["cy"], errors="coerce") / IMG_H
    df["area_norm"] = pd.to_numeric(df["bbox_area"], errors="coerce") / (IMG_W * IMG_H)
    ego_x, ego_y = 0.5, 0.9
    df["ego_center_inside"] = df["cx_norm"].between(0.35, 0.65) & df["cy_norm"].between(0.45, 1.0)
    df["dist_to_ego"] = np.sqrt((df["cx_norm"] - ego_x) ** 2 + (df["cy_norm"] - ego_y) ** 2)

    g = df.groupby("track_id", sort=False)
    for col in ["timestamp_sec", "cx_norm", "cy_norm", "area_norm", "ego_center_inside", "dist_to_ego"]:
        df[f"prev_{col}"] = g[col].shift(1)
    df["dt"] = pd.to_numeric(df["timestamp_sec"] - df["prev_timestamp_sec"], errors="coerce")
    valid = df["dt"] > 0
    df["vx_norm_per_s"] = np.where(valid, (df["cx_norm"] - df["prev_cx_norm"]) / df["dt"], 0.0)
    df["vy_norm_per_s"] = np.where(valid, (df["cy_norm"] - df["prev_cy_norm"]) / df["dt"], 0.0)
    df["speed_norm_per_s"] = np.sqrt(df["vx_norm_per_s"] ** 2 + df["vy_norm_per_s"] ** 2)
    df["area_change_per_s"] = np.where(valid, (df["area_norm"] - df["prev_area_norm"]) / df["dt"], 0.0)
    df["ego_approach_rate"] = np.where(valid, (df["prev_dist_to_ego"] - df["dist_to_ego"]) / df["dt"], 0.0)
    df["entered_ego_center"] = valid & (~df["prev_ego_center_inside"].fillna(False).astype(bool)) & df["ego_center_inside"]
    df["approaching_ego"] = df["ego_approach_rate"] > 0.02
    return df


def pair_rows_for_frame(frame: pd.DataFrame) -> dict[str, float]:
    n = len(frame)
    if n < 2:
        return {
            "pair_count": 0,
            "close_pair_count": 0,
            "approaching_pair_count": 0,
            "min_pair_distance": np.nan,
            "min_ttc": np.nan,
            "max_closing_rate": 0.0,
            "mean_relative_speed": 0.0,
        }
    xy = frame[["cx_norm", "cy_norm"]].to_numpy(float)
    vv = frame[["vx_norm_per_s", "vy_norm_per_s"]].to_numpy(float)
    dists: list[float] = []
    ttcs: list[float] = []
    closing_rates: list[float] = []
    rel_speeds: list[float] = []
    close_count = 0
    approaching_count = 0
    for i in range(n):
        for j in range(i + 1, n):
            rel_pos = xy[j] - xy[i]
            dist = float(np.linalg.norm(rel_pos))
            rel_vel = vv[j] - vv[i]
            rel_speed = float(np.linalg.norm(rel_vel))
            closing = 0.0
            if dist > 1e-9:
                unit = rel_pos / dist
                closing = float(-np.dot(rel_vel, unit))
            if dist < 0.08:
                close_count += 1
            if closing > 0.02:
                approaching_count += 1
                ttcs.append(dist / closing)
            dists.append(dist)
            rel_speeds.append(rel_speed)
            closing_rates.append(closing)
    return {
        "pair_count": int(n * (n - 1) / 2),
        "close_pair_count": close_count,
        "approaching_pair_count": approaching_count,
        "min_pair_distance": float(np.min(dists)) if dists else np.nan,
        "min_ttc": float(np.min(ttcs)) if ttcs else np.nan,
        "max_closing_rate": float(np.max(closing_rates)) if closing_rates else 0.0,
        "mean_relative_speed": float(np.mean(rel_speeds)) if rel_speeds else 0.0,
    }


def aggregate_track_features(bin_seconds: int, det: pd.DataFrame, offset: float) -> pd.DataFrame:
    d = det.copy()
    d["local_timestamp_sec"] = d["timestamp_sec"] - offset
    d = d[(d["local_timestamp_sec"] >= 0.0) & (d["local_timestamp_sec"] <= 1200.0)].copy()
    d["local_bin_start"] = np.floor(d["local_timestamp_sec"] / bin_seconds) * bin_seconds
    frame_pairs = []
    for (local_bin, ts), frame in d.groupby(["local_bin_start", "timestamp_sec"], sort=True):
        pr = pair_rows_for_frame(frame)
        pr["local_bin_start"] = local_bin
        pr["timestamp_sec"] = ts
        frame_pairs.append(pr)
    pairs = pd.DataFrame(frame_pairs)
    rows = []
    for local_bin, g in d.groupby("local_bin_start", sort=True):
        pg = pairs[pairs["local_bin_start"] == local_bin] if len(pairs) else pd.DataFrame()
        rows.append(
            {
                "probe_set_usage": "not_used",
                "feature_source": "track_transition_validation_v1/object_tracks_dataset3_2fps.csv",
                "bin_seconds": bin_seconds,
                "local_t_start": float(local_bin),
                "local_t_end": float(local_bin + bin_seconds),
                "media_t_start": float(local_bin + offset),
                "media_t_end": float(local_bin + offset + bin_seconds),
                "num_detections": int(len(g)),
                "num_tracks": int(g["track_id"].nunique()),
                "tracks_in_ego_center_mean": float(g.groupby("timestamp_sec")["ego_center_inside"].sum().mean()),
                "ego_enter_count": int(g["entered_ego_center"].sum()),
                "approach_ego_count": int(g["approaching_ego"].sum()),
                "max_ego_approach_rate": float(g["ego_approach_rate"].max()),
                "mean_track_speed": float(g["speed_norm_per_s"].mean()),
                "max_track_speed": float(g["speed_norm_per_s"].max()),
                "mean_area_change_per_s": float(g["area_change_per_s"].mean()),
                "pair_count_mean": float(pg["pair_count"].mean()) if len(pg) else 0.0,
                "close_pair_count_sum": int(pg["close_pair_count"].sum()) if len(pg) else 0,
                "approaching_pair_count_sum": int(pg["approaching_pair_count"].sum()) if len(pg) else 0,
                "min_pair_distance": float(pg["min_pair_distance"].min()) if len(pg) else np.nan,
                "min_ttc": float(pg["min_ttc"].min()) if len(pg) else np.nan,
                "max_closing_rate": float(pg["max_closing_rate"].max()) if len(pg) else 0.0,
                "mean_relative_speed": float(pg["mean_relative_speed"].mean()) if len(pg) else 0.0,
            }
        )
    return pd.DataFrame(rows)


def build_track_interaction_features() -> pd.DataFrame:
    src = TRACK_OUT / "tables/object_tracks_dataset3_2fps.csv"
    if not src.exists():
        raise FileNotFoundError(src)
    det = pd.read_csv(src)
    det = add_track_dynamics(det)
    offset = reference_offset_seconds()
    out = pd.concat([aggregate_track_features(1, det, offset), aggregate_track_features(5, det, offset)], ignore_index=True)
    out.to_csv(CHEAP_OUT / "track_interaction_features.csv", index=False)
    out.to_csv(CHEAP_OUT / "tables/track_interaction_features.csv", index=False)
    return out


def build_contrast_features(window_seconds: float = 30.0) -> pd.DataFrame:
    src = REF_OUT / "cheap_signals_per_unit.csv"
    if not src.exists():
        raise FileNotFoundError(src)
    units = pd.read_csv(src).copy()
    candidate_cols = [
        "yolo_vehicle_count",
        "person_count",
        "bbox_area_mean",
        "bbox_area_max",
        "bbox_size_change",
        "track_speed",
        "track_acceleration",
        "relative_motion_score",
        "motion_energy",
        "optical_flow_burst",
        "object_density_change",
        "signal_disagreement",
        "cheap_fused_score",
        "primary_signal_score",
    ]
    cols = [c for c in candidate_cols if c in units.columns]
    rows = []
    for r in units.itertuples(index=False):
        row = {
            "unit_id": r.unit_id,
            "video_id": getattr(r, "video_id", "realcartest"),
            "local_t_start": float(r.t_start),
            "local_t_end": float(r.t_end),
            "absolute_t_start": float(r.absolute_t_start),
            "absolute_t_end": float(r.absolute_t_end),
            "window_seconds_each_side": window_seconds,
            "probe_set_usage": "not_used",
        }
        center = (float(r.t_start) + float(r.t_end)) / 2.0
        nbr = units[(units["t_start"] >= center - window_seconds) & (units["t_end"] <= center + window_seconds)]
        for c in cols:
            vals = pd.to_numeric(nbr[c], errors="coerce").dropna()
            x = float(getattr(r, c))
            mu = float(vals.mean()) if len(vals) else 0.0
            sd = float(vals.std(ddof=0)) if len(vals) else 0.0
            row[c] = x
            row[f"{c}_neighborhood_mean"] = mu
            row[f"{c}_contrast"] = x - mu
            row[f"{c}_z"] = (x - mu) / sd if sd > 1e-12 else 0.0
        rows.append(row)
    out = pd.DataFrame(rows)
    out.to_csv(CHEAP_OUT / "inside_outside_contrast_features.csv", index=False)
    out.to_csv(CHEAP_OUT / "tables/inside_outside_contrast_features.csv", index=False)
    return out


def auc_score(y: np.ndarray, s: np.ndarray) -> float:
    y = np.asarray(y).astype(int)
    s = np.asarray(s).astype(float)
    mask = np.isfinite(s)
    y = y[mask]
    s = s[mask]
    pos = int(y.sum())
    neg = int(len(y) - pos)
    if pos == 0 or neg == 0:
        return float("nan")
    order = np.argsort(s)
    ranks = np.empty(len(s), dtype=float)
    ranks[order] = np.arange(1, len(s) + 1)
    _, inv, counts = np.unique(s, return_inverse=True, return_counts=True)
    for group_id in np.where(counts > 1)[0]:
        idx = np.where(inv == group_id)[0]
        ranks[idx] = ranks[idx].mean()
    return float((ranks[y == 1].sum() - pos * (pos + 1) / 2.0) / (pos * neg))


def precision_at_20(y: np.ndarray, s: np.ndarray, descending: bool) -> float:
    y = np.asarray(y).astype(int)
    s = np.asarray(s).astype(float)
    s = np.where(np.isfinite(s), s, -np.inf if descending else np.inf)
    order = np.argsort(-s, kind="stable") if descending else np.argsort(s, kind="stable")
    k = min(20, len(order))
    if k == 0:
        return float("nan")
    return float(y[order[:k]].mean())


def aggregate_feature_table(intervals: pd.DataFrame, features: pd.DataFrame, prefix: str, feature_cols: list[str]) -> pd.DataFrame:
    rows = []
    f = features.copy()
    for r in intervals[["interval_id", "t_start", "t_end"]].itertuples(index=False):
        g = f[(f["local_t_start"] < float(r.t_end)) & (f["local_t_end"] > float(r.t_start))]
        row = {"interval_id": r.interval_id}
        for c in feature_cols:
            vals = pd.to_numeric(g[c], errors="coerce") if len(g) and c in g else pd.Series(dtype=float)
            row[f"{prefix}_{c}_mean"] = float(vals.mean()) if len(vals.dropna()) else 0.0
            row[f"{prefix}_{c}_max"] = float(vals.max()) if len(vals.dropna()) else 0.0
            row[f"{prefix}_{c}_min"] = float(vals.min()) if len(vals.dropna()) else 0.0
            if c.endswith("count") or c.endswith("sum") or c in {"ego_enter_count", "approach_ego_count"}:
                row[f"{prefix}_{c}_sum"] = float(vals.sum()) if len(vals.dropna()) else 0.0
        rows.append(row)
    return pd.DataFrame(rows)


def true_interval_event_ids() -> set[str]:
    ref = pd.read_csv(REF_OUT / "reference_events.csv")
    true_ref = ref[pd.to_numeric(ref["duration"], errors="coerce") >= 5.0]
    return set(true_ref["event_id"].astype(str))


def build_eval_table(track_features: pd.DataFrame, contrast_features: pd.DataFrame) -> pd.DataFrame:
    intervals = pd.read_csv(REF_OUT / "interval_lattice_features_only.csv")
    labels = pd.read_csv(REF_OUT / "interval_labels_v2_clean.csv")
    base = intervals.merge(labels, on="interval_id", how="left")

    track_1s = track_features[track_features["bin_seconds"] == 1].copy()
    track_cols = [
        "num_detections",
        "num_tracks",
        "tracks_in_ego_center_mean",
        "ego_enter_count",
        "approach_ego_count",
        "max_ego_approach_rate",
        "mean_track_speed",
        "max_track_speed",
        "close_pair_count_sum",
        "approaching_pair_count_sum",
        "min_pair_distance",
        "min_ttc",
        "max_closing_rate",
        "mean_relative_speed",
    ]
    track_cols = [c for c in track_cols if c in track_1s.columns]
    track_iv = aggregate_feature_table(intervals, track_1s, "track", track_cols)

    contrast_cols = [c for c in contrast_features.columns if c.endswith("_z")]
    contrast_iv = aggregate_feature_table(intervals, contrast_features, "contrast", contrast_cols)

    out = base.merge(track_iv, on="interval_id", how="left").merge(contrast_iv, on="interval_id", how="left")
    out.to_csv(CHEAP_OUT / "tables/interval_features_with_signal_v2.csv", index=False)
    return out


def evaluate_signals() -> pd.DataFrame:
    track_features = pd.read_csv(CHEAP_OUT / "track_interaction_features.csv")
    contrast_features = pd.read_csv(CHEAP_OUT / "inside_outside_contrast_features.csv")
    table = build_eval_table(track_features, contrast_features)
    bin_path = TIEBREAK_OUT / "top_p_answer_bin_candidates.csv"
    if not bin_path.exists():
        raise FileNotFoundError(bin_path)
    top_bin_ids = set(pd.read_csv(bin_path)["interval_id"].astype(str))
    eval_df = table[table["interval_id"].astype(str).isin(top_bin_ids)].copy()
    event_ids = true_interval_event_ids()
    eval_df["label_6_event_reference"] = eval_df["matched_event_id"].astype(str).isin(event_ids) & eval_df["event_hit_iou_0_3"].fillna(False).astype(bool)
    y = eval_df["label_6_event_reference"].astype(int).to_numpy()

    existing = [
        "active_score",
        "max_score",
        "mean_score",
        "score_persistence",
        "boundary_left_drop",
        "boundary_right_drop",
        "signal_disagreement",
        "vehicle_count_mean",
        "person_count_mean",
        "motion_energy_mean",
    ]
    new_track = [c for c in eval_df.columns if c.startswith("track_")]
    new_contrast = [c for c in eval_df.columns if c.startswith("contrast_")]
    rows = []
    for group, cols in [
        ("existing_signal", [c for c in existing if c in eval_df.columns]),
        ("track_interaction_signal", new_track),
        ("inside_outside_contrast_signal", new_contrast),
    ]:
        for c in cols:
            s = pd.to_numeric(eval_df[c], errors="coerce").fillna(0.0).to_numpy()
            auc_desc = auc_score(y, s)
            auc_asc = 1.0 - auc_desc if not math.isnan(auc_desc) else float("nan")
            if math.isnan(auc_desc):
                direction = "undefined"
                auc_best = float("nan")
                p20 = float("nan")
            elif auc_desc >= auc_asc:
                direction = "desc"
                auc_best = auc_desc
                p20 = precision_at_20(y, s, True)
            else:
                direction = "asc"
                auc_best = auc_asc
                p20 = precision_at_20(y, s, False)
            rows.append(
                {
                    "dataset_source": "6_event_reference",
                    "analysis_scope": "within_top_p_answer_bin",
                    "feature_group": group,
                    "feature": c,
                    "n_rows": int(len(eval_df)),
                    "n_positive": int(y.sum()),
                    "n_negative": int(len(y) - y.sum()),
                    "auc_desc": auc_desc,
                    "auc_best_direction": auc_best,
                    "ranking_direction_for_precision_at20": direction,
                    "precision_at20_best_direction": p20,
                    "probe_set_v1_usage": "not_used_for_tuning_or_threshold_selection",
                }
            )
    res = pd.DataFrame(rows)
    res = res.sort_values(["auc_best_direction", "precision_at20_best_direction"], ascending=False, na_position="last")
    res.to_csv(CHEAP_OUT / "tables/signal_upgrade_within_bin_metrics.csv", index=False)
    res.to_csv(CHEAP_OUT / "signal_upgrade_within_bin_metrics.csv", index=False)
    return res


def write_feature_reports(track_features: pd.DataFrame, contrast_features: pd.DataFrame, metrics: pd.DataFrame | None = None) -> None:
    expanded_status = "missing"
    expanded_rows = 0
    if EXPANDED_REF.exists():
        ex = pd.read_csv(EXPANDED_REF)
        expanded_rows = len(ex)
        expanded_status = "available_empty" if expanded_rows == 0 else "available_nonempty"
    probe_status = "pending_annotation"
    if (PROBE_OUT / "probe_set_review_sheet.csv").exists():
        probe = pd.read_csv(PROBE_OUT / "probe_set_review_sheet.csv")
        human_col = probe.get("human_is_true_interval", pd.Series(dtype=object))
        filled = (human_col.notna() & human_col.astype(str).str.strip().ne("")).sum()
        probe_status = "annotated" if filled else "pending_annotation"

    input_rows = [
        {"path": str((REF_OUT / "interval_lattice_features_only.csv").relative_to(ROOT)), "role": "existing interval lattice features", "exists": (REF_OUT / "interval_lattice_features_only.csv").exists()},
        {"path": str((REF_OUT / "interval_labels_v2_clean.csv").relative_to(ROOT)), "role": "evaluation labels only", "exists": (REF_OUT / "interval_labels_v2_clean.csv").exists()},
        {"path": str((REF_OUT / "cheap_signals_per_unit.csv").relative_to(ROOT)), "role": "existing cheap signal unit table", "exists": (REF_OUT / "cheap_signals_per_unit.csv").exists()},
        {"path": str((TRACK_OUT / "tables/object_tracks_dataset3_2fps.csv").relative_to(ROOT)), "role": "existing YOLO 2fps track table", "exists": (TRACK_OUT / "tables/object_tracks_dataset3_2fps.csv").exists()},
        {"path": str(EXPANDED_REF.relative_to(ROOT)), "role": "expanded reference if human review completed", "exists": EXPANDED_REF.exists()},
        {"path": str((PROBE_OUT / "probe_set_review_sheet.csv").relative_to(ROOT)), "role": "independent probe set annotation sheet", "exists": (PROBE_OUT / "probe_set_review_sheet.csv").exists()},
    ]
    inv = pd.DataFrame(input_rows)
    inv.to_csv(CHEAP_OUT / "data_manifest/input_manifest.csv", index=False)

    write_text(
        CHEAP_OUT / "config/cheap_signal_v2.yaml",
        f"""experiment: cheap_signal_v2
created_utc: {utc_now()}
uses_formal_guarantee: false
default_selector_changed: false
track_source: {TRACK_OUT / "tables/object_tracks_dataset3_2fps.csv"}
track_sample_rate_fps: 2
track_time_alignment: local_time = media_timestamp_sec - {reference_offset_seconds()}
inside_outside_window_seconds_each_side: 30
evaluation_scope: within_top_p_answer_bin
evaluation_sources:
  - 6_event_reference
  - expanded_reference_status: {expanded_status}
  - probe_set_v1_status: {probe_status}
""",
    )

    if metrics is None:
        metrics_md = "_Metrics not run._"
        decision = "NO-GO_PENDING_EVALUATION"
    else:
        top = metrics.head(20)
        metrics_md = md_table(top, 20)
        new = metrics[metrics["feature_group"].ne("existing_signal")]
        old = metrics[metrics["feature_group"].eq("existing_signal")]
        best_new = float(new["auc_best_direction"].max()) if len(new) else float("nan")
        best_old = float(old["auc_best_direction"].max()) if len(old) else float("nan")
        decision = "WEAK_GO_DIAGNOSTIC" if not math.isnan(best_new) and best_new > best_old else "NO_GO_DIAGNOSTIC"

    report = f"""# Cheap Signal V2 Evaluation Report

## Scope

This run implements SQ-CRAQ v2 Phase B only. It does not compute formal guarantee,
confidence interval, gamma lower bound, sample splitting, or certificate statistics.
The default selector was not changed.

## Inputs

{md_table(inv, 20)}

## New Feature Tables

| output | rows | notes |
| --- | ---: | --- |
| `track_interaction_features.csv` | {len(track_features)} | 1s and 5s bins from existing YOLO 2fps tracks |
| `inside_outside_contrast_features.csv` | {len(contrast_features)} | per-2s unit z/contrast features against +/-30s temporal neighborhood |

## Evaluation Availability

| dataset_source | status | action |
| --- | --- | --- |
| `6_event_reference` | available | within-bin AUC/precision@20 reported below |
| `expanded_reference` | {expanded_status} ({expanded_rows} rows) | not used unless non-empty human-reviewed file exists |
| `probe_set_v1` | {probe_status} | read-only evaluation only after annotation; not used for tuning |

## Within-Bin Results

Metrics below are on `dataset_source=6_event_reference`, `analysis_scope=within_top_p_answer_bin`.
`auc_best_direction` reports the better of ascending/descending ranking direction as a diagnostic
separation readout; it is not a selector change.

{metrics_md}

## Limitations

- Existing expanded reference is empty, so no `expanded_reference` metrics are available.
- `probe_set_v1` has no completed labels in this run, so no probe metrics are available.
- Track features reuse existing 2fps YOLO/linkage outputs; no new detector or VLM inference was run.
- Track timestamps are aligned to local reference time with the historical +2000s offset.
- Results are diagnostic empirical recall/precision signal checks, not formal guarantees.

## Decision

`{decision}`
"""
    write_text(CHEAP_OUT / "signal_upgrade_evaluation_report.md", report)
    write_text(CHEAP_OUT / "reports/signal_upgrade_evaluation_report.md", report)
    append_progress(CHEAP_OUT, "write_feature_reports", decision)


def build_features_and_eval() -> None:
    ensure_dirs()
    track = build_track_interaction_features()
    contrast = build_contrast_features()
    metrics = evaluate_signals()
    write_feature_reports(track, contrast, metrics)
    append_progress(CHEAP_OUT, "features_and_eval", f"track_rows={len(track)} contrast_rows={len(contrast)} metric_rows={len(metrics)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["probe", "features", "evaluate", "all"])
    parser.add_argument("--probe-count", type=int, default=25)
    parser.add_argument("--probe-duration", type=float, default=10.0)
    args = parser.parse_args()

    ensure_dirs()
    if args.stage in {"probe", "all"}:
        build_probe_set(args.probe_count, args.probe_duration)
    if args.stage in {"features", "all"}:
        build_features_and_eval()
    if args.stage == "evaluate":
        track = pd.read_csv(CHEAP_OUT / "track_interaction_features.csv")
        contrast = pd.read_csv(CHEAP_OUT / "inside_outside_contrast_features.csv")
        metrics = evaluate_signals()
        write_feature_reports(track, contrast, metrics)


if __name__ == "__main__":
    main()
