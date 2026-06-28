#!/usr/bin/env python3
"""Stage 10 / Task 1: Vehicle query geometric proxy check on dataset3.

Vehicle-involved positives n=4 on dataset3. EXTREMELY SMALL N.
Results are directional signals only, NOT statistical significance.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import common as C

C.ensure_dirs()
df = C.load_dataset3()

# Build vehicle subquery: positive iff involved_object == vehicle AND is_positive
inv = df["involved_object"].astype(str)
y_vehicle = ((inv == "vehicle") & df["is_positive"]).astype(int)
n_pos = int(y_vehicle.sum())
n_neg = len(y_vehicle) - n_pos

features = {
    "score_fusion_geometry_motion": df["score_fusion_geometry_motion"].astype(float).to_numpy(),
    "lateral_presence_max": df["lateral_presence_max"].astype(float).to_numpy() if "lateral_presence_max" in df.columns else None,
    "vehicle_count_mean": df["vehicle_count_mean"].astype(float).to_numpy() if "vehicle_count_mean" in df.columns else None,
    "object_count_mean": df["object_count_mean"].astype(float).to_numpy(),
    "motion_energy_mean": df["motion_energy_mean"].astype(float).to_numpy(),
    "person_count_max": df["person_count_max"].astype(float).to_numpy() if "person_count_max" in df.columns else None,
}

rows = []
for name, s in features.items():
    if s is None:
        rows.append({"feature": name, "auroc": float("nan"), "n_pos": n_pos, "n_neg": n_neg, "note": "feature not available"})
        continue
    auc = C.tie_aware_auroc(s, y_vehicle.astype(float))
    ap = C.average_precision(s, y_vehicle.astype(float))
    # top-4 yield (since n_pos=4)
    order = np.argsort(-s, kind="mergesort")[:4]
    top4_pos = int(y_vehicle[order].sum())
    rows.append({"feature": name, "auroc": auc, "auprc": ap, "n_pos": n_pos, "n_neg": n_neg, "top4_yield": top4_pos, "note": ""})

res = pd.DataFrame(rows).sort_values("auroc", ascending=False)
res.to_csv(C.TABLES / "stage10_vehicle_query_auroc.csv", index=False)

# Directional check: geometric features vs vehicle_count_mean
geom = res[res["feature"].isin(["score_fusion_geometry_motion", "lateral_presence_max"])]
vc = res[res["feature"] == "vehicle_count_mean"]
geom_best = float(geom["auroc"].max())
vc_auc = float(vc["auroc"].iloc[0]) if len(vc) else float("nan")

if geom_best > vc_auc + 0.05:
    decision = "GEOMETRIC_PROXY_PROMISING_LOW_N"
else:
    decision = "GEOMETRIC_PROXY_NOT_SUPPORTED_LOW_N"

report = f"""# Stage 10: Vehicle Query Geometric Proxy Check

## Setup

Sub-query: `involved_object == 'vehicle' AND is_positive` on dataset3.
This isolates the 4 vehicle-involved positives from the 40 total positives.

**Sample size: n_pos={n_pos}, n_neg={n_neg}. EXTREMELY SMALL N.**
All results below are **directional signals only**. No statistical significance
can be claimed. These numbers must NOT be used to conclude "P1 geometric hypothesis
is valid/invalid" — only as a direction indicator for Task 2 cross-video check.

## AUROC on vehicle sub-query

{C.md_table(res)}

## Directional assessment

- Best geometric feature AUROC: {geom_best:.4f}
- `vehicle_count_mean` AUROC: {vc_auc:.4f} (baseline comparator)
- Geometric advantage: {geom_best - vc_auc:+.4f}

Threshold for "promising": geometric AUROC > vehicle_count_mean AUROC + 0.05.

## DECISION

`{decision}`

## Guardrail notice

- n=4 positives. A single flip changes AUROC by ~0.25. These numbers are noise-sensitive.
- Do NOT write "geometric proxy works for vehicles" in the paper based on this alone.
- This result only justifies (or not) running the cross-video check in Stage 11.
- If Stage 11 (realcartest, 67 vehicle positives) shows the same direction,
  the combined signal is stronger but still not a formal proof.

## Outputs

- `tables/stage10_vehicle_query_auroc.csv`
"""
(C.REPORTS / "STAGE10_VEHICLE_QUERY_GEOMETRIC_PROXY_CHECK.md").write_text(report, encoding="utf-8")
print(f"Stage 10 done. n_pos={n_pos} decision={decision}")
print(res[["feature", "auroc", "top4_yield"]].to_string(index=False))
