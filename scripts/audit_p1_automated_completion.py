#!/usr/bin/env python3
"""Materialize an explicitly model-relative, human-free P1 completion audit.

This is deliberately separate from the frozen P1 human-endpoint implementation.
It is a post-completion descriptive audit of the two complete Qwen outcome tables,
the already frozen outcome-blind traces, and the two frozen natural proxy families.
It cannot issue P1 PASS/FAIL or make a human-recovery claim.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/gvaqp_long_horizon_p1_p3_v1"
TRACE = OUT / "P1_OUTCOME_BLIND_TRACE_MANIFEST.csv"
QWEN_DIR = OUT / "qwen32_oracle"
QWEN = QWEN_DIR / "P1_QWEN32_UNIT_OUTCOMES.parquet"
QWEN_COMPLETE = QWEN_DIR / "P1_QWEN32_ORACLE_COMPLETION.json"
V10 = ROOT / "outputs/v10_multiseal_reference_v1/FINAL_UNIT_REFERENCE.parquet"
PROXY_PROTOCOL = OUT / "P1_PROXY_CHARACTERIZATION_PROTOCOL.json"
PROXY_REPORT = OUT / "P1_PROXY_CHARACTERIZATION_REPORT.md"
PROXY_METRICS = OUT / "P1_PROXY_CHARACTERIZATION.csv"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def c1_events(frame: pd.DataFrame) -> list[tuple[float, float]]:
    """Frozen C1 ten-second-gap event construction, used only descriptively."""
    # Cluster frames retain unit_id as a lookup index as well as a column.
    # Resetting here prevents Pandas treating the sort key as ambiguous.
    positive = frame[frame.label == "relevant"].reset_index(drop=True).sort_values(["start_time", "end_time", "unit_id"])
    groups: list[list[tuple[float, float]]] = []
    for row in positive.itertuples():
        item = (float(row.start_time), float(row.end_time))
        if not groups or item[0] - groups[-1][-1][1] > 10.0:
            groups.append([item])
        else:
            groups[-1].append(item)
    return [(min(x[0] for x in group), max(x[1] for x in group)) for group in groups]


def overlaps(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return max(a[0], b[0]) < min(a[1], b[1])


def labels() -> dict[tuple[str, str], pd.DataFrame]:
    old = pd.read_parquet(V10)[["video_id", "unit_id", "start_time", "end_time", "authoritative_label"]]
    old = old.rename(columns={"authoritative_label": "label"})
    new = pd.read_parquet(QWEN)[["video_id", "unit_id", "start_time", "end_time", "label"]]
    result: dict[tuple[str, str], pd.DataFrame] = {}
    for query, frame in (("Q_DRIVER_RESPONSE_V1", old), ("Q_VULNERABLE_ROAD_USER_CONFLICT_V1", new)):
        for video, group in frame.groupby("video_id", sort=True):
            result[(str(video), query)] = group.copy().set_index("unit_id", drop=False)
    expected = {(v, q) for v in ("DALI", "HANGZHOU", "WUHAN") for q in ("Q_DRIVER_RESPONSE_V1", "Q_VULNERABLE_ROAD_USER_CONFLICT_V1")}
    if set(result) != expected:
        raise RuntimeError("semantic source tables do not cover all six video-query clusters")
    return result


def main() -> None:
    complete = json.loads(QWEN_COMPLETE.read_text())
    if complete.get("status") != "COMPLETE" or complete.get("units") != 1475 or complete.get("table_sha256") != sha(QWEN):
        raise RuntimeError("Qwen completion release is not authentic and complete")
    trace = pd.read_csv(TRACE)
    if len(trace) != 504 or trace.protocol_hash.nunique() != 1:
        raise RuntimeError("frozen trace population is invalid")
    if not PROXY_REPORT.exists() or len(pd.read_csv(PROXY_METRICS)) != 90:
        raise RuntimeError("two-natural-proxy characterization is incomplete")

    by_cluster = labels()
    rows = []
    for item in trace.itertuples():
        selected_ids = json.loads(item.selected_unit_ids_json)
        for query in ("Q_DRIVER_RESPONSE_V1", "Q_VULNERABLE_ROAD_USER_CONFLICT_V1"):
            full = by_cluster[(item.video_id, query)]
            if any(unit_id not in full.index for unit_id in selected_ids):
                raise RuntimeError("trace selected an unknown semantic unit")
            selected = full.loc[selected_ids]
            full_positive = int((full.label == "relevant").sum())
            selected_positive = int((selected.label == "relevant").sum())
            full_events = c1_events(full)
            selected_positive_intervals = [
                (float(row.start_time), float(row.end_time))
                for row in selected[selected.label == "relevant"].itertuples()
            ]
            touched = sum(any(overlaps(event, interval) for interval in selected_positive_intervals) for event in full_events)
            rows.append({
                **item._asdict(),
                "query_id": query,
                "full_relevant_unit_count": full_positive,
                "selected_relevant_unit_count": selected_positive,
                "selected_positive_yield": selected_positive / len(selected_ids),
                "model_relative_relevant_unit_coverage": selected_positive / full_positive if full_positive else 1.0,
                "full_C1_event_count": len(full_events),
                "selected_positive_touches_full_C1_event_count": touched,
                "model_relative_full_C1_event_coverage": touched / len(full_events) if full_events else 1.0,
            })
    endpoints = pd.DataFrame(rows)
    endpoint_path = OUT / "P1_AUTOMATED_MODEL_RELATIVE_TRACE_ENDPOINTS.csv"
    endpoints.to_csv(endpoint_path, index=False)

    matched_rows = []
    group_cols = ["video_id", "query_id", "proxy_family", "budget", "selected_relevant_unit_count"]
    for key, group in endpoints.groupby(group_cols, sort=True):
        if len(group) < 2 or group.number_of_temporal_regions_touched.nunique() < 2:
            continue
        high = group.sort_values(["number_of_temporal_regions_touched", "trace_hash"], ascending=[False, True]).iloc[0]
        low = group.sort_values(["number_of_temporal_regions_touched", "trace_hash"], ascending=[True, True]).iloc[0]
        matched_rows.append({
            **dict(zip(group_cols, key)),
            "traces_in_stratum": len(group),
            "geometry_high": int(high.number_of_temporal_regions_touched),
            "geometry_low": int(low.number_of_temporal_regions_touched),
            "trace_high": high.trace_hash,
            "trace_low": low.trace_hash,
            "delta_model_relative_relevant_unit_coverage": float(high.model_relative_relevant_unit_coverage - low.model_relative_relevant_unit_coverage),
            "delta_model_relative_full_C1_event_coverage": float(high.model_relative_full_C1_event_coverage - low.model_relative_full_C1_event_coverage),
        })
    matched = pd.DataFrame(matched_rows)
    matched_path = OUT / "P1_AUTOMATED_MODEL_RELATIVE_EQUAL_YIELD_MATCHED.csv"
    matched.to_csv(matched_path, index=False)
    cluster = (matched.groupby(["video_id", "query_id", "proxy_family"], sort=True)
               .agg(matched_strata=("budget", "size"),
                    median_delta_relevant_unit_coverage=("delta_model_relative_relevant_unit_coverage", "median"),
                    median_delta_full_C1_event_coverage=("delta_model_relative_full_C1_event_coverage", "median"))
               .reset_index()) if len(matched) else pd.DataFrame()
    cluster_path = OUT / "P1_AUTOMATED_MODEL_RELATIVE_CLUSTER_SUMMARY.csv"
    cluster.to_csv(cluster_path, index=False)

    audit = {
        "status": "COMPLETE_AUTOMATED_ONLY_MODEL_RELATIVE_AUDIT",
        "scope": "post-completion descriptive audit; not a frozen P1 primary analysis and not a P1 PASS/FAIL result",
        "prohibited_claims": [
            "human semantic correctness",
            "independent event recovery",
            "P1 PASS or P1 FAIL",
            "geometry-aware policy benefit",
        ],
        "automated_inputs_verified": {
            "qwen_completion": complete,
            "trace_rows": len(trace),
            "trace_protocol_hash": str(trace.protocol_hash.iloc[0]),
            "proxy_metric_rows": len(pd.read_csv(PROXY_METRICS)),
        },
        "derived_outputs": {
            endpoint_path.name: {"rows": len(endpoints), "sha256": sha(endpoint_path)},
            matched_path.name: {"rows": len(matched), "sha256": sha(matched_path)},
            cluster_path.name: {"rows": len(cluster), "sha256": sha(cluster_path)},
        },
        "input_hashes": {
            "trace": sha(TRACE), "qwen_table": sha(QWEN), "original_query": sha(V10),
            "proxy_protocol": sha(PROXY_PROTOCOL), "proxy_report": sha(PROXY_REPORT),
        },
        "code_sha256": sha(Path(__file__)),
    }
    audit_path = OUT / "P1_AUTOMATED_ONLY_COMPLETION_AUDIT.json"
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    report = """# P1 automated-only completion audit

## Status

`COMPLETE_AUTOMATED_ONLY_MODEL_RELATIVE_AUDIT`

All non-human automatic work is complete: the 1,475-unit Qwen3-VL-32B grid
passed integrity verification, the two frozen natural-proxy characterizations
completed, and this audit materialized outcome-blind-trace diagnostics over
both complete semantic queries and both proxy families.

## What the derived endpoints mean

- `model_relative_relevant_unit_coverage`: fraction of all Qwen/released-model
  relevant units acquired by a trace.
- `model_relative_full_C1_event_coverage`: fraction of C1 events constructed
  from the *complete same-model semantic table* touched by the trace's
  verified-positive units.

They are automated, model-relative coverage diagnostics only. They are not
human labels, an independent reference, a P1 primary endpoint, a P1 PASS/FAIL
decision, or evidence for a geometry-aware policy.

## Files

- `P1_AUTOMATED_MODEL_RELATIVE_TRACE_ENDPOINTS.csv`: all 1,008 trace-query rows.
- `P1_AUTOMATED_MODEL_RELATIVE_EQUAL_YIELD_MATCHED.csv`: deterministic
  equal-selected-positive, high-versus-low geometry contrasts.
- `P1_AUTOMATED_MODEL_RELATIVE_CLUSTER_SUMMARY.csv`: within video-query-proxy
  medians; strata are not treated as independent samples.

The accompanying JSON contains exact input/output/code hashes.
"""
    (OUT / "P1_AUTOMATED_ONLY_COMPLETION_AUDIT.md").write_text(report)
    print(json.dumps({"status": audit["status"], "trace_query_rows": len(endpoints), "matched_rows": len(matched), "cluster_rows": len(cluster)}, sort_keys=True))


if __name__ == "__main__":
    main()
