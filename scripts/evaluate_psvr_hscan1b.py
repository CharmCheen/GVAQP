#!/usr/bin/env python3
"""Evaluator-only metrics and preregistered decisions for H-SCAN1B."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd


REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "outputs/psvr_autonomous_research/cycle_05_H_SCAN1B"
STAGE2 = REPO / "scripts/run_psvr_core_pilot.py"


def dump(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def runtime():
    spec = importlib.util.spec_from_file_location("psvr_hscan1b_eval_runtime", STAGE2)
    m = importlib.util.module_from_spec(spec); sys.modules[spec.name] = m; spec.loader.exec_module(m); return m


def evaluate(phase: str) -> None:
    methods = ("TB0", "TB1", "TB2") if phase == "tie" else ("F00", "F10", "F01", "F11")
    raw = OUT / ("raw_tie" if phase == "tie" else "raw_factorial")
    expected = 9 if phase == "tie" else 24
    runs = [json.loads(p.read_text()) for p in sorted(raw.glob("*/attempt_*/complete.json"))]
    if len(runs) != expected: raise RuntimeError(f"expected {expected} complete runs, found {len(runs)}")
    m = runtime(); benchmark = m.benchmark_module()
    reference = pd.read_csv(m.REFERENCE_PATH); units = pd.read_csv(m.UNITS_PATH)
    evaluator_hash = m.sha256_file(m.MATERIALIZER); rows = []
    for run in runs:
        summary, _ = m.evaluate_run(run, benchmark, reference, units, evaluator_hash)
        summary["scan_prefix"] = repr(tuple(u for a in run["actions"] if a["action"] == "scan" for u in a["unit_ids"]))
        rows.append(summary)
    frame = pd.DataFrame(rows); frame.to_csv(OUT / f"{phase.upper()}_RUN_METRICS.csv", index=False)
    aggregate = frame.groupby(["method", "deadline_name"], as_index=False).agg(
        runs=("run_id", "count"), auc_mean=("AnytimeAUC_F1", "mean"), auc_min=("AnytimeAUC_F1", "min"),
        f1_min=("F1_at_deadline", "min"), f1_median=("F1_at_deadline", "median"),
        unique_events_max=("unique_confirmed_events", "max"), ttfc_median=("time_to_first_confirmed_event", "median"),
        deadline_misses=("deadline_met", lambda x: int((~x).sum())), scan_prefixes=("scan_prefix", "nunique"))
    aggregate.to_csv(OUT / f"{phase.upper()}_AGGREGATE.csv", index=False)
    effective = {method: all((g.F1_at_deadline > 0) & (g.AnytimeAUC_F1 > 0)) and len(g) == (3 if phase == "tie" else 6)
                 for method in methods for g in [frame[frame.method == method]]}
    validity = {"complete": len(runs), "expected": expected,
                "deadline_misses": int((~frame.deadline_met).sum()),
                "cache_replays": sum(r["cache_replay_calls"] for r in runs),
                "future_proxy_accesses": sum(r["future_proxy_accesses"] for r in runs),
                "visibility_violations": sum(r["candidate_observation_violations"] for r in runs)}
    if phase == "tie":
        if not effective["TB0"]: decision = "ANOMALOUS"
        elif effective["TB1"] and effective["TB2"]: decision = "STRONG"
        elif effective["TB1"] or effective["TB2"]: decision = "WEAK"
        else: decision = "FAIL"
        payload = {"hypothesis_id": "H-SCAN1B_STAGE5A", "decision": decision,
                   "effectiveness": effective, "validity": validity,
                   "factorial_authorized": decision in ("STRONG", "WEAK"),
                   "semantic_samples": 1, "repeats_are_execution_stability_only": True,
                   "aggregate": json.loads(aggregate.to_json(orient="records"))}
        dump(OUT / "TIE_GATE_DECISION.json", payload)
    else:
        if effective["F00"]: branch = "ZERO"
        elif effective["F10"] and effective["F01"] and effective["F11"]: branch = "SIMPLE"
        elif effective["F10"] and effective["F11"] and not effective["F01"]: branch = "U"
        elif effective["F01"] and effective["F11"] and not effective["F10"]: branch = "L"
        elif effective["F11"] and not effective["F10"] and not effective["F01"]: branch = "UL"
        else: branch = "NONE"
        seq_equal = all(frame[frame.method == "F10"].sort_values(["deadline_name", "replicate"]).scan_prefix.reset_index(drop=True) ==
                        frame[frame.method == "F01"].sort_values(["deadline_name", "replicate"]).scan_prefix.reset_index(drop=True))
        payload = {"hypothesis_id": "H-SCAN1B_STAGE5B", "decision": branch,
                   "effectiveness": effective, "validity": validity,
                   "F10_F01_physical_scan_sequences_equal": bool(seq_equal),
                   "component_identity_nonidentifiable": True,
                   "supported_conclusion": "span-order structural term sufficient" if branch == "SIMPLE" else "see decision",
                   "forbidden_conclusion": "duration versus hierarchy debt identity",
                   "semantic_samples": 1, "aggregate": json.loads(aggregate.to_json(orient="records"))}
        dump(OUT / "FACTORIAL_DECISION.json", payload)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("phase", choices=("tie", "factorial")); evaluate(p.parse_args().phase)
