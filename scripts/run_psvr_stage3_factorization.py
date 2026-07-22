#!/usr/bin/env python3
"""Execute and evaluate the preregistered Stage-3 H-FACT1 physical matrix."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
from garc_eval.psvr_factorization import start_factor_policy_service
from garc_eval.psvr_runtime import durable_json

OUT = REPO / "outputs/psvr_autonomous_research/stage_3_factorization"
SMOKE_RAW = OUT / "raw_smoke"
MATRIX_RAW = OUT / "raw_matrix"
TABLES = OUT / "tables"
REPORTS = OUT / "reports"
STAGE2_RUNNER = REPO / "scripts/run_psvr_core_pilot.py"
METHODS = ("C0", "C1", "C2", "C3")
METHOD_LABELS = {
    "C0": "C0 S0+A0", "C1": "C1 S1+A0",
    "C2": "C2 S0+A1", "C3": "C3 S1+A1",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def load_stage2():
    spec = importlib.util.spec_from_file_location("psvr_stage3_stage2_runtime", STAGE2_RUNNER)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.METHOD_LABELS = METHOD_LABELS
    module.start_pilot_policy_service = start_factor_policy_service
    return module


def prepare(stage2) -> tuple[dict, dict[str, float]]:
    for directory in (OUT, SMOKE_RAW, MATRIX_RAW, TABLES, REPORTS):
        directory.mkdir(parents=True, exist_ok=True)
    manifest_path = OUT / "DEV_TASK_MANIFEST.json"
    deadline_path = OUT / "TRANSITION_DEADLINES.json"
    prereg_path = OUT / "H_FACT1_PREREGISTRATION.json"
    manifest = json.loads(manifest_path.read_text())
    deadline_manifest = json.loads(deadline_path.read_text())
    prereg = json.loads(prereg_path.read_text())
    deadlines = dict(deadline_manifest["deadlines_seconds"])
    config = {
        "experiment_id": "psvr_stage_3_H_FACT1_v1",
        "benchmark_id": manifest["benchmark_id"],
        "runtime_identity": manifest["runtime_identity"],
        "runtime_identity_hash": manifest["runtime_identity_hash"],
        "deadlines_seconds": deadlines,
        "methods": METHOD_LABELS,
        "coverage_debt_parameters": {"lambda": 0.5, "beta": 0.25, "revision": 0},
        "batch_size": 4,
        "proxy_observation": manifest["frozen_operators"]["proxy"],
        "oracle": manifest["frozen_operators"]["physical_oracle"],
        "materializer": manifest["frozen_operators"]["K3"],
        "snapshot_checkpoint": manifest["frozen_operators"]["snapshot_checkpoints"],
        "heldout_opened": False,
        "evidence_scope": manifest["scope"],
        "frozen_input_hashes": {
            "DEV_TASK_MANIFEST.json": sha256(manifest_path),
            "TRANSITION_DEADLINES.json": sha256(deadline_path),
            "H_FACT1_PREREGISTRATION.json": sha256(prereg_path),
        },
        "implementation_hashes": {
            "runner": sha256(Path(__file__)),
            "factor_policy": sha256(SRC / "garc_eval/psvr_factorization/policy_service.py"),
            "stage2_physical_runtime": sha256(STAGE2_RUNNER),
            "materializer_evaluator": sha256(stage2.MATERIALIZER),
        },
        "preregistered_cells": prereg["cells"],
    }
    path = OUT / "resolved_config.json"
    if path.exists() and json.loads(path.read_text()) != config:
        raise RuntimeError("H-FACT1 resolved config changed after freeze")
    if not path.exists():
        durable_json(path, config)
    (OUT / "commands.sh").write_text(
        "#!/usr/bin/env bash\n"
        "PYTHONPATH=src pytest -q tests/psvr_runtime\n"
        "python scripts/analyze_psvr_stage3_attribution.py\n"
        "python scripts/run_psvr_stage3_factorization.py smoke\n"
        "python scripts/run_psvr_stage3_factorization.py matrix\n"
        "python scripts/run_psvr_stage3_factorization.py finalize\n")
    return config, deadlines


def configure_runtime(stage2, raw: Path) -> None:
    stage2.OUT, stage2.RAW, stage2.TABLES, stage2.REPORTS = OUT, raw, TABLES, REPORTS


def attempted(raw: Path, method: str, deadline: str, replicate: int) -> bool:
    root = raw / f"{method}__{deadline}__replicate_{replicate:02d}"
    return any(root.glob("attempt_*/complete.json")) or any(root.glob("attempt_*/failed.json"))


def physical_attempt_count() -> int:
    completed = sum(1 for _ in OUT.glob("raw_*/*/attempt_*/complete.json"))
    runtime_failures = 0
    for path in OUT.glob("raw_*/*/attempt_*/failed.json"):
        if json.loads(path.read_text()).get("run_elapsed_seconds") is not None:
            runtime_failures += 1
    return completed + runtime_failures


def execute(kind: str) -> None:
    stage2 = load_stage2(); config, deadlines = prepare(stage2)
    raw = SMOKE_RAW if kind == "smoke" else MATRIX_RAW
    configure_runtime(stage2, raw)
    hds = stage2.load_module(f"psvr_stage3_hds_{kind}", stage2.HDS_PATH)
    profiler = stage2.load_module(f"psvr_stage3_profiler_{kind}", stage2.PROFILER_PATH)
    jobs = ([(method, "T_transition", deadlines["T_transition"], 0) for method in METHODS]
            if kind == "smoke" else
            [(method, deadline_name, deadlines[deadline_name], replicate)
             for method in METHODS for deadline_name in ("T_low", "T_transition", "T_high")
             for replicate in range(3)])
    if kind == "matrix":
        smoke = list(SMOKE_RAW.glob("*/attempt_*/complete.json"))
        if len(smoke) != 4 or not all(json.loads(path.read_text()).get("status") == "ok" for path in smoke):
            raise RuntimeError("all four smoke cells must be valid before matrix execution")
    for method, deadline_name, deadline, replicate in jobs:
        if attempted(raw, method, deadline_name, replicate):
            continue
        if physical_attempt_count() >= 40:
            raise RuntimeError("preregistered physical run cap of 40 reached")
        stage2.run_one(method, deadline_name, deadline, replicate, config, hds, profiler)
    completed = [json.loads(path.read_text()) for path in raw.glob("*/attempt_*/complete.json")]
    failed = list(raw.glob("*/attempt_*/failed.json"))
    summary = {"phase": kind, "expected_runs": len(jobs), "completed_ok": len(completed),
               "failed": len(failed), "deadline_misses": sum(not row["deadline_met"] for row in completed),
               "cache_replay_calls": sum(row["cache_replay_calls"] for row in completed),
               "future_proxy_accesses": sum(row["future_proxy_accesses"] for row in completed),
               "candidate_observation_violations": sum(row["candidate_observation_violations"] for row in completed),
               "physical_attempts_total": physical_attempt_count()}
    durable_json(OUT / f"{kind.upper()}_RESULTS.json", summary)
    print(json.dumps(summary, indent=2))


def extrema(values: pd.Series) -> dict:
    clean = values.dropna().astype(float)
    return {"median": None if clean.empty else float(clean.median()),
            "min": None if clean.empty else float(clean.min()),
            "max": None if clean.empty else float(clean.max())}


def finalize() -> None:
    stage2 = load_stage2(); config, deadlines = prepare(stage2); configure_runtime(stage2, MATRIX_RAW)
    benchmark = stage2.benchmark_module(); reference = pd.read_csv(stage2.REFERENCE_PATH)
    units = pd.read_csv(stage2.UNITS_PATH); evaluator_hash = sha256(stage2.MATERIALIZER)
    rows = [json.loads(path.read_text()) for path in sorted(MATRIX_RAW.glob("*/attempt_*/complete.json"))]
    summaries, mechanism = [], []
    for row in rows:
        summary, points = stage2.evaluate_run(row, benchmark, reference, units, evaluator_hash)
        summary["TP"] = int(round(summary["recall"] * len(reference)))
        summary["FP"] = int(round(summary["TP"] / summary["precision"] - summary["TP"])) if summary["precision"] else int(summary["confirmed_events"])
        summary["FN"] = len(reference) - summary["TP"]
        summary["scan_actions"] = sum(a["action"] == "scan" for a in row["actions"])
        summary["verify_actions"] = sum(a["action"] == "query" for a in row["actions"])
        # The inherited Stage-2 runtime did not timestamp the sandbox RPC
        # separately.  Keep this unavailable rather than misreporting zero.
        summary["scheduler_overhead_seconds"] = np.nan
        summary["refinement_actions"] = 0
        summary["proxy_batches"] = summary["scan_actions"]
        summary["verify_admitted"] = summary["verify_actions"]
        summary["verify_rejected"] = int(str(row["stop_reason"]).startswith("verify_not_admitted:"))
        summary["decoded_frames"] = sum(r.get("operator") == "decode_seek" and r.get("status") == "ok"
                                        for r in row["proxy_operator_rows"])
        summary["event_set"] = "|".join(str(e.get("event_id", e.get("reference_event_id", "unknown")))
                                          for e in json.loads(Path(row["final_snapshot_path"]).read_text())["strict_confirmed_events"])
        summary["action_trace"] = "".join("S" if a["action"] == "scan" else "V" for a in row["actions"])
        summaries.append(summary); mechanism.extend(points)
    frame = pd.DataFrame(summaries); mech = pd.DataFrame(mechanism)
    frame.to_csv(TABLES / "physical_run_metrics.csv", index=False); mech.to_csv(TABLES / "mechanism_curves.csv", index=False)
    metric_names = ["AnytimeAUC_F1", "F1_at_deadline", "TP", "FP", "FN", "unique_confirmed_events",
                    "time_to_first_confirmed_event", "time_to_first_candidate", "precision", "recall",
                    "max_unobserved_gap_auc_fraction", "max_unobserved_gap", "physical_oracle_calls",
                    "GPU_seconds", "unused_deadline_seconds", "scan_actions", "verify_actions", "decoded_frames",
                    "proxy_batches", "refinement_actions", "verify_admitted", "verify_rejected",
                    "scheduler_overhead_seconds"]
    aggregates = []
    for (method, deadline), group in frame.groupby(["method", "deadline_name"]):
        row = {"method": method, "deadline_name": deadline, "runs": len(group),
               "event_set_consistency": int(group.event_set.nunique()) == 1,
               "event_sets": sorted(group.event_set.unique().tolist()),
               "action_trace_variation": int(group.action_trace.nunique()),
               "action_traces": sorted(group.action_trace.unique().tolist())}
        for metric in metric_names:
            row[metric] = extrema(group[metric])
        aggregates.append(row)
    durable_json(TABLES / "method_deadline_median_min_max.json", aggregates)

    validation = {"matrix_complete": len(rows) == 36, "all_cells_three_runs": len(aggregates) == 12 and all(r["runs"] == 3 for r in aggregates),
                  "deadline_misses": int((~frame.deadline_met).sum()), "cache_replay_calls": int(frame.cache_replay_calls.sum()),
                  "future_proxy_accesses": int(frame.future_proxy_accesses.sum()),
                  "candidate_observation_violations": int(frame.candidate_observation_violations.sum()),
                  "runtime_identity_count": len({row["runtime_identity_hash"] for row in rows}),
                  "physical_attempts_total": physical_attempt_count(), "heldout_opened": False}
    durable_json(OUT / "MATRIX_VALIDATION.json", validation)
    # Branching is based on repeatable event-quality differences, not runtime repeats as semantic replication.
    quality = frame.groupby("method").agg(AUC=("AnytimeAUC_F1", "median"), F1=("F1_at_deadline", "median"),
                                           recovered=("unique_confirmed_events", lambda x: int((x > 0).sum())))
    c0, c1, c2, c3 = (quality.loc[m] for m in METHODS)
    improves = lambda x: bool(x.recovered > c0.recovered and (x.AUC > c0.AUC or x.F1 > c0.F1))
    signals = {"C1_over_C0": improves(c1), "C2_over_C0": improves(c2), "C3_over_C0": improves(c3)}
    if signals == {"C1_over_C0": True, "C2_over_C0": False, "C3_over_C0": True}:
        branch, conclusion = "A", "COMPOSITE_SCAN_SIGNAL = PRESENT"
    elif signals == {"C1_over_C0": False, "C2_over_C0": True, "C3_over_C0": True}:
        branch, conclusion = "B", "ALLOCATION_MECHANISM_SIGNAL = PRESENT; H-COV1 = REJECT"
    elif signals == {"C1_over_C0": False, "C2_over_C0": False, "C3_over_C0": True}:
        branch, conclusion = "C", "SCAN_VERIFY_INTERACTION = PRESENT"
    elif not any(signals.values()):
        branch, conclusion = "D", "COVERAGE_ALLOCATION_ROUTE = NO_GO"
    else:
        branch, conclusion = "INCONCLUSIVE", "Observed marginal pattern does not uniquely match preregistered A/B/C/D"
    decision = {"H_FACT1": "VALID" if all([validation["matrix_complete"], validation["all_cells_three_runs"],
                                              validation["deadline_misses"] == 0, validation["cache_replay_calls"] == 0,
                                              validation["future_proxy_accesses"] == 0,
                                              validation["candidate_observation_violations"] == 0]) else "INVALID",
                "branch": branch, "conclusion": conclusion, "signals": signals,
                "semantic_sample_count": 1, "runtime_repeats_are_stability_only": True,
                "quality_summary": quality.reset_index().to_dict("records"),
                "next_action": {"A": "scan-priority component ablation", "B": "event-aware or deadline-aware verification allocation",
                                "C": "pre-frozen multi-video-query development validation in a later cycle",
                                "D": "stop lambda/beta/coverage tuning"}.get(branch, "resolve branch ambiguity without tuning")}
    durable_json(OUT / "DECISION.json", decision)
    print(json.dumps({"validation": validation, "decision": decision}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("command", choices=("smoke", "matrix", "finalize"))
    args = parser.parse_args()
    execute(args.command) if args.command in ("smoke", "matrix") else finalize()


if __name__ == "__main__":
    main()
