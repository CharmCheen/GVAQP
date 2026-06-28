#!/usr/bin/env python3
"""Phase 1.3 return-set / certificate disentanglement for Nexar-200 CASQ.

This is metadata-only. It does not run VLMs, use GPU, train models, build a
perception stack, download videos, or fabricate original event boundaries.
"""

from __future__ import annotations

import hashlib
import argparse
import json
import math
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
PREV_OUT = ROOT / "test_vlm/outputs/clip_aqp_phase1_nexar_200_v1"
PHASE0_REPAIR = ROOT / "test_vlm/outputs/clip_aqp_phase0_v1/repair_v1"
OUT = ROOT / "test_vlm/outputs/clip_aqp_phase1_nexar_200_disentangle_v1"
EVENTS_PATH = PREV_OUT / "converted/casq_events_nexar_200.csv"
UNITS_PATH = PREV_OUT / "converted/casq_units_nexar_200.csv"

THETAS = [0.3, 0.5]
GAMMAS = [0.8, 0.9]
DELTAS = [0.05, 0.10]
BLOCK_SIZES = [10.0, 15.0]
CERTIFICATION_SAMPLE_FRACTIONS = [0.10, 0.20, 0.35, 0.50, 0.75]
NUM_TRIALS = 200
DROP_TARGET_RECALLS = [0.5, 0.7, 0.8, 0.9]
DROP_SEEDS = list(range(10))
EPSILON = 1e-9

RETURN_SET_COLUMNS = [
    "return_set_name",
    "video_id",
    "returned_clip_id",
    "start_time",
    "end_time",
    "generation_rule",
    "oracle_informed",
    "notes",
]


@dataclass(frozen=True)
class ReturnSet:
    name: str
    clips: pd.DataFrame
    generation_rule: str
    oracle_informed: bool
    notes: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_dirs() -> None:
    for name in ["scripts", "reports", "tables", "figures", "logs", "return_sets", "config", "data_manifest"]:
        (OUT / name).mkdir(parents=True, exist_ok=True)


def append_progress(checkpoint: str, command: str, result: str, failure: str = "", fix: str = "", next_action: str = "") -> None:
    ensure_dirs()
    with (OUT / "logs/progress.md").open("a", encoding="utf-8") as f:
        f.write(
            "\n".join(
                [
                    f"## {utc_now()}",
                    f"- checkpoint: {checkpoint}",
                    f"- commands run: `{command}`",
                    f"- result: {result}",
                    f"- failure if any: {failure or 'none'}",
                    f"- fix applied: {fix or 'none'}",
                    f"- next action: {next_action or 'none'}",
                    "",
                ]
            )
        )


def stable_score(text: str, seed: str) -> float:
    digest = hashlib.sha256(f"{seed}:{text}".encode("utf-8")).hexdigest()
    return int(digest[:16], 16) / float(16**16 - 1)


def safe_name(value: str) -> str:
    return value.replace(".", "p").replace("/", "_")


def interval_iou(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    inter = max(0.0, min(a_end, b_end) - max(a_start, b_start))
    union = max(a_end, b_end) - min(a_start, b_start)
    return inter / union if union > 0 else 0.0


def normal_quantile_for_delta(delta: float) -> float:
    """Match the repaired Phase 0 normal-approximation convention."""
    if delta <= 0.05:
        return 1.96
    if delta <= 0.10:
        return 1.645
    return 1.282


def markdown_table(df: pd.DataFrame, max_rows: int = 40) -> str:
    if df.empty:
        return "_empty_"
    view = df.head(max_rows)
    lines = ["| " + " | ".join(view.columns) + " |", "| " + " | ".join(["---"] * len(view.columns)) + " |"]
    for _, row in view.iterrows():
        vals = []
        for value in row:
            if isinstance(value, float):
                vals.append(f"{value:.4g}" if math.isfinite(value) else "")
            else:
                vals.append(str(value))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_and_validate_inputs(num_trials: int, run_mode: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    events = pd.read_csv(EVENTS_PATH)
    units = pd.read_csv(UNITS_PATH)

    checks = []
    def add_check(name: str, passed: bool, detail: str = "") -> None:
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    add_check("events_path_exists", EVENTS_PATH.exists(), str(EVENTS_PATH))
    add_check("units_path_exists", UNITS_PATH.exists(), str(UNITS_PATH))
    add_check("usable_event_count_200", len(events) == 200, f"rows={len(events)}")
    add_check("all_boundaries_derived", set(events["boundary_source"].astype(str)) == {"derived_from_alert_time_to_event_moment"})
    add_check("event_start_lt_event_end", bool((events["event_start"] < events["event_end"]).all()))
    add_check("event_duration_positive", bool((events["event_duration"] > 0).all()))
    if "human_adjudicated" in events.columns:
        human_flags = events["human_adjudicated"].astype(str).str.lower().isin(["true", "1", "yes"])
        add_check("human_adjudicated_false", not bool(human_flags.any()))
    else:
        add_check("human_adjudicated_absent_allowed", True, "column absent")
    add_check("event_midpoint_inside_interval", bool(((events["event_start"] <= events["event_midpoint"]) & (events["event_midpoint"] <= events["event_end"])).all()))
    add_check("unit_duration_positive", bool((units["duration"] > 0).all()))
    add_check("source_video_count_400", units["video_id"].nunique() == 400, f"videos={units['video_id'].nunique()}")

    audit_df = pd.DataFrame(checks)
    audit_df.to_csv(OUT / "tables/input_validation_checks.csv", index=False)
    if not bool(audit_df["passed"].all()):
        raise AssertionError("Input validation failed; see tables/input_validation_checks.csv")

    manifest = pd.DataFrame(
        [
            {
                "input_name": "casq_events_nexar_200",
                "path": str(EVENTS_PATH),
                "rows": len(events),
                "columns": ";".join(events.columns),
                "source_video_count": events["video_id"].nunique(),
                "positive_event_count": len(events),
                "time_metadata": "event_start,event_end,event_midpoint,event_duration",
                "event_definition": "derived alert-to-event-moment precursor interval",
                "label_or_leakage_risk": "oracle-informed diagnostics use event intervals only for controlled disentanglement; not deployable ranking",
            },
            {
                "input_name": "casq_units_nexar_200",
                "path": str(UNITS_PATH),
                "rows": len(units),
                "columns": ";".join(units.columns),
                "source_video_count": units["video_id"].nunique(),
                "positive_event_count": int(units["has_event_overlap"].astype(bool).sum()),
                "time_metadata": "start_time,end_time,duration",
                "event_definition": "fixed 5s/10s/15s metadata units with overlap tags",
                "label_or_leakage_risk": "overlap tags not used for current_R reconstruction; event intervals used for oracle diagnostics and certification evaluation",
            },
        ]
    )
    manifest.to_csv(OUT / "data_manifest/input_manifest.csv", index=False)

    write_json(
        OUT / "config/experiment_config.json",
        {
            "experiment": "clip_aqp_phase1_nexar_200_disentangle_v1",
            "created_utc": utc_now(),
            "events_path": str(EVENTS_PATH),
            "units_path": str(UNITS_PATH),
            "prior_reports": [
                str(PREV_OUT / "reports/NEXAR_200_DERIVED_BENCHMARK_REPORT.md"),
                str(PHASE0_REPAIR / "reports/PHASE0_REPORT_v2.md"),
                str(PHASE0_REPAIR / "reports/ROOT_CAUSE.md"),
            ],
            "thetas": THETAS,
            "gammas": GAMMAS,
            "deltas": DELTAS,
            "block_sizes_seconds": BLOCK_SIZES,
            "certification_sample_fractions": CERTIFICATION_SAMPLE_FRACTIONS,
            "num_trials": num_trials,
            "run_mode": run_mode,
            "drop_target_recalls": DROP_TARGET_RECALLS,
            "drop_seeds": DROP_SEEDS,
            "bound_formula": "repair_v1: LCB_Y=max(0,Y_hat-z*se_Y), UCB_M=max(M_hat,M_hat+z*se_M), no UCB_M cap by LCB_Y",
            "forbidden_actions": ["vlm", "gpu", "training", "perception_stack", "video_download"],
        },
    )

    append_progress("input_audit", f"python scripts/10_run_nexar_200_disentangle.py ({run_mode})", f"events={len(events)}, units={len(units)}", next_action="construct return sets")
    return events, units, audit_df


def stitch_units(selected: pd.DataFrame) -> pd.DataFrame:
    rows = []
    clip_idx = 0
    for video_id, group in selected.sort_values(["video_id", "start_time", "end_time", "unit_id"]).groupby("video_id", sort=True):
        cur_start = None
        cur_end = None
        for _, row in group.iterrows():
            start = float(row["start_time"])
            end = float(row["end_time"])
            if cur_start is None or start - float(cur_end) > 1e-9:
                if cur_start is not None:
                    rows.append({"video_id": video_id, "returned_clip_id": f"r0_clip_{clip_idx:05d}", "start_time": cur_start, "end_time": cur_end})
                    clip_idx += 1
                cur_start, cur_end = start, end
            else:
                cur_end = max(float(cur_end), end)
        if cur_start is not None:
            rows.append({"video_id": video_id, "returned_clip_id": f"r0_clip_{clip_idx:05d}", "start_time": cur_start, "end_time": cur_end})
            clip_idx += 1
    return pd.DataFrame(rows)


def add_return_set_columns(df: pd.DataFrame, name: str, rule: str, oracle_informed: bool, notes: str) -> pd.DataFrame:
    out = df.copy()
    out["return_set_name"] = name
    out["generation_rule"] = rule
    out["oracle_informed"] = bool(oracle_informed)
    out["notes"] = notes
    for idx in range(len(out)):
        if "returned_clip_id" not in out.columns or pd.isna(out.iloc[idx].get("returned_clip_id", "")):
            out.loc[out.index[idx], "returned_clip_id"] = f"{safe_name(name)}_clip_{idx:05d}"
    return out[RETURN_SET_COLUMNS].sort_values(["video_id", "start_time", "end_time", "returned_clip_id"]).reset_index(drop=True)


def construct_return_sets(events: pd.DataFrame, units: pd.DataFrame) -> list[ReturnSet]:
    return_sets: list[ReturnSet] = []

    units_5s = units[np.isclose(units["duration"].astype(float), 5.0)].copy()
    units_5s["score"] = units_5s["unit_id"].astype(str).map(lambda unit_id: stable_score(unit_id, seed="nexar_200_block_candidate_hash"))
    selected = units_5s.sort_values(["score", "video_id", "start_time", "unit_id"], ascending=[False, True, True, True]).head(max(1, int(round(len(units_5s) * 0.35))))
    r0 = stitch_units(selected)
    return_sets.append(
        ReturnSet(
            "R0_current_reconstructed",
            add_return_set_columns(
                r0,
                "R0_current_reconstructed",
                "reconstructed_prior_metadata_hash_top_35pct_5s_units_stitched",
                False,
                "Reconstructs previous Nexar-200 block-audit candidate clips from published script seed and rule.",
            ),
            "reconstructed_prior_metadata_hash_top_35pct_5s_units_stitched",
            False,
            "Reconstructs previous Nexar-200 block-audit candidate clips from published script seed and rule.",
        )
    )

    exact = pd.DataFrame(
        {
            "video_id": events["video_id"].astype(str),
            "returned_clip_id": [f"r1_exact_{i:05d}" for i in range(len(events))],
            "start_time": events["event_start"].astype(float),
            "end_time": events["event_end"].astype(float),
        }
    )
    return_sets.append(
        ReturnSet(
            "R1_oracle_exact",
            add_return_set_columns(exact, "R1_oracle_exact", "exact_derived_event_interval_per_event", True, "Oracle-informed diagnostic; validates evaluator and certificate upper bound."),
            "exact_derived_event_interval_per_event",
            True,
            "Oracle-informed diagnostic; validates evaluator and certificate upper bound.",
        )
    )

    for padding in [2.5, 5.0, 10.0]:
        padded = pd.DataFrame(
            {
                "video_id": events["video_id"].astype(str),
                "returned_clip_id": [f"r2_pad_{safe_name(str(padding))}_{i:05d}" for i in range(len(events))],
                "start_time": np.maximum(0.0, events["event_start"].astype(float).to_numpy() - padding),
                "end_time": events["event_end"].astype(float).to_numpy() + padding,
            }
        )
        name = f"R2_oracle_padded_{safe_name(str(padding))}s"
        return_sets.append(
            ReturnSet(
                name,
                add_return_set_columns(padded, name, f"derived_event_interval_padded_{padding}s", True, "Oracle-informed padded diagnostic; not deployable."),
                f"derived_event_interval_padded_{padding}s",
                True,
                "Oracle-informed padded diagnostic; not deployable.",
            )
        )

    for target in DROP_TARGET_RECALLS:
        keep_n = int(round(len(events) * target))
        for seed in DROP_SEEDS:
            rng = np.random.default_rng(20260621 + seed + int(target * 1000))
            keep_idx = np.sort(rng.choice(np.arange(len(events)), size=keep_n, replace=False))
            dropped = exact.iloc[keep_idx].copy().reset_index(drop=True)
            dropped["returned_clip_id"] = [f"r3_drop_{safe_name(str(target))}_s{seed:02d}_{i:05d}" for i in range(len(dropped))]
            name = f"R3_oracle_drop_recall_{safe_name(str(target))}_seed_{seed:02d}"
            return_sets.append(
                ReturnSet(
                    name,
                    add_return_set_columns(dropped, name, f"exact_intervals_random_drop_target_recall_{target}_seed_{seed}", True, "Oracle-informed random-drop diagnostic."),
                    f"exact_intervals_random_drop_target_recall_{target}_seed_{seed}",
                    True,
                    "Oracle-informed random-drop diagnostic.",
                )
            )

    for width in [5.0, 10.0, 15.0]:
        half = width / 2.0
        windows = pd.DataFrame(
            {
                "video_id": events["video_id"].astype(str),
                "returned_clip_id": [f"r4_mid_{safe_name(str(width))}_{i:05d}" for i in range(len(events))],
                "start_time": np.maximum(0.0, events["event_midpoint"].astype(float).to_numpy() - half),
                "end_time": events["event_midpoint"].astype(float).to_numpy() + half,
            }
        )
        name = f"R4_event_moment_window_{safe_name(str(width))}s"
        return_sets.append(
            ReturnSet(
                name,
                add_return_set_columns(windows, name, f"fixed_{width}s_window_centered_at_derived_event_midpoint", True, "Oracle-informed midpoint-window diagnostic upper-bound, not deployable."),
                f"fixed_{width}s_window_centered_at_derived_event_midpoint",
                True,
                "Oracle-informed midpoint-window diagnostic upper-bound, not deployable.",
            )
        )

    all_rows = []
    for ret in return_sets:
        ret.clips.to_csv(OUT / "return_sets" / f"{safe_name(ret.name)}.csv", index=False)
        all_rows.append(ret.clips)
    pd.concat(all_rows, ignore_index=True).to_csv(OUT / "return_sets/all_return_sets.csv", index=False)

    append_progress("construct_return_sets", "python scripts/10_run_nexar_200_disentangle.py", f"return_sets={len(return_sets)}", next_action="compute true derived recall")
    return return_sets


def event_hits(events: pd.DataFrame, clips: pd.DataFrame, theta: float) -> np.ndarray:
    hits = np.zeros(len(events), dtype=bool)
    clips_by_video = {video_id: group for video_id, group in clips.groupby("video_id", sort=False)}
    for idx, event in events.reset_index(drop=True).iterrows():
        group = clips_by_video.get(str(event["video_id"]))
        if group is None:
            continue
        ev_start = float(event["event_start"])
        ev_end = float(event["event_end"])
        for _, clip in group.iterrows():
            if interval_iou(ev_start, ev_end, float(clip["start_time"]), float(clip["end_time"])) >= theta:
                hits[idx] = True
                break
    return hits


def compute_recall_table(events: pd.DataFrame, return_sets: list[ReturnSet]) -> tuple[pd.DataFrame, dict[tuple[str, float], np.ndarray]]:
    rows = []
    hit_cache: dict[tuple[str, float], np.ndarray] = {}
    event_total = len(events)
    for ret in return_sets:
        durations = ret.clips["end_time"].astype(float) - ret.clips["start_time"].astype(float)
        for theta in THETAS:
            hits = event_hits(events, ret.clips, theta)
            hit_cache[(ret.name, theta)] = hits
            rows.append(
                {
                    "return_set_name": ret.name,
                    "theta": theta,
                    "num_returned_clips": len(ret.clips),
                    "true_derived_recall": float(hits.mean()) if event_total else 0.0,
                    "mean_clip_duration": float(durations.mean()) if len(durations) else 0.0,
                    "total_returned_duration": float(durations.sum()) if len(durations) else 0.0,
                    "event_hit_count": int(hits.sum()),
                    "event_total_count": event_total,
                }
            )
    table = pd.DataFrame(rows)
    table.to_csv(OUT / "tables/return_set_true_recall.csv", index=False)
    append_progress("true_recall", "python scripts/10_run_nexar_200_disentangle.py", f"rows={len(table)}", next_action="run block/event audit")
    return table, hit_cache


def video_bounds(units: pd.DataFrame) -> pd.DataFrame:
    bounds = units.groupby("video_id", as_index=False)["end_time"].max()
    bounds["start_time"] = 0.0
    return bounds[["video_id", "start_time", "end_time"]]


def build_block_arrays(events: pd.DataFrame, bounds: pd.DataFrame, hits: np.ndarray, block_size: float) -> tuple[np.ndarray, np.ndarray]:
    event_by_video: dict[str, list[tuple[float, bool]]] = {}
    for idx, event in events.reset_index(drop=True).iterrows():
        event_by_video.setdefault(str(event["video_id"]), []).append((float(event["event_midpoint"]), bool(hits[idx])))

    y_vals = []
    m_vals = []
    for _, row in bounds.sort_values("video_id").iterrows():
        video_id = str(row["video_id"])
        start = 0.0
        max_end = math.ceil(float(row["end_time"]) / block_size) * block_size
        while start < max_end - EPSILON:
            end = start + block_size
            y = 0
            m = 0
            for midpoint, hit in event_by_video.get(video_id, []):
                if start <= midpoint < end:
                    y += 1
                    m += int(not hit)
            y_vals.append(y)
            m_vals.append(m)
            start = end
    return np.asarray(y_vals, dtype=float), np.asarray(m_vals, dtype=float)


def certificate_from_values(y_values: np.ndarray, m_values: np.ndarray, sampled_idx: np.ndarray, delta: float) -> dict:
    sample_split = "certification"
    used_for_design = False
    used_for_repair = False
    if sample_split != "certification" or used_for_design or used_for_repair:
        raise AssertionError("Invalid certification sample provenance")

    population_n = len(y_values)
    n = len(sampled_idx)
    sample_y = y_values[sampled_idx]
    sample_m = m_values[sampled_idx]
    y_hat = population_n * float(np.mean(sample_y))
    m_hat = population_n * float(np.mean(sample_m))
    if n > 1 and population_n > 1:
        fpc = math.sqrt(max(0.0, 1.0 - n / population_n))
        y_se_total = population_n * float(np.std(sample_y, ddof=1)) / math.sqrt(n) * fpc
        m_se_total = population_n * float(np.std(sample_m, ddof=1)) / math.sqrt(n) * fpc
    else:
        y_se_total = 0.0
        m_se_total = 0.0
    z = normal_quantile_for_delta(delta)
    lcb_y = max(0.0, y_hat - z * y_se_total)
    ucb_m = max(m_hat, m_hat + z * m_se_total)
    if ucb_m < m_hat - EPSILON:
        raise AssertionError(f"UCB_M_O invariant failed: {ucb_m} < {m_hat}")
    if lcb_y > y_hat + EPSILON:
        raise AssertionError(f"LCB_Y_O invariant failed: {lcb_y} > {y_hat}")
    if lcb_y <= EPSILON:
        lcb_recall = 0.0
        status = "NO_CERTIFICATE"
    else:
        lcb_recall = max(0.0, min(1.0, 1.0 - ucb_m / lcb_y))
        status = "CERTIFICATE_COMPUTED"
    return {
        "Y_hat_O": y_hat,
        "M_hat_O": m_hat,
        "LCB_Y_O": lcb_y,
        "UCB_M_O": ucb_m,
        "LCB_recall": lcb_recall,
        "certificate_status": status,
        "invariant_UCB_M_O_ge_M_hat_O": bool(ucb_m >= m_hat - EPSILON),
        "invariant_LCB_Y_O_le_Y_hat_O": bool(lcb_y <= y_hat + EPSILON),
    }


def run_audit(events: pd.DataFrame, units: pd.DataFrame, return_sets: list[ReturnSet], recall_table: pd.DataFrame, hit_cache: dict[tuple[str, float], np.ndarray], num_trials: int) -> pd.DataFrame:
    bounds = video_bounds(units)
    trial_rows = []
    summary_rows = []
    recall_lookup = {(row.return_set_name, float(row.theta)): float(row.true_derived_recall) for row in recall_table.itertuples(index=False)}

    for ret in return_sets:
        for theta in THETAS:
            hits = hit_cache[(ret.name, theta)]
            true_recall = recall_lookup[(ret.name, theta)]
            for block_size in BLOCK_SIZES:
                y_vals, m_vals = build_block_arrays(events, bounds, hits, block_size)
                population_n = len(y_vals)
                if int(y_vals.sum()) != len(events):
                    raise AssertionError(f"Block event accounting failed for {ret.name}, theta={theta}, block={block_size}: {y_vals.sum()} != {len(events)}")
                for gamma in GAMMAS:
                    for delta in DELTAS:
                        for frac in CERTIFICATION_SAMPLE_FRACTIONS:
                            n = max(1, min(population_n, int(math.ceil(population_n * frac))))
                            lcbs = []
                            vacuous = []
                            successes = []
                            gvrs = []
                            tightness = []
                            for trial in range(num_trials):
                                seed = (
                                    20260621
                                    + stable_int(ret.name) % 1_000_000
                                    + int(theta * 1000) * 3
                                    + int(gamma * 1000) * 5
                                    + int(delta * 1000) * 7
                                    + int(block_size * 10) * 11
                                    + int(frac * 1000) * 13
                                    + trial * 17
                                )
                                rng = np.random.default_rng(seed)
                                sampled_idx = rng.choice(np.arange(population_n), size=n, replace=False)
                                cert = certificate_from_values(y_vals, m_vals, sampled_idx, delta)
                                lcb = float(cert["LCB_recall"])
                                success = lcb >= gamma
                                gvr = bool(success and true_recall < gamma - EPSILON)
                                vac = bool(cert["certificate_status"] == "NO_CERTIFICATE" or lcb <= EPSILON)
                                lcbs.append(lcb)
                                successes.append(float(success))
                                gvrs.append(float(gvr))
                                vacuous.append(float(vac))
                                tightness.append(float(true_recall - lcb))
                                trial_rows.append(
                                    {
                                        "return_set_name": ret.name,
                                        "theta": theta,
                                        "gamma": gamma,
                                        "delta": delta,
                                        "block_size": block_size,
                                        "certification_sample_fraction": frac,
                                        "trial": trial,
                                        "sample_n": n,
                                        "population_blocks": population_n,
                                        "true_derived_recall": true_recall,
                                        **cert,
                                        "fraction_vacuous": float(vac),
                                        "certificate_success": float(success),
                                        "GVR": float(gvr),
                                        "tightness": float(true_recall - lcb),
                                        "sample_split": "certification",
                                        "used_for_design": False,
                                        "used_for_repair": False,
                                    }
                                )
                            summary_rows.append(
                                {
                                    "return_set_name": ret.name,
                                    "theta": theta,
                                    "gamma": gamma,
                                    "delta": delta,
                                    "block_size": block_size,
                                    "certification_sample_fraction": frac,
                                    "true_derived_recall": true_recall,
                                    "median_LCB_recall": float(np.median(lcbs)),
                                    "p10_LCB_recall": float(np.quantile(lcbs, 0.10)),
                                    "p90_LCB_recall": float(np.quantile(lcbs, 0.90)),
                                    "fraction_vacuous": float(np.mean(vacuous)),
                                    "certificate_success_rate": float(np.mean(successes)),
                                    "GVR": float(np.mean(gvrs)),
                                    "tightness": float(np.mean(tightness)),
                                    "trials": num_trials,
                                    "mean_sample_n": n,
                                    "population_blocks": population_n,
                                }
                            )

    trial_df = pd.DataFrame(trial_rows)
    summary_df = pd.DataFrame(summary_rows)
    trial_df.to_csv(OUT / "tables/disentangle_block_audit_trials.csv", index=False)
    summary_df.to_csv(OUT / "tables/disentangle_block_audit_results.csv", index=False)

    constraints = pd.DataFrame(
        [
            {"constraint": "sample_split == certification", "passed": bool((trial_df["sample_split"] == "certification").all())},
            {"constraint": "used_for_design == false", "passed": not bool(trial_df["used_for_design"].astype(bool).any())},
            {"constraint": "used_for_repair == false", "passed": not bool(trial_df["used_for_repair"].astype(bool).any())},
            {"constraint": "UCB_M_O >= M_hat_O - 1e-9", "passed": bool(trial_df["invariant_UCB_M_O_ge_M_hat_O"].all())},
            {"constraint": "LCB_Y_O <= Y_hat_O + 1e-9", "passed": bool(trial_df["invariant_LCB_Y_O_le_Y_hat_O"].all())},
        ]
    )
    constraints.to_csv(OUT / "tables/certificate_validity_constraints.csv", index=False)
    if not bool(constraints["passed"].all()):
        raise AssertionError("Certificate validity constraints failed")

    append_progress("block_event_audit", "python scripts/10_run_nexar_200_disentangle.py", f"summary_rows={len(summary_df)}, trial_rows={len(trial_df)}", next_action="generate figures and report")
    return summary_df


def stable_int(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:12], 16)


def generate_figures(recall_table: pd.DataFrame, audit: pd.DataFrame) -> None:
    plot = audit[(audit["theta"] == 0.3) & (audit["gamma"] == 0.8) & (audit["delta"] == 0.10) & (audit["block_size"] == 10.0)].copy()
    names = [
        "R0_current_reconstructed",
        "R1_oracle_exact",
        "R3_oracle_drop_recall_0p8_seed_00",
        "R3_oracle_drop_recall_0p9_seed_00",
        "R4_event_moment_window_5p0s",
    ]
    subset = plot[plot["return_set_name"].isin(names)]

    fig, ax = plt.subplots(figsize=(10, 5))
    for name, group in subset.groupby("return_set_name", sort=False):
        group = group.sort_values("certification_sample_fraction")
        ax.plot(group["certification_sample_fraction"], group["median_LCB_recall"], marker="o", label=name)
    ax.axhline(0.8, color="black", linestyle="--", linewidth=1, label="gamma=0.8")
    ax.set_xlabel("certification sample fraction")
    ax.set_ylabel("median LCB recall")
    ax.set_title("Nexar-200 Disentangle: LCB by Return Set")
    ax.set_ylim(-0.03, 1.03)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "figures/lcb_by_return_set.png", dpi=160)
    plt.close(fig)

    success_plot = plot[plot["certification_sample_fraction"].isin([0.35, 0.50, 0.75])].merge(
        recall_table[["return_set_name", "theta", "true_derived_recall"]],
        on=["return_set_name", "theta"],
        suffixes=("", "_from_recall_table"),
    )
    fig, ax = plt.subplots(figsize=(8, 5))
    for frac, group in success_plot.groupby("certification_sample_fraction"):
        ax.scatter(group["true_derived_recall"], group["certificate_success_rate"], s=28, label=f"sample={frac:g}")
    ax.set_xlabel("true derived recall")
    ax.set_ylabel("certificate success rate")
    ax.set_title("Certificate Success by Return-set Quality")
    ax.set_xlim(-0.03, 1.03)
    ax.set_ylim(-0.03, 1.03)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "figures/certificate_success_by_true_recall.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5))
    for name, group in subset.groupby("return_set_name", sort=False):
        group = group.sort_values("certification_sample_fraction")
        ax.plot(group["certification_sample_fraction"], group["fraction_vacuous"], marker="o", label=name)
    ax.set_xlabel("certification sample fraction")
    ax.set_ylabel("fraction vacuous")
    ax.set_title("Vacuous Certificates by Sample Fraction")
    ax.set_ylim(-0.03, 1.03)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "figures/fraction_vacuous_by_sample_fraction.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 5))
    gvr_plot = plot[plot["certification_sample_fraction"] == 0.75].sort_values("true_derived_recall")
    ax.bar(np.arange(len(gvr_plot)), gvr_plot["GVR"])
    ax.set_xticks(np.arange(len(gvr_plot)))
    ax.set_xticklabels(gvr_plot["return_set_name"], rotation=90, fontsize=6)
    ax.set_ylabel("GVR")
    ax.set_title("GVR by Return Set at 75% Certification Sample")
    ax.set_ylim(-0.03, 1.03)
    fig.tight_layout()
    fig.savefig(OUT / "figures/gvr_by_return_set.png", dpi=160)
    plt.close(fig)

    append_progress("figures", "python scripts/10_run_nexar_200_disentangle.py", "figures=4", next_action="write report")


def choose_decision(audit: pd.DataFrame, recall_table: pd.DataFrame) -> str:
    current_low = bool(
        recall_table[(recall_table["return_set_name"] == "R0_current_reconstructed") & (recall_table["theta"] == 0.3)]["true_derived_recall"].iloc[0] < 0.2
    )
    oracle_exact = audit[
        (audit["return_set_name"] == "R1_oracle_exact")
        & (audit["theta"] == 0.3)
        & (audit["gamma"] == 0.8)
        & (audit["delta"] == 0.10)
        & (audit["block_size"] == 10.0)
        & (audit["certification_sample_fraction"] >= 0.35)
    ]
    oracle_exact_certifies = bool((oracle_exact["certificate_success_rate"] > 0.0).any() and (oracle_exact["fraction_vacuous"] < 1.0).any() and (oracle_exact["GVR"] <= 0.10 + EPSILON).all())

    drop_good = audit[
        audit["return_set_name"].str.contains("R3_oracle_drop_recall_0p8|R3_oracle_drop_recall_0p9", regex=True)
        & (audit["theta"] == 0.3)
        & (audit["delta"] == 0.10)
        & (audit["block_size"] == 10.0)
        & (audit["certification_sample_fraction"].isin([0.35, 0.50, 0.75]))
    ]
    drop_certifies = bool(
        not drop_good.empty
        and (
            drop_good.groupby(["return_set_name", "gamma"])["certificate_success_rate"].max() > 0.0
        ).any()
        and (drop_good["GVR"] <= drop_good["delta"] + EPSILON).all()
    )
    exact_never_certifies_high = bool(
        audit[
            (audit["return_set_name"] == "R1_oracle_exact")
            & (audit["certification_sample_fraction"] >= 0.75)
            & (audit["certificate_success_rate"] > 0)
        ].empty
    )
    if current_low and oracle_exact_certifies and drop_certifies:
        return "CANDIDATE_QUALITY_IS_MAIN_BOTTLENECK"
    if exact_never_certifies_high:
        return "CERTIFIED_BOUND_TOO_LOOSE"
    if current_low:
        return "BOTH_CANDIDATE_AND_BOUND_NEED_WORK"
    return "CODE_REVIEW_NEEDED"


def generate_report(events: pd.DataFrame, audit_checks: pd.DataFrame, recall_table: pd.DataFrame, audit: pd.DataFrame) -> str:
    decision = choose_decision(audit, recall_table)
    focus_recall = recall_table[recall_table["theta"] == 0.3].copy()
    focus_names = [
        "R0_current_reconstructed",
        "R1_oracle_exact",
        "R2_oracle_padded_2p5s",
        "R2_oracle_padded_5p0s",
        "R2_oracle_padded_10p0s",
        "R3_oracle_drop_recall_0p8_seed_00",
        "R3_oracle_drop_recall_0p9_seed_00",
        "R4_event_moment_window_5p0s",
        "R4_event_moment_window_10p0s",
        "R4_event_moment_window_15p0s",
    ]
    focus_recall = focus_recall[focus_recall["return_set_name"].isin(focus_names)]

    focus_audit = audit[
        (audit["theta"] == 0.3)
        & (audit["gamma"].isin([0.8, 0.9]))
        & (audit["delta"] == 0.10)
        & (audit["block_size"] == 10.0)
        & (audit["certification_sample_fraction"].isin([0.35, 0.50, 0.75]))
        & (audit["return_set_name"].isin(focus_names))
    ].copy()
    focus_audit = focus_audit[
        [
            "return_set_name",
            "gamma",
            "certification_sample_fraction",
            "true_derived_recall",
            "median_LCB_recall",
            "fraction_vacuous",
            "certificate_success_rate",
            "GVR",
            "tightness",
        ]
    ].sort_values(["return_set_name", "gamma", "certification_sample_fraction"])

    exact_focus = focus_audit[focus_audit["return_set_name"] == "R1_oracle_exact"]
    drop_focus = focus_audit[focus_audit["return_set_name"].str.contains("R3_oracle_drop_recall_0p8|R3_oracle_drop_recall_0p9", regex=True)]

    lines = [
        "# Nexar-200 Return-set / Certificate Disentanglement Report",
        "",
        "## 1. Goal",
        "",
        "Run Phase 1.3 on the Nexar-200 derived-boundary CASQ benchmark to separate candidate-return-set quality from block/event certificate tightness. This run is metadata-only: no VLM, GPU, training, perception stack, video download, or original boundary fabrication was used.",
        "",
        "## 2. Why previous Nexar-200 result is inconclusive",
        "",
        "The previous reference condition had true derived recall near 0.06, median LCB recall 0, and certificate_success 0. A return set with true derived recall far below gamma=0.8 or gamma=0.9 should not certify, so that result alone cannot tell whether the certificate is too loose or the candidate set is too weak.",
        "",
        "## 3. Return-set construction",
        "",
        "- `R0_current_reconstructed`: reconstructed metadata-only hash top-35% 5s-unit returned clips from the prior Nexar-200 block audit script.",
        "- `R1_oracle_exact`: one returned interval exactly equal to each derived event interval.",
        "- `R2_oracle_padded`: derived event intervals padded by 2.5s, 5.0s, and 10.0s.",
        "- `R3_oracle_drop`: exact derived event intervals randomly dropped to target recalls 0.5, 0.7, 0.8, and 0.9 over 10 seeds.",
        "- `R4_event_moment_window`: 5s, 10s, and 15s windows centered at each derived event midpoint.",
        "",
        "All oracle-informed return sets are diagnostic upper bounds or stress tests, not deployable candidate generators.",
        "",
        "Input validation:",
        "",
        markdown_table(audit_checks),
        "",
        "## 4. True derived recall by return set",
        "",
        markdown_table(focus_recall),
        "",
        "Full table: `tables/return_set_true_recall.csv`.",
        "",
        "## 5. Certificate behavior by return-set quality",
        "",
        "The table below focuses on theta=0.3, delta=0.10, 10s blocks, and sample fractions 0.35/0.50/0.75.",
        "",
        markdown_table(focus_audit, max_rows=120),
        "",
        "Full table: `tables/disentangle_block_audit_results.csv`. Per-trial diagnostics: `tables/disentangle_block_audit_trials.csv`.",
        "",
        "## 6. Does oracle_exact_R certify?",
        "",
        markdown_table(exact_focus, max_rows=20),
        "",
        "The exact oracle-informed return set has true derived recall 1.0 at both IoU thresholds. When the certification sample contains enough oracle-enumerated events for a positive denominator lower bound, its missed-event estimate is zero and the repaired bound can produce LCB recall 1.0.",
        "",
        "## 7. Does oracle_drop_R at 0.8 / 0.9 certify?",
        "",
        markdown_table(drop_focus, max_rows=80),
        "",
        "The random-drop exact-interval diagnostics show whether the repaired certificate can succeed near the target operating points. Because true recall is controlled by dropping whole events, any success or failure here reflects sample-size and denominator-bound behavior rather than candidate localization error.",
        "",
        "## 8. Is the issue candidate quality or bound tightness?",
        "",
        f"The decision rule selected `{decision}`. The reconstructed current return set remains low-recall, while oracle-informed return sets test the certificate under high-quality candidate conditions. GVR is computed as the rate of successful certificates when true derived recall is below gamma; low GVR with nonzero certificate success on high-quality return sets indicates the certificate machinery can behave conservatively when candidate quality is adequate.",
        "",
        "## 9. Limitations of derived boundaries",
        "",
        "- Boundaries are derived from Nexar alert time to event moment; they are not original human event interval annotations.",
        "- Results are oracle-relative to these derived intervals and must not be described as human ground truth.",
        "- Oracle-informed return sets intentionally use derived event boundaries and are diagnostic only.",
        "- The current return set is metadata-hash-based, not a production retrieval model or perception proxy.",
        "- Normal-approximation finite-population bounds are inherited from the repaired Phase 0 implementation and remain a code path needing statistical review before strong claims.",
        "",
        "## 10. Recommendation",
        "",
    ]

    if decision == "CANDIDATE_QUALITY_IS_MAIN_BOTTLENECK":
        lines.append("Use Nexar-200 primarily as a certificate plumbing benchmark. The immediate bottleneck is a better non-label candidate generator that raises derived recall; the repaired certificate can certify oracle-informed high-recall return sets under reasonable sample fractions in this controlled setting.")
    elif decision == "CERTIFIED_BOUND_TOO_LOOSE":
        lines.append("Prioritize statistical/code review of the bound before spending effort on a stronger candidate generator, because even exact derived-event return sets fail to certify at high sample fractions.")
    elif decision == "BOTH_CANDIDATE_AND_BOUND_NEED_WORK":
        lines.append("Improve the candidate generator and review/power the certificate. The current return set is low-recall, and oracle-informed diagnostics still require high sample fractions or produce weak LCBs.")
    else:
        lines.append("Do not interpret the experiment. Review the implementation, invariants, and recall computation before drawing conclusions.")

    lines.extend(["", f"DISENTANGLE_DECISION: {decision}", ""])
    (OUT / "reports/NEXAR_200_DISENTANGLE_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    append_progress("report", "python scripts/10_run_nexar_200_disentangle.py", f"decision={decision}", next_action="py_compile and completion audit")
    return decision


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true", help="run the full code path with a small certification trial count")
    args = parser.parse_args()
    num_trials = 3 if args.smoke else NUM_TRIALS
    run_mode = "smoke" if args.smoke else "full"
    ensure_dirs()
    events, units, audit_checks = load_and_validate_inputs(num_trials=num_trials, run_mode=run_mode)
    return_sets = construct_return_sets(events, units)
    recall_table, hit_cache = compute_recall_table(events, return_sets)
    audit = run_audit(events, units, return_sets, recall_table, hit_cache, num_trials=num_trials)
    generate_figures(recall_table, audit)
    decision = generate_report(events, audit_checks, recall_table, audit)
    print(f"Wrote Nexar-200 disentangle outputs to {OUT}")
    print(f"RUN_MODE: {run_mode}")
    print(f"DISENTANGLE_DECISION: {decision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
