#!/usr/bin/env python3
"""Complete Phase-1 determinism/observability evidence for every P0 config.

This is verification only: it does not select a different operator and does not
read labels, references, candidate maps, or full-SCAN outputs.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from run_mrpo_preview_p0 import (
    CONFIGS, IMM, OUT, canonical_feature_hash, dump_json, extract,
)


def main() -> None:
    videos = pd.read_csv(IMM / "videos.csv")
    manifest_path = OUT / "preview/operator_manifests/P0_SELECTION.json"
    cost_path = OUT / "audits/preview_cost_audit.json"
    manifest = json.loads(manifest_path.read_text())
    cost_audit = json.loads(cost_path.read_text())
    determinism = {}
    observability = {}
    decompositions = {}

    for config in CONFIGS:
        operator_id = config["operator_id"]
        first = pd.read_parquet(OUT / f"preview/region_features/{operator_id}.parquet")
        repeat_tables = []
        for video in videos.itertuples(index=False):
            runtime_path = OUT / f"preview/runtime_samples/{operator_id}__{video.video_id}__run2.json"
            if runtime_path.exists() and operator_id == manifest["selected_operator_id"]:
                # Selected repeat features were hash-checked during extraction;
                # retain its frozen hashes rather than perform a third decode.
                continue
            table, runtime = extract(pd.Series(video._asdict()), config, 2)
            repeat_tables.append(table)
            dump_json(runtime_path, runtime)
        if repeat_tables:
            repeat = pd.concat(repeat_tables, ignore_index=True)
            first_hash = canonical_feature_hash(first)
            repeat_hash = canonical_feature_hash(repeat)
        else:
            first_hash = manifest["chosen_run1_hash"]
            repeat_hash = manifest["chosen_run2_hash"]
        determinism[operator_id] = {
            "run1_feature_hash": first_hash,
            "run2_feature_hash": repeat_hash,
            "hash_match": first_hash == repeat_hash,
            "videos_repeated": list(videos.video_id.astype(str)),
        }
        feature_columns = [
            column for column in first.columns
            if column not in {
                "operator_id", "video_id", "region_id", "region_index",
                "start_sec", "end_sec", "actual_duration_sec",
            }
        ]
        observability[operator_id] = {
            "region_count": len(first),
            "zero_sample_region_count": int(first.preview_sample_count.eq(0).sum()),
            "missing_feature_cell_count": int(first[feature_columns].isna().sum().sum()),
            "mean_support_fraction": float(first.preview_support_fraction.mean()),
            "minimum_support_fraction": float(first.preview_support_fraction.min()),
            "feature_column_count": len(feature_columns),
        }
        run1 = [
            json.loads((OUT / f"preview/runtime_samples/{operator_id}__{video_id}__run1.json").read_text())
            for video_id in videos.video_id.astype(str)
        ]
        run2 = [
            json.loads((OUT / f"preview/runtime_samples/{operator_id}__{video_id}__run2.json").read_text())
            for video_id in videos.video_id.astype(str)
        ]
        decompositions[operator_id] = {
            "run1_decode_and_pipe_wait_sec": sum(row["decode_and_pipe_wait_sec"] for row in run1),
            "run1_model_inference_sec": sum(row["model_inference_sec"] for row in run1),
            "run1_feature_compute_sec": sum(row["feature_compute_sec"] for row in run1),
            "run1_total_wallclock_sec": sum(row["wallclock_sec"] for row in run1),
            "run1_seconds_per_video_hour": sum(row["wallclock_sec"] for row in run1) / sum(row["video_duration_sec"] for row in run1) * 3600.0,
            "run1_peak_memory_kib_process_lifetime": max(row["max_rss_kib_process_lifetime"] for row in run1),
            "run2_total_wallclock_sec": sum(row["wallclock_sec"] for row in run2),
            "cost_measurement_scope": "FULL_TWO_VIDEO_OPERATOR_RUN",
        }

    if not all(row["hash_match"] for row in determinism.values()):
        raise RuntimeError("At least one preview config failed deterministic feature-hash replay")
    manifest["per_operator_determinism"] = determinism
    manifest["per_operator_observability"] = observability
    manifest["all_candidate_operator_determinism_pass"] = True
    manifest["all_candidate_operator_missingness_pass"] = all(
        row["missing_feature_cell_count"] == 0 for row in observability.values()
    )
    cost_audit["per_operator_cost_decomposition"] = decompositions
    cost_audit["all_candidate_operator_determinism_pass"] = True
    cost_audit["all_candidate_operator_observability_complete"] = True
    dump_json(manifest_path, manifest)
    dump_json(cost_path, cost_audit)
    print(json.dumps({
        "status": "PASS", "determinism": determinism,
        "observability": observability, "cost_decomposition": decompositions,
    }, indent=2))


if __name__ == "__main__":
    main()
