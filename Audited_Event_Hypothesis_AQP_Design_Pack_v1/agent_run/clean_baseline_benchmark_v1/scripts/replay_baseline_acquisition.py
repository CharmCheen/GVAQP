#!/usr/bin/env python3
"""Replay a saved acquisition trace with a selected benchmark materializer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
PACK = HERE.parent
sys.path.insert(0, str(HERE))

from benchmark_lib import evaluate_events, materialize_from_trace  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--oracle-observations", type=Path, default=PACK / "oracle/oracle_presence_observations.csv")
    parser.add_argument("--unit-table", type=Path, default=PACK / "frozen_inputs/unit_table.csv")
    parser.add_argument("--reference", type=Path, default=PACK / "frozen_inputs/event_reference.csv")
    parser.add_argument("--evaluator-config", type=Path, default=PACK / "frozen_inputs/evaluator_config.json")
    parser.add_argument("--materializer", choices=["original_k3", "k3_bridge_safe"], required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    trace = pd.read_csv(args.trace)
    observations = pd.read_csv(args.oracle_observations)
    units = pd.read_csv(args.unit_table)
    reference = pd.read_csv(args.reference)
    evaluator = json.loads(args.evaluator_config.read_text())
    required = ["benchmark_id", "run_id", "method", "method_variant", "seed", "horizon_budget", "unit_id"]
    missing = [c for c in required if c not in trace]
    if missing:
        raise ValueError(f"Trace missing required fields: {missing}")
    if trace.unit_id.duplicated().any():
        raise ValueError("Trace contains duplicate logical queries")
    if not set(trace.unit_id.astype(int)).issubset(set(observations.unit_id.astype(int))):
        raise ValueError("Frozen observations do not cover every logically requested unit")
    labels = observations.drop_duplicates("unit_id").set_index("unit_id")["parsed_label"]
    trace["oracle_label_after_query"] = trace.unit_id.astype(int).map(labels)
    if trace.oracle_label_after_query.isna().any():
        raise ValueError("A requested label could not be joined from frozen observations")

    first = trace.iloc[0]
    meta = {key: first[key] for key in ["benchmark_id", "run_id", "method", "method_variant", "seed", "horizon_budget"]}
    config = evaluator["materializers"][args.materializer]
    segments = materialize_from_trace(trace, units, meta, args.materializer, config)
    manifest = json.loads((PACK / "BENCHMARK_MANIFEST.json").read_text())
    matches, metrics = evaluate_events(segments, reference, meta, manifest["compatibility"]["evaluator_hash"])
    args.output_dir.mkdir(parents=True, exist_ok=False)
    segments.to_csv(args.output_dir / "event_segments.csv", index=False)
    matches.to_csv(args.output_dir / "event_matches.csv", index=False)
    metrics.to_csv(args.output_dir / "metrics.csv", index=False)
    (args.output_dir / "replay_manifest.json").write_text(json.dumps({
        "source_trace": str(args.trace.resolve()), "oracle_observations": str(args.oracle_observations.resolve()),
        "materializer": args.materializer, "benchmark_id": meta["benchmark_id"], "logical_calls_replayed": len(trace),
        "new_oracle_calls": 0, "new_vlm_calls": 0,
    }, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output_dir": str(args.output_dir), "segments": len(segments), "matches": len(matches), "metrics": len(metrics)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

