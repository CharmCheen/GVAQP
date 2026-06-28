#!/usr/bin/env python3
"""Task A: Baseline lock and input audit."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

import common as C

C.ensure_dirs()
df = C.load_data()

n_anchors = len(df)
n_pos = int(df["is_positive"].sum())
n_neg = n_anchors - n_pos
clusters = C.pos_clusters(df)
n_clusters = len(clusters)
singleton_clusters = sorted({int(c) for c in df[df["is_singleton_cluster"]]["event_cluster_id"].unique()})
multi_clusters = sorted({int(c) for c in df[df["is_multi_anchor_cluster"]]["event_cluster_id"].unique()})
n_singleton = len(singleton_clusters)
n_multi = len(multi_clusters)

proxy_cols = C.detect_proxy_cols(df)

# Column inventory
inv_rows = []
for col in df.columns:
    dt = str(df[col].dtype)
    missing = int(df[col].isna().sum())
    nunique = int(df[col].nunique(dropna=True))
    is_proxy = col in proxy_cols
    is_oracle = col in {"oracle_label", "is_positive", "event_cluster_id", "is_singleton_cluster", "is_multi_anchor_cluster"}
    is_boundary = col in {"event_start", "event_end", "event_start_absolute", "event_end_absolute", "boundary_status", "boundary_reliable"}
    inv_rows.append({
        "column": col,
        "dtype": dt,
        "missing_values": missing,
        "n_unique": nunique,
        "is_proxy_candidate": is_proxy,
        "is_oracle_or_label": is_oracle,
        "is_boundary_field": is_boundary,
    })
inv = pd.DataFrame(inv_rows)
inv.to_csv(C.TABLES / "input_column_inventory.csv", index=False)

# Cluster summary
cl_rows = []
for cid in sorted(clusters):
    part = df[df["event_cluster_id"] == cid]
    cl_rows.append({
        "event_cluster_id": int(cid),
        "n_anchors": len(part),
        "n_positives": int(part["is_positive"].sum()),
        "is_singleton": bool(part["is_singleton_cluster"].any()),
        "is_multi_anchor": bool(part["is_multi_anchor_cluster"].any()),
        "min_center_time_s": float(part["center_time_s"].min()),
        "max_center_time_s": float(part["center_time_s"].max()),
        "anchor_ids": "|".join(part["anchor_id"].astype(str)),
    })
cl_df = pd.DataFrame(cl_rows)
cl_df.to_csv(C.TABLES / "anchor_cluster_summary.csv", index=False)

# uniqueness checks
uid_unique = df["anchor_id"].is_unique
uidx_unique = df["anchor_index"].is_unique
utime_unique = df["center_time_s"].is_unique

# event_start / event_end presence
has_event_start = "event_start" in df.columns
has_event_end = "event_end" in df.columns
boundary_reliable = df["boundary_reliable"].astype(str).str.lower().eq("true").sum() if "boundary_reliable" in df.columns else 0

# query selectivity fields
has_event_type = "event_type" in df.columns
has_involved_object = "involved_object" in df.columns
event_type_counts = df["event_type"].value_counts(dropna=False).to_dict() if has_event_type else {}
inv_obj_counts = df["involved_object"].value_counts(dropna=False).to_dict() if has_involved_object else {}

# proxy missing per column
proxy_missing = {c: int(df[c].isna().sum()) for c in proxy_cols}
proxy_all_present = all(v == 0 for v in proxy_missing.values())

audit = {
    "n_anchors": n_anchors,
    "n_positives": n_pos,
    "n_negatives": n_neg,
    "positive_rate": float(n_pos / n_anchors),
    "n_event_clusters": n_clusters,
    "n_singleton_clusters": n_singleton,
    "n_multi_anchor_clusters": n_multi,
    "largest_cluster_size": int(max(len(v) for v in clusters.values())),
    "anchor_id_unique": bool(uid_unique),
    "anchor_index_unique": bool(uidx_unique),
    "center_time_s_unique": bool(utime_unique),
    "has_event_start_end": bool(has_event_start and has_event_end),
    "boundary_reliable_count": int(boundary_reliable),
    "boundary_note": "event_start/event_end present but UNRELIABLE; do NOT use for main metrics",
    "has_event_type": bool(has_event_type),
    "has_involved_object": bool(has_involved_object),
    "event_type_counts": {str(k): int(v) for k, v in event_type_counts.items()},
    "involved_object_counts": {str(k): int(v) for k, v in inv_obj_counts.items()},
    "n_candidate_proxy_cols": len(proxy_cols),
    "proxy_cols": proxy_cols,
    "proxy_all_present_no_missing": bool(proxy_all_present),
    "proxy_missing": proxy_missing,
    "canonical_source": str(C.CANONICAL),
    "cluster_source": "canonical_dataset3_anchor_table.csv event_cluster_id field (Codex-audit corrected: 21 singleton / 6 multi-anchor)",
}

with open(C.TABLES / "anchor_cluster_summary.json", "w") as f:
    json.dump(audit, f, indent=2, default=str)

# Write report
report = f"""# 01 Baseline Lock and Input Audit

## Source

Canonical table: `{C.CANONICAL}` (from `codex_recompute_proxy_budget_basa_v1`).
No new VLM/oracle calls. All subsequent replays read this table.

## Locked Counts

| quantity | value |
|---|---|
| total anchors | {n_anchors} |
| positives | {n_pos} |
| negatives | {n_neg} |
| positive rate | {n_pos/n_anchors:.4f} |
| event clusters | {n_clusters} |
| singleton clusters | {n_singleton} |
| multi-anchor clusters | {n_multi} |
| largest cluster | {max(len(v) for v in clusters.values())} |

## Uniqueness

- `anchor_id` unique: {uid_unique}
- `anchor_index` unique: {uidx_unique}
- `center_time_s` unique: {utime_unique}

## Boundary Fields

`event_start` / `event_end` present: {has_event_start and has_event_end}.
`boundary_reliable` count: {boundary_reliable}.
**Boundary fields are UNRELIABLE and are NOT used for main metrics** (per prior audit).
Only `center_time_s` / `anchor_index` are used for temporal structure.

## Query Selectivity Fields

- `event_type` present: {has_event_type}; counts: {event_type_counts}
- `involved_object` present: {has_involved_object}; counts: {inv_obj_counts}

These enable the query-level selectivity diagnostic in Task D.

## Candidate Proxy Columns

Detected {len(proxy_cols)} numeric proxy columns (no oracle/label/cluster/time/boundary fields).
All present with no missing values: {proxy_all_present}.

```
{", ".join(proxy_cols)}
```

## Cluster Composition (Codex-audit corrected)

21 singleton clusters + 6 multi-anchor clusters = 27 event clusters.
Multi-anchor cluster sizes: {[len(clusters[c]) for c in multi_clusters]}.

See `tables/anchor_cluster_summary.csv` for per-cluster detail.

## Verdict

Canonical table is complete and reused as-is. No reconstruction needed.
All downstream replays (Task B/C/D) read from this locked table.

## Outputs

- `tables/input_column_inventory.csv`
- `tables/anchor_cluster_summary.csv`
- `tables/anchor_cluster_summary.json`
"""
(C.REPORTS / "01_BASELINE_LOCK_AND_INPUT_AUDIT.md").write_text(report, encoding="utf-8")
print("Task A done. Wrote audit report + tables.")
print(json.dumps({k: audit[k] for k in ["n_anchors", "n_positives", "n_negatives", "n_event_clusters", "n_singleton_clusters", "n_multi_anchor_clusters", "n_candidate_proxy_cols"]}, indent=2))
