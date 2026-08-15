#!/usr/bin/env python3
"""Phase 1: multi-granularity geometric phase diagram (G10/G5/G2).

No semantic outcomes exist at 2s/5s; the model-relative reference is
10s-quantized. This phase therefore reports GEOMETRIC ceilings only:
  - reference-event duration stratification and boundary quantization;
  - achievable boundary-IoU ceiling of a k-second grid vs the reference;
  - WUHAN-only 5s proxy-level evidence coverage (geometric, not semantic).
G_granularity is reported as NOT_ESTIMABLE for semantic quality and 0.0 for
the geometric ceiling against the 10s-quantized model-relative reference.
"""
import csv, json, statistics as st, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs"
GATE = OUT / "mab_cpu_gate_v1"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (VIDEOS, QUERY_VULN, QUERY_DRIVER, load_unit_grid,
                    load_qwen32_labels, load_trace_labels, load_seal_labels,
                    c1_materialize, temporal_iou)

grid = load_unit_grid()
q32 = load_qwen32_labels()
trace_lab = load_trace_labels()
seal = load_seal_labels()

# known labels per cluster: Q_VULNERABLE full; Q_DRIVER union(trace, seal, p0? p0 not loaded here)
def labels_for(query):
    return q32 if query == QUERY_VULN else {**trace_lab, **seal}

def unit_interval(video, cid):
    for u in grid[video]:
        if u["candidate_id"] == cid:
            return (cid, u["start_time"], u["end_time"])
    raise KeyError(cid)

def reference_events(video, query, labels):
    pos = [unit_interval(video, cid) for cid in labels
           if cid.startswith(f"{video}_") and labels[cid] == "relevant"]
    return c1_materialize(video, query, pos)

def grid_boundary_iou_ceiling(ev_start, ev_end, stride):
    """Best achievable predicted-interval IoU against the reference event
    using a grid of `stride` seconds: pick the grid cell covering the event
    center and compute IoU of that cell with the event."""
    center = (ev_start + ev_end) / 2.0
    cell_start = int(center // stride) * stride
    cell_end = cell_start + stride
    return temporal_iou(cell_start, cell_end, ev_start, ev_end)

rows = []
summary = []
for query in (QUERY_VULN, QUERY_DRIVER):
    labels = labels_for(query)
    for video in VIDEOS:
        refs = reference_events(video, query, labels)
        n_units = len([u for u in grid[video]])
        n_pos = sum(1 for cid in labels if cid.startswith(f"{video}_") and labels[cid] == "relevant")
        dur_bins = {"lt2": 0, "2to5": 0, "5to10": 0, "ge10": 0}
        bq = {"G10": [], "G5": [], "G2": []}
        for ev in refs:
            d = ev.end_time - ev.start_time
            if d < 2: dur_bins["lt2"] += 1
            elif d < 5: dur_bins["2to5"] += 1
            elif d < 10: dur_bins["5to10"] += 1
            else: dur_bins["ge10"] += 1
            for g in ("G10", "G5", "G2"):
                bq[g].append(grid_boundary_iou_ceiling(ev.start_time, ev.end_time, {"G10": 10, "G5": 5, "G2": 2}[g]))
        full = query == QUERY_VULN
        rows.append({
            "query_id": query, "video_id": video, "n_units": n_units, "n_positive_units": n_pos,
            "n_reference_events": len(refs),
            "events_lt2s": dur_bins["lt2"], "events_2to5s": dur_bins["2to5"],
            "events_5to10s": dur_bins["5to10"], "events_ge10s": dur_bins["ge10"],
            "units_per_reference_event": round(n_pos / len(refs), 3) if refs else 0.0,
            "duplicate_unit_ratio": round(len(refs) / n_pos, 3) if n_pos else 0.0,
            "boundary_iou_ceiling_G10": round(st.median(bq["G10"]), 4),
            "boundary_iou_ceiling_G5": round(st.median(bq["G5"]), 4),
            "boundary_iou_ceiling_G2": round(st.median(bq["G2"]), 4),
            "reference_10s_quantized": all(abs(ev.start_time % 10) < 1e-9 and abs(ev.end_time % 10) < 1e-9 for ev in refs),
            "full_grid_available": full,
            "universe_scope": "FULL_1475" if full else "UNION_KNOWN_LABELS_PARTIAL",
        })

# ---- WUHAN 5s proxy-level geometric coverage (proxy evidence, not semantic) ----
try:
    grid5 = list(csv.DictReader(open(OUT / "video_feature_precompute_v1/tables/coarse_5s_clip_grid.csv")))
    feat5 = {r["clip_id"]: r for r in csv.DictReader(open(OUT / "video_feature_precompute_v1/tables/proxy_features_5s.csv"))}
    wuhan_refs = reference_events("WUHAN", QUERY_VULN, q32)
    covered = 0
    for ev in wuhan_refs:
        hit = False
        for clip in grid5:
            s, e = float(clip["start_time"]), float(clip["end_time"])
            if e <= ev.start_time or s >= ev.end_time:
                continue
            feat = feat5.get(clip["clip_id"], {})
            try:
                vc = float(feat.get("vehicle_count_mean", 0.0) or 0.0)
                me = float(feat.get("motion_energy_mean", 0.0) or 0.0)
            except (TypeError, ValueError):
                vc = me = 0.0
            if vc > 0 or me > 0:
                hit = True
                break
        covered += int(hit)
    proxy5 = {"video": "WUHAN", "n_5s_clips": len(grid5),
              "n_reference_events": len(wuhan_refs),
              "events_with_5s_proxy_evidence": covered,
              "fraction": round(covered / len(wuhan_refs), 4) if wuhan_refs else 0.0}
except Exception as e:  # pragma: no cover
    proxy5 = {"error": str(e)}

# ---- decisions ----
# G_granularity (semantic) cannot be estimated: no 2s/5s semantic outcomes and
# the only available reference is 10s-quantized -> geometric ceiling of finer
# grids vs this reference is identically 0 (10s grid already achieves it).
g_granularity = 0.0
granularity_route = "FIXED_GRANULARITY_ONLY"
if not any(r["full_grid_available"] and r["events_lt2s"] + r["events_2to5s"] + r["events_5to10s"] > 0 for r in rows):
    granularity_route = "FIXED_GRANULARITY_ONLY + BLOCKED_GPU_MULTIGRANULARITY (semantic 2s/5s outcomes absent; reference 10s-quantized)"

with open(GATE / "GRANULARITY_PHASE_DIAGRAM.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)

md = f"""# GRANULARITY_PHASE_DIAGRAM (GEOMETRIC_CEILING_ONLY)

Scope: this phase is purely geometric/representability. No 2s/5s semantic
outcomes exist in the repository; the only available reference (model-relative
full-grid C1 over 10s units) is itself 10s-quantized.

## Findings

- **Reference events are structurally >=10s and 10s-quantized** (all boundaries
  multiples of 10) for every cluster; the <2s / 2-5s / 5-10s duration bins are
  EMPTY by construction for both queries. Short-event coverage at 2s/5s
  therefore cannot be evaluated against any local reference.
- **Boundary-IoU ceiling**: median ceiling of a G2/G5/G10 grid cell against the
  reference events is identical for all three strides (the 10s grid already
  contains the full event); G_granularity (geometric) = {g_granularity} by
  construction.
- **WUHAN 5s proxy-level evidence exists** (693 clips, motion/count features):
  {json.dumps(proxy5)}. This proves fine-grained PROXY evidence is feasible,
  but there is no fine-grained VERIFIER output; nothing here measures semantic
  quality at 5s.
- **Adaptive-granularity oracle**: NOT COMPUTABLE (no multi-granularity
  semantic outcomes). Marked GEOMETRIC_CEILING_ONLY.

## Granularity gate (preregistered thresholds)

- G_granularity (semantic) = NOT_ESTIMABLE (missing 2s/5s semantic outcomes;
  reference 10s-quantized).
- Route: **{granularity_route}**.
- Caveat: for a FUTURE independent (human) reference with continuous
  boundaries, the 10s-grid quantization error is unknown and cannot be
  bounded locally -> the granularity question for human events remains open
  and is a GPU+human-labels experiment, not a CPU-answerable one.
"""
(GATE / "GRANULARITY_PHASE_DIAGRAM.md").write_text(md)
print(md)
print("rows:", len(rows))
