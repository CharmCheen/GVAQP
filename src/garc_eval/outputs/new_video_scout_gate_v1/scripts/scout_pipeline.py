#!/usr/bin/env python3
"""P0 New-Video Scout Gate — low-cost data-availability & event-density screening.

CHEAP SIGNALS ONLY. No VLM / LLM oracle. No semantic event labels. No claim that
proxy high-score windows are real events. The output is a NECESSARY-condition
non-degeneracy screen that decides whether a video is worth a center10 pilot next.

For each video:
  1. live ffprobe metadata (duration / resolution / fps / frame count / bitrate)
  2. one sequential cv2 pass:
       - motion energy @ 2fps (resize 320x180, absdiff) aggregated per 5s window
       - 1 midpoint frame per 5s window stashed for batched YOLOv8n inference
       - 1 frame per 60s stashed for the contact sheet
  3. batched YOLOv8n (GPU) on midpoint frames -> per-window:
       vehicle / person / bicycle / motorcycle / object counts,
       bbox_area_sum, max_bbox_area,
       center-ROI & bottom-ROI vehicle occupancy (V13.5 thirds, true bbox center),
       near-ego lower-center band occupancy (kinematic ROI 0.35-0.65 x, 0.45-1.0 y),
       bbox lateral activity (cx std, lateral-presence count)
  4. per-window CSV (V13.5 schema + extra class/ROI/lateral columns)
  5. summary stats CSV, timeline figures, contact sheet montage
  6. append a per-video JSON summary for the report

Schema is a superset of V13.5 proxy_features_5s.csv so downstream V13 code can
consume it; extra columns are appended (never rename the V13.5 columns).
"""
import argparse
import csv
import json
import os
import subprocess
import sys
import time
from collections import OrderedDict

import cv2
import numpy as np

OUTROOT = "/qiuyeqing/llama_prl/G-ARC/garc_eval/outputs/new_video_scout_gate_v1"
YOLO_MODEL = "/qiuyeqing/llama_prl/G-ARC/models/yolo/yolov8n.pt"

# COCO class ids
PERSON = 0
BICYCLE = 1
CAR = 2
MOTORCYCLE = 3
BUS = 5
TRUCK = 7
VEHICLE_CLS = [CAR, MOTORCYCLE, BUS, TRUCK]  # matches V13.5 vehicle_mask

WINDOW = 5.0          # seconds per coarse window (V13.5)
MOTION_FPS = 2        # motion sampling rate
MOTION_W, MOTION_H = 320, 180
CONTACT_INTERVAL = 60.0  # one contact-sheet frame every N seconds
YOLO_BATCH = 16


def log(msg, fh=None):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    if fh is not None:
        fh.write(line + "\n")
        fh.flush()


def ffprobe_meta(path):
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json",
           "-show_format", "-show_streams", path]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    vs = next(s for s in d["streams"] if s["codec_type"] == "video")
    fmt = d.get("format", {})
    fr = vs.get("r_frame_rate", "0/1")
    num, den = fr.split("/")
    fps = float(num) / float(den) if float(den) != 0 else 0.0
    return {
        "path": path,
        "width": int(vs["width"]),
        "height": int(vs["height"]),
        "fps": fps,
        "r_frame_rate": fr,
        "nb_frames": int(vs.get("nb_frames", 0)) if vs.get("nb_frames") else 0,
        "duration": float(vs.get("duration", fmt.get("duration", 0))),
        "bit_rate": int(vs.get("bit_rate", 0)) if vs.get("bit_rate") else 0,
        "codec": vs.get("codec_name"),
        "profile": vs.get("profile"),
        "pix_fmt": vs.get("pix_fmt"),
    }


def build_windows(duration):
    wins = []
    t = 0.0
    idx = 0
    while t < duration:
        end = min(t + WINDOW, duration)
        wins.append({"idx": idx, "start": t, "end": end,
                     "mid": (t + end) / 2.0})
        t = end
        idx += 1
    return wins


def run_motion_and_collect(video_path, meta, windows, limit_sec, logfh, collect_yolo=True, collect_contact=True):
    """Single sequential pass. Returns motion_per_window, yolo_frames, contact_frames, read_stats."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        log(f"FAILED to open {video_path}", logfh)
        return None
    fps = meta["fps"] if meta["fps"] > 0 else cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    motion_interval = max(1, int(round(fps / MOTION_FPS)))
    end_frame = int(limit_sec * fps) if limit_sec else total
    log(f"  pass: fps={fps:.3f} total={total} motion_every={motion_interval} "
        f"(~{MOTION_FPS}fps) end_frame={end_frame}", logfh)

    motion_samples = {w["idx"]: [] for w in windows}
    # map midpoint frame -> window idx
    mid_frames = {}
    for w in windows:
        mf = int(w["mid"] * fps)
        if mf < end_frame:
            mid_frames[mf] = w["idx"]

    yolo_buffer = []  # list of (win_idx, frame_bgr)
    yolo_frames = {}  # win_idx -> frame (kept only if collect_yolo and used for batched inference later)
    contact_thumbs = []  # (timestamp, thumb_bgr small)
    last_contact_t = -CONTACT_INTERVAL

    prev_gray = None
    frame_idx = 0
    read_ok = 0
    read_fail = 0
    t0 = time.time()
    while True:
        if frame_idx >= end_frame:
            break
        ret, frame = cap.read()
        if not ret:
            read_fail += 1
            if frame_idx == 0:
                log(f"  read failed at frame 0 — abort", logfh)
                cap.release()
                return None
            frame_idx += 1
            continue
        read_ok += 1
        ts = frame_idx / fps

        # motion
        if frame_idx % motion_interval == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray_s = cv2.resize(gray, (MOTION_W, MOTION_H))
            motion = 0.0
            if prev_gray is not None:
                motion = float(np.mean(cv2.absdiff(gray_s, prev_gray)))
            prev_gray = gray_s
            for w in windows:
                if w["start"] <= ts < w["end"]:
                    motion_samples[w["idx"]].append(motion)
                    break

        # yolo midpoint stash (buffered, flushed by caller via batch loop below)
        if collect_yolo and frame_idx in mid_frames:
            yolo_buffer.append((mid_frames[frame_idx], frame.copy()))

        # contact sheet
        if collect_contact and ts - last_contact_t >= CONTACT_INTERVAL - 1e-3:
            thumb = cv2.resize(frame, (160, 90))
            contact_thumbs.append((ts, thumb))
            last_contact_t = ts

        frame_idx += 1
        if frame_idx % 5000 == 0:
            elapsed = time.time() - t0
            pct = frame_idx / end_frame * 100
            log(f"    read {frame_idx}/{end_frame} ({pct:.1f}%) ok={read_ok} "
                f"fail={read_fail} {frame_idx/elapsed:.0f}fps", logfh)

    cap.release()
    elapsed = time.time() - t0
    log(f"  pass done: read_ok={read_ok} read_fail={read_fail} "
        f"motion_frames={sum(len(v) for v in motion_samples.values())} "
        f"yolo_stashed={len(yolo_buffer)} contact={len(contact_thumbs)} "
        f"elapsed={elapsed:.1f}s", logfh)

    # aggregate motion
    motion_per_window = {}
    for w in windows:
        ms = motion_samples[w["idx"]]
        if ms:
            motion_per_window[w["idx"]] = {
                "motion_energy_mean": float(np.mean(ms)),
                "motion_energy_max": float(np.max(ms)),
                "motion_energy_std": float(np.std(ms)),
                "motion_frames_sampled": len(ms),
            }
        else:
            motion_per_window[w["idx"]] = {
                "motion_energy_mean": 0.0, "motion_energy_max": 0.0,
                "motion_energy_std": 0.0, "motion_frames_sampled": 0,
            }
    read_stats = {"read_ok": read_ok, "read_fail": read_fail,
                  "end_frame": end_frame, "pass_seconds": elapsed}
    return motion_per_window, yolo_buffer, contact_thumbs, read_stats


def yolo_features_for_batch(model, device, batch_frames, logfh):
    """Run YOLO on a list of BGR frames, return list of feature dicts."""
    results = model(batch_frames, device=device, verbose=False)
    out = []
    for r in results:
        boxes = r.boxes
        fh_img, fw_img = r.orig_shape[0], r.orig_shape[1]
        feat = {
            "vehicle_count": 0, "person_count": 0, "bicycle_count": 0,
            "motorcycle_count": 0, "object_count": 0,
            "bbox_area_sum": 0.0, "max_bbox_area": 0.0,
            "center_roi_vehicle_count": 0, "bottom_roi_vehicle_count": 0,
            "near_ego_vehicle_count": 0,
            "bbox_cx_std": 0.0, "lateral_presence_count": 0,
            "yolo_status": "no_detections",
        }
        if boxes is not None and len(boxes) > 0:
            cls = boxes.cls.cpu().numpy().astype(int)
            xyxy = boxes.xyxy.cpu().numpy()
            areas = (xyxy[:, 2] - xyxy[:, 0]) * (xyxy[:, 3] - xyxy[:, 1])
            cx = (xyxy[:, 0] + xyxy[:, 2]) / 2.0
            cy = (xyxy[:, 1] + xyxy[:, 3]) / 2.0  # TRUE vertical center (fixes V13.5 bug)
            veh = np.isin(cls, VEHICLE_CLS)
            feat["vehicle_count"] = int(veh.sum())
            feat["person_count"] = int((cls == PERSON).sum())
            feat["bicycle_count"] = int((cls == BICYCLE).sum())
            feat["motorcycle_count"] = int((cls == MOTORCYCLE).sum())
            feat["object_count"] = int(len(cls))
            feat["bbox_area_sum"] = float(areas.sum())
            feat["max_bbox_area"] = float(areas.max())
            # V13.5 thirds ROI
            center_mask = (cx > fw_img/3) & (cx < 2*fw_img/3) & \
                          (cy > fh_img/3) & (cy < 2*fh_img/3)
            feat["center_roi_vehicle_count"] = int((veh & center_mask).sum())
            bottom_mask = cy > 2*fh_img/3
            feat["bottom_roi_vehicle_count"] = int((veh & bottom_mask).sum())
            # near-ego lower-center band (kinematic ROI 0.35-0.65 x, 0.45-1.0 y)
            ego_mask = (cx > 0.35*fw_img) & (cx < 0.65*fw_img) & (cy > 0.45*fh_img)
            feat["near_ego_vehicle_count"] = int((veh & ego_mask).sum())
            # lateral activity
            if len(cx) >= 2:
                feat["bbox_cx_std"] = float(np.std(cx) / fw_img)  # normalized
            lateral = (cx < fw_img/3) | (cx > 2*fw_img/3)
            feat["lateral_presence_count"] = int(lateral.sum())
            feat["yolo_status"] = "ok"
        out.append(feat)
    return out


def build_contact_sheet(thumbs, out_path, video_id, logfh):
    if not thumbs:
        log(f"  no contact frames for {video_id}", logfh)
        return None
    cols = 12
    rows = (len(thumbs) + cols - 1) // cols
    tw, th = 160, 90
    pad = 4
    sheet = np.full((rows * (th + pad) + pad, cols * (tw + pad) + pad, 3), 255, np.uint8)
    for i, (ts, thumb) in enumerate(thumbs):
        r, c = i // cols, i % cols
        y = pad + r * (th + pad)
        x = pad + c * (tw + pad)
        sheet[y:y+th, x:x+tw] = thumb
        cv2.putText(sheet, f"{ts/60:.1f}m", (x + 2, y + 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1, cv2.LINE_AA)
    cv2.imwrite(out_path, sheet)
    log(f"  contact sheet: {out_path} ({len(thumbs)} thumbs, {rows}x{cols})", logfh)
    return out_path


def write_window_csv(windows, motion_per_window, yolo_per_window, video_id, out_path, logfh):
    fieldnames = [
        "clip_id", "video_id", "start_time", "end_time",
        "motion_energy_mean", "motion_energy_max", "motion_energy_std", "motion_frames_sampled",
        "vehicle_count_mean", "vehicle_count_max",
        "object_count_mean", "object_count_max",
        "bbox_area_sum_mean", "bbox_area_sum_max",
        "max_bbox_area_mean",
        "center_roi_vehicle_count_mean",
        "bottom_roi_vehicle_count_mean",
        "yolo_status",
        # --- extra scout columns (not in V13.5 schema) ---
        "person_count", "bicycle_count", "motorcycle_count",
        "near_ego_vehicle_count", "bbox_cx_std", "lateral_presence_count",
    ]
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for win in windows:
            cid = f"{video_id}_w{win['idx']:05d}"
            row = {"clip_id": cid, "video_id": video_id,
                   "start_time": f"{win['start']:.3f}", "end_time": f"{win['end']:.3f}"}
            m = motion_per_window.get(win["idx"], {})
            row["motion_energy_mean"] = m.get("motion_energy_mean", 0.0)
            row["motion_energy_max"] = m.get("motion_energy_max", 0.0)
            row["motion_energy_std"] = m.get("motion_energy_std", 0.0)
            row["motion_frames_sampled"] = m.get("motion_frames_sampled", 0)
            y = yolo_per_window.get(win["idx"], {})
            # map to V13.5 column names (single midpoint frame -> mean==max==value)
            vc = y.get("vehicle_count", 0)
            oc = y.get("object_count", 0)
            bas = y.get("bbox_area_sum", 0.0)
            mba = y.get("max_bbox_area", 0.0)
            row["vehicle_count_mean"] = vc
            row["vehicle_count_max"] = vc
            row["object_count_mean"] = oc
            row["object_count_max"] = oc
            row["bbox_area_sum_mean"] = bas
            row["bbox_area_sum_max"] = bas
            row["max_bbox_area_mean"] = mba
            row["center_roi_vehicle_count_mean"] = y.get("center_roi_vehicle_count", 0)
            row["bottom_roi_vehicle_count_mean"] = y.get("bottom_roi_vehicle_count", 0)
            row["yolo_status"] = y.get("yolo_status", "not_attempted")
            # extras
            row["person_count"] = y.get("person_count", 0)
            row["bicycle_count"] = y.get("bicycle_count", 0)
            row["motorcycle_count"] = y.get("motorcycle_count", 0)
            row["near_ego_vehicle_count"] = y.get("near_ego_vehicle_count", 0)
            row["bbox_cx_std"] = y.get("bbox_cx_std", 0.0)
            row["lateral_presence_count"] = y.get("lateral_presence_count", 0)
            w.writerow(row)
    log(f"  wrote {out_path} ({len(windows)} rows)", logfh)
    return fieldnames


def make_timelines(windows, csv_path, video_id, figdir, logfh):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows = []
    with open(csv_path) as f:
        for r in csv.DictReader(f):
            rows.append(r)
    t = [float(r["start_time"]) for r in rows]
    me = [float(r["motion_energy_mean"]) for r in rows]
    vc = [int(r["vehicle_count_mean"]) for r in rows]
    oc = [int(r["object_count_mean"]) for r in rows]
    pc = [int(r["person_count"]) for r in rows]
    bc = [int(r["bicycle_count"]) for r in rows]
    mc = [int(r["motorcycle_count"]) for r in rows]
    ego = [int(r["near_ego_vehicle_count"]) for r in rows]
    lat = [float(r["bbox_cx_std"]) for r in rows]

    fig, axes = plt.subplots(3, 1, figsize=(13, 8), sharex=True)
    axes[0].plot(t, me, lw=0.8, color="tab:blue")
    axes[0].set_ylabel("motion_energy_mean\n(0-255 absdiff)")
    axes[0].set_title(f"{video_id}: cheap scout signal timelines (5s windows)")
    axes[1].plot(t, vc, lw=0.8, color="tab:orange", label="vehicle")
    axes[1].plot(t, pc, lw=0.8, color="tab:green", label="person")
    axes[1].plot(t, bc, lw=0.8, color="tab:red", label="bicycle")
    axes[1].plot(t, mc, lw=0.8, color="tab:purple", label="motorcycle")
    axes[1].set_ylabel("YOLOv8n count\n(midpoint frame)")
    axes[1].legend(loc="upper right", fontsize=7, ncol=4)
    axes[2].plot(t, ego, lw=0.8, color="tab:brown", label="near_ego_vehicle")
    axes[2].plot(t, lat, lw=0.8, color="tab:gray", label="bbox_cx_std (norm)")
    axes[2].set_ylabel("ego occupancy / lateral")
    axes[2].set_xlabel("time (s)")
    axes[2].legend(loc="upper right", fontsize=7, ncol=2)
    for ax in axes:
        ax.grid(alpha=0.3)
    plt.tight_layout()
    out = os.path.join(figdir, f"scout_timeline_{video_id}.png")
    plt.savefig(out, dpi=110)
    plt.close()
    log(f"  timeline figure: {out}", logfh)
    return out


def summarize(windows, csv_path, meta, read_stats, video_id, logfh):
    rows = []
    with open(csv_path) as f:
        for r in csv.DictReader(f):
            rows.append(r)
    n = len(rows)
    def col(name, cast=float):
        return [cast(r[name]) for r in rows]
    me = col("motion_energy_mean")
    vc = col("vehicle_count_mean", int)
    oc = col("object_count_mean", int)
    pc = col("person_count", int)
    bc = col("bicycle_count", int)
    mc = col("motorcycle_count", int)
    ego = col("near_ego_vehicle_count", int)
    lat = col("bbox_cx_std")
    latpres = col("lateral_presence_count", int)

    def stat(v):
        v = np.array(v, float)
        return {"mean": float(v.mean()), "std": float(v.std()),
                "min": float(v.min()), "max": float(v.max()),
                "p50": float(np.median(v)), "p90": float(np.percentile(v, 90))}

    # non-degeneracy flags (necessary, not sufficient)
    motion_nonzero = sum(1 for x in me if x > 1e-6)
    vehicle_nonzero = sum(1 for x in vc if x > 0)
    person_nonzero = sum(1 for x in pc if x > 0)
    bike_any = sum(1 for x in bc if x > 0) + sum(1 for x in mc if x > 0)
    # temporal variation: std/mean ratio (coefficient of variation), guard div0
    def cv(v):
        v = np.array(v, float)
        return float(v.std() / (v.mean() + 1e-9))
    # "active windows": motion or vehicle count above a low threshold (proxy density, NOT events)
    me_p75 = np.percentile(me, 75)
    active = sum(1 for i in range(n) if (me[i] >= me_p75 and me[i] > 0) or vc[i] > 0)

    summary = OrderedDict([
        ("video_id", video_id),
        ("path", meta["path"]),
        ("width", meta["width"]), ("height", meta["height"]),
        ("fps", meta["fps"]), ("duration_s", meta["duration"]),
        ("duration_min", meta["duration"] / 60.0),
        ("nb_frames_ffprobe", meta["nb_frames"]),
        ("bit_rate", meta["bit_rate"]),
        ("n_windows_5s", n),
        ("read_ok", read_stats["read_ok"]), ("read_fail", read_stats["read_fail"]),
        ("pass_seconds", read_stats["pass_seconds"]),
        ("motion", stat(me)),
        ("vehicle_count", stat(vc)),
        ("object_count", stat(oc)),
        ("person_count", stat(pc)),
        ("bicycle_count", stat(bc)),
        ("motorcycle_count", stat(mc)),
        ("near_ego_vehicle_count", stat(ego)),
        ("bbox_cx_std", stat(lat)),
        ("lateral_presence_count", stat(latpres)),
        ("motion_nonzero_windows", motion_nonzero),
        ("vehicle_nonzero_windows", vehicle_nonzero),
        ("person_nonzero_windows", person_nonzero),
        ("bike_nonzero_windows", bike_any),
        ("cv_motion", cv(me)),
        ("cv_vehicle", cv(vc)),
        ("cv_object", cv(oc)),
        ("active_windows_proxy", active),
        ("active_window_rate", active / n if n else 0.0),
    ])
    log(f"  SUMMARY {video_id}: windows={n} motion_mean={summary['motion']['mean']:.2f} "
        f"veh_mean={summary['vehicle_count']['mean']:.2f} person_win={person_nonzero} "
        f"bike_win={bike_any} cv_veh={summary['cv_vehicle']:.2f} "
        f"active_rate={summary['active_window_rate']:.3f}", logfh)
    return summary


def process_video(video_id, video_path, mode, outroot, logfh):
    log(f"==== PROCESS {video_id}  mode={mode}  path={video_path} ====", logfh)
    meta = ffprobe_meta(video_path)
    log(f"  meta: {meta['width']}x{meta['height']} {meta['fps']:.3f}fps "
        f"{meta['duration']:.1f}s ({meta['duration']/60:.1f}min) "
        f"nb_frames={meta['nb_frames']} br={meta['bit_rate']}", logfh)
    limit = 120.0 if mode == "smoke" else None
    eff_dur = limit if limit else meta["duration"]
    windows = build_windows(eff_dur)
    log(f"  windows: {len(windows)} (limit={limit})", logfh)

    res = run_motion_and_collect(video_path, meta, windows, limit, logfh,
                                 collect_yolo=True, collect_contact=True)
    if res is None:
        log(f"  ABORT {video_id}: pass failed", logfh)
        return None
    motion_per_window, yolo_buffer, contact_thumbs, read_stats = res

    # batched YOLO
    log(f"  YOLO: {len(yolo_buffer)} midpoint frames, batch={YOLO_BATCH}", logfh)
    import torch
    from ultralytics import YOLO
    model = YOLO(YOLO_MODEL)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    log(f"  YOLO device={device} model={YOLO_MODEL}", logfh)
    yolo_per_window = {}
    t0 = time.time()
    done = 0
    for i in range(0, len(yolo_buffer), YOLO_BATCH):
        chunk = yolo_buffer[i:i + YOLO_BATCH]
        frames = [c[1] for c in chunk]
        feats = yolo_features_for_batch(model, device, frames, logfh)
        for (win_idx, _f), feat in zip(chunk, feats):
            yolo_per_window[win_idx] = feat
        done += len(chunk)
        if done % 64 == 0 or done == len(yolo_buffer):
            el = time.time() - t0
            log(f"    YOLO {done}/{len(yolo_buffer)} {done/el:.1f}frames/s", logfh)
    log(f"  YOLO done in {time.time()-t0:.1f}s", logfh)
    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    suffix = "_smoke" if mode == "smoke" else ""
    csv_path = os.path.join(outroot, "tables", f"window_features_{video_id}{suffix}.csv")
    fieldnames = write_window_csv(windows, motion_per_window, yolo_per_window,
                                  video_id, csv_path, logfh)

    # forbidden-field invariant
    forbidden = any(k in fn.lower() for fn in fieldnames
                    for k in ("vlm", "oracle", "label", "event_start", "event_end", "ground_truth"))
    log(f"  INVARIANT no-forbidden-fields: {'PASS' if not forbidden else 'FAIL'}", logfh)

    figdir = os.path.join(outroot, "figures")
    make_timelines(windows, csv_path, video_id, figdir, logfh)
    sheet_path = os.path.join(figdir, f"contact_sheet_{video_id}{suffix}.jpg")
    build_contact_sheet(contact_thumbs, sheet_path, video_id, logfh)

    summary = summarize(windows, csv_path, meta, read_stats, video_id, logfh)
    summary["forbidden_fields_present"] = bool(forbidden)
    sj = os.path.join(outroot, "tables", f"summary_{video_id}{suffix}.json")
    with open(sj, "w") as f:
        json.dump(summary, f, indent=2)
    log(f"  summary json: {sj}", logfh)
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["smoke", "full"], default="full")
    ap.add_argument("--videos", default="both", help="d2|d3|both")
    args = ap.parse_args()

    outroot = OUTROOT
    os.makedirs(outroot, exist_ok=True)
    for sub in ("logs", "tables", "figures"):
        os.makedirs(os.path.join(outroot, sub), exist_ok=True)

    logpath = os.path.join(outroot, "logs", f"scout_{args.mode}.log")
    logfh = open(logpath, "a")
    log(f"########## SCOUT RUN mode={args.mode} videos={args.videos} ##########", logfh)
    log(f"OUTROOT={outroot}", logfh)
    log(f"YOLO_MODEL={YOLO_MODEL}", logfh)

    vids = {
        "d2": ("dataset2", "/qiuyeqing/llama_prl/G-ARC/data/realcam/long_video_data/long_video_dataset2.mp4"),
        "d3": ("dataset3", "/qiuyeqing/llama_prl/G-ARC/data/realcam/long_video_data/long_video_dataset3.mp4"),
    }
    sel = ["d2", "d3"] if args.videos == "both" else [args.videos]
    summaries = {}
    for key in sel:
        vid, path = vids[key]
        if not os.path.exists(path):
            log(f"  MISSING {path}", logfh)
            continue
        s = process_video(vid, path, args.mode, outroot, logfh)
        if s is not None:
            summaries[vid] = s

    # combined summary table
    if summaries:
        comb = os.path.join(outroot, "tables", f"summary_combined_{args.mode}.csv")
        keys = list(next(iter(summaries.values())).keys())
        with open(comb, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            for vid, s in summaries.items():
                w.writerow(s)
        log(f"  combined summary: {comb}", logfh)
        with open(os.path.join(outroot, "tables", f"summary_combined_{args.mode}.json"), "w") as f:
            json.dump(summaries, f, indent=2)
    log(f"########## SCOUT RUN DONE ##########", logfh)
    logfh.close()


if __name__ == "__main__":
    main()
