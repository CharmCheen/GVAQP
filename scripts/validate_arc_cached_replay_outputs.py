#!/usr/bin/env python3
"""Independently recheck persisted ARC cached-replay outputs without writing."""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
from pathlib import Path

import pandas as pd

from garc_eval.arc_cached_replay.experiment import BENCH, K3_CONFIG, REPO


CHECKED_METRICS = [
    "event_precision",
    "event_recall",
    "event_f1",
    "tiou_03",
    "tiou_05",
    "matched_mean_iou",
    "overmerge",
    "oversplit",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate(root: Path) -> None:
    required = [
        "RUN_MANIFEST.json",
        "DATA_PROVENANCE.json",
        "CONFIG.json",
        "per_run_metrics.csv",
        "selection_traces",
        "predictions",
        "event_matches",
        "macro_curve.csv",
        "macro_auc.csv",
        "paired_comparison.csv",
        "validation_checks.json",
        "command_log.txt",
        "reports/ARC_CACHED_REPLAY_REPORT.md",
    ]
    missing = [name for name in required if not (root / name).exists()]
    if missing:
        raise RuntimeError(f"missing required outputs: {missing}")

    rows = pd.read_csv(root / "per_run_metrics.csv")
    failures: list[tuple[object, ...]] = []
    for row in rows.itertuples(index=False):
        prediction_path = REPO / row.prediction_path
        match_path = REPO / row.event_match_path
        trace_path = REPO / row.selection_trace_path
        predicted = pd.read_csv(prediction_path)
        persisted_matches = pd.read_csv(match_path)
        trace = pd.read_csv(trace_path)
        reference = pd.read_csv(
            REPO
            / "BSEC_AQP_Development_Gate_v1"
            / "outputs"
            / "native_arc_vs_pstr"
            / "frozen_inputs"
            / row.domain
            / "reference_events.csv"
        )
        run_meta = {
            "benchmark_id": str(reference.benchmark_id.iloc[0]),
            "run_id": str(persisted_matches.run_id.iloc[0]),
            "method": row.method,
            "method_variant": row.method_variant,
            "seed": int(row.seed),
            "horizon_budget": int(row.budget),
        }
        _, metric_rows = BENCH.evaluate_events(
            predicted, reference, run_meta, "independent-persisted-output-recheck"
        )
        values = dict(zip(metric_rows.metric_name, metric_rows.metric_value))
        for metric in CHECKED_METRICS:
            if not math.isclose(
                float(getattr(row, metric)), float(values[metric]), rel_tol=0.0, abs_tol=1e-12
            ):
                failures.append(
                    (row.domain, row.method, row.seed, row.budget, metric, getattr(row, metric), values[metric])
                )
        if trace.unit_id.duplicated().any():
            failures.append((row.domain, row.method, row.seed, row.budget, "duplicate_query"))
        positive_ids = set(
            trace.loc[
                trace.oracle_label_after_query.astype(str).str.lower() == "positive", "unit_id"
            ].astype(int)
        )
        anchor_ids = {
            unit_id
            for raw_ids in predicted.anchor_unit_ids
            for unit_id in BENCH.read_ids(raw_ids)
        } if len(predicted) else set()
        if not anchor_ids <= positive_ids:
            failures.append((row.domain, row.method, row.seed, row.budget, "non_explicit_anchor"))

    artifact_failures: list[tuple[object, ...]] = []
    with (root / "ARTIFACT_HASHES.csv").open(newline="", encoding="utf-8") as handle:
        artifact_count = 0
        for record in csv.DictReader(handle):
            artifact_count += 1
            path = root / record["path"]
            actual_hash = sha256_file(path)
            actual_size = path.stat().st_size
            if actual_hash != record["sha256"] or actual_size != int(record["bytes"]):
                artifact_failures.append(
                    (record["path"], actual_hash, record["sha256"], actual_size, record["bytes"])
                )
    if failures or artifact_failures:
        raise RuntimeError(
            f"persisted-output failures={failures[:10]}, artifact failures={artifact_failures[:10]}"
        )
    print(f"independent_rows_recomputed={len(rows)}")
    print("metric_or_anchor_failures=0")
    print(f"artifact_rows_checked={artifact_count}")
    print("artifact_hash_failures=0")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO / "outputs" / "arc_cached_replay_v1",
    )
    args = parser.parse_args()
    validate(args.output.resolve())


if __name__ == "__main__":
    main()
