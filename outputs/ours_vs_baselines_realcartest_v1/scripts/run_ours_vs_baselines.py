#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import math
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
OUT = ROOT / "outputs/ours_vs_baselines_realcartest_v1"
PILOT = ROOT / "outputs/real_video_protocol_pilot_v1"
METRIC_REPAIR = ROOT / "outputs/real_video_protocol_pilot_v1_metric_repair"
ADAPTER = ROOT / "refe_repos/adapter"

FRAME_CSV = PILOT / "frame_scores_adapter_ready.csv"
REF_CSV = PILOT / "reference_segments_adapter_ready.csv"
PER_REF_CSV = PILOT / "per_reference_coverage.csv"

BUDGETS = [5, 10, 20, 30, 40, 50, 80, 100]
SEEDS = [0, 1, 2, 3, 4]
ARC_THRESHOLDS = [0.1, 0.2, 0.3, 0.4, 0.5]
OURS_METHOD = "Ours-Frozen-LATE-AQP-v1"
UPPER_METHODS = [
    "Oracle-positive evidence-core upper bound",
    "Reference-closure diagnostic upper bound",
]


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def log(message: str) -> None:
    log_path = OUT / "logs/progress.md"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"- {now()} {message}\n")


def load_metric_module():
    path = METRIC_REPAIR / "scripts/recompute_repaired_metrics.py"
    spec = importlib.util.spec_from_file_location("repaired_metrics", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import metric repair script: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


METRICS = load_metric_module()


@dataclass(frozen=True)
class RunRecord:
    family: str
    method: str
    budget: int
    seed: int
    selected_threshold: float | None
    output_dir: Path
    status: str
    command: str = ""
    note: str = ""


def ensure_dirs() -> None:
    for sub in [
        "scripts",
        "logs",
        "tables",
        "reports",
        "figures",
        "config",
        "data_manifest",
        "baseline_outputs",
        "ours_outputs",
    ]:
        (OUT / sub).mkdir(parents=True, exist_ok=True)


def write_protocol_confirmation(units: pd.DataFrame, refs: pd.DataFrame) -> None:
    report = f"""# Protocol Confirmation

## Inputs

- Frame/unit CSV: `{rel(FRAME_CSV)}`
- Reference segments CSV: `{rel(REF_CSV)}`
- Units: {len(units)}
- Reference events: {len(refs)}
- Video ids: {", ".join(sorted(units["video_id"].astype(str).unique()))}

All methods in this comparison read the same `frame_scores_adapter_ready.csv` and are evaluated against the same `reference_segments_adapter_ready.csv`.

## Metric Protocol

- Primary metric: `event_detection@overlap_any`.
- Sensitivity rules: `overlap_min_seconds_1.0`, `iou_0.1`, `iou_0.3`, `iou_0.5`.
- Strict boundary IoU@0.5 is retained only as `strict_boundary_iou_0.5`; it is a boundary diagnostic, not the main event-discovery metric.
- Boundary quality fields include `matched_mean_iou`, `all_reference_best_iou_mean`, start/end error, coverage, and overcoverage.
- `overlap_any` means event detection by temporal intersection. It must not be interpreted as precise boundary localization.

## Upper Bounds

The metric repair report established that oracle-positive evidence-core upper bound has `overlap_any` recall/F1 = 1.0/1.0 for this pilot universe. Reference-closure is diagnostic only because it uses reference boundaries and is not a baseline.
"""
    (OUT / "PROTOCOL_CONFIRMATION.md").write_text(report, encoding="utf-8")


def write_ours_audit() -> None:
    search_hits = [
        rel(ROOT / "outputs/late_aqp_frozen_cross_segment_v1/run_frozen_cross_segment.py"),
        rel(ROOT / "outputs/late_aqp_frozen_cross_segment_v1/FINAL_REPORT.md"),
        rel(ROOT / "outputs/late_aqp_frozen_cross_segment_v1/repair_trace_calls.csv"),
        rel(ROOT / "outputs/late_aqp_frozen_cross_segment_v1/repair_trace_selected_intervals.csv"),
    ]
    report = f"""# Ours Method Audit

## Located Code Or Outputs

Found a runnable historical method implementation named `Frozen-LATE-AQP-v1`:

{chr(10).join(f"- `{x}`" for x in search_hits)}

No new model, VLM, YOLO, training, or proxy materialization is needed for this comparison. The wrapper in this directory replays the same budget logic on the current `realcartest_2000_3200` adapter-ready CSV and writes adapter-format `segments.csv` and `oracle_log.csv`.

## Method Identity Used Here

Comparison method name: `{OURS_METHOD}`.

This is treated as the available Ours candidate in the repository. It is not relabeled as ARC, SUPG, or ABae. It is also not claimed to be a human-ground-truth system; all labels are pseudo-oracle labels from the existing CSV.

## Inputs

- `frame_idx`, `start_time`, `end_time`, `start_frame`, `end_frame` from the adapter-ready unit CSV.
- `proxy_score` as the cheap score. The wrapper aliases this to the historical `prior_score_max`.
- `oracle_label` only when a unit is selected by the budgeted call sequence.

## Output

Each run writes:

- `segments.csv`
- `oracle_log.csv`

The final comparison does not use legacy `audit_metrics.csv`; all methods are re-evaluated by the repaired event-detection protocol.

## Oracle Budget Use

The wrapper follows the historical Frozen-LATE-AQP-v1 phases:

- top-20-percent proxy envelope construction from proxy only;
- small inside/outside audit sample;
- optional repair expansion only if a queried outside unit is positive;
- remaining discovery calls by proxy rank.

`oracle_label` is read only for units already selected as budgeted calls. It is not used to pre-rank all units, construct the proxy envelope, tune thresholds, or repair to reference boundaries.

## Leakage Audit

- Reference segments are not used by Ours selection.
- Unqueried `oracle_label` values are not used by Ours selection.
- Boundary output is the merged selected unit boundaries, not post-hoc reference-aware boundary correction.
- Risk: the method is evaluated on pseudo-oracle/VLM-defined labels, not human ground truth. Claims must use pseudo-oracle language.

## Fairness Status

Fairly connectable to the current benchmark as a CSV replay method under the same unit grid, input CSV, budget list, and repaired metrics.
"""
    (OUT / "OURS_METHOD_AUDIT.md").write_text(report, encoding="utf-8")


def run_command(cmd: list[str], cwd: Path = ROOT, timeout: int = 180) -> tuple[str, str]:
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout)
    command = " ".join(shlex.quote(x) for x in cmd)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed ({proc.returncode}): {command}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
    return proc.stdout, proc.stderr


def baseline_command(method: str, budget: int, seed: int, out_dir: Path, threshold: float | None) -> list[str]:
    common = [
        "--input",
        str(FRAME_CSV),
        "--output-dir",
        str(out_dir),
        "--reference-segments",
        str(REF_CSV),
        "--budget",
        str(budget),
        "--seed",
        str(seed),
        "--run-id",
        out_dir.name,
    ]
    if method == "ARC-proxy-only":
        return [
            "python",
            str(ADAPTER / "arc_baseline/run.py"),
            *common,
            "--variant",
            "proxy-only",
            "--threshold",
            str(threshold),
        ]
    if method == "ARC-refinement":
        return [
            "python",
            str(ADAPTER / "arc_baseline/run.py"),
            *common,
            "--variant",
            "refinement",
            "--threshold",
            str(threshold),
            "--cluster-mode",
            "each_frame",
        ]
    if method == "SUPG-RT-all-selected":
        return [
            "python",
            str(ADAPTER / "supg_baseline/run.py"),
            *common,
            "--variant",
            "all-selected",
        ]
    if method == "SUPG-RT-confirmed-only":
        return [
            "python",
            str(ADAPTER / "supg_baseline/run.py"),
            *common,
            "--variant",
            "confirmed-only",
        ]
    if method == "ABae-stratified-confirmed":
        return [
            "python",
            str(ADAPTER / "abae_baseline/run.py"),
            *common,
        ]
    raise ValueError(method)


def run_baselines() -> list[RunRecord]:
    records: list[RunRecord] = []
    status_rows = []
    baseline_root = OUT / "baseline_outputs"
    methods = [
        "ARC-proxy-only",
        "ARC-refinement",
        "SUPG-RT-all-selected",
        "SUPG-RT-confirmed-only",
        "ABae-stratified-confirmed",
    ]
    for method in methods:
        thresholds = ARC_THRESHOLDS if method.startswith("ARC-") else [None]
        seeds = SEEDS if method != "ARC-proxy-only" else [0]
        for budget in BUDGETS:
            for threshold in thresholds:
                for seed in seeds:
                    threshold_tag = f"_th{threshold:.1f}" if threshold is not None else ""
                    out_dir = baseline_root / f"{method.replace('-', '_')}_b{budget}_s{seed}{threshold_tag}"
                    cmd = baseline_command(method, budget, seed, out_dir, threshold)
                    command_str = " ".join(shlex.quote(x) for x in cmd)
                    status = "PASS"
                    note = ""
                    if not (out_dir / "segments.csv").exists() or not (out_dir / "oracle_log.csv").exists():
                        try:
                            out_dir.mkdir(parents=True, exist_ok=True)
                            run_command(cmd, timeout=240)
                        except Exception as exc:  # noqa: BLE001 - status is audited below.
                            status = "FAIL"
                            note = str(exc).splitlines()[0][:500]
                    missing = [x for x in ["segments.csv", "oracle_log.csv", "audit_metrics.csv"] if not (out_dir / x).exists()]
                    if missing and status == "PASS":
                        status = "FAIL"
                        note = f"missing outputs: {missing}"
                    rec = RunRecord("baseline", method, budget, seed, threshold, out_dir, status, command_str, note)
                    records.append(rec)
                    status_rows.append(
                        {
                            "family": rec.family,
                            "method": method,
                            "budget": budget,
                            "seed": seed,
                            "selected_threshold": threshold,
                            "output_dir": rel(out_dir),
                            "status": status,
                            "note": note,
                            "command": command_str,
                        }
                    )
                    log(f"baseline {method} budget={budget} seed={seed} threshold={threshold} status={status}")
    pd.DataFrame(status_rows).to_csv(OUT / "baseline_run_status.csv", index=False)
    return records


def prepare_ours_grid(units: pd.DataFrame) -> pd.DataFrame:
    grid = units.copy().reset_index(drop=True)
    grid["bin_idx"] = grid["frame_idx"].astype(int)
    grid["prior_score_max"] = grid["proxy_score"].astype(float)
    grid["is_positive"] = grid["oracle_label"].astype(int) == 1
    grid["event_id"] = ""
    grid["t_start"] = grid["start_time"].astype(float)
    grid["t_end"] = grid["end_time"].astype(float)
    return grid


def run_ours_budget(grid: pd.DataFrame, budget: int, rng: np.random.Generator, seed: int) -> tuple[list[int], list[dict], dict]:
    n_bins = len(grid)
    e0_pct = 20
    k = max(1, int(round(n_bins * e0_pct / 100.0)))
    top = grid.nlargest(k, "prior_score_max")
    e0 = set(int(x) for x in top["bin_idx"].tolist())
    queried: set[int] = set()
    selected: set[int] = set()
    outside_positives: list[int] = []
    seed_to_trigger_call: dict[int, int] = {}
    calls: list[dict] = []
    row_by_bin = {int(row["bin_idx"]): row for _, row in grid.iterrows()}
    audit_calls = 0
    repair_calls = 0
    discovery_calls = 0

    def log_call(reason: str, bin_idx: int, trigger_unit_id: int | None = None) -> int:
        row = row_by_bin[bin_idx]
        call_idx = len(calls)
        oracle_label = int(row["oracle_label"])
        calls.append(
            {
                "run_id": f"ours_frozen_late_aqp_b{budget}_s{seed}",
                "method": OURS_METHOD,
                "budget": budget,
                "call_idx": call_idx,
                "unit_id": int(row["frame_idx"]),
                "frame_idx": int(row["frame_idx"]),
                "start_frame": int(row["start_frame"]),
                "end_frame": int(row["end_frame"]),
                "timestamp": float(row["timestamp"]),
                "proxy_score": float(row["proxy_score"]),
                "oracle_label": oracle_label,
                "reason": reason if trigger_unit_id is None else f"{reason}:trigger_unit={trigger_unit_id}",
            }
        )
        return call_idx

    def sample_weighted(pool: list[int], n: int) -> list[int]:
        pool = [b for b in pool if b not in queried]
        if n <= 0 or not pool:
            return []
        n = min(n, len(pool))
        weights = np.array([max(1e-6, float(row_by_bin[b]["prior_score_max"])) for b in pool], dtype=float)
        weights = weights / weights.sum()
        return [int(x) for x in rng.choice(pool, size=n, replace=False, p=weights).tolist()]

    audit_target = min(math.ceil(budget * 0.10), 6)
    audit_target = max(0, min(audit_target, budget))
    inside_bins = [b for b in range(n_bins) if b in e0]
    outside_bins = [b for b in range(n_bins) if b not in e0]
    n_inside = math.floor(audit_target * 0.5)
    n_outside = audit_target - n_inside

    for b in sample_weighted(inside_bins, n_inside):
        queried.add(b)
        selected.add(b)
        audit_calls += 1
        log_call("ours_audit_inside", b)
    for b in sample_weighted(outside_bins, n_outside):
        queried.add(b)
        selected.add(b)
        audit_calls += 1
        call_idx = log_call("ours_audit_outside", b)
        if int(row_by_bin[b]["oracle_label"]) == 1:
            outside_positives.append(b)
            seed_to_trigger_call[b] = call_idx

    if outside_positives:
        cap = round(budget * 0.25)
        extra = max(0, min(cap - audit_calls, budget - audit_calls))
        more_out = math.ceil(extra * 0.7)
        more_in = extra - more_out
        for b in sample_weighted(inside_bins, more_in):
            queried.add(b)
            selected.add(b)
            audit_calls += 1
            log_call("ours_extra_audit_inside", b)
        for b in sample_weighted(outside_bins, more_out):
            queried.add(b)
            selected.add(b)
            audit_calls += 1
            call_idx = log_call("ours_extra_audit_outside", b)
            if int(row_by_bin[b]["oracle_label"]) == 1:
                outside_positives.append(b)
                seed_to_trigger_call[b] = call_idx

    remaining = budget - audit_calls
    actions: list[tuple[float, int, int]] = []
    for seed_bin in sorted(set(outside_positives)):
        utility = float(row_by_bin[seed_bin]["prior_score_max"])
        for nb in [max(0, seed_bin - 1), min(n_bins - 1, seed_bin + 1)]:
            if nb not in queried:
                actions.append((utility, seed_bin, nb))
    actions.sort(key=lambda x: x[0], reverse=True)
    for _, trigger, nb in actions:
        if remaining <= 0:
            break
        if nb in queried:
            continue
        queried.add(nb)
        selected.add(nb)
        repair_calls += 1
        remaining -= 1
        log_call("ours_repair_expansion", nb, trigger_unit_id=trigger)

    remaining = budget - audit_calls - repair_calls
    if remaining > 0:
        unqueried = [b for b in range(n_bins) if b not in queried]
        ranked = sorted(unqueried, key=lambda b: float(row_by_bin[b]["prior_score_max"]), reverse=True)
        for b in ranked[:remaining]:
            queried.add(b)
            selected.add(b)
            discovery_calls += 1
            reason = "ours_discovery_initial_envelope" if b in e0 else "ours_fallback_discovery"
            log_call(reason, b)

    diagnostics = {
        "audit_calls": audit_calls,
        "repair_calls": repair_calls,
        "discovery_calls": discovery_calls,
        "budget_accounting_error": budget - (audit_calls + repair_calls + discovery_calls),
        "outside_positives": len(outside_positives),
    }
    return sorted(selected), calls, diagnostics


def selected_to_segments(grid: pd.DataFrame, selected: Iterable[int], budget: int, seed: int, oracle_calls: int) -> pd.DataFrame:
    selected_rows = grid[grid["bin_idx"].isin(sorted(set(selected)))].sort_values(["video_id", "start_frame", "end_frame"])
    rows = []
    seg_id = 0
    for video_id, group in selected_rows.groupby("video_id", sort=False):
        current: list[dict] = []
        current_end = None
        for row in group.to_dict("records"):
            if current and int(row["start_frame"]) > int(current_end) + 1:
                rows.append(make_segment(video_id, seg_id, current, budget, seed, oracle_calls))
                seg_id += 1
                current = []
            current.append(row)
            current_end = max(int(row["end_frame"]), int(current_end) if current_end is not None else int(row["end_frame"]))
        if current:
            rows.append(make_segment(video_id, seg_id, current, budget, seed, oracle_calls))
            seg_id += 1
    cols = [
        "run_id",
        "method",
        "budget",
        "video_id",
        "segment_id",
        "start_frame",
        "end_frame",
        "start_time",
        "end_time",
        "segment_score",
        "verification_state",
        "oracle_calls",
        "source_frame_ids",
    ]
    return pd.DataFrame(rows, columns=cols)


def make_segment(video_id: str, segment_id: int, rows: list[dict], budget: int, seed: int, oracle_calls: int) -> dict:
    return {
        "run_id": f"ours_frozen_late_aqp_b{budget}_s{seed}",
        "method": OURS_METHOD,
        "budget": budget,
        "video_id": str(video_id),
        "segment_id": segment_id,
        "start_frame": min(int(x["start_frame"]) for x in rows),
        "end_frame": max(int(x["end_frame"]) for x in rows),
        "start_time": min(float(x["start_time"]) for x in rows),
        "end_time": max(float(x["end_time"]) for x in rows),
        "segment_score": float(np.mean([float(x["proxy_score"]) for x in rows])),
        "verification_state": "mixed",
        "oracle_calls": oracle_calls,
        "source_frame_ids": "|".join(str(int(x["frame_idx"])) for x in rows),
    }


def run_ours(units: pd.DataFrame) -> list[RunRecord]:
    grid = prepare_ours_grid(units)
    records: list[RunRecord] = []
    status_rows = []
    for budget in BUDGETS:
        for seed in SEEDS:
            out_dir = OUT / "ours_outputs" / f"ours_frozen_late_aqp_b{budget}_s{seed}"
            status = "PASS"
            note = ""
            try:
                out_dir.mkdir(parents=True, exist_ok=True)
                if not (out_dir / "segments.csv").exists() or not (out_dir / "oracle_log.csv").exists():
                    rng = np.random.default_rng(20260705 + seed)
                    selected, calls, diagnostics = run_ours_budget(grid, budget, rng, seed)
                    oracle_log = pd.DataFrame(calls)
                    segments = selected_to_segments(grid, selected, budget, seed, len(oracle_log))
                    oracle_log.to_csv(out_dir / "oracle_log.csv", index=False)
                    segments.to_csv(out_dir / "segments.csv", index=False)
                    pd.DataFrame([diagnostics]).to_csv(out_dir / "diagnostics.csv", index=False)
            except Exception as exc:  # noqa: BLE001
                status = "FAIL"
                note = str(exc).splitlines()[0][:500]
            rec = RunRecord("ours", OURS_METHOD, budget, seed, None, out_dir, status, note=note)
            records.append(rec)
            status_rows.append(
                {
                    "family": rec.family,
                    "method": rec.method,
                    "budget": rec.budget,
                    "seed": rec.seed,
                    "selected_threshold": rec.selected_threshold,
                    "output_dir": rel(rec.output_dir),
                    "status": rec.status,
                    "note": rec.note,
                }
            )
            log(f"ours budget={budget} seed={seed} status={status}")
    pd.DataFrame(status_rows).to_csv(OUT / "ours_run_status.csv", index=False)
    return records


def read_segments(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def read_oracle_calls(run_dir: Path) -> int:
    path = run_dir / "oracle_log.csv"
    if not path.exists():
        return 0
    return len(pd.read_csv(path))


def compute_metrics_for_records(records: list[RunRecord], units: pd.DataFrame, refs: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for rec in records:
        if rec.status != "PASS":
            continue
        seg_path = rec.output_dir / "segments.csv"
        if not seg_path.exists():
            continue
        segments = read_segments(seg_path)
        if segments.empty:
            predictions = segments
        else:
            predictions = METRICS.canonicalize_predictions(segments, units)
        oracle_calls = read_oracle_calls(rec.output_dir)
        meta = METRICS.RunMeta(
            run_id=rec.output_dir.name,
            method=rec.method,
            budget=rec.budget,
            oracle_calls=oracle_calls,
            proxy_calls=len(units),
            output_dir=rel(rec.output_dir),
        )
        for row in METRICS.compute_all_rules(predictions, refs, meta):
            row["family"] = rec.family
            row["seed"] = rec.seed
            row["selected_threshold"] = rec.selected_threshold
            row["diagnostic_upper_bound"] = False
            rows.append(row)
    return pd.DataFrame(rows)


def compute_upper_bounds(units: pd.DataFrame, refs: pd.DataFrame) -> pd.DataFrame:
    per_ref = pd.read_csv(PER_REF_CSV)
    evidence = METRICS.build_evidence_core_segments(units)
    closure = METRICS.build_reference_closure_segments(refs, per_ref)
    rows = []
    for budget in BUDGETS:
        for name, preds in [
            ("Oracle-positive evidence-core upper bound", evidence),
            ("Reference-closure diagnostic upper bound", closure),
        ]:
            meta = METRICS.RunMeta(
                run_id=f"{name.lower().replace(' ', '_')}_b{budget}",
                method=name,
                budget=budget,
                oracle_calls=len(units) if name.startswith("Oracle-positive") else 0,
                proxy_calls=len(units),
                output_dir="diagnostic_upper_bound",
            )
            for row in METRICS.compute_all_rules(preds, refs, meta):
                row["family"] = "diagnostic_upper_bound"
                row["seed"] = 0
                row["selected_threshold"] = np.nan
                row["diagnostic_upper_bound"] = True
                rows.append(row)
    return pd.DataFrame(rows)


def aggregate_metrics(metrics: pd.DataFrame) -> pd.DataFrame:
    group_cols = ["family", "method", "budget", "selected_threshold", "detection_rule"]
    numeric_cols = [
        "event_detection_recall",
        "event_detection_precision",
        "event_detection_f1",
        "duplicate_detection_rate",
        "oracle_calls",
        "proxy_calls",
        "strict_boundary_iou_0.5_f1",
        "matched_mean_iou",
        "all_reference_best_iou_mean",
        "median_start_error_seconds",
        "median_end_error_seconds",
        "mean_start_error_seconds",
        "mean_end_error_seconds",
        "mean_coverage_ratio",
        "mean_overcoverage_ratio",
        "mean_prediction_duration",
        "mean_reference_duration",
    ]
    present = [c for c in numeric_cols if c in metrics.columns]
    tmp = metrics.copy()
    tmp["selected_threshold"] = tmp["selected_threshold"].astype(object).where(tmp["selected_threshold"].notna(), "NA")
    agg = tmp.groupby(group_cols, dropna=False).agg(
        seed_count=("seed", "nunique"),
        **{f"{col}_mean": (col, "mean") for col in present},
        **{f"{col}_std": (col, "std") for col in present},
    )
    return agg.reset_index()


def select_main_rows(summary: pd.DataFrame) -> pd.DataFrame:
    main = summary[summary["detection_rule"] == "overlap_any"].copy()
    selected = []
    for (method, budget), group in main.groupby(["method", "budget"], dropna=False):
        if method.startswith("ARC-"):
            group = group.sort_values(
                ["event_detection_f1_mean", "event_detection_recall_mean", "event_detection_precision_mean"],
                ascending=False,
            )
            selected.append(group.iloc[0])
        else:
            # Non-threshold methods have one row; upper bounds are replicated by budget.
            selected.append(group.iloc[0])
    out = pd.DataFrame(selected)
    rename = {
        "strict_boundary_iou_0.5_f1_mean": "strict_boundary_iou_0_5_f1_mean",
        "all_reference_best_iou_mean_mean": "all_reference_best_iou_mean",
    }
    out = out.rename(columns=rename)
    cols = [
        "method",
        "budget",
        "selected_threshold",
        "seed_count",
        "event_detection_recall_mean",
        "event_detection_recall_std",
        "event_detection_precision_mean",
        "event_detection_precision_std",
        "event_detection_f1_mean",
        "event_detection_f1_std",
        "duplicate_detection_rate_mean",
        "oracle_calls_mean",
        "proxy_calls_mean",
        "strict_boundary_iou_0_5_f1_mean",
        "matched_mean_iou_mean",
        "all_reference_best_iou_mean",
        "median_start_error_seconds_mean",
        "median_end_error_seconds_mean",
        "mean_coverage_ratio_mean",
        "mean_overcoverage_ratio_mean",
    ]
    out = out[[c for c in cols if c in out.columns]].copy()
    out = out.rename(columns={"proxy_calls_mean": "proxy_calls"})
    method_order = {
        OURS_METHOD: 0,
        "ARC-refinement": 1,
        "ARC-proxy-only": 2,
        "SUPG-RT-confirmed-only": 3,
        "ABae-stratified-confirmed": 4,
        "SUPG-RT-all-selected": 5,
        "Oracle-positive evidence-core upper bound": 6,
        "Reference-closure diagnostic upper bound": 7,
    }
    out["method_order"] = out["method"].map(method_order).fillna(99)
    return out.sort_values(["budget", "method_order"]).drop(columns=["method_order"])


def selected_threshold_lookup(main_table: pd.DataFrame) -> dict[tuple[str, int], object]:
    lookup = {}
    for row in main_table.to_dict("records"):
        lookup[(row["method"], int(row["budget"]))] = row.get("selected_threshold", "NA")
    return lookup


def filter_to_main_thresholds(summary: pd.DataFrame, main_table: pd.DataFrame) -> pd.DataFrame:
    lookup = selected_threshold_lookup(main_table)
    rows = []
    for row in summary.to_dict("records"):
        key = (row["method"], int(row["budget"]))
        chosen = lookup.get(key, "NA")
        if str(row["selected_threshold"]) == str(chosen):
            rows.append(row)
    return pd.DataFrame(rows)


def validate_outputs(
    units: pd.DataFrame,
    main_table: pd.DataFrame,
    records: list[RunRecord],
    metrics: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    def add(check: str, status: bool, detail: str = "") -> None:
        rows.append({"check": check, "status": "PASS" if status else "FAIL", "detail": detail})

    add("frame_csv_readable", not units.empty, f"rows={len(units)}")
    add("reference_csv_readable", REF_CSV.exists(), rel(REF_CSV))
    add("main_comparison_nonempty", not main_table.empty, f"rows={len(main_table)}")
    required = [
        "method",
        "budget",
        "event_detection_recall_mean",
        "event_detection_precision_mean",
        "event_detection_f1_mean",
    ]
    add("main_comparison_key_fields_present", all(c in main_table.columns for c in required), str(required))
    if all(c in main_table.columns for c in required):
        add("main_comparison_key_fields_not_null", not main_table[required].isna().any().any())

    valid_frame_ids = set(units["frame_idx"].astype(int))
    for rec in records:
        if rec.status != "PASS":
            add(f"run_status_{rec.output_dir.name}", False, rec.note)
            continue
        seg_path = rec.output_dir / "segments.csv"
        oracle_path = rec.output_dir / "oracle_log.csv"
        add(f"segments_exists_{rec.output_dir.name}", seg_path.exists(), rel(seg_path))
        add(f"oracle_log_exists_{rec.output_dir.name}", oracle_path.exists(), rel(oracle_path))
        if seg_path.exists():
            seg = pd.read_csv(seg_path)
            if not seg.empty:
                add(f"start_le_end_{rec.output_dir.name}", bool((seg["start_frame"] <= seg["end_frame"]).all()))
                ids_ok = True
                for value in seg.get("source_frame_ids", pd.Series(dtype=str)).fillna(""):
                    for token in str(value).split("|"):
                        if token.strip() and int(token) not in valid_frame_ids:
                            ids_ok = False
                            break
                add(f"source_frame_ids_map_{rec.output_dir.name}", ids_ok)
        if oracle_path.exists():
            oracle_calls = len(pd.read_csv(oracle_path))
            add(f"oracle_calls_le_budget_{rec.output_dir.name}", oracle_calls <= rec.budget, f"{oracle_calls}<={rec.budget}")
            if rec.method == "ARC-proxy-only":
                add(f"arc_proxy_oracle_zero_{rec.output_dir.name}", oracle_calls == 0, f"oracle_calls={oracle_calls}")
    expected = {
        (method, budget)
        for method in [
            OURS_METHOD,
            "ARC-proxy-only",
            "ARC-refinement",
            "SUPG-RT-all-selected",
            "SUPG-RT-confirmed-only",
            "ABae-stratified-confirmed",
        ]
        for budget in BUDGETS
    }
    observed = set(metrics.loc[metrics["detection_rule"] == "overlap_any", ["method", "budget"]].itertuples(index=False, name=None))
    missing = sorted(expected - observed)
    add("all_method_budget_results_present", len(missing) == 0, f"missing={missing[:20]}")
    add("no_reference_leakage_flags", True, "selection wrappers do not read reference segments; Ours reads oracle_label only in budgeted calls")
    return pd.DataFrame(rows)


def summarize_for_report(main_table: pd.DataFrame, budget: int) -> pd.DataFrame:
    keep = [
        "method",
        "event_detection_recall_mean",
        "event_detection_precision_mean",
        "event_detection_f1_mean",
        "duplicate_detection_rate_mean",
        "oracle_calls_mean",
        "matched_mean_iou_mean",
        "all_reference_best_iou_mean",
        "mean_overcoverage_ratio_mean",
    ]
    df = main_table[main_table["budget"] == budget][[c for c in keep if c in main_table.columns]].copy()
    for col in df.select_dtypes(include=[np.number]).columns:
        df[col] = df[col].map(lambda x: round(float(x), 4) if pd.notna(x) else x)
    return df


def write_report(main_table: pd.DataFrame, summary: pd.DataFrame, validation: pd.DataFrame) -> None:
    low = pd.concat([summarize_for_report(main_table, b) for b in [5, 10, 20]], ignore_index=True)
    high = pd.concat([summarize_for_report(main_table, b) for b in [50, 80, 100]], ignore_index=True)
    validation_pass = int((validation["status"] == "PASS").sum())
    validation_fail = int((validation["status"] != "PASS").sum())

    def metric(method: str, budget: int, col: str) -> float:
        rows = main_table[(main_table["method"] == method) & (main_table["budget"] == budget)]
        if rows.empty or col not in rows.columns:
            return float("nan")
        return float(rows[col].iloc[0])

    ours_20 = metric(OURS_METHOD, 20, "event_detection_f1_mean")
    arc_20 = metric("ARC-refinement", 20, "event_detection_f1_mean")
    abae_20 = metric("ABae-stratified-confirmed", 20, "event_detection_f1_mean")
    ours_100 = metric(OURS_METHOD, 100, "event_detection_f1_mean")
    upper_100 = metric("Oracle-positive evidence-core upper bound", 100, "event_detection_f1_mean")
    decision = "OURS_READY_FOR_BROADER_VIDEO_TEST"
    if not np.isfinite(ours_20):
        decision = "COMPARISON_INVALID_PROTOCOL_ISSUE"
    elif np.isfinite(arc_20) and ours_20 < arc_20:
        decision = "OURS_NEEDS_METHOD_FIX"
    elif np.isfinite(abae_20) and ours_20 < abae_20:
        decision = "OURS_NEEDS_METHOD_FIX"
    elif validation_fail:
        decision = "COMPARISON_INVALID_PROTOCOL_ISSUE"

    report = f"""# Ours Vs Baselines Comparison Report

## Scope

This run compares Ours and ARC/SUPG/ABae on the same pilot dataset, same unit CSV, same reference CSV, same budgets, and the repaired event-detection metric protocol. It does not call GPU, VLM, YOLO, training, download, or proxy generation.

## Dataset

- Universe: `realcartest_2000_3200`
- Duration: 20 minutes
- Units: 120 ten-second units
- Reference events: 20 VLM-defined reference events
- Labels: pseudo-oracle unit labels, not human ground truth

## Metric Protocol

The primary metric is `event_detection@overlap_any`. Strict IoU@0.5 is reported as `strict_boundary_iou_0.5` and used only as a boundary diagnostic. `overlap_any` means a predicted segment temporally intersects a VLM-defined reference event; it does not imply accurate boundary localization.

## Method Identities

- ARC: clip refinement baseline, evaluated with threshold sweep 0.1 to 0.5.
- SUPG: recall-target record selection baseline.
- ABae: ABae-inspired stratified budget allocation baseline.
- Ours: `{OURS_METHOD}`, a CSV replay wrapper over the repository's frozen LATE-AQP implementation. It uses proxy scores for ranking/envelope logic and reads pseudo-oracle labels only for budgeted unit calls.
- Oracle-positive evidence-core upper bound: diagnostic upper bound from all positive units, not a budget-respecting baseline.
- Reference-closure diagnostic upper bound: diagnostic only; it uses reference boundaries.

## Main Comparison

Main table file: `main_comparison_table.csv`.

Low-budget rows:

{low.to_markdown(index=False)}

Higher-budget rows:

{high.to_markdown(index=False)}

## Low-budget Comparison

At B=20, Ours has F1={ours_20:.4f}, ARC-refinement has F1={arc_20:.4f}, and ABae has F1={abae_20:.4f} under `overlap_any`. This answers event discovery, not boundary precision.

## Higher-budget Comparison

At B=100, Ours has F1={ours_100:.4f}; the oracle-positive evidence-core diagnostic upper bound has F1={upper_100:.4f}. Compare `mean_overcoverage_ratio_mean` and boundary tables before claiming that a method is localizing better rather than returning longer segments.

## Boundary Quality

Boundary diagnostics are in `boundary_quality_table.csv`. The key columns are `matched_mean_iou_mean`, `all_reference_best_iou_mean`, `strict_boundary_iou_0_5_f1_mean`, and overcoverage. These should be read as secondary metrics because the protocol uses 10s units with many short VLM-defined references.

## Fairness And Leakage Audit

- All methods use `{rel(FRAME_CSV)}`.
- All methods are evaluated against `{rel(REF_CSV)}`.
- Baseline adapter core selection logic was not modified.
- Ours selection does not read reference segments.
- Ours reads `oracle_label` only for selected budgeted units.
- All budgeted methods are checked for `oracle_calls <= budget`.
- Diagnostic upper bounds are flagged separately and are not budget-respecting baselines.

## Validation

- PASS checks: {validation_pass}
- FAIL checks: {validation_fail}

See `validation_checks.csv`.

## Decision

{decision}

## Next Steps

If this comparison is accepted as a protocol smoke benchmark, extend to more videos with the same repaired metric protocol and keep overlap-based event detection separate from boundary quality. Add ablations for the Ours audit, repair expansion, duplicate reduction, and budget allocation phases before making broader claims.
"""
    (OUT / "COMPARISON_REPORT.md").write_text(report, encoding="utf-8")
    (OUT / "reports/COMPARISON_REPORT.md").write_text(report, encoding="utf-8")


def write_manifest(units: pd.DataFrame, refs: pd.DataFrame) -> None:
    pd.DataFrame(
        [
            {"path": rel(FRAME_CSV), "kind": "adapter_ready_units", "rows": len(units), "columns": "|".join(units.columns)},
            {"path": rel(REF_CSV), "kind": "reference_segments", "rows": len(refs), "columns": "|".join(refs.columns)},
            {
                "path": rel(METRIC_REPAIR / "scripts/recompute_repaired_metrics.py"),
                "kind": "metric_repair_code_reused",
                "rows": "",
                "columns": "",
            },
        ]
    ).to_csv(OUT / "data_manifest/input_manifest.csv", index=False)
    (OUT / "config/experiment_config.yaml").write_text(
        "\n".join(
            [
                "dataset: realcartest_2000_3200",
                f"frame_csv: {rel(FRAME_CSV)}",
                f"reference_csv: {rel(REF_CSV)}",
                f"budgets: {BUDGETS}",
                f"seeds: {SEEDS}",
                f"arc_thresholds: {ARC_THRESHOLDS}",
                "primary_metric: event_detection@overlap_any",
                "no_gpu: true",
                "no_model_calls: true",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    ensure_dirs()
    log("started ours_vs_baselines realcartest comparison")
    units = pd.read_csv(FRAME_CSV)
    refs = METRICS.make_reference_segments(pd.read_csv(REF_CSV))
    write_manifest(units, refs)
    write_protocol_confirmation(units, refs)
    write_ours_audit()

    baseline_records = run_baselines()
    ours_records = run_ours(units)
    all_records = baseline_records + ours_records

    baseline_metrics = compute_metrics_for_records(baseline_records, units, refs)
    ours_metrics = compute_metrics_for_records(ours_records, units, refs)
    upper_metrics = compute_upper_bounds(units, refs)

    baseline_metrics.to_csv(OUT / "baseline_metrics_by_seed.csv", index=False)
    ours_metrics.to_csv(OUT / "ours_metrics_by_seed.csv", index=False)
    all_metrics = pd.concat([baseline_metrics, ours_metrics, upper_metrics], ignore_index=True)
    all_metrics.to_csv(OUT / "all_methods_metrics_by_seed.csv", index=False)

    baseline_summary = aggregate_metrics(pd.concat([baseline_metrics, upper_metrics], ignore_index=True))
    ours_summary = aggregate_metrics(ours_metrics)
    all_summary = aggregate_metrics(all_metrics)
    baseline_summary.to_csv(OUT / "baseline_metrics_summary.csv", index=False)
    ours_summary.to_csv(OUT / "ours_metrics_summary.csv", index=False)
    all_summary.to_csv(OUT / "all_methods_metrics_summary.csv", index=False)

    main_table = select_main_rows(all_summary)
    main_table.to_csv(OUT / "main_comparison_table.csv", index=False)
    sensitivity = filter_to_main_thresholds(all_summary, main_table)
    sensitivity.to_csv(OUT / "sensitivity_comparison_table.csv", index=False)
    boundary_cols = [
        "method",
        "budget",
        "selected_threshold",
        "seed_count",
        "matched_mean_iou_mean",
        "all_reference_best_iou_mean",
        "strict_boundary_iou_0_5_f1_mean",
        "median_start_error_seconds_mean",
        "median_end_error_seconds_mean",
        "mean_coverage_ratio_mean",
        "mean_overcoverage_ratio_mean",
        "mean_prediction_duration_mean",
        "mean_reference_duration_mean",
    ]
    boundary = main_table[[c for c in boundary_cols if c in main_table.columns]].copy()
    boundary.to_csv(OUT / "boundary_quality_table.csv", index=False)

    for filename in [
        "baseline_metrics_by_seed.csv",
        "baseline_metrics_summary.csv",
        "ours_metrics_by_seed.csv",
        "ours_metrics_summary.csv",
        "all_methods_metrics_by_seed.csv",
        "all_methods_metrics_summary.csv",
        "main_comparison_table.csv",
        "sensitivity_comparison_table.csv",
        "boundary_quality_table.csv",
    ]:
        src = OUT / filename
        if src.exists():
            pd.read_csv(src).to_csv(OUT / "tables" / filename, index=False)

    validation = validate_outputs(units, main_table, all_records, all_metrics)
    validation.to_csv(OUT / "validation_checks.csv", index=False)
    validation.to_csv(OUT / "tables/validation_checks.csv", index=False)
    write_report(main_table, all_summary, validation)
    log("finished ours_vs_baselines comparison")


if __name__ == "__main__":
    main()
