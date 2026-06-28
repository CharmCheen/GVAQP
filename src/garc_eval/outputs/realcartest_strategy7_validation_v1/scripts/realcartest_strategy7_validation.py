#!/usr/bin/env python3
"""Realcartest Strategy 7 validation with an acceptance gate.

This script intentionally keeps selection policies label-free. Qwen labels and
event clusters are joined only inside evaluation/reporting functions.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


ROOT = Path("/qiuyeqing/llama_prl/G-ARC")
OUT = ROOT / "src/garc_eval/outputs/realcartest_strategy7_validation_v1"
PREV = ROOT / "src/garc_eval/outputs/realcartest_proxy_materialization_v1"
TABLES = OUT / "tables"
REPORTS = OUT / "reports"
LOGS = OUT / "logs"
CONFIG = OUT / "config"
MANIFEST = OUT / "data_manifest"
SCRIPTS = OUT / "scripts"
CONTACT_DIR = OUT / "inputs/contact_sheets"
RAW_GLM_DIR = OUT / "raw_outputs/glm_fixed_prompt"

FEATURE_PATH = PREV / "tables/realcartest_anchor_proxy_features_2fps.csv"
L3_EVAL_PATH = PREV / "tables/realcartest_l3_labeled_subset_eval.csv"
SCOUT_PATH = PREV / "tables/realcartest_high_selectivity_predicate_scout.csv"
FINAL_DECISION_PREV = PREV / "tables/final_decision.csv"
VIDEO_PATH = ROOT / "try_or_no/videos/realcartest.mp4"
PROMPT_PATH = ROOT / "src/garc_eval/outputs/prompt_tuning_v1/prompts/BEST_glm_final.md"
MODEL_PATHS = ROOT / "garc_eval/outputs/glm41v_vs_qwen32b_oracle_pilot_v1/config/model_paths.yaml"
DECODING_CONFIG = ROOT / "garc_eval/outputs/glm41v_vs_qwen32b_oracle_pilot_v1/config/decoding_config.yaml"

DATASET3_CANON = ROOT / "src/garc_eval/outputs/codex_recompute_proxy_budget_basa_v1/tables/canonical_dataset3_anchor_table.csv"
DATASET3_STRAT7 = ROOT / "src/garc_eval/outputs/post_transition_strategy7_audit_v1/tables/strategy7_budget_curve.csv"
DATASET3_CLEAN_CASCADE = ROOT / "src/garc_eval/outputs/prompt_tuning_v1/heldout_cascade_eval_v1/tables/cascade_simulation_results_clean.csv"

BUDGETS = [20, 30, 40, 60, 80, 100, 150]
SEEDS = [202606270000 + i for i in range(500)]
POSITIVE_LABELS = {"positive", "true", "1", "yes"}
GLM_POS_UNC = {"positive", "uncertain"}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_dirs() -> None:
    for d in [TABLES, REPORTS, LOGS, CONFIG, MANIFEST, SCRIPTS, CONTACT_DIR, RAW_GLM_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def append_progress(message: str) -> None:
    ensure_dirs()
    with (LOGS / "progress.md").open("a", encoding="utf-8") as f:
        f.write(f"- {utc_now()} {message}\n")
    print(message, flush=True)


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def as_bool_series(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s.fillna(False)
    return s.astype(str).str.lower().isin(POSITIVE_LABELS)


def auc_rank(y_true: Iterable[bool], scores: Iterable[float]) -> float:
    y = np.asarray(list(y_true), dtype=bool)
    x = np.asarray(list(scores), dtype=float)
    valid = ~np.isnan(x)
    y = y[valid]
    x = x[valid]
    n_pos = int(y.sum())
    n_neg = int((~y).sum())
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    order = np.argsort(x)
    ranks = np.empty(len(x), dtype=float)
    sorted_x = x[order]
    i = 0
    while i < len(x):
        j = i + 1
        while j < len(x) and sorted_x[j] == sorted_x[i]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        ranks[order[i:j]] = avg_rank
        i = j
    rank_sum_pos = ranks[y].sum()
    return float((rank_sum_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


def order_by_l3(df: pd.DataFrame) -> list[int]:
    ordered = df.sort_values(
        ["object_count_mean", "anchor_timestamp", "anchor_id"],
        ascending=[False, True, True],
        kind="mergesort",
    )
    return ordered.index.tolist()


def top_l3_indices(df: pd.DataFrame, n: int) -> list[int]:
    return order_by_l3(df)[: min(n, len(df))]


def maxmin_temporal_from_candidates(df: pd.DataFrame, budget: int, pool_factor: int = 2) -> list[int]:
    pool_n = min(len(df), max(budget, pool_factor * budget))
    pool = top_l3_indices(df, pool_n)
    if budget >= len(pool):
        return pool
    times = df.loc[pool, "anchor_timestamp"].astype(float).to_dict()
    scores = df.loc[pool, "object_count_mean"].astype(float).to_dict()
    selected = [pool[0]]
    remaining = set(pool[1:])
    while len(selected) < budget and remaining:
        def key(idx: int) -> tuple[float, float, float, str]:
            min_dist = min(abs(times[idx] - times[j]) for j in selected)
            return (min_dist, scores[idx], -times[idx], str(df.at[idx, "anchor_id"]))
        best = max(remaining, key=key)
        selected.append(best)
        remaining.remove(best)
    return selected


def event_cluster_set(df: pd.DataFrame) -> set[str]:
    if "event_cluster_id" not in df.columns:
        return set()
    vals = df.loc[df["is_positive_bool"], "event_cluster_id"].dropna().astype(str)
    return {v for v in vals if v and v.lower() not in {"nan", "-1", "none"}}


def selected_metrics(
    df: pd.DataFrame,
    selected: list[int],
    budget: int,
    strategy: str,
    seed: int | None = None,
    audit_indices: list[int] | None = None,
    l3_reference: set[int] | None = None,
) -> dict[str, Any]:
    sel = df.loc[selected]
    pos_mask = sel["is_positive_bool"].astype(bool)
    total_pos = int(df["is_positive_bool"].sum())
    selected_pos = int(pos_mask.sum())
    precision = selected_pos / len(sel) if len(sel) else float("nan")
    anchor_recall = selected_pos / total_pos if total_pos else float("nan")
    all_clusters = event_cluster_set(df)
    selected_clusters = event_cluster_set(sel.assign(is_positive_bool=pos_mask))
    event_recall = len(selected_clusters) / len(all_clusters) if all_clusters else float("nan")
    singleton_recall = float("nan")
    if "singleton_flag" in df.columns:
        denom = int((df["is_positive_bool"] & df["singleton_flag_bool"]).sum())
        num = int((sel["is_positive_bool"] & sel["singleton_flag_bool"]).sum())
        singleton_recall = num / denom if denom else float("nan")
    l3_reference = l3_reference or set(top_l3_indices(df, budget))
    l3_missed_pos = set(df.index[df["is_positive_bool"]]) - set(l3_reference)
    recovered_missed = set(selected) & l3_missed_pos
    audit_hit_rate = float("nan")
    audit_positive_count = 0
    if audit_indices is not None and len(audit_indices) > 0:
        audit_positive_count = int(df.loc[audit_indices, "is_positive_bool"].sum())
        audit_hit_rate = audit_positive_count / len(audit_indices)
    return {
        "strategy": strategy,
        "B": budget,
        "seed": seed if seed is not None else "",
        "selected_count": len(selected),
        "selected_positive_count": selected_pos,
        "precision": precision,
        "positive_yield": selected_pos / budget if budget else float("nan"),
        "anchor_recall": anchor_recall,
        "event_cluster_recall": event_recall,
        "singleton_recall": singleton_recall,
        "l3_missed_positive_total": len(l3_missed_pos),
        "l3_missed_positive_recovered_count": len(recovered_missed),
        "l3_missed_positive_recovery": len(recovered_missed) / len(l3_missed_pos) if l3_missed_pos else float("nan"),
        "audit_count": len(audit_indices) if audit_indices is not None else 0,
        "audit_positive_count": audit_positive_count,
        "audit_hit_rate": audit_hit_rate,
        "deployable_selection_uses_qwen_or_event_cluster": False,
    }


def summarize_seed_rows(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    group_cols = ["strategy", "B"]
    metric_cols = [
        "selected_count", "selected_positive_count", "precision", "positive_yield",
        "anchor_recall", "event_cluster_recall", "singleton_recall",
        "l3_missed_positive_total", "l3_missed_positive_recovered_count",
        "l3_missed_positive_recovery", "audit_count", "audit_positive_count", "audit_hit_rate",
    ]
    out = []
    for (strategy, budget), g in df.groupby(group_cols, sort=False):
        row: dict[str, Any] = {
            "strategy": strategy,
            "B": budget,
            "n_seeds": int(g["seed"].replace("", np.nan).dropna().shape[0]) if "seed" in g else 0,
        }
        for col in metric_cols:
            vals = pd.to_numeric(g[col], errors="coerce")
            row[f"mean_{col}"] = float(vals.mean()) if vals.notna().any() else float("nan")
            row[f"std_{col}"] = float(vals.std(ddof=1)) if vals.notna().sum() > 1 else 0.0
            row[f"ci95_halfwidth_{col}"] = 1.96 * row[f"std_{col}"] / math.sqrt(len(vals.dropna())) if vals.notna().sum() > 1 else 0.0
        out.append(row)
    return pd.DataFrame(out)


def load_realcartest_features() -> pd.DataFrame:
    df = pd.read_csv(FEATURE_PATH)
    df["is_positive_bool"] = as_bool_series(df["is_positive"])
    if "singleton_flag" in df.columns:
        df["singleton_flag_bool"] = as_bool_series(df["singleton_flag"])
    else:
        df["singleton_flag_bool"] = False
    return df


def phase0_acceptance() -> str:
    append_progress("Phase 0: acceptance audit started.")
    required = [
        "FINAL_SUMMARY.md",
        "RUN_LOG.md",
        "reports/INPUT_INVENTORY.md",
        "reports/SMOKE_TEST_REPORT.md",
        "reports/FULL_RUN_REPORT.md",
        "reports/ANCHOR_FEATURE_REPORT.md",
        "reports/FEASIBILITY_AUDIT_REPORT.md",
        "tables/realcartest_anchor_proxy_features_2fps.csv",
        "tables/realcartest_l3_labeled_subset_eval.csv",
        "tables/realcartest_high_selectivity_predicate_scout.csv",
        "tables/final_decision.csv",
    ]
    checks: list[dict[str, Any]] = []
    missing = []
    for rel in required:
        exists = (PREV / rel).exists()
        checks.append({"check": f"file_exists:{rel}", "status": "PASS" if exists else "FAIL", "raw_value": str(exists), "condition": "required file exists"})
        if not exists:
            missing.append(rel)

    final_summary = read_text(PREV / "FINAL_SUMMARY.md")
    input_inventory = read_text(PREV / "reports/INPUT_INVENTORY.md")
    run_log = read_text(PREV / "RUN_LOG.md")
    feature_report = read_text(PREV / "reports/ANCHOR_FEATURE_REPORT.md")
    scout_report = read_text(PREV / "reports/FEASIBILITY_AUDIT_REPORT.md")
    combined_text = "\n".join([final_summary, input_inventory, feature_report, scout_report])

    label_prov_ok = all(x in combined_text for x in ["Qwen3-VL-32B", "V13.6", "O_enter_ego_path_v0"])
    dataset3_query_evidence = "O_enter_ego_path_v0" in read_text(DATASET3_CANON.parent.parent / "reports/INPUT_INVENTORY.md") or DATASET3_CANON.exists()
    label_status = "PASS" if label_prov_ok and dataset3_query_evidence else "LIMITED"
    checks.append({
        "check": "label_provenance",
        "status": label_status,
        "raw_value": "Qwen3-VL-32B/V13.6/O_enter_ego_path_v0" if label_prov_ok else "missing provenance tokens",
        "condition": "V13.8 labels must be Qwen3-VL-32B V13.6 O_enter_ego_path_v0 and comparable to dataset3 query",
    })

    window_confirmed = ("center_time_s +/- 5 s" in combined_text or "anchor_time +/- 5 s" in combined_text) and "fallback" not in combined_text.lower()
    checks.append({
        "check": "dataset3_window_definition",
        "status": "PASS" if window_confirmed else "LIMITED",
        "raw_value": "confirmed center_time_s/anchor_time +/- 5 s" if window_confirmed else "WINDOW_DEFINITION_FALLBACK_USED",
        "condition": "dataset3 object_count_mean window found and realcartest uses same window, or fallback explicitly marked",
    })

    run_log_lower = run_log.lower()
    run_log_phase_count = run_log_lower.count("phase")
    run_log_decision_count = run_log_lower.count("decision")
    run_log_unattended_decision = (
        "output directory decision" in run_log_lower
        and ("decision tendency" in run_log_lower or "final decision" in run_log_lower)
    )
    run_log_complete = bool(run_log) and run_log_phase_count >= 5 and run_log_decision_count >= 3 and run_log_unattended_decision
    checks.append({
        "check": "run_log_completeness",
        "status": "PASS" if run_log_complete else "FAIL",
        "raw_value": f"phase_mentions={run_log_phase_count}, decision_mentions={run_log_decision_count}, unattended_decision_recorded={run_log_unattended_decision}" if run_log_complete else "RUN_LOG_INCOMPLETE",
        "condition": "RUN_LOG exists, records phases, and records unattended autonomous decisions",
    })

    scout_df = pd.read_csv(SCOUT_PATH) if SCOUT_PATH.exists() else pd.DataFrame()
    scout_ok = (
        not scout_df.empty
        and "circular_definition_warning" in scout_df
        and set(scout_df["circular_definition_warning"].astype(str).str.upper()) == {"NONE"}
        and "positive_definition" in scout_df
        and scout_df["positive_definition"].astype(str).str.contains("Qwen", case=False, na=False).all()
    )
    checks.append({
        "check": "high_selectivity_scout",
        "status": "PASS" if scout_ok else "FAIL",
        "raw_value": f"rows={len(scout_df)}, circular={sorted(set(scout_df.get('circular_definition_warning', pd.Series(dtype=str)).astype(str)))}",
        "condition": "CIRCULAR_DEFINITION_WARNING absent/NONE and positives are existing Qwen oracle labels",
    })

    features_ok = False
    labels_ok = False
    warning_rows = None
    auc = float("nan")
    pos_n = neg_n = row_n = 0
    if FEATURE_PATH.exists():
        df = load_realcartest_features()
        row_n = len(df)
        pos_n = int(df["is_positive_bool"].sum())
        neg_n = row_n - pos_n
        warning_rows = int(df["proxy_feature_warning"].notna().sum()) if "proxy_feature_warning" in df else None
        required_cols = {"object_count_mean", "vehicle_count_mean", "person_count_mean", "qwen_label"}
        features_ok = row_n == 399 and required_cols.issubset(df.columns) and warning_rows == 0
        labels_ok = row_n == 399 and pos_n == 94 and neg_n == 305
        auc = auc_rank(df["is_positive_bool"], df["object_count_mean"])
    checks.append({
        "check": "raw_feature_sanity",
        "status": "PASS" if features_ok and labels_ok else "FAIL",
        "raw_value": f"rows={row_n}, positive={pos_n}, negative={neg_n}, feature_warning_rows={warning_rows}, object_count_mean_auc={auc:.6f}",
        "condition": "399 rows, 94 positive, 305 negative, required proxy columns present, feature warnings 0",
    })

    if missing or not features_ok or not labels_ok or not scout_ok or not run_log_complete:
        decision = "REJECT_REALCARTEST_FOR_STRATEGY7_VALIDATION"
    elif label_status == "PASS" and window_confirmed:
        decision = "ACCEPT_REALCARTEST_FOR_STRICT_SECOND_VIDEO_VALIDATION"
    else:
        decision = "ACCEPT_REALCARTEST_WITH_COMPARABILITY_LIMITATIONS"

    checks.append({
        "check": "acceptance_decision",
        "status": decision,
        "raw_value": f"missing_files={missing}; label_status={label_status}; window_confirmed={window_confirmed}",
        "condition": "decision enum from task acceptance gate",
    })
    pd.DataFrame(checks).to_csv(TABLES / "acceptance_audit_summary.csv", index=False)

    lines = [
        "# Acceptance Audit",
        "",
        f"- Output timestamp: {utc_now()}",
        f"- Previous output directory: `{PREV}`",
        f"- Acceptance decision: `{decision}`",
        "",
        "## Required File Checks",
        "",
        "| check | status | raw value | condition |",
        "|---|---:|---|---|",
    ]
    for row in checks:
        lines.append(f"| {row['check']} | {row['status']} | {row['raw_value']} | {row['condition']} |")
    lines.extend([
        "",
        "## Deployable vs Evaluation Boundary",
        "",
        "- Deployable policy inputs for later phases are `anchor_id`, timestamp, cheap proxy scores, and GLM parsed labels.",
        "- Existing Qwen labels and `event_cluster_id` are used only for evaluation metrics in this validation.",
        "",
        "## Comparability Notes",
        "",
        "- Label provenance is accepted only because the prior materialization reports V13.8 Qwen3-VL-32B with the V13.6 `O_enter_ego_path_v0` prompt.",
        "- Window comparability is accepted only because dataset3 and realcartest both report a 10s center window, `center_time_s`/`anchor_time` +/- 5s.",
        "- The high-selectivity scout is not treated as oracle-relative evidence beyond its existing Qwen-label evaluation columns.",
    ])
    write_text(REPORTS / "ACCEPTANCE_AUDIT.md", "\n".join(lines) + "\n")
    append_progress(f"Phase 0 complete: {decision}.")
    return decision


def phase1_l3_replay(df: pd.DataFrame) -> pd.DataFrame:
    append_progress("Phase 1: L3 baseline replay started.")
    rows: list[dict[str, Any]] = []
    for budget in BUDGETS:
        l3 = top_l3_indices(df, budget)
        rows.append(selected_metrics(df, l3, budget, "L3_object_count_mean"))
        temporal = maxmin_temporal_from_candidates(df, budget)
        rows.append(selected_metrics(df, temporal, budget, "L3_temporal_maxmin"))
        for seed in SEEDS:
            rng = np.random.default_rng(seed)
            selected = rng.choice(df.index.to_numpy(), size=min(budget, len(df)), replace=False).tolist()
            rows.append(selected_metrics(df, selected, budget, "uniform_random", seed=seed))
    raw = pd.DataFrame(rows)
    summary = summarize_seed_rows(rows)
    deterministic = raw[raw["seed"].astype(str) == ""].copy()
    deterministic["n_seeds"] = 0
    deterministic = deterministic.rename(columns={c: f"mean_{c}" for c in deterministic.columns if c not in ["strategy", "B", "n_seeds"]})
    for col in list(deterministic.columns):
        if col.startswith("mean_"):
            deterministic["std_" + col[5:]] = 0.0
            deterministic["ci95_halfwidth_" + col[5:]] = 0.0
    out = pd.concat([deterministic, summary], ignore_index=True, sort=False)
    out.to_csv(TABLES / "realcartest_l3_replay_results.csv", index=False)

    pos_rate = df["is_positive_bool"].mean()
    l3_rows = out[out["strategy"] == "L3_object_count_mean"].sort_values("B")
    lines = [
        "# Realcartest L3 Baseline Report",
        "",
        f"- Output timestamp: {utc_now()}",
        f"- Candidate universe: {len(df)} anchors.",
        f"- Existing V13.8 positives: {int(df['is_positive_bool'].sum())}; negatives: {len(df) - int(df['is_positive_bool'].sum())}.",
        f"- Realcartest positive rate: {pos_rate:.6f} ({int(df['is_positive_bool'].sum())}/{len(df)}).",
        f"- `object_count_mean` AUC: {auc_rank(df['is_positive_bool'], df['object_count_mean']):.6f}.",
        "- Dataset3 clean-pool positive rate is not directly comparable to this full realcartest anchor universe.",
        "",
        "## Policy Boundary",
        "",
        "- `L3_object_count_mean` sorts by `object_count_mean` descending with timestamp/anchor-id tie breaks; no labels are used.",
        "- `L3_temporal_maxmin` first forms a top `2B` cheap-proxy candidate pool, then greedily maximizes timestamp spread; no labels are used.",
        "- `uniform_random` uses 500 fixed seeds and no labels.",
        "",
        "## L3 Object Count Curve",
        "",
        "| B | selected positives | precision | anchor recall | event recall | L3-missed positives |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in l3_rows.iterrows():
        lines.append(
            f"| {int(r['B'])} | {r['mean_selected_positive_count']:.3f} | {r['mean_precision']:.6f} | "
            f"{r['mean_anchor_recall']:.6f} | {r['mean_event_cluster_recall']:.6f} | {r['mean_l3_missed_positive_total']:.3f} |"
        )
    write_text(REPORTS / "REALCARTEST_L3_BASELINE_REPORT.md", "\n".join(lines) + "\n")
    append_progress("Phase 1 complete: wrote L3 baseline replay results.")
    return out


def build_contact_sheets(df: pd.DataFrame) -> pd.DataFrame:
    import cv2
    from PIL import Image, ImageDraw, ImageFont

    append_progress("Phase 2: building or verifying lightweight contact sheets.")
    cap = cv2.VideoCapture(str(VIDEO_PATH))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {VIDEO_PATH}")
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0.0
    cell_w, cell_h = 480, 270
    label_h = 24
    rel_ts = [0.0, 2.0, 4.0, 6.0, 8.0]
    grid_cols = 5
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    except Exception:
        font = ImageFont.load_default()

    def frame_at(t: float) -> np.ndarray:
        idx = int(max(0, min(total_frames - 1, round(t * fps))))
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if not ok:
            return np.zeros((cell_h, cell_w, 3), dtype=np.uint8)
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    rows = []
    for i, row in df.iterrows():
        aid = str(row["anchor_id"])
        center = float(row["anchor_timestamp"])
        start = max(0.0, center - 5.0)
        end = min(duration, center + 5.0)
        actual = [min(end, start + t) for t in rel_ts]
        out_path = CONTACT_DIR / f"{aid}.jpg"
        if not out_path.exists():
            sheet = Image.new("RGB", (grid_cols * cell_w, cell_h + label_h), (40, 40, 40))
            draw = ImageDraw.Draw(sheet)
            for j, ts in enumerate(actual):
                frame = Image.fromarray(frame_at(ts)).resize((cell_w, cell_h), Image.LANCZOS)
                x = j * cell_w
                sheet.paste(frame, (x, 0))
                label = f"{ts:.1f}s"
                bbox = draw.textbbox((0, 0), label, font=font)
                tx = x + (cell_w - (bbox[2] - bbox[0])) // 2
                draw.text((tx, cell_h + 2), label, fill=(220, 220, 220), font=font)
            sheet.save(out_path, quality=92)
        rows.append({
            "anchor_id": aid,
            "anchor_timestamp": center,
            "start_time_s": start,
            "end_time_s": end,
            "contact_sheet_path": str(out_path),
            "actual_timestamps": ",".join(f"{x:.2f}" for x in actual),
        })
        if (i + 1) % 50 == 0:
            append_progress(f"Phase 2 contact sheets checked/built: {i + 1}/{len(df)}.")
    cap.release()
    manifest = pd.DataFrame(rows)
    manifest.to_csv(MANIFEST / "realcartest_glm_contact_sheet_manifest.csv", index=False)
    return manifest


def parse_glm_label(raw: str) -> dict[str, Any]:
    jsons = re.findall(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", raw or "")
    for j_str in reversed(jsons):
        try:
            j = json.loads(j_str)
            if "event_label" in j:
                return j
        except Exception:
            continue
    ans = re.search(r"<answer>(.*?)</answer>", raw or "", re.DOTALL)
    if ans:
        return parse_glm_label(ans.group(1))
    return {"event_label": "parse_error"}


def normalize_glm_label(label: Any) -> str:
    s = str(label).strip().lower()
    if s in {"positive", "negative", "uncertain"}:
        return s
    return "parse_error"


def find_existing_realcartest_glm(df: pd.DataFrame) -> Path | None:
    candidates = list(ROOT.glob("src/garc_eval/outputs/**/tables/*realcartest*glm*outputs*.csv"))
    candidates += list(ROOT.glob("garc_eval/outputs/**/tables/*realcartest*glm*outputs*.csv"))
    expected = set(df["anchor_id"].astype(str))
    for p in candidates:
        if p == TABLES / "realcartest_glm_fixed_prompt_outputs.csv":
            continue
        try:
            t = pd.read_csv(p)
        except Exception:
            continue
        if "anchor_id" not in t.columns:
            continue
        if set(t["anchor_id"].astype(str)) >= expected and any(c in t.columns for c in ["parsed_label", "glm_pred"]):
            return p
    return None


def load_yaml_simple(path: Path) -> dict[str, Any]:
    try:
        import yaml
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        out: dict[str, Any] = {}
        for line in read_text(path).splitlines():
            if ":" in line and not line.lstrip().startswith("#"):
                k, v = line.split(":", 1)
                out[k.strip()] = v.strip()
        return out


def phase2_glm(df: pd.DataFrame, skip_glm: bool = False) -> tuple[pd.DataFrame | None, str]:
    append_progress("Phase 2: GLM fixed-prompt materialization started.")
    table_out = TABLES / "realcartest_glm_fixed_prompt_outputs.csv"
    if table_out.exists():
        existing = pd.read_csv(table_out)
        if set(existing.get("anchor_id", pd.Series(dtype=str)).astype(str)) >= set(df["anchor_id"].astype(str)):
            append_progress("Phase 2: reusing current realcartest GLM output table.")
            write_glm_report(existing, reused=True, blocked_reason="")
            return existing, "available"
    external = find_existing_realcartest_glm(df)
    if external:
        existing = pd.read_csv(external)
        if "parsed_label" not in existing and "glm_pred" in existing:
            existing["parsed_label"] = existing["glm_pred"]
        existing.to_csv(table_out, index=False)
        append_progress(f"Phase 2: reused external realcartest GLM outputs from {external}.")
        write_glm_report(existing, reused=True, blocked_reason="")
        return existing, "available"
    if skip_glm:
        reason = "No existing realcartest GLM outputs and --skip-glm was set."
        write_glm_report(pd.DataFrame(), reused=False, blocked_reason=reason)
        append_progress(f"Phase 2 blocked: {reason}")
        return None, "blocked"

    if not PROMPT_PATH.exists():
        reason = f"Frozen prompt missing: {PROMPT_PATH}"
        write_glm_report(pd.DataFrame(), reused=False, blocked_reason=reason)
        append_progress(f"Phase 2 blocked: {reason}")
        return None, "blocked"

    try:
        manifest = build_contact_sheets(df)
    except Exception as exc:
        reason = f"Contact sheet evidence unavailable: {exc}"
        write_glm_report(pd.DataFrame(), reused=False, blocked_reason=reason)
        append_progress(f"Phase 2 blocked: {reason}")
        return None, "blocked"

    missing_contact = [p for p in manifest["contact_sheet_path"] if not Path(p).exists()]
    if missing_contact:
        reason = f"Missing contact sheets: {len(missing_contact)}"
        write_glm_report(pd.DataFrame(), reused=False, blocked_reason=reason)
        append_progress(f"Phase 2 blocked: {reason}")
        return None, "blocked"

    prompt_text = PROMPT_PATH.read_text(encoding="utf-8")
    model_paths = load_yaml_simple(MODEL_PATHS)
    dec_cfg = load_yaml_simple(DECODING_CONFIG)
    model_path = model_paths.get("glm41v")
    if not model_path:
        reason = f"GLM model path missing from {MODEL_PATHS}"
        write_glm_report(pd.DataFrame(), reused=False, blocked_reason=reason)
        append_progress(f"Phase 2 blocked: {reason}")
        return None, "blocked"

    append_progress("Phase 2: loading GLM-4.1V local model for deterministic fixed-prompt inference.")
    try:
        import torch
        from PIL import Image
        from transformers import Glm4vForConditionalGeneration, Glm4vProcessor
    except Exception as exc:
        reason = f"GLM runtime imports failed: {exc}"
        write_glm_report(pd.DataFrame(), reused=False, blocked_reason=reason)
        append_progress(f"Phase 2 blocked: {reason}")
        return None, "blocked"

    t0 = time.time()
    try:
        model = Glm4vForConditionalGeneration.from_pretrained(
            model_path,
            torch_dtype=torch.bfloat16,
            device_map="auto",
            local_files_only=True,
        )
        processor = Glm4vProcessor.from_pretrained(model_path, local_files_only=True)
    except Exception as exc:
        reason = f"GLM model load failed: {exc}"
        write_glm_report(pd.DataFrame(), reused=False, blocked_reason=reason)
        append_progress(f"Phase 2 blocked: {reason}")
        return None, "blocked"
    append_progress(f"Phase 2: GLM model loaded in {time.time() - t0:.1f}s.")

    rows = []
    # The frozen BEST prompt used by the existing GLM pilot is verbose enough
    # that 768 tokens can truncate before the final JSON. Keep the prompt fixed
    # and use the established pilot cap instead of treating truncation as a
    # model label.
    max_tokens = max(2048, int(dec_cfg.get("max_new_tokens", 768)))
    temperature = float(dec_cfg.get("temperature", 0.0))
    do_sample = str(dec_cfg.get("do_sample", "false")).lower() == "true" if isinstance(dec_cfg.get("do_sample"), str) else bool(dec_cfg.get("do_sample", False))
    top_p = float(dec_cfg.get("top_p", 1.0))
    for i, row in manifest.iterrows():
        aid = str(row["anchor_id"])
        out_json = RAW_GLM_DIR / f"{aid}.json"
        use_cache = False
        if out_json.exists():
            cached = json.loads(out_json.read_text(encoding="utf-8"))
            raw = cached.get("raw_output", "")
            parsed = cached.get("parsed", parse_glm_label(raw))
            latency = float(cached.get("latency", cached.get("latency_s", 0.0)))
            output_tokens = int(cached.get("output_token_count", cached.get("output_tokens", 0)))
            timestamp = cached.get("timestamp", "")
            cached_limit = int(cached.get("decoding", {}).get("max_new_tokens", cached.get("max_new_tokens", 0) or 0))
            cached_label = normalize_glm_label(parsed.get("event_label", "parse_error"))
            cache_is_truncated_parse_error = cached_label == "parse_error" and cached_limit and output_tokens >= cached_limit and cached_limit < max_tokens
            use_cache = not cache_is_truncated_parse_error
        if not use_cache:
            image = Image.open(row["contact_sheet_path"]).convert("RGB")
            messages = [{"role": "user", "content": [{"type": "image", "image": image}, {"type": "text", "text": prompt_text}]}]
            text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = processor(text=[text], images=[image], padding=True, return_tensors="pt")
            inputs = {k: v.to(model.device) for k, v in inputs.items()}
            input_len = inputs["input_ids"].shape[1]
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            t1 = time.time()
            with torch.no_grad():
                gen_ids = model.generate(
                    **inputs,
                    max_new_tokens=max_tokens,
                    temperature=temperature,
                    do_sample=do_sample,
                    top_p=top_p,
                )
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            latency = time.time() - t1
            gen_trimmed = gen_ids[0][input_len:]
            raw = processor.decode(gen_trimmed, skip_special_tokens=True)
            output_tokens = int(len(gen_trimmed))
            parsed = parse_glm_label(raw)
            timestamp = utc_now()
            out_json.write_text(json.dumps({
                "anchor_id": aid,
                "raw_output": raw,
                "parsed": parsed,
                "latency": latency,
                "output_token_count": output_tokens,
                "prompt_path": str(PROMPT_PATH),
                "model_name": "GLM-4.1V",
                "model_path": str(model_path),
                "timestamp": timestamp,
                "decoding": {
                    "temperature": temperature,
                    "do_sample": do_sample,
                    "top_p": top_p,
                    "max_new_tokens": max_tokens,
                },
            }, indent=2), encoding="utf-8")
        parsed_label = normalize_glm_label(parsed.get("event_label", "parse_error"))
        rows.append({
            "anchor_id": aid,
            "raw_output": raw,
            "parsed_label": parsed_label,
            "confidence": parsed.get("confidence"),
            "latency": round(latency, 3),
            "output_token_count": output_tokens,
            "prompt_path": str(PROMPT_PATH),
            "model_name": "GLM-4.1V",
            "timestamp": timestamp,
            "deterministic_decoding": (temperature == 0.0 and not do_sample),
            "contact_sheet_path": row["contact_sheet_path"],
            "primary_actor_type": parsed.get("primary_actor_type"),
            "interaction_type": parsed.get("interaction_type"),
            "ego_relevant": parsed.get("ego_relevant"),
        })
        if (i + 1) % 10 == 0:
            partial = pd.DataFrame(rows)
            partial.to_csv(table_out, index=False)
            append_progress(f"Phase 2 GLM processed: {i + 1}/{len(manifest)} anchors.")
    glm = pd.DataFrame(rows)
    glm.to_csv(table_out, index=False)
    write_glm_report(glm, reused=False, blocked_reason="")
    append_progress("Phase 2 complete: GLM fixed-prompt outputs materialized.")
    return glm, "available"


def write_glm_report(glm: pd.DataFrame, reused: bool, blocked_reason: str) -> None:
    if blocked_reason:
        lines = [
            "# Realcartest GLM Fixed Prompt Report",
            "",
            f"- Output timestamp: {utc_now()}",
            "- GLM status: BLOCKED",
            f"- Blocked reason: {blocked_reason}",
            "- No Qwen/final oracle was called.",
            "- No YOLO was called.",
        ]
        write_text(REPORTS / "REALCARTEST_GLM_FIXED_PROMPT_REPORT.md", "\n".join(lines) + "\n")
        return
    labels = glm["parsed_label"].astype(str).str.lower() if "parsed_label" in glm else pd.Series(dtype=str)
    lats = pd.to_numeric(glm.get("latency", pd.Series(dtype=float)), errors="coerce")
    positive = int((labels == "positive").sum())
    negative = int((labels == "negative").sum())
    uncertain = int((labels == "uncertain").sum())
    parse_error = int((labels == "parse_error").sum())
    parse_success = len(glm) - parse_error
    mean_lat = float(lats[lats > 0].mean()) if (lats > 0).any() else float("nan")
    p95_lat = float(lats[lats > 0].quantile(0.95)) if (lats > 0).any() else float("nan")
    deterministic = bool(glm.get("deterministic_decoding", pd.Series([True])).fillna(True).all()) if len(glm) else True
    lines = [
        "# Realcartest GLM Fixed Prompt Report",
        "",
        f"- Output timestamp: {utc_now()}",
        f"- Reused existing realcartest GLM outputs: {str(reused).lower()}",
        f"- Prompt path: `{PROMPT_PATH}`",
        "- Prompt status: frozen/best prompt (`BEST_glm_final.md`).",
        "- Model name: GLM-4.1V.",
        f"- Deterministic decoding: {str(deterministic).lower()}.",
        "- No Qwen/final oracle was called.",
        "- No YOLO was called.",
        "",
        "## Counts",
        "",
        f"- Processed anchors: {len(glm)}.",
        f"- Parse success: {parse_success}.",
        f"- Positive count: {positive}.",
        f"- Uncertain count: {uncertain}.",
        f"- Negative count: {negative}.",
        f"- Parse error count: {parse_error}.",
        f"- Mean latency: {mean_lat:.3f}s.",
        f"- P95 latency: {p95_lat:.3f}s.",
    ]
    write_text(REPORTS / "REALCARTEST_GLM_FIXED_PROMPT_REPORT.md", "\n".join(lines) + "\n")


def phase3_groups(df: pd.DataFrame, glm: pd.DataFrame) -> pd.DataFrame:
    append_progress("Phase 3: constructing pre-registered disagreement groups.")
    g = glm[["anchor_id", "parsed_label"]].copy()
    merged = df.merge(g, on="anchor_id", how="left")
    merged["parsed_label"] = merged["parsed_label"].fillna("parse_error").astype(str).str.lower()
    q75 = float(merged["object_count_mean"].quantile(0.75))
    median = float(merged["object_count_mean"].median())
    l3_top_by_budget = {b: set(top_l3_indices(df, b)) for b in BUDGETS}
    masks = {
        "L3_high_GLM_negative": (merged["object_count_mean"] >= q75) & (merged["parsed_label"] == "negative"),
        "L3_low_GLM_positive_or_uncertain": (merged["object_count_mean"] <= median) & (merged["parsed_label"].isin(GLM_POS_UNC)),
        "object_count_low_GLM_positive_or_uncertain": (merged["object_count_mean"] < median) & (merged["parsed_label"].isin(GLM_POS_UNC)),
        "GLM_positive_or_uncertain": merged["parsed_label"].isin(GLM_POS_UNC),
        "GLM_negative": merged["parsed_label"] == "negative",
    }
    base_rate = float(merged["is_positive_bool"].mean())
    rows = []
    for name, mask in masks.items():
        idx = set(merged.index[mask])
        group = merged.loc[list(idx)] if idx else merged.iloc[0:0]
        pos = int(group["is_positive_bool"].sum())
        size = len(group)
        row: dict[str, Any] = {
            "group": name,
            "group_size": size,
            "qwen_positive_count": pos,
            "positive_rate": pos / size if size else float("nan"),
            "base_positive_rate": base_rate,
            "enrichment_vs_base_rate": (pos / size) / base_rate if size and base_rate else float("nan"),
            "contains_l3_missed_positives_B20": int(len(idx & (set(merged.index[merged["is_positive_bool"]]) - l3_top_by_budget[20])) > 0),
            "l3_missed_positive_count_B20": len(idx & (set(merged.index[merged["is_positive_bool"]]) - l3_top_by_budget[20])),
            "deployable_group_definition_uses_qwen_or_event_cluster": False,
            "evaluation_uses_existing_qwen_and_event_cluster": True,
        }
        for b, top in l3_top_by_budget.items():
            row[f"overlap_with_L3_top_{b}"] = len(idx & top)
        rows.append(row)
    groups = pd.DataFrame(rows)
    groups.to_csv(TABLES / "realcartest_strategy7_disagreement_groups.csv", index=False)

    lines = [
        "# Realcartest Disagreement Group Report",
        "",
        f"- Output timestamp: {utc_now()}",
        f"- High threshold: top 25% `object_count_mean`, implemented as >= q75={q75:.6f}.",
        f"- Low threshold: bottom 50% `object_count_mean`, implemented as <= median={median:.6f}.",
        "- Thresholds were pre-registered and not tuned using Qwen labels.",
        "- Group construction uses cheap proxy score and GLM parsed label only.",
        "- Qwen labels and event clusters are evaluation-only.",
        "",
        "| group | size | Qwen positives | positive rate | enrichment | L3-missed positives B20 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for _, r in groups.iterrows():
        lines.append(
            f"| {r['group']} | {int(r['group_size'])} | {int(r['qwen_positive_count'])} | "
            f"{r['positive_rate']:.6f} | {r['enrichment_vs_base_rate']:.6f} | {int(r['l3_missed_positive_count_B20'])} |"
        )
    write_text(REPORTS / "REALCARTEST_DISAGREEMENT_GROUP_REPORT.md", "\n".join(lines) + "\n")
    append_progress("Phase 3 complete: disagreement groups written.")
    return groups


def fill_unique(primary: list[int], fallback: list[int], budget: int) -> list[int]:
    out = []
    seen = set()
    for idx in primary + fallback:
        if idx not in seen:
            out.append(idx)
            seen.add(idx)
        if len(out) >= budget:
            break
    return out


def phase4_replay(df: pd.DataFrame, glm: pd.DataFrame) -> pd.DataFrame:
    append_progress("Phase 4: Strategy 7 replay started.")
    merged = df.merge(glm[["anchor_id", "parsed_label", "confidence"]], on="anchor_id", how="left")
    merged["parsed_label"] = merged["parsed_label"].fillna("parse_error").astype(str).str.lower()
    merged["confidence_num"] = pd.to_numeric(merged["confidence"], errors="coerce").fillna(0.0)
    median = float(merged["object_count_mean"].median())
    l3_order = order_by_l3(merged)
    low_glm_pool = merged.index[(merged["object_count_mean"] <= median) & merged["parsed_label"].isin(GLM_POS_UNC)].tolist()
    low_glm_pool = sorted(low_glm_pool, key=lambda i: (merged.at[i, "object_count_mean"], -merged.at[i, "confidence_num"], merged.at[i, "anchor_timestamp"], str(merged.at[i, "anchor_id"])))
    pos_unc_pool = merged.index[merged["parsed_label"].isin(GLM_POS_UNC)].tolist()
    pos_unc_pool = sorted(pos_unc_pool, key=lambda i: (-merged.at[i, "confidence_num"], -merged.at[i, "object_count_mean"], merged.at[i, "anchor_timestamp"], str(merged.at[i, "anchor_id"])))
    glm_boost_order = fill_unique(pos_unc_pool, l3_order, len(merged))
    rows: list[dict[str, Any]] = []

    for budget in BUDGETS:
        l3_ref = set(top_l3_indices(merged, budget))
        l3 = top_l3_indices(merged, budget)
        rows.append(selected_metrics(merged, l3, budget, "L3_baseline", l3_reference=l3_ref))
        temporal = maxmin_temporal_from_candidates(merged, budget)
        rows.append(selected_metrics(merged, temporal, budget, "L3_temporal_maxmin", l3_reference=l3_ref))
        boost = glm_boost_order[:budget]
        rows.append(selected_metrics(merged, boost, budget, "GLM_priority_boost", l3_reference=l3_ref))

        exploit_n = min(budget, math.floor(0.7 * budget))
        s7_disagree_n = min(budget - exploit_n, math.floor(0.2 * budget))
        s7_uniform_n = budget - exploit_n - s7_disagree_n
        l3_exploit = top_l3_indices(merged, exploit_n)
        s7_audit_det = fill_unique(low_glm_pool + pos_unc_pool, [i for i in l3_order if i not in l3_exploit], s7_disagree_n)
        for seed in SEEDS:
            rng = np.random.default_rng(seed)
            uniform = rng.choice(merged.index.to_numpy(), size=min(budget, len(merged)), replace=False).tolist()
            rows.append(selected_metrics(merged, uniform, budget, "uniform_random", seed=seed, l3_reference=l3_ref))

            base_pool = [i for i in merged.index if i not in set(l3_exploit)]
            plus_uniform = rng.choice(np.array(base_pool), size=min(budget - exploit_n, len(base_pool)), replace=False).tolist()
            selected_plus = fill_unique(l3_exploit + plus_uniform, [i for i in l3_order if i not in l3_exploit], budget)
            rows.append(selected_metrics(
                merged, selected_plus, budget, "L3_plus_uniform_audit", seed=seed,
                audit_indices=plus_uniform, l3_reference=l3_ref,
            ))

            already = set(l3_exploit + s7_audit_det)
            s7_pool = [i for i in merged.index if i not in already]
            s7_uniform = rng.choice(np.array(s7_pool), size=min(s7_uniform_n, len(s7_pool)), replace=False).tolist() if s7_uniform_n else []
            selected_s7 = fill_unique(l3_exploit + s7_audit_det + s7_uniform, [i for i in l3_order if i not in already], budget)
            rows.append(selected_metrics(
                merged, selected_s7, budget, "Strategy7_disagreement_audit", seed=seed,
                audit_indices=s7_audit_det + s7_uniform, l3_reference=l3_ref,
            ))

    raw = pd.DataFrame(rows)
    raw.to_csv(TABLES / "realcartest_strategy7_replay_results_per_seed.csv", index=False)
    summary_random = summarize_seed_rows([r for r in rows if r.get("seed") != ""])
    deterministic = raw[raw["seed"].astype(str) == ""].copy()
    deterministic["n_seeds"] = 0
    deterministic = deterministic.rename(columns={c: f"mean_{c}" for c in deterministic.columns if c not in ["strategy", "B", "n_seeds"]})
    for col in list(deterministic.columns):
        if col.startswith("mean_"):
            deterministic["std_" + col[5:]] = 0.0
            deterministic["ci95_halfwidth_" + col[5:]] = 0.0
    budget_curve = pd.concat([deterministic, summary_random], ignore_index=True, sort=False)

    # Add requested comparison gaps.
    for budget in BUDGETS:
        s7_mask = (budget_curve["B"] == budget) & (budget_curve["strategy"] == "Strategy7_disagreement_audit")
        uniform_mask = (budget_curve["B"] == budget) & (budget_curve["strategy"] == "L3_plus_uniform_audit")
        l3_mask = (budget_curve["B"] == budget) & (budget_curve["strategy"] == "L3_baseline")
        if s7_mask.any():
            s7_rec = float(budget_curve.loc[s7_mask, "mean_l3_missed_positive_recovery"].iloc[0])
            s7_anchor = float(budget_curve.loc[s7_mask, "mean_anchor_recall"].iloc[0])
            if uniform_mask.any():
                u_rec = float(budget_curve.loc[uniform_mask, "mean_l3_missed_positive_recovery"].iloc[0])
                u_anchor = float(budget_curve.loc[uniform_mask, "mean_anchor_recall"].iloc[0])
                budget_curve.loc[s7_mask, "strategy7_vs_uniform_audit_gap_l3_missed_recovery"] = s7_rec - u_rec
                budget_curve.loc[s7_mask, "strategy7_vs_uniform_audit_gap_anchor_recall"] = s7_anchor - u_anchor
            if l3_mask.any():
                l3_anchor = float(budget_curve.loc[l3_mask, "mean_anchor_recall"].iloc[0])
                budget_curve.loc[s7_mask, "strategy7_vs_l3_gap_anchor_recall"] = s7_anchor - l3_anchor

    budget_curve.to_csv(TABLES / "realcartest_strategy7_replay_results.csv", index=False)
    budget_curve.to_csv(TABLES / "realcartest_strategy7_budget_curve.csv", index=False)
    write_strategy7_replay_report(budget_curve, merged)
    append_progress("Phase 4 complete: Strategy 7 replay results written.")
    return budget_curve


def write_strategy7_replay_report(curve: pd.DataFrame, df: pd.DataFrame) -> None:
    s7 = curve[curve["strategy"] == "Strategy7_disagreement_audit"].sort_values("B")
    uni = curve[curve["strategy"] == "L3_plus_uniform_audit"].sort_values("B")
    l3 = curve[curve["strategy"] == "L3_baseline"].sort_values("B")
    merged = s7[["B", "mean_l3_missed_positive_recovery", "mean_anchor_recall", "mean_audit_hit_rate"]].merge(
        uni[["B", "mean_l3_missed_positive_recovery", "mean_anchor_recall", "mean_audit_hit_rate"]],
        on="B",
        suffixes=("_s7", "_uniform_audit"),
    ).merge(l3[["B", "mean_anchor_recall"]], on="B")
    merged["gap_l3_missed_recovery"] = merged["mean_l3_missed_positive_recovery_s7"] - merged["mean_l3_missed_positive_recovery_uniform_audit"]
    merged["gap_anchor_recall_vs_l3"] = merged["mean_anchor_recall_s7"] - merged["mean_anchor_recall"]
    positive_gaps = int((merged["gap_l3_missed_recovery"] > 0).sum())
    positive_rate = df["is_positive_bool"].mean()
    glm_pos_unc_rate = df["parsed_label"].isin(GLM_POS_UNC).mean()
    lines = [
        "# Realcartest Strategy 7 Replay Report",
        "",
        f"- Output timestamp: {utc_now()}",
        "- Deployable selection policies use cheap proxy score, timestamps, random seeds, and GLM parsed labels only.",
        "- Existing Qwen labels and `event_cluster_id` are evaluation-only.",
        f"- Realcartest positive rate: {positive_rate:.6f}.",
        f"- GLM positive/uncertain selection fraction: {glm_pos_unc_rate:.6f}.",
        "",
        "## Budget Curve",
        "",
        "| B | S7 L3-missed recovery | uniform-audit L3-missed recovery | S7 gap | S7 anchor recall | L3 anchor recall | S7 audit hit rate |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in merged.iterrows():
        lines.append(
            f"| {int(r['B'])} | {r['mean_l3_missed_positive_recovery_s7']:.6f} | "
            f"{r['mean_l3_missed_positive_recovery_uniform_audit']:.6f} | {r['gap_l3_missed_recovery']:.6f} | "
            f"{r['mean_anchor_recall_s7']:.6f} | {r['mean_anchor_recall']:.6f} | {r['mean_audit_hit_rate_s7']:.6f} |"
        )
    lines.extend([
        "",
        "## Required Questions",
        "",
        f"1. Strategy 7 L3-missed positive recovery improvement: positive at {positive_gaps}/{len(merged)} budget points.",
        f"2. Strategy 7 versus uniform audit: mean L3-missed gap {merged['gap_l3_missed_recovery'].mean():.6f}.",
        f"3. Higher positive-rate setting: marginal value is measured by the audit hit rate and missed-positive gap above; interpretation is deferred to final decision.",
        f"4. Dataset3-effective/realcartest-ineffective case: determined in the cross-video report from these gaps.",
        "5. If weak/invalid, attribution checks compare L3 baseline strength, positive rate, and GLM disagreement enrichment.",
    ])
    write_text(REPORTS / "REALCARTEST_STRATEGY7_REPLAY_REPORT.md", "\n".join(lines) + "\n")


def dataset3_metrics() -> dict[str, Any]:
    out: dict[str, Any] = {}
    if DATASET3_CANON.exists():
        d3 = pd.read_csv(DATASET3_CANON)
        d3["is_positive_bool"] = as_bool_series(d3["is_positive"])
        out["dataset3_full_n"] = len(d3)
        out["dataset3_full_positive_n"] = int(d3["is_positive_bool"].sum())
        out["dataset3_full_positive_rate"] = float(d3["is_positive_bool"].mean())
        out["dataset3_object_count_mean_auc"] = auc_rank(d3["is_positive_bool"], d3["object_count_mean"])
        d3_l3 = d3.sort_values(["object_count_mean", "center_time_s", "anchor_id"], ascending=[False, True, True], kind="mergesort").head(20)
        out["dataset3_l3_p20"] = float(d3_l3["is_positive_bool"].mean())
        out["dataset3_l3_r20"] = float(d3_l3["is_positive_bool"].sum() / d3["is_positive_bool"].sum()) if d3["is_positive_bool"].sum() else float("nan")
    if DATASET3_STRAT7.exists():
        s7 = pd.read_csv(DATASET3_STRAT7)
        clean = s7[s7["strategy"].astype(str).str.contains("7_Strategy7", na=False)]
        uniform = s7[s7["strategy"].astype(str).str.contains("6_L3_plus_uniform", na=False)]
        if clean.empty:
            clean = s7[s7["strategy"].astype(str).str.contains("Strategy7", na=False)]
        if not clean.empty:
            out["dataset3_strategy7_budget_points"] = int(len(clean))
            out["dataset3_strategy7_l3_missed_recovery_mean"] = float((clean["l3_missed_recovered_count"] / (28 - s7[s7["strategy"].astype(str).str.contains("1_L3", na=False)]["anchor_recall_x_n"].reindex(clean.index, fill_value=np.nan))).replace([np.inf, -np.inf], np.nan).mean()) if "l3_missed_recovered_count" in clean else float("nan")
            out["dataset3_strategy7_audit_hit_rate_mean"] = float(clean["audit_hit_rate"].mean())
        if not clean.empty and not uniform.empty:
            gaps = []
            for b in sorted(set(clean["B"]) & set(uniform["B"])):
                c = clean[clean["B"] == b].iloc[0]
                u = uniform[uniform["B"] == b].iloc[0]
                gaps.append(float(c["l3_missed_recovered_count"] - u["l3_missed_recovered_count"]))
            out["dataset3_s7_vs_uniform_l3_missed_count_gap_mean"] = float(np.mean(gaps)) if gaps else float("nan")
    if DATASET3_CLEAN_CASCADE.exists():
        cas = pd.read_csv(DATASET3_CLEAN_CASCADE)
        l3 = cas[(cas["strategy"] == "1_L3_baseline") & (cas["B"] == 20)]
        if not l3.empty:
            out["dataset3_clean_l3_p20"] = float(l3["mean_precision"].iloc[0])
            out["dataset3_clean_l3_r20"] = float(l3["mean_recall"].iloc[0])
    return out


def phase5_cross_video(real_curve: pd.DataFrame, groups: pd.DataFrame, acceptance_decision: str, real_df: pd.DataFrame) -> pd.DataFrame:
    append_progress("Phase 5: cross-video comparison started.")
    d3 = dataset3_metrics()
    real_l3_20 = real_curve[(real_curve["strategy"] == "L3_baseline") & (real_curve["B"] == 20)].iloc[0]
    real_s7 = real_curve[real_curve["strategy"] == "Strategy7_disagreement_audit"].copy()
    mean_s7_gap = float(real_s7["strategy7_vs_uniform_audit_gap_l3_missed_recovery"].mean()) if "strategy7_vs_uniform_audit_gap_l3_missed_recovery" in real_s7 else float("nan")
    glm_group = groups[groups["group"] == "GLM_positive_or_uncertain"].iloc[0] if not groups[groups["group"] == "GLM_positive_or_uncertain"].empty else None
    strict = acceptance_decision == "ACCEPT_REALCARTEST_FOR_STRICT_SECOND_VIDEO_VALIDATION"
    rows = [
        {"metric": "comparison_mode", "dataset3_clean_pool": "strict replication reference" if strict else "directional reference", "realcartest_v13": "strict validation" if strict else "directional only", "note": acceptance_decision},
        {"metric": "positive_rate", "dataset3_clean_pool": d3.get("dataset3_full_positive_rate", float("nan")), "realcartest_v13": float(real_df["is_positive_bool"].mean()), "note": "dataset3 full canonical rate vs realcartest full V13 anchor rate"},
        {"metric": "object_count_mean_auc", "dataset3_clean_pool": d3.get("dataset3_object_count_mean_auc", float("nan")), "realcartest_v13": auc_rank(real_df["is_positive_bool"], real_df["object_count_mean"]), "note": "proxy ranking strength"},
        {"metric": "L3_P20", "dataset3_clean_pool": d3.get("dataset3_clean_l3_p20", d3.get("dataset3_l3_p20", float("nan"))), "realcartest_v13": float(real_l3_20["mean_precision"]), "note": "dataset3 clean pool if available; realcartest full universe"},
        {"metric": "L3_R20", "dataset3_clean_pool": d3.get("dataset3_clean_l3_r20", d3.get("dataset3_l3_r20", float("nan"))), "realcartest_v13": float(real_l3_20["mean_anchor_recall"]), "note": "dataset3 clean pool if available; realcartest full universe"},
        {"metric": "Strategy7_vs_uniform_audit_gap_mean", "dataset3_clean_pool": d3.get("dataset3_s7_vs_uniform_l3_missed_count_gap_mean", float("nan")), "realcartest_v13": mean_s7_gap, "note": "dataset3 value is missed-positive count gap; realcartest value is recovery-rate gap"},
        {"metric": "GLM_positive_or_uncertain_enrichment", "dataset3_clean_pool": "see post_transition_strategy7_audit_v1", "realcartest_v13": float(glm_group["enrichment_vs_base_rate"]) if glm_group is not None else float("nan"), "note": "Qwen evaluation-only enrichment"},
        {"metric": "Strategy7_effect_transfers", "dataset3_clean_pool": "confirmed in dataset3 clean-pool audit", "realcartest_v13": "positive" if mean_s7_gap > 0 else "not_positive", "note": "transfer assessed by realcartest S7 vs uniform-audit L3-missed recovery gap"},
    ]
    out = pd.DataFrame(rows)
    out.to_csv(TABLES / "cross_video_strategy7_comparison.csv", index=False)
    mode = "strict replication" if strict else "directional comparison"
    lines = [
        "# Cross-Video Strategy 7 Comparison",
        "",
        f"- Output timestamp: {utc_now()}",
        f"- Comparison mode: {mode}.",
        "- Dataset3 clean-pool and realcartest are not pooled because positive rate, proxy strength, and candidate universe differ.",
        "- Dataset3 is lower-positive-rate/weaker-proxy in the project framing; realcartest has higher positive rate and stronger `object_count_mean`.",
        "",
        "| metric | dataset3 | realcartest | note |",
        "|---|---:|---:|---|",
    ]
    for _, r in out.iterrows():
        lines.append(f"| {r['metric']} | {r['dataset3_clean_pool']} | {r['realcartest_v13']} | {r['note']} |")
    write_text(REPORTS / "CROSS_VIDEO_STRATEGY7_COMPARISON.md", "\n".join(lines) + "\n")
    append_progress("Phase 5 complete: cross-video comparison written.")
    return out


def final_decision(acceptance_decision: str, glm_status: str, real_curve: pd.DataFrame | None) -> str:
    if acceptance_decision == "REJECT_REALCARTEST_FOR_STRATEGY7_VALIDATION":
        return "REALCARTEST_VALIDATION_REJECTED"
    if glm_status != "available":
        return "STRATEGY7_REALCARTEST_BLOCKED_NO_GLM_OUTPUTS"
    if real_curve is None or real_curve.empty:
        return "STRATEGY7_REALCARTEST_BLOCKED_NO_GLM_OUTPUTS"
    s7 = real_curve[real_curve["strategy"] == "Strategy7_disagreement_audit"].copy()
    if s7.empty or "strategy7_vs_uniform_audit_gap_l3_missed_recovery" not in s7:
        return "STRATEGY7_DATASET3_SPECIFIC"
    gaps = pd.to_numeric(s7["strategy7_vs_uniform_audit_gap_l3_missed_recovery"], errors="coerce").dropna()
    positives = int((gaps > 0).sum())
    if acceptance_decision == "ACCEPT_REALCARTEST_FOR_STRICT_SECOND_VIDEO_VALIDATION" and positives >= 2 and gaps.mean() > 0:
        return "STRATEGY7_TRANSFER_CONFIRMED"
    if positives >= 1 or gaps.mean() > 0:
        return "STRATEGY7_TRANSFER_WEAK_BUT_DIRECTIONAL"
    return "STRATEGY7_DATASET3_SPECIFIC"


def write_final_summary(
    acceptance_decision: str,
    glm_status: str,
    decision: str,
    real_df: pd.DataFrame | None,
    l3: pd.DataFrame | None,
    real_curve: pd.DataFrame | None,
    cross: pd.DataFrame | None,
) -> None:
    pos_rate = float(real_df["is_positive_bool"].mean()) if real_df is not None else float("nan")
    auc = auc_rank(real_df["is_positive_bool"], real_df["object_count_mean"]) if real_df is not None else float("nan")
    l3_b20 = None
    s7_summary = "not run"
    if l3 is not None and not l3.empty:
        rows = l3[(l3["strategy"] == "L3_object_count_mean") & (l3["B"] == 20)]
        if not rows.empty:
            l3_b20 = rows.iloc[0]
    if real_curve is not None and not real_curve.empty:
        s7 = real_curve[real_curve["strategy"] == "Strategy7_disagreement_audit"]
        if not s7.empty:
            gaps = pd.to_numeric(s7.get("strategy7_vs_uniform_audit_gap_l3_missed_recovery", pd.Series(dtype=float)), errors="coerce")
            s7_summary = f"mean S7-vs-uniform-audit L3-missed recovery gap={gaps.mean():.6f}; positive budget gaps={(gaps > 0).sum()}/{gaps.notna().sum()}"
    cross_conclusion = "not run"
    if cross is not None and not cross.empty:
        row = cross[cross["metric"] == "Strategy7_effect_transfers"]
        if not row.empty:
            cross_conclusion = str(row["realcartest_v13"].iloc[0])
    lines = [
        "# Final Summary",
        "",
        f"- Output timestamp: {utc_now()}",
        "- Qwen/final oracle called: NO.",
        f"- GLM called: {'YES' if glm_status == 'available' and (TABLES / 'realcartest_glm_fixed_prompt_outputs.csv').exists() else 'NO or reused/blocked; see GLM report'}.",
        "- YOLO called: NO.",
        f"- Acceptance audit decision: `{acceptance_decision}`.",
        f"- Realcartest positive rate: {pos_rate:.6f}.",
        f"- Realcartest `object_count_mean` AUC: {auc:.6f}.",
        f"- Realcartest L3 baseline B=20: precision={float(l3_b20['mean_precision']):.6f}, recall={float(l3_b20['mean_anchor_recall']):.6f}, positives={float(l3_b20['mean_selected_positive_count']):.3f}." if l3_b20 is not None else "- Realcartest L3 baseline: not run.",
        f"- Strategy 7 realcartest result: {s7_summary}.",
        f"- Cross-video comparison conclusion: {cross_conclusion}.",
        f"- Final decision label: `{decision}`.",
        "",
        "## Limitations",
        "",
        "- All evaluation labels are existing V13.8 Qwen3-VL-32B oracle-relative labels, not human ground truth.",
        "- GLM is used only as a fixed-prompt auxiliary mechanism; no prompt tuning was done on realcartest.",
        "- Strategy replay is a no-new-final-oracle simulation over 399 pre-existing labeled anchors.",
        "- Dataset3 and realcartest differ in positive rate, proxy ranking strength, and clean-pool/full-universe definitions.",
        "",
        "realcartest_strategy7_validation_complete=true",
    ]
    write_text(OUT / "FINAL_SUMMARY.md", "\n".join(lines) + "\n")
    final_row = {
        "decision_label": decision,
        "acceptance_decision": acceptance_decision,
        "glm_status": glm_status,
        "timestamp_utc": utc_now(),
        "qwen_or_final_oracle_called": False,
        "glm_called_or_reused": glm_status == "available",
        "yolo_called": False,
        "output_dir": str(OUT),
    }
    pd.DataFrame([final_row]).to_csv(TABLES / "final_decision.csv", index=False)


def write_config_and_manifest() -> None:
    write_text(CONFIG / "experiment_config.yaml", "\n".join([
        "task: realcartest_strategy7_validation_v1",
        f"previous_output_dir: {PREV}",
        f"feature_path: {FEATURE_PATH}",
        f"frozen_glm_prompt_path: {PROMPT_PATH}",
        "budgets: [20, 30, 40, 60, 80, 100, 150]",
        "n_random_seeds: 500",
        "qwen_or_final_oracle_calls_allowed: false",
        "yolo_calls_allowed: false",
        "glm_fixed_prompt_allowed_after_acceptance: true",
    ]) + "\n")
    rows = [
        {"role": "previous_realcartest_materialization", "path": str(PREV), "read_only": True},
        {"role": "realcartest_anchor_features", "path": str(FEATURE_PATH), "read_only": True},
        {"role": "frozen_glm_prompt", "path": str(PROMPT_PATH), "read_only": True},
        {"role": "realcartest_video_for_contact_sheets", "path": str(VIDEO_PATH), "read_only": True},
        {"role": "dataset3_strategy7_reference", "path": str(DATASET3_STRAT7), "read_only": True},
    ]
    pd.DataFrame(rows).to_csv(MANIFEST / "input_manifest.csv", index=False)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-glm", action="store_true", help="Do not call GLM; block if no existing realcartest GLM outputs are present.")
    parser.add_argument("--acceptance-only", action="store_true")
    args = parser.parse_args()
    ensure_dirs()
    write_config_and_manifest()
    acceptance_decision = phase0_acceptance()
    if args.acceptance_only:
        return 0
    if acceptance_decision == "REJECT_REALCARTEST_FOR_STRATEGY7_VALIDATION":
        write_glm_report(pd.DataFrame(), reused=False, blocked_reason="Phase 0 acceptance rejected realcartest.")
        write_final_summary(acceptance_decision, "blocked", "REALCARTEST_VALIDATION_REJECTED", None, None, None, None)
        return 0
    real_df = load_realcartest_features()
    l3 = phase1_l3_replay(real_df)
    glm, glm_status = phase2_glm(real_df, skip_glm=args.skip_glm)
    if glm_status != "available" or glm is None:
        decision = final_decision(acceptance_decision, glm_status, None)
        write_final_summary(acceptance_decision, glm_status, decision, real_df, l3, None, None)
        return 0
    groups = phase3_groups(real_df, glm)
    real_curve = phase4_replay(real_df, glm)
    cross = phase5_cross_video(real_curve, groups, acceptance_decision, real_df)
    decision = final_decision(acceptance_decision, glm_status, real_curve)
    write_final_summary(acceptance_decision, glm_status, decision, real_df, l3, real_curve, cross)
    append_progress(f"Task complete: {decision}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
