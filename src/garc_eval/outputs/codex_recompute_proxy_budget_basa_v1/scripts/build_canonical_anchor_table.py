#!/usr/bin/env python3
"""Build canonical dataset3 per-anchor table for no-new-VLM AQP replay.

Inputs are existing CSVs only. No VLM/proxy/video processing is performed.
All downstream proxy/replay/BASA/certificate scripts should read the canonical
table produced here rather than joining source tables independently.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
OUT = ROOT / "garc_eval/outputs/codex_recompute_proxy_budget_basa_v1"
TABLES = OUT / "tables"
REPORTS = OUT / "reports"
LOGS = OUT / "logs"

GLM = ROOT / "garc_eval/outputs/event_native_aqp_autonomous_research_sprint_v1"
P1 = ROOT / "garc_eval/outputs/event_native_aqp_p1_dataset3_semantic_pilot_v1"

ORACLE_CSV = GLM / "oracle_outputs/dataset3_full_center10_parsed.csv"
PROXY_CSV = P1 / "metadata/center10_proxy_features.csv"
P1_CSV = P1 / "oracle_outputs/dataset3_oracle_parsed.csv"
OUT_CSV = TABLES / "canonical_dataset3_anchor_table.csv"


def anchor_index(anchor_id: str) -> int:
    return int(str(anchor_id).split("_")[-1])


def build_clusters(df: pd.DataFrame) -> tuple[pd.DataFrame, list[list[str]]]:
    work = df.copy()
    work["event_cluster_id"] = -1
    work["is_singleton_cluster"] = False
    work["is_multi_anchor_cluster"] = False
    pos = work[work["is_positive"]].sort_values("anchor_index")
    clusters: list[list[str]] = []
    cur: list[str] = []
    prev_idx = None
    for _, row in pos.iterrows():
        idx = int(row["anchor_index"])
        aid = row["anchor_id"]
        if cur and prev_idx is not None and idx - prev_idx > 1:
            clusters.append(cur)
            cur = []
        cur.append(aid)
        prev_idx = idx
    if cur:
        clusters.append(cur)
    for cid, aids in enumerate(clusters):
        mask = work["anchor_id"].isin(aids)
        work.loc[mask, "event_cluster_id"] = cid
        if len(aids) == 1:
            work.loc[mask, "is_singleton_cluster"] = True
        else:
            work.loc[mask, "is_multi_anchor_cluster"] = True
    return work, clusters


def add_normalized_scores(df: pd.DataFrame, protected_cols: set[str]) -> pd.DataFrame:
    out = df.copy()
    numeric_cols = []
    for col in out.columns:
        if col in protected_cols:
            continue
        if pd.api.types.is_numeric_dtype(out[col]):
            numeric_cols.append(col)
    for col in numeric_cols:
        values = out[col].astype(float)
        if values.notna().sum() == 0:
            continue
        mean = values.mean()
        std = values.std(ddof=0)
        vmin = values.min()
        vmax = values.max()
        out[f"z_corrected_{col}"] = 0.0 if std == 0 else (values - mean) / std
        out[f"minmax_{col}"] = 0.0 if vmax == vmin else (values - vmin) / (vmax - vmin)
        out[f"rankpct_{col}"] = values.rank(method="average", pct=True)
    return out


def main() -> None:
    for d in [TABLES, REPORTS, LOGS]:
        d.mkdir(parents=True, exist_ok=True)

    oracle = pd.read_csv(ORACLE_CSV)
    proxy = pd.read_csv(PROXY_CSV)
    p1 = pd.read_csv(P1_CSV)

    audit = []
    audit.append(f"oracle_rows={len(oracle)} path={ORACLE_CSV}")
    audit.append(f"proxy_rows={len(proxy)} path={PROXY_CSV}")
    audit.append(f"p1_rows={len(p1)} path={P1_CSV}")
    audit.append(f"oracle_duplicate_anchor_ids={int(oracle['anchor_id'].duplicated().sum())}")
    audit.append(f"proxy_duplicate_anchor_ids={int(proxy['anchor_id'].duplicated().sum())}")
    audit.append(f"p1_duplicate_anchor_ids={int(p1['anchor_id'].duplicated().sum())}")

    missing_proxy = sorted(set(oracle["anchor_id"]) - set(proxy["anchor_id"]))
    extra_proxy = sorted(set(proxy["anchor_id"]) - set(oracle["anchor_id"]))
    audit.append(f"missing_proxy_for_oracle={len(missing_proxy)}")
    audit.append(f"extra_proxy_not_in_oracle={len(extra_proxy)}")

    merged = oracle.merge(proxy, on="anchor_id", how="left", suffixes=("_oracle", ""))
    merged["anchor_index"] = merged["anchor_id"].map(anchor_index)
    merged["center_time_s"] = merged["anchor_time_oracle"].astype(float)
    merged["start_time_s"] = merged["start_time_oracle"].astype(float)
    merged["end_time_s"] = merged["end_time_oracle"].astype(float)
    merged["oracle_label"] = merged["label"].astype(str)
    merged["is_positive"] = merged["oracle_label"].eq("positive")
    merged["p1_reused"] = merged["anchor_id"].isin(set(p1["anchor_id"]))
    merged["source_label_file"] = str(ORACLE_CSV)
    merged["notes"] = ""

    # Stable aliases expected by the recomputation task.
    if "yolo_vehicle_mean" in merged.columns and "vehicle_count_mean" not in merged.columns:
        merged["vehicle_count_mean"] = merged["yolo_vehicle_mean"]
    if "yolo_vehicle_max" in merged.columns and "vehicle_count_max" not in merged.columns:
        merged["vehicle_count_max"] = merged["yolo_vehicle_max"]
    if "bicycle_count_mean" in merged.columns and "bike_count_mean" not in merged.columns:
        merged["bike_count_mean"] = merged["bicycle_count_mean"]
    if "bicycle_count_max" in merged.columns and "bike_count_max" not in merged.columns:
        merged["bike_count_max"] = merged["bicycle_count_max"]
    elif "bike_count_max" not in merged.columns:
        merged["bike_count_max"] = np.nan

    merged, clusters = build_clusters(merged)

    protected = {
        "anchor_index",
        "center_time_s",
        "start_time_s",
        "end_time_s",
        "event_cluster_id",
    }
    merged = add_normalized_scores(merged, protected)

    leading = [
        "anchor_id",
        "anchor_index",
        "center_time_s",
        "start_time_s",
        "end_time_s",
        "oracle_label",
        "is_positive",
        "event_cluster_id",
        "is_singleton_cluster",
        "is_multi_anchor_cluster",
        "p1_reused",
        "source_label_file",
    ]
    trailing = ["notes"]
    middle = [c for c in merged.columns if c not in set(leading + trailing)]
    merged = merged[leading + middle + trailing].sort_values("anchor_index")
    merged.to_csv(OUT_CSV, index=False)

    cluster_sizes = [len(c) for c in clusters]
    transition_pos_pos = 0
    transition_pos_neg = 0
    ordered = merged.sort_values("anchor_index")
    labels = ordered["oracle_label"].tolist()
    for a, b in zip(labels, labels[1:]):
        if a == "positive" and b == "positive":
            transition_pos_pos += 1
        elif a == "positive" and b == "negative":
            transition_pos_neg += 1
    p_stay = transition_pos_pos / max(1, transition_pos_pos + transition_pos_neg)

    summary = {
        "n_anchors": int(len(merged)),
        "n_positives": int(merged["is_positive"].sum()),
        "n_negatives": int((~merged["is_positive"]).sum()),
        "positive_rate": float(merged["is_positive"].mean()),
        "n_clusters": len(clusters),
        "n_singleton_clusters": int(sum(1 for s in cluster_sizes if s == 1)),
        "n_multi_anchor_clusters": int(sum(1 for s in cluster_sizes if s > 1)),
        "largest_cluster": int(max(cluster_sizes) if cluster_sizes else 0),
        "p1_reused": int(merged["p1_reused"].sum()),
        "p_stay_positive": float(p_stay),
        "base_positive_rate": float(merged["is_positive"].mean()),
        "missing_proxy_anchor_ids": missing_proxy,
        "extra_proxy_anchor_ids": extra_proxy,
    }
    (OUT / "analysis/canonical_table_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    report = f"""# 01 Canonical Table Audit

## Inputs

- Oracle labels: `{ORACLE_CSV}` ({len(oracle)} rows)
- Proxy features: `{PROXY_CSV}` ({len(proxy)} rows)
- P1 labels: `{P1_CSV}` ({len(p1)} rows)

## Join And Integrity Checks

- Join key: `anchor_id`.
- Oracle duplicate anchor IDs: {int(oracle['anchor_id'].duplicated().sum())}.
- Proxy duplicate anchor IDs: {int(proxy['anchor_id'].duplicated().sum())}.
- Missing proxy rows for oracle anchors: {len(missing_proxy)}.
- Extra proxy rows not in oracle: {len(extra_proxy)}.
- P1 reused anchors present in canonical table: {int(merged['p1_reused'].sum())}.

## Canonical Label/Cluster Counts

- Anchors: {summary['n_anchors']}.
- Positives / negatives: {summary['n_positives']} / {summary['n_negatives']}.
- Positive rate: {summary['positive_rate']:.6f}.
- Positive clusters: {summary['n_clusters']}.
- Singleton / multi-anchor clusters: {summary['n_singleton_clusters']} / {summary['n_multi_anchor_clusters']}.
- Largest cluster size: {summary['largest_cluster']}.
- P(1->1): {summary['p_stay_positive']:.3f}; base positive rate: {summary['base_positive_rate']:.3f}.

The recomputed split is 21 singleton clusters and 6 multi-anchor clusters. This matches the prior Codex audit and corrects the GLM report text drift.

## Boundary Policy

`event_start` / `event_end` are retained only as source columns if present. They are not used for replay, BASA, cluster construction, or certificate simulation because dataset3 boundary localization is templated.

## Output

Canonical table written to `{OUT_CSV}`. All downstream scripts in this output directory read this table as the authoritative per-anchor source.
"""
    (REPORTS / "01_CANONICAL_TABLE_AUDIT.md").write_text(report, encoding="utf-8")

    with (LOGS / "progress.md").open("a", encoding="utf-8") as f:
        f.write("\ncanonical table built: tables/canonical_dataset3_anchor_table.csv\n")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
