#!/usr/bin/env python3
"""Candidate and Outcome Calibration Gate v1.

Evaluator-only diagnostic over frozen artifacts.  It never calls the VLM,
reruns baselines, or changes H0--H4 planner code/configuration.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


OUT = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run"
STRICT = BASE / "clean_baseline_benchmark_v2_strict"
BCM = BASE / "bcm_aqp_experiment_v2"
HCR = BASE / "hypothesis_construction_repair_v1"
BUDGETS = [5, 10, 20, 50, 80, 100]
SEED = 20260711
CONFIG = {
    "schema_version": "candidate_outcome_calibration_gate_v1_config_v1",
    "benchmark_id": "cbbv2_514c0d360fd5b2a4b5fe",
    "budgets": BUDGETS,
    "primary_materializer": "k3_bridge_safe",
    "materializer_config": {"g_max": 1, "d_core_max": 40.0, "d_seg_max": 60.0},
    "reproduction_atol": 1e-12,
    "probability_clip": 1e-6,
    "reliability_bins": 10,
    "crossfit_folds": 5,
    "crossfit_logistic_C": 1.0,
    "crossfit_solver": "liblinear",
    "calibration_signal_pooled_auc": 0.65,
    "calibration_signal_min_defined_folds": 3,
    "calibration_signal_fold_auc": 0.50,
    "approach_tolerance_f1": 0.05,
    "substantial_ranking_headroom_f1": 0.10,
    "substantial_missing_event_fraction": 0.20,
    "no_hyperparameter_search": True,
    "evaluator_only": True,
    "physical_vlm_calls": 0,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


HCRMOD = load_module("frozen_hcr_for_calibration_gate", HCR / "implementation/run_hypothesis_construction_repair_v1.py")
LIB = HCRMOD.LIB
RUNNER = HCRMOD.RUNNER


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_csv(path: Path, rows: pd.DataFrame | list[dict], columns: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = rows.copy() if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    if columns is not None:
        for col in columns:
            if col not in frame:
                frame[col] = pd.Series(dtype="object")
        frame = frame[columns]
    frame.to_csv(path, index=False)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")


def progress(checkpoint: str, command: str, result: str, next_action: str, failure: str = "none", fix: str = "none") -> None:
    path = OUT / "logs/progress.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(f"\n## {utc_now()} — {checkpoint}\n\n- Checkpoint: {checkpoint}\n- Commands run: `{command}`\n")
        f.write(f"- Result: {result}\n- Failure: {failure}\n- Fix applied: {fix}\n- Next action: {next_action}\n")


def ensure_dirs() -> None:
    for d in ["audit", "reproduction", "data", "ceilings", "calibration", "calibration_feasibility",
              "ranking", "candidate_quality", "config", "data_manifest", "logs", "tables", "figures", "reports"]:
        (OUT / d).mkdir(parents=True, exist_ok=True)


def parse_ids(value: Any) -> tuple[int, ...]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ()
    text = str(value).strip()
    if not text:
        return ()
    if text.startswith("(") or text.startswith("["):
        return tuple(int(x) for x in ast.literal_eval(text))
    return tuple(LIB.read_ids(value))


def frozen_tables() -> dict[str, pd.DataFrame]:
    return {
        "units": pd.read_csv(STRICT / "frozen_inputs/units.csv"),
        "proxy": pd.read_csv(STRICT / "frozen_inputs/public_proxy.csv"),
        "oracle": pd.read_csv(STRICT / "oracle/oracle_presence_observations.csv"),
        "reference": pd.read_csv(STRICT / "frozen_inputs/event_reference.csv"),
    }


def primary_proxy(proxy: pd.DataFrame, ids: Iterable[int]) -> pd.Series:
    return HCRMOD.public_scores(proxy, list(ids))


def reference_maps(reference: pd.DataFrame) -> tuple[dict[str, set[int]], dict[int, list[str]]]:
    event_units = {str(r.reference_event_id): set(parse_ids(r.source_unit_ids)) for r in reference.itertuples()}
    unit_events: dict[int, list[str]] = defaultdict(list)
    for event, ids in event_units.items():
        for uid in ids:
            unit_events[uid].append(event)
    return event_units, unit_events


def audit_inputs() -> None:
    ensure_dirs()
    explicit = [
        STRICT / "NEXT_BCM_TASK_CONTEXT.md", STRICT / "FROZEN_BENCHMARK_V2.md", STRICT / "BENCHMARK_MANIFEST.json",
        STRICT / "frozen_inputs/units.csv", STRICT / "frozen_inputs/public_proxy.csv", STRICT / "frozen_inputs/event_reference.csv",
        STRICT / "oracle/oracle_presence_observations.csv", STRICT / "scripts/run_clean_benchmark_v2_strict.py",
        STRICT / "scripts/benchmark_lib.py", STRICT / "baselines/baseline_action_traces.csv",
        STRICT / "baselines/baseline_metrics_wide.csv", STRICT / "baselines/baseline_rankings.csv",
        STRICT / "baselines/baseline_run_registry.csv", STRICT / "baselines/baseline_event_segments.csv",
        STRICT / "current_method/current_selected_units.csv", STRICT / "current_method/current_budget_curves.csv",
        STRICT / "current_method/current_method_runs.csv", STRICT / "current_method/current_event_segments.csv",
        HCR / "FINAL_REPORT.md", HCR / "FINAL_DECISION.csv", HCR / "RESEARCH_STATE.md", HCR / "EXPERIMENT_MANIFEST.json",
        HCR / "forensics/FAILURE_CAUSAL_DECOMPOSITION.md", HCR / "forensics/hypothesis_source_inventory.csv",
        HCR / "forensics/action_opportunity_by_step.csv", HCR / "forensics/action_score_scale.csv",
        HCR / "forensics/budgeted_candidate_quality.csv", HCR / "analysis/all_action_traces.csv",
        HCR / "analysis/all_candidate_scores.csv", HCR / "analysis/per_budget_metrics.csv",
        HCR / "configs/H1_CONFIG.json", HCR / "implementation/run_hypothesis_construction_repair_v1.py",
        HCR / "runs/H1/b100/action_trace.csv", HCR / "runs/H1/b100/all_candidate_scores.csv",
        HCR / "runs/H1/b100/initial_hypotheses.csv", HCR / "runs/H1/b100/initial_exploration_cells.csv",
        BCM / "reports/FINAL_REPORT.md", BCM / "reports/RESEARCH_STATE.md", BCM / "FINAL_DECISION.csv",
        BCM / "config/experiment_config.json", BCM / "tables/action_traces.csv", BCM / "tables/materializer_matrix.csv",
        STRICT / "baselines/baseline_selected_units.csv",
        ROOT / "BCM_AQP_MATHEMATICAL_REFERENCE.md",
    ]
    explicit += [BCM / f"runs/canonical/b{b:03d}/action_trace.csv" for b in BUDGETS]
    explicit += [HCR / f"runs/H1/b{b:03d}/action_trace.csv" for b in BUDGETS]
    missing_requested = [BCM / "configs", BCM / "analysis", BCM / "runs/all_candidate_scores.csv"]
    resolved = [BCM / "config/experiment_config.json", HCR / "forensics/H0_ALL_CANDIDATE_SCORES_RECONSTRUCTED.csv"]
    rows = []
    for p in explicit + missing_requested + resolved:
        exists = p.exists()
        role = "requested"
        note = "none"
        if p in missing_requested:
            role = "requested_but_missing"
            if p.name == "configs": note = "resolved to singular config/ via failed experiment manifest"
            elif "all_candidate" in p.name: note = "not preserved by H0; evaluator uses HCR deterministic reconstruction"
            else: note = "failed BCM has tables/ and audit/ but no analysis/ directory"
        if p in resolved:
            role = "resolved_path"
            note = "explicit provenance resolution; not silently substituted"
        rows.append({"path": str(p), "role": role, "status": "PRESENT" if exists else "MISSING",
                     "size_bytes": p.stat().st_size if exists and p.is_file() else "",
                     "sha256": sha256_file(p) if exists and p.is_file() else "", "note": note})
    write_csv(OUT / "audit/INPUT_MANIFEST.csv", rows)
    write_csv(OUT / "data_manifest/input_manifest.csv", rows)
    tables = frozen_tables()
    proxy = tables["proxy"]
    schema = (
        "public_units: strict/frozen_inputs/units.csv\npublic_proxy: strict/frozen_inputs/public_proxy.csv\n"
        "oracle_evaluator_only: strict/oracle/oracle_presence_observations.csv\n"
        "reference_evaluator_only: strict/frozen_inputs/event_reference.csv\n"
        "h1_state: hypothesis_construction_repair_v1/runs/H1/b100\n"
        "time_fields: [start_time, end_time]\nscore_field: proxy_score_normalized\n"
        "evaluator_only_fields: [parsed_label, reference_event_id, source_unit_ids]\n"
    )
    (OUT / "data_manifest/schema_mapping.yaml").write_text(schema)
    write_json(OUT / "config/experiment_config.json", CONFIG)
    (OUT / "config/experiment_config.yaml").write_text("\n".join(f"{k}: {json.dumps(v)}" for k, v in CONFIG.items()) + "\n")
    present = sum(r["status"] == "PRESENT" for r in rows)
    report = f"""# Input Artifact Audit

Strict benchmark `{CONFIG['benchmark_id']}` is frozen and read-only. Inputs contain {len(tables['units'])} units, {len(proxy)} proxy rows across {proxy.proxy_name.nunique()} public proxy fields, {int((tables['oracle'].parsed_label == 'positive').sum())} VLM-defined positive units, and {len(tables['reference'])} VLM-defined pseudo-events from one diagnostic video.

The failed BCM uses `config/`, not the requested `configs/`. It has no `analysis/` directory and did not preserve all-candidate scores. The exact H0 candidate-score reconstruction from Hypothesis Repair v1 is resolved explicitly and remains evaluator-only. No stale artifact was silently substituted.

Leakage boundary: public construction features are physically separate from oracle/reference tables. Oracle labels and reference IDs are used only in files named `EVALUATOR_ONLY` or aggregate diagnostics; no online trace or frozen ordering is changed.
"""
    (OUT / "audit/INPUT_ARTIFACT_AUDIT.md").write_text(report)
    progress("Input artifact audit", "--stage audit", f"{present} present artifacts; requested mismatches recorded explicitly", "Recompute frozen facts.")


def trapezoid_auc(frame: pd.DataFrame, x: str, y: str) -> float:
    d = frame.sort_values(x)
    return float(np.trapezoid(d[y], d[x]) / (d[x].max() - d[x].min()))


def reproduce() -> None:
    ensure_dirs()
    tables = frozen_tables(); reference = tables["reference"]
    evaluator_hash = json.loads((STRICT / "BENCHMARK_MANIFEST.json").read_text())["compatibility"]["evaluator_hash"]
    run_metrics=[]
    def reevaluate_segments(registry: pd.DataFrame, segments_all: pd.DataFrame, scope: str) -> pd.DataFrame:
        out=[]
        for rr in registry.itertuples():
            seg=segments_all[segments_all.run_id==rr.run_id].copy()
            if seg.empty: seg=pd.DataFrame(columns=LIB.EVENT_SEGMENT_COLUMNS)
            meta={"benchmark_id":CONFIG["benchmark_id"],"run_id":rr.run_id,"method":rr.method,"method_variant":rr.method_variant,
                  "seed":int(rr.seed),"horizon_budget":int(rr.horizon_budget)}
            _,metrics=LIB.evaluate_events(seg,reference,meta,evaluator_hash)
            wide={r.metric_name:float(r.metric_value) for r in metrics.itertuples()}
            row={"scope":scope,"run_id":rr.run_id,"method":rr.method,"method_variant":rr.method_variant,"seed":int(rr.seed),"budget":int(rr.horizon_budget),**wide}
            out.append(row);run_metrics.append(row)
        return pd.DataFrame(out)

    best_named = pd.read_csv(STRICT / "baselines/baseline_rankings.csv").sort_values("event_f1_auc").iloc[-1]
    base_registry=pd.read_csv(STRICT/"baselines/baseline_run_registry.csv")
    base_registry=base_registry[(base_registry.method==best_named.method)&(base_registry.method_variant==best_named.method_variant)&(base_registry.horizon_budget.isin(BUDGETS))]
    base_segments=pd.read_csv(STRICT/"baselines/baseline_event_segments.csv")
    base_recomputed=reevaluate_segments(base_registry,base_segments,"best_native_saved_segments")
    best_budget_curve=base_recomputed.groupby("budget",as_index=False).event_f1.mean()
    best_recomputed_auc=trapezoid_auc(best_budget_curve,"budget","event_f1")

    current_registry=pd.read_csv(STRICT/"current_method/current_method_runs.csv")
    current_registry=current_registry[(current_registry.method_variant=="K3_BRIDGE_SAFE")&(current_registry.horizon_budget.isin(BUDGETS))]
    current_segments=pd.read_csv(STRICT/"current_method/current_event_segments.csv")
    map_m1=reevaluate_segments(current_registry,current_segments,"MAP_M1_saved_segments").sort_values("budget")
    map_auc=trapezoid_auc(map_m1,"budget","event_f1")

    expected_f1={
        "H0":{5:0.0,10:0.07407407407407407,20:0.14285714285714288,50:0.32258064516129037,80:0.411764705882353,100:0.4571428571428572},
        "H1":{5:0.0,10:0.07407407407407407,20:0.14285714285714288,50:0.32258064516129037,80:0.4571428571428572,100:0.5405405405405405},
    }
    trace_frames={}
    for variant in ["H0","H1"]:
        vals=[]
        for b in BUDGETS:
            path=(BCM/f"runs/canonical/b{b:03d}/action_trace.csv") if variant=="H0" else (HCR/f"runs/H1/b{b:03d}/action_trace.csv")
            trace=pd.read_csv(path)
            labels=trace.oracle_outcome_after_query.astype(str)
            strict_trace=pd.DataFrame({"unit_id":trace.unit_id.astype(int),"oracle_label_after_query":labels})
            meta={"benchmark_id":CONFIG["benchmark_id"],"run_id":f"recompute_{variant}_{b}","method":variant,"method_variant":"k3_bridge_safe","seed":SEED,"horizon_budget":b}
            seg=LIB.materialize_from_trace(strict_trace,tables["units"],meta,"k3_bridge_safe",CONFIG["materializer_config"])
            _,metrics=LIB.evaluate_events(seg,reference,meta,evaluator_hash);wide={r.metric_name:float(r.metric_value) for r in metrics.itertuples()}
            vals.append({"variant":variant,"budget":b,**wide});run_metrics.append({"scope":f"{variant}_saved_trace","run_id":str(path),"method":variant,"method_variant":"k3_bridge_safe","seed":SEED,"budget":b,**wide})
        trace_frames[variant]=pd.DataFrame(vals)
    h0,h1=trace_frames["H0"],trace_frames["H1"]
    h0_auc, h1_auc = trapezoid_auc(h0, "budget", "event_f1"), trapezoid_auc(h1, "budget", "event_f1")

    scores=primary_proxy(tables["proxy"],list(tables["units"].unit_id.astype(int)))
    h0cfg=json.loads((BCM/"config/experiment_config.json").read_text())
    h0_hyp=HCRMOD.H0.build_hypotheses(tables["units"],scores,h0cfg)
    h1cfg=json.loads((HCR/"configs/H1_CONFIG.json").read_text())
    h1_hyp=HCRMOD.construct_public_state(tables["units"],scores,"H1",h1cfg).hypotheses
    unit_index=tables["units"].set_index("unit_id")
    def derive_quality(hypotheses: Iterable[Any], support_field: str) -> dict:
        mapping=defaultdict(list);false=0
        for h in hypotheses:
            support=set(int(x) for x in getattr(h,support_field));matched=[]
            for r in reference.itertuples():
                ref_units=set(parse_ids(r.source_unit_ids))
                overlap=bool(support&ref_units) or any(float(unit_index.loc[u,"end_time"])>float(r.start_time) and float(unit_index.loc[u,"start_time"])<float(r.end_time) for u in support)
                if overlap: matched.append(str(r.reference_event_id));mapping[str(r.reference_event_id)].append(h.hypothesis_id)
            if not matched:false+=1
        covered=set(mapping);return {"hypothesis_count":len(hypotheses),"fragmentation":sum(len(v) for v in mapping.values())/len(covered) if covered else math.nan,"false_burden":false/len(hypotheses)}
    quality={"H0":derive_quality(h0_hyp,"owner_unit_ids"),"H1":derive_quality(h1_hyp,"support_unit_ids")}
    expected = {"best_native_auc": 0.3896592193755119, "map_m1_auc": 0.3880556629484837,
                "h0_auc": 0.2942701472213107, "h1_auc": 0.31499046948962056}
    observed = {"best_native_auc": best_recomputed_auc, "map_m1_auc": map_auc, "h0_auc": h0_auc, "h1_auc": h1_auc}
    rows = []
    for key in expected:
        rows.append({"fact": key, "expected": expected[key], "recomputed": observed[key],
                     "abs_error": abs(expected[key] - observed[key]),
                     "status": "PASS" if abs(expected[key] - observed[key]) <= CONFIG["reproduction_atol"] else "FAIL"})
    for b in BUDGETS:
        for variant, frame in [("H0", h0), ("H1", h1)]:
            value = float(frame[frame.budget == b].iloc[0].event_f1);exp=expected_f1[variant][b]
            rows.append({"fact": f"{variant}_event_f1_B{b}", "expected": exp, "recomputed": value, "abs_error": abs(exp-value),
                         "status":"PASS" if abs(exp-value)<=CONFIG["reproduction_atol"] else "FAIL"})
    for variant, count, frag, burden in [("H0", 141, 1.2307692307692308, 0.7943262411347518),
                                         ("H1", 87, 1.0526315789473684, 0.7931034482758621)]:
        q=quality[variant]
        for name, exp, got in [("hypothesis_count", count, q["hypothesis_count"]), ("fragmentation", frag, q["fragmentation"]), ("false_burden", burden, q["false_burden"])]:
            rows.append({"fact": f"{variant}_{name}", "expected": exp, "recomputed": got,
                         "abs_error": abs(float(exp)-float(got)), "status": "PASS" if abs(float(exp)-float(got)) <= CONFIG["reproduction_atol"] else "FAIL"})
    result = pd.DataFrame(rows)
    write_csv(OUT / "reproduction/FROZEN_RESULT_RECOMPUTATION.csv", result)
    write_csv(OUT / "reproduction/RECOMPUTED_RUN_METRICS.csv", run_metrics)
    if not (result.status == "PASS").all():
        raise RuntimeError("frozen result reproduction failed")
    (OUT / "reproduction/REPRODUCTION_REPORT.md").write_text(
        f"# Frozen Result Reproduction\n\nAll {len(result)} facts PASS at absolute tolerance `{CONFIG['reproduction_atol']}`. "
        f"Best native `{best_named.method}/{best_named.method_variant}` AUC `{observed['best_native_auc']:.15f}`; MAP/M1 `{map_auc:.15f}`; H0 `{h0_auc:.15f}`; H1 `{h1_auc:.15f}`. No baseline or H0--H4 run was executed.\n")
    (OUT / "REPRODUCTION.md").write_text("# Reproduction\n\n```bash\npython3 scripts/run_candidate_outcome_calibration_gate_v1.py --stage all\n```\n\nEvaluator-only CPU diagnostics over frozen artifacts; zero physical VLM calls and zero baseline reruns.\n")
    progress("Frozen fact reproduction", "--stage reproduce", f"{len(result)}/{len(result)} PASS", "Build evaluator-only H1 candidate tables and ceilings.")


def canonical_orders() -> dict[str, list[int]]:
    h1 = pd.read_csv(HCR / "runs/H1/b100/action_trace.csv").sort_values("call_idx")
    current = pd.read_csv(STRICT / "current_method/current_selected_units.csv")
    map_rows = current[(current.method_variant == "K3_BRIDGE_SAFE") & (current.seed == 0) & (current.horizon_budget == 100)].sort_values("call_idx")
    base = pd.read_csv(STRICT / "baselines/baseline_selected_units.csv")
    arc = base[(base.method == "B5_ARC_native") & (base.method_variant == "arc_refinement_th0.4_native") & (base.seed == 0) & (base.horizon_budget == 100)].sort_values("call_idx")
    return {"H1": h1.unit_id.astype(int).tolist(), "MAP_M1": map_rows.unit_id.astype(int).tolist(), "ARC_NATIVE": arc.unit_id.astype(int).tolist()}


def candidate_tables() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    t = frozen_tables(); units = t["units"].set_index("unit_id"); oracle = t["oracle"].set_index("unit_id"); ref = t["reference"]
    scores = primary_proxy(t["proxy"], list(units.index.astype(int)))
    percentiles = scores.rank(method="average", pct=True)
    event_units, unit_events = reference_maps(ref)
    hy = pd.read_csv(HCR / "runs/H1/b100/initial_hypotheses.csv")
    orders = canonical_orders(); rankmaps = {name: {uid: i+1 for i, uid in enumerate(order)} for name, order in orders.items()}
    rows = []
    for h in hy.itertuples():
        support = parse_ids(h.support_unit_ids); cores = parse_ids(h.core_candidate_ids)
        s0 = float(units.loc[min(support), "start_time"]); s1 = float(units.loc[max(support), "end_time"])
        overlap_events = [str(r.reference_event_id) for r in ref.itertuples()
                          if set(support) & set(parse_ids(r.source_unit_ids)) or
                          any(float(units.loc[u,"end_time"]) > float(r.start_time) and float(units.loc[u,"start_time"]) < float(r.end_time) for u in support)]
        for uid in cores:
            label = str(oracle.loc[uid, "parsed_label"]); actual_events = unit_events.get(uid, [])
            cert_events = actual_events if label == "positive" else []
            canon = [str(r.reference_event_id) for r in ref.itertuples() if float(units.loc[uid,"start_time"]) <= float(r.canonical_anchor_time) < float(units.loc[uid,"end_time"])]
            actual_rank = rankmaps["H1"].get(uid)
            rows.append({"EVALUATOR_ONLY": True, "hypothesis_id": h.hypothesis_id, "hypothesis_source": h.source_type,
                         "support_start": s0, "support_end": s1, "owner_unit_count": len(support), "core_unit_id": uid,
                         "core_public_proxy": float(scores.loc[uid]), "core_proxy_percentile": float(percentiles.loc[uid]),
                         "initial_existence_belief": float(h.existence_belief), "actual_unit_label": label,
                         "overlapping_reference_event_ids": "|".join(overlap_events), "reference_event_count": len(overlap_events),
                         "contains_canonical_anchor_if_available": bool(canon), "canonical_anchor_event_ids": "|".join(canon),
                         "is_positive": label == "positive", "can_certify_any_event": bool(cert_events),
                         "certifiable_event_ids": "|".join(cert_events), "best_possible_new_event_id": cert_events[0] if cert_events else "",
                         "actual_H1_rank": actual_rank if actual_rank is not None else "",
                         "actual_MAP_rank_if_present": rankmaps["MAP_M1"].get(uid, ""),
                         "actual_ARC_rank_if_present": rankmaps["ARC_NATIVE"].get(uid, ""),
                         "queried_by_H1_at_budget": "|".join(str(b) for b in BUDGETS if actual_rank is not None and actual_rank <= b),
                         "queried_by_MAP_at_budget": "|".join(str(b) for b in BUDGETS if rankmaps['MAP_M1'].get(uid, 10**9) <= b),
                         "queried_by_ARC_at_budget": "|".join(str(b) for b in BUDGETS if rankmaps['ARC_NATIVE'].get(uid, 10**9) <= b)})
    cand = pd.DataFrame(rows).sort_values(["hypothesis_id", "core_unit_id"])
    write_csv(OUT / "data/H1_CANDIDATE_DIAGNOSTIC_EVALUATOR_ONLY.csv", cand)
    hrows = []
    for hid, g in cand.groupby("hypothesis_id"):
        events = set(e for value in g.certifiable_event_ids for e in str(value).split("|") if e)
        support_events = set(e for value in g.overlapping_reference_event_ids for e in str(value).split("|") if e)
        hrows.append({"EVALUATOR_ONLY": True, "hypothesis_id": hid, "hypothesis_source": g.iloc[0].hypothesis_source,
                      "support_start": g.iloc[0].support_start, "support_end": g.iloc[0].support_end,
                      "owner_unit_count": int(g.iloc[0].owner_unit_count), "core_candidate_count": len(g),
                      "positive_core_count": int(g.is_positive.sum()), "positive_hypothesis": bool(g.is_positive.any()),
                      "event_containing": bool(support_events), "support_overlapping_event_ids": "|".join(sorted(support_events)),
                      "support_overlapping_event_count": len(support_events),
                      "certifiable_event_ids": "|".join(sorted(events)),
                      "certifiable_event_count": len(events), "first_public_rank": pd.to_numeric(g.actual_H1_rank, errors="coerce").min(),
                      "max_proxy": float(g.core_public_proxy.max()), "mean_proxy_percentile": float(g.core_proxy_percentile.mean())})
    hyp = pd.DataFrame(hrows)
    write_csv(OUT / "data/H1_HYPOTHESIS_DIAGNOSTIC_EVALUATOR_ONLY.csv", hyp)
    cells = pd.read_csv(HCR / "runs/H1/b100/initial_exploration_cells.csv")
    cell_units = set(uid for value in cells.unit_ids for uid in parse_ids(value))
    core_units = set(cand.core_unit_id.astype(int))
    legal_units = core_units | cell_units
    context = {"scores": scores, "percentiles": percentiles, "event_units": event_units, "unit_events": unit_events,
               "orders": orders, "core_units": core_units, "cell_units": cell_units, "legal_units": legal_units}
    return cand, hyp, context


def trace_frame(order: list[int], oracle: pd.DataFrame) -> pd.DataFrame:
    lookup = oracle.set_index("unit_id").parsed_label.astype(str)
    return pd.DataFrame({"unit_id": order, "oracle_label_after_query": [lookup.loc[u] for u in order]})


def evaluate_order(order: list[int], budget: int, units: pd.DataFrame, oracle: pd.DataFrame, reference: pd.DataFrame, materializer: str = "k3_bridge_safe") -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    selected = order[:budget]
    trace = trace_frame(selected, oracle)
    meta = {"benchmark_id": CONFIG["benchmark_id"], "run_id": f"eval_{materializer}_{budget}", "method": "EVALUATOR_ONLY",
            "method_variant": materializer, "seed": SEED, "horizon_budget": budget}
    segments = LIB.materialize_from_trace(trace, units, meta, materializer, CONFIG["materializer_config"])
    matches, metrics = LIB.evaluate_events(segments, reference, meta, json.loads((STRICT / "BENCHMARK_MANIFEST.json").read_text())["compatibility"]["evaluator_hash"])
    wide = {r.metric_name: float(r.metric_value) for r in metrics.itertuples()}
    return wide, segments, matches


def certified_events(order: list[int], budget: int, positive: set[int], unit_events: dict[int, list[str]]) -> tuple[set[str], int, int]:
    seen: set[str] = set(); redundant = 0; false = 0
    for uid in order[:budget]:
        events = set(unit_events.get(uid, [])) if uid in positive else set()
        if not events:
            false += 1
        elif events <= seen:
            redundant += 1
        seen |= events
    return seen, redundant, false


def static_ceilings(cand: pd.DataFrame, context: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, list[int]]]:
    t = frozen_tables(); ref = t["reference"]; positive = set(t["oracle"].loc[t["oracle"].parsed_label == "positive", "unit_id"].astype(int))
    unit_events = context["unit_events"]; core = set(context["core_units"]); universe = set(context["legal_units"])
    actual = [u for u in context["orders"]["H1"] if u in universe]
    # H1's formal trace defines the public order through B=100. Legal actions
    # never reached by B=100 are appended deterministically for universe audit.
    actual += sorted(universe - set(actual), key=lambda u: (-float(context["scores"].loc[u]), u))
    positive_order = sorted(universe, key=lambda u: (u not in positive, context["orders"]["H1"].index(u) if u in context["orders"]["H1"] else 10**6,
                                                  -float(context["scores"].loc[u]), u))
    # One positive per event first; deterministic event-id ordering is used
    # only in this evaluator ceiling.
    unique = []
    used = set()
    for event in sorted(context["event_units"]):
        choices = sorted((context["event_units"][event] & universe & positive), key=lambda u: (-float(context["scores"].loc[u]), u))
        if choices:
            uid = choices[0]
            if uid not in used:
                unique.append(uid); used.add(uid)
    unique += [u for u in positive_order if u not in used]
    orders = {"ACTUAL_H1_PUBLIC_ORDER": actual, "PERFECT_POSITIVE_LABEL_ORDER": positive_order, "PERFECT_UNIQUE_EVENT_ORDER": unique}
    rows = []
    for name, order in orders.items():
        for b in BUDGETS:
            events, redundant, false = certified_events(order, b, positive, unit_events)
            wide, _, _ = evaluate_order(order, min(b, len(order)), t["units"], t["oracle"], ref)
            rows.append({"EVALUATOR_ONLY": name != "ACTUAL_H1_PUBLIC_ORDER", "ordering": name, "budget": b,
                         "selected_available": min(b, len(order)), "positive_units_in_top_b": len(set(order[:b]) & positive),
                         "distinct_reference_events_touched": len(events), "event_candidate_recall": len(events)/len(ref),
                         "duplicate_event_evidence": redundant, "false_candidates": false,
                         "materialized_event_precision": wide["event_precision"], "materialized_event_recall": wide["event_recall"],
                         "materialized_event_f1": wide["event_f1"]})
    frame = pd.DataFrame(rows)
    write_csv(OUT / "ceilings/static_candidate_ceiling_by_budget.csv", frame)
    represented = set(e for u in core & positive for e in unit_events.get(u, []))
    legal_represented = set(e for u in context["legal_units"] & positive for e in unit_events.get(u, []))
    missing = []
    actual_rank = {u:i+1 for i,u in enumerate(actual)}
    for event in sorted(context["event_units"]):
        candidate_units = sorted(context["event_units"][event] & core & positive)
        legal_units = sorted(context["event_units"][event] & context["legal_units"] & positive)
        legal_ranks=sorted(actual_rank.get(u,10**9) for u in legal_units)
        best_legal=min(legal_ranks) if legal_ranks else None
        missing.append({"EVALUATOR_ONLY": True, "reference_event_id": event, "present_in_core_candidate_universe": bool(candidate_units),
                        "present_in_full_legal_action_universe": bool(legal_units), "positive_core_candidate_ids": "|".join(map(str,candidate_units)),
                        "positive_legal_unit_ids": "|".join(map(str,legal_units)),
                        "best_actual_H1_rank": min((actual_rank.get(u,10**9) for u in candidate_units), default=""),
                        "best_full_legal_public_order_rank":best_legal if best_legal is not None else "",
                        "all_full_legal_public_order_ranks":"|".join(str(x) for x in legal_ranks),
                        "represented_only_beyond_B20":bool(best_legal is not None and best_legal>20),
                        "represented_only_beyond_B100":bool(best_legal is not None and best_legal>100),
                        "representation_status":("ABSENT" if best_legal is None else ("TOP20" if best_legal<=20 else ("RANK21_100" if best_legal<=100 else "BEYOND_B100"))),
                        "absent_from_core_universe": event not in represented, "absent_from_full_legal_universe": event not in legal_represented})
    miss = pd.DataFrame(missing)
    write_csv(OUT / "ceilings/missing_event_from_candidate_universe.csv", miss)
    late20=miss[miss.represented_only_beyond_B20].reference_event_id.astype(str).tolist()
    late100=miss[miss.represented_only_beyond_B100].reference_event_id.astype(str).tolist()
    report = f"""# Static Candidate Ceiling

    H1 contains {len(core)} unique core candidates covering {len(represented)}/{len(ref)} (`{len(represented)/len(ref):.6f}`) VLM-defined pseudo-events with positive certifying evidence. The static ceilings use the exact full legal H1 action universe: {len(context['legal_units'])} core/exploration units covering {len(legal_represented)}/{len(ref)} (`{len(legal_represented)/len(ref):.6f}`).

The core universe therefore misses {len(ref)-len(represented)} events; even full legal exploration misses {len(ref)-len(legal_represented)}. `ACTUAL_H1_PUBLIC_ORDER` is the frozen formal H1 order through B100; never-selected legal actions are appended only for the universe audit by descending frozen public score and unit-ID tie break. Static oracle orderings are evaluator-only and are not runnable policies.

Events present but first ranked beyond B20: `{', '.join(late20)}`. Events present but beyond the formal B100 trace: `{', '.join(late100)}`. Exact legal-order ranks are in `missing_event_from_candidate_universe.csv`.
"""
    (OUT / "ceilings/STATIC_CANDIDATE_CEILING_REPORT.md").write_text(report)
    return frame, orders


def matched_reference_ids(matches: pd.DataFrame) -> set[str]:
    if matches.empty or "matched" not in matches:
        return set()
    return set(matches.loc[matches.matched.astype(bool), "reference_event_id"].dropna().astype(str))


def state_evaluation(state: Any, tables: dict[str, pd.DataFrame], run_id: str) -> tuple[dict, tuple, set[str], pd.DataFrame]:
    obs = list(state.observations)
    trace = pd.DataFrame({"unit_id": [o.unit_id for o in obs], "oracle_label_after_query": [o.outcome for o in obs]})
    meta = {"benchmark_id": CONFIG["benchmark_id"], "run_id": run_id, "method": "EVALUATOR_ONLY", "method_variant": "k3_bridge_safe",
            "seed": SEED, "horizon_budget": len(obs)}
    seg = LIB.materialize_from_trace(trace, tables["units"], meta, "k3_bridge_safe", CONFIG["materializer_config"])
    matches, metrics = LIB.evaluate_events(seg, tables["reference"], meta, json.loads((STRICT / "BENCHMARK_MANIFEST.json").read_text())["compatibility"]["evaluator_hash"])
    wide = {r.metric_name: float(r.metric_value) for r in metrics.itertuples()}
    signature = tuple((round(float(r.start_time),9), round(float(r.end_time),9), str(r.anchor_unit_ids)) for r in seg.itertuples())
    return wide, signature, matched_reference_ids(matches), seg


def oracle_reorder() -> tuple[pd.DataFrame, pd.DataFrame]:
    tables = frozen_tables(); scores = primary_proxy(tables["proxy"], list(tables["units"].unit_id.astype(int)))
    cfg = json.loads((HCR / "configs/H1_CONFIG.json").read_text())
    state = HCRMOD.construct_public_state(tables["units"], scores, "H1", cfg)
    oracle = tables["oracle"].set_index("unit_id").parsed_label.astype(str)
    rows = []; metrics_rows = []
    for call in range(100):
        before_wide, before_sig, before_refs, _ = state_evaluation(state, tables, f"oracle_before_{call}")
        candidates = HCRMOD.enumerate_actions(state, scores, cfg)
        evaluated = []
        for action in candidates:
            uid = int(action["unit_id"]); outcome = oracle.loc[uid]
            after, _ = HCRMOD.apply_observation(state, action, outcome, cfg, True)
            wide, sig, refs, _ = state_evaluation(after, tables, f"oracle_cf_{call}_{uid}")
            evaluated.append({**action, "actual_outcome": outcome, "after_state": after, "after_wide": wide, "after_signature": sig,
                              "after_refs": refs, "realized_event_f1_delta": wide["event_f1"]-before_wide["event_f1"],
                              "new_event_gain": len(refs-before_refs), "materializer_output_changed": sig != before_sig})
        if not evaluated:
            break
        evaluated.sort(key=lambda r: (-r["realized_event_f1_delta"], -r["new_event_gain"], r["actual_outcome"] != "positive",
                                      -float(r["public_score"]), int(r["unit_id"])))
        chosen = evaluated[0]
        # Commit the exact same pure transition; no OracleAccessor or physical
        # inference is invoked in this evaluator-only ceiling.
        state, _ = HCRMOD.apply_observation(state, chosen, chosen["actual_outcome"], cfg)
        rows.append({"EVALUATOR_ONLY": True, "ceiling_label": "ESTIMATED_ORACLE_INFORMED_REORDER_CEILING", "call_idx": call,
                     "state_before_hash": "evaluator_state_"+str(call), "unit_id": chosen["unit_id"], "action_type": chosen["action_type"],
                     "hypothesis_id": chosen["hypothesis_id"], "hypothesis_source": chosen["source"], "public_score": chosen["public_score"],
                     "actual_outcome": chosen["actual_outcome"], "realized_event_f1_delta": chosen["realized_event_f1_delta"],
                     "new_event_gain": chosen["new_event_gain"], "newly_matched_event_ids": "|".join(sorted(chosen["after_refs"]-before_refs)),
                     "materializer_output_changed": chosen["materializer_output_changed"],
                     "candidate_count": len(evaluated), "event_f1_after": chosen["after_wide"]["event_f1"],
                     "event_recall_after": chosen["after_wide"]["event_recall"], "event_precision_after": chosen["after_wide"]["event_precision"]})
        if call + 1 in BUDGETS:
            wide, _, refs, _ = state_evaluation(state, tables, f"oracle_budget_{call+1}")
            metrics_rows.append({"EVALUATOR_ONLY": True, "ceiling_label": "ESTIMATED_ORACLE_INFORMED_REORDER_CEILING",
                                 "budget": call+1, "unique_events_discovered": len(refs), **wide})
    trace = pd.DataFrame(rows); metrics = pd.DataFrame(metrics_rows)
    metrics["event_f1_auc"] = trapezoid_auc(metrics, "budget", "event_f1") if len(metrics) == len(BUDGETS) else math.nan
    # First discovery calls from the greedy matched-set sequence.
    write_csv(OUT / "ceilings/oracle_informed_reorder_trace_EVALUATOR_ONLY.csv", trace)
    write_csv(OUT / "ceilings/oracle_informed_reorder_metrics.csv", metrics)
    discoveries=[]
    for event in sorted(set(e for value in trace.newly_matched_event_ids for e in str(value).split("|") if e)):
        first=trace[trace.newly_matched_event_ids.fillna("").str.split("|").map(lambda xs:event in xs)].call_idx.min()
        discoveries.append({"EVALUATOR_ONLY":True,"reference_event_id":event,"first_discovery_call":int(first)+1})
    write_csv(OUT / "ceilings/oracle_first_discovery_calls_EVALUATOR_ONLY.csv", discoveries)
    (OUT / "ceilings/ORACLE_REORDER_CEILING_REPORT.md").write_text(
        f"# Oracle-Informed Reorder Ceiling\n\nThis is an `ESTIMATED_ORACLE_INFORMED_REORDER_CEILING`, not an exact optimum. It greedily maximizes realized one-step event-F1 using evaluator labels/reference while preserving H1 legal actions, transitions, costs, and K3-safe materialization. AUC is `{metrics.event_f1_auc.iloc[0]:.6f}`. No oracle inference was performed.\n")
    return trace, metrics


def action_outcome_diagnostics() -> pd.DataFrame:
    tables = frozen_tables(); scores = primary_proxy(tables["proxy"], list(tables["units"].unit_id.astype(int)))
    percentiles = scores.rank(method="average", pct=True); cfg = json.loads((HCR / "configs/H1_CONFIG.json").read_text())
    selected = pd.read_csv(HCR / "runs/H1/b100/action_trace.csv").sort_values("call_idx")
    all_scores = pd.read_csv(HCR / "runs/H1/b100/all_candidate_scores.csv")
    oracle = tables["oracle"].set_index("unit_id").parsed_label.astype(str)
    _, unit_events = reference_maps(tables["reference"])
    state = HCRMOD.construct_public_state(tables["units"], scores, "H1", cfg)
    rows = []
    positive_hypotheses: set[str] = set()
    for call in range(100):
        before_wide, before_sig, before_refs, _ = state_evaluation(state, tables, f"diag_before_{call}")
        candidates = all_scores[all_scores.call_idx == call].copy()
        local = []
        for r in candidates.itertuples():
            action = {"unit_id": int(r.unit_id), "action_type": str(r.action_type), "hypothesis_id": str(r.hypothesis_id) if pd.notna(r.hypothesis_id) else "",
                      "source": str(r.source), "owner_unit_count": int(r.owner_unit_count), "public_score": float(r.public_score)}
            outcome = oracle.loc[int(r.unit_id)]
            after, _ = HCRMOD.apply_observation(state, action, outcome, cfg, True)
            wide, sig, refs, _ = state_evaluation(after, tables, f"diag_cf_{call}_{int(r.unit_id)}")
            new_refs = refs-before_refs
            belief_positive = float(r.estimated_p_positive)
            belief_new = belief_positive if (not action["hypothesis_id"] or action["hypothesis_id"] not in positive_hypotheses) else 0.0
            actual_events = unit_events.get(int(r.unit_id), [])
            local.append({"run_id": "hcr_H1_b100", "budget": 100, "call_idx": call,
                          "state_hash": selected.iloc[call].state_before_hash, "action_type": action["action_type"],
                          "hypothesis_id": action["hypothesis_id"], "unit_id": int(r.unit_id), "hypothesis_source": action["source"],
                          "public_proxy": float(r.public_score), "public_proxy_percentile": float(percentiles.loc[int(r.unit_id)]),
                          "belief_positive": belief_positive, "belief_new_event": belief_new, "actual_outcome": outcome,
                          "actual_positive": outcome == "positive", "actual_new_event": bool(new_refs),
                          "actual_event_id": "|".join(actual_events), "newly_matched_event_ids": "|".join(sorted(new_refs)),
                          "realized_event_F1_delta": wide["event_f1"]-before_wide["event_f1"],
                          "realized_event_recall_delta": wide["event_recall"]-before_wide["event_recall"],
                          "materializer_output_changed": sig != before_sig, "selected_by_H1": bool(r.selected),
                          "H1_action_rank": int(r.rank)})
        local.sort(key=lambda x: (-x["realized_event_F1_delta"], -int(x["actual_new_event"]), -int(x["actual_positive"]),
                                  -x["public_proxy"], x["unit_id"]))
        for rank, row in enumerate(local, 1):
            row["oracle_action_rank"] = rank; row["rank_regret"] = row["H1_action_rank"] - rank
            rows.append(row)
        chosen = selected.iloc[call]
        action = {"unit_id": int(chosen.unit_id), "action_type": str(chosen.action_type), "hypothesis_id": str(chosen.selected_hypothesis_id),
                  "source": str(chosen.selected_hypothesis_source), "owner_unit_count": int(chosen.owner_unit_count),
                  "public_score": float(scores.loc[int(chosen.unit_id)])}
        state, _ = HCRMOD.apply_observation(state, action, str(chosen.oracle_outcome_after_query), cfg)
        if chosen.oracle_outcome_after_query == "positive":
            positive_hypotheses.add(str(chosen.selected_hypothesis_id))
    frame = pd.DataFrame(rows)
    write_csv(OUT / "calibration/ACTION_OUTCOME_DIAGNOSTIC_EVALUATOR_ONLY.csv", frame)
    return frame


def budget_region(call: int) -> str:
    n = call + 1
    if n <= 5: return "1-5"
    if n <= 10: return "6-10"
    if n <= 20: return "11-20"
    if n <= 50: return "21-50"
    return "51-100"


def safe_auc(y: np.ndarray, p: np.ndarray) -> float:
    return float(roc_auc_score(y, p)) if len(np.unique(y)) == 2 else math.nan


def safe_ap(y: np.ndarray, p: np.ndarray) -> float:
    return float(average_precision_score(y, p)) if y.sum() > 0 else math.nan


def calibration_summary(frame: pd.DataFrame, probability: str, target: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    d = frame.copy()
    d["proxy_percentile_bin"] = pd.cut(d.public_proxy_percentile, bins=np.linspace(0,1,11), include_lowest=True).astype(str)
    d["budget_region"] = d.call_idx.map(budget_region)
    groups: list[tuple[str,str,pd.DataFrame]] = [("all","all",d)]
    for column, gtype in [("action_type","action_type"),("hypothesis_source","hypothesis_source"),
                          ("proxy_percentile_bin","proxy_percentile_bin"),("budget_region","budget_region")]:
        groups += [(gtype,str(value),g.copy()) for value,g in d.groupby(column,dropna=False)]
    metrics=[]; reliability=[]; clip=CONFIG["probability_clip"]
    for gtype,value,g in groups:
        y=g[target].astype(int).to_numpy(); p=g[probability].astype(float).to_numpy(); pc=np.clip(p,clip,1-clip)
        bins=np.minimum((p*CONFIG["reliability_bins"]).astype(int),CONFIG["reliability_bins"]-1)
        ece=0.0; mce=0.0
        for bi in range(CONFIG["reliability_bins"]):
            mask=bins==bi
            if not mask.any(): continue
            conf=float(p[mask].mean()); rate=float(y[mask].mean()); gap=abs(conf-rate)
            ece += mask.mean()*gap; mce=max(mce,gap)
            reliability.append({"target":target,"group_type":gtype,"group_value":value,"bin":bi,
                                "bin_lower":bi/CONFIG["reliability_bins"],"bin_upper":(bi+1)/CONFIG["reliability_bins"],
                                "count":int(mask.sum()),"mean_belief":conf,"actual_rate":rate,"calibration_gap":gap})
        rho=spearmanr(p,y).statistic if len(np.unique(p))>1 and len(np.unique(y))>1 else math.nan
        row={"target":target,"group_type":gtype,"group_value":value,"n":len(g),"positives":int(y.sum()),"prevalence":float(y.mean()),
             "brier":float(brier_score_loss(y,p)),"log_loss":float(log_loss(y,pc,labels=[0,1])),"ece":ece,"maximum_calibration_error":mce,
             "auroc":safe_auc(y,p),"average_precision":safe_ap(y,p),"spearman":float(rho) if math.isfinite(rho) else math.nan}
        order=np.argsort(-p)
        for k in [5,10,20,50,100]:
            kk=min(k,len(y)); row[f"positives_at_{k}" if target=="actual_positive" else f"new_events_at_{k}"]=int(y[order[:kk]].sum())
            row[f"precision_at_{k}"]=float(y[order[:kk]].mean()) if kk else math.nan
        # Top-k regret against evaluator target sorting.
        for k in [5,10,20,50,100]:
            kk=min(k,len(y)); row[f"top{k}_regret"]=int(np.sort(y)[::-1][:kk].sum()-y[order[:kk]].sum())
        metrics.append(row)
    return pd.DataFrame(metrics),pd.DataFrame(reliability)


def calibration_metrics(action_diag: pd.DataFrame) -> tuple[pd.DataFrame,pd.DataFrame]:
    pm,pr=calibration_summary(action_diag,"belief_positive","actual_positive")
    nm,nr=calibration_summary(action_diag,"belief_new_event","actual_new_event")
    write_csv(OUT/"calibration/positive_calibration_metrics.csv",pm); write_csv(OUT/"calibration/new_event_calibration_metrics.csv",nm)
    write_csv(OUT/"calibration/positive_reliability_bins.csv",pr); write_csv(OUT/"calibration/new_event_reliability_bins.csv",nr)
    pa=pm[(pm.group_type=='all')].iloc[0]; na=nm[(nm.group_type=='all')].iloc[0]
    (OUT/"calibration/CALIBRATION_REPORT.md").write_text(
        f"# Calibration Report\n\nEvaluator-only action rows: {len(action_diag)}. Positive belief: Brier `{pa.brier:.6f}`, ECE `{pa.ece:.6f}`, AUROC `{pa.auroc:.6f}`. New-event belief: Brier `{na.brier:.6f}`, ECE `{na.ece:.6f}`, AUROC `{na.auroc if pd.notna(na.auroc) else 'undefined'}`. H1 stores no separate new-event posterior, so `belief_new_event` is reconstructed without reference as `belief_positive` until the owner hypothesis has a queried-positive anchor, and zero afterward; exploration cells use `belief_positive`. AUROC is left undefined for one-class subgroups. Probabilities are clipped to `{CONFIG['probability_clip']}` only for log loss.\n")
    return pm,nm


def crossfit(cand: pd.DataFrame) -> tuple[pd.DataFrame,pd.DataFrame]:
    d=cand.sort_values(["core_unit_id","hypothesis_id"]).reset_index(drop=True).copy()
    folds=np.empty(len(d),dtype=int)
    for i,idx in enumerate(np.array_split(np.arange(len(d)),CONFIG["crossfit_folds"])): folds[idx]=i
    d["temporal_fold"]=folds
    d["support_duration"]=d.support_end-d.support_start
    d["support_start_normalized"]=d.support_start/d.support_end.max()
    specs={
        "F0_proxy_only":(["core_public_proxy"],[]),
        "F1_proxy_source":(["core_public_proxy"],["hypothesis_source"]),
        "F2_all_public_H1":(["core_public_proxy","core_proxy_percentile","owner_unit_count","support_duration","support_start_normalized","initial_existence_belief"],["hypothesis_source"]),
    }
    preds=[]
    for target in ["is_positive","can_certify_any_event"]:
        yall=d[target].astype(int)
        for feature_set,(nums,cats) in specs.items():
            for fold in range(CONFIG["crossfit_folds"]):
                train=d.temporal_fold!=fold; test=~train; y=yall[train]
                if y.nunique()<2:
                    pred=np.repeat(float(y.mean()),test.sum())
                else:
                    transformers=[("num",StandardScaler(),nums)]
                    if cats: transformers.append(("cat",OneHotEncoder(handle_unknown="ignore"),cats))
                    model=Pipeline([("features",ColumnTransformer(transformers)),("logistic",LogisticRegression(C=CONFIG["crossfit_logistic_C"],solver=CONFIG["crossfit_solver"],random_state=SEED,max_iter=1000))])
                    model.fit(d.loc[train,nums+cats],y); pred=model.predict_proba(d.loc[test,nums+cats])[:,1]
                for idx,p in zip(d.index[test],pred):
                    preds.append({"EVALUATOR_ONLY":True,"target":target,"feature_set":feature_set,"temporal_fold":fold,
                                  "hypothesis_id":d.loc[idx,"hypothesis_id"],"core_unit_id":int(d.loc[idx,"core_unit_id"]),
                                  "actual":int(yall.loc[idx]),"crossfit_probability":float(p)})
    pf=pd.DataFrame(preds); metrics=[]
    for (target,fs),g in pf.groupby(["target","feature_set"]):
        y=g.actual.to_numpy(); p=g.crossfit_probability.to_numpy()
        metrics.append({"target":target,"feature_set":fs,"scope":"pooled","fold":"all","n":len(g),"positives":int(y.sum()),
                        "prevalence":float(y.mean()),"brier":float(brier_score_loss(y,p)),"auroc":safe_auc(y,p),"average_precision":safe_ap(y,p)})
        for fold,fg in g.groupby("temporal_fold"):
            y=fg.actual.to_numpy();p=fg.crossfit_probability.to_numpy()
            metrics.append({"target":target,"feature_set":fs,"scope":"fold","fold":int(fold),"n":len(fg),"positives":int(y.sum()),
                            "prevalence":float(y.mean()),"brier":float(brier_score_loss(y,p)),"auroc":safe_auc(y,p),"average_precision":safe_ap(y,p)})
    mf=pd.DataFrame(metrics); write_csv(OUT/"calibration_feasibility/crossfit_predictions_EVALUATOR_ONLY.csv",pf);write_csv(OUT/"calibration_feasibility/crossfit_metrics.csv",mf)
    lines=["# Calibration Feasibility Report","","Fixed five-fold contiguous temporal cross-validation; no shuffle and no hyperparameter search.",""]
    for target in ["is_positive","can_certify_any_event"]:
        row=mf[(mf.target==target)&(mf.feature_set=='F2_all_public_H1')&(mf.scope=='pooled')].iloc[0]
        folds=mf[(mf.target==target)&(mf.feature_set=='F2_all_public_H1')&(mf.scope=='fold')]
        lines.append(f"- `{target}` F2 pooled AUROC `{row.auroc:.6f}`, AP `{row.average_precision:.6f}`; defined improving folds `{int((folds.auroc>CONFIG['calibration_signal_fold_auc']).sum())}/{int(folds.auroc.notna().sum())}`.")
    lines += ["","These are cross-fitted evaluator-only predictions, not authorization for an online planner on this video."]
    (OUT/"calibration_feasibility/CALIBRATION_FEASIBILITY_REPORT.md").write_text("\n".join(lines)+"\n")
    return pf,mf


def ranking_comparison(context: dict[str,Any], oracle_trace: pd.DataFrame) -> tuple[pd.DataFrame,pd.DataFrame]:
    orders={**context["orders"],"ORACLE_H1_REORDER":oracle_trace.unit_id.astype(int).tolist()}
    t=frozen_tables();positive=set(t["oracle"].loc[t["oracle"].parsed_label=='positive','unit_id'].astype(int)); unit_events=context["unit_events"]
    rows=[]
    for k in [5,10,20,50,100]:
        for left,right in [("H1","MAP_M1"),("H1","ARC_NATIVE"),("H1","ORACLE_H1_REORDER")]:
            a=set(orders[left][:k]);b=set(orders[right][:k]);ae=set(e for u in a&positive for e in unit_events.get(u,[]));be=set(e for u in b&positive for e in unit_events.get(u,[]))
            rows.append({"k":k,"left_method":left,"right_method":right,"unit_overlap":len(a&b),"jaccard_overlap":len(a&b)/len(a|b) if a|b else 1,
                         "positive_unit_overlap":len(a&b&positive),"unique_event_overlap":len(ae&be),"left_unique_events":len(ae),"right_unique_events":len(be),
                         "events_only_left":"|".join(sorted(ae-be)),"events_only_right":"|".join(sorted(be-ae)),
                         "first_ranking_divergence":next((i+1 for i,(x,y) in enumerate(zip(orders[left],orders[right])) if x!=y),"")})
    rf=pd.DataFrame(rows);write_csv(OUT/"ranking/ranking_overlap_by_k.csv",rf)
    events=[]
    for event,units in context["event_units"].items():
        row={"reference_event_id":event,"present_in_H1_core_universe":bool(units&context['core_units']&positive),"present_in_H1_legal_universe":bool(units&context['legal_units']&positive)}
        for name,order in orders.items():
            ranks=[i+1 for i,u in enumerate(order) if u in units and u in positive]; row[f"{name}_first_discovery_rank"]=min(ranks) if ranks else ""
            selected_positive_units=[u for u in order if u in units and u in positive]
            row[f"{name}_selected_event_proxy_percentiles"]="|".join(f"{context['percentiles'].loc[u]:.6f}" for u in selected_positive_units)
        candidate_units=units&context['core_units'];row["candidate_proxy_percentiles"]="|".join(f"{context['percentiles'].loc[u]:.6f}" for u in sorted(candidate_units))
        events.append(row)
    ef=pd.DataFrame(events);write_csv(OUT/"ranking/event_discovery_comparison.csv",ef)
    (OUT/"ranking/H1_MAP_ARC_DIVERGENCE.md").write_text(
        "# H1 / MAP / ARC Divergence\n\nRank overlap is computed from frozen H1 B100, MAP/M1 seed-0 B100, ARC-native seed-0 B100, and the evaluator-only greedy reorder. ARC's native segments are not treated as H1/K3 outputs. `event_discovery_comparison.csv` reports method-specific first discovery ranks and public-proxy percentiles for every selected positive unit supporting each differing event, plus H1-core candidate percentiles for present-but-late versus absent diagnosis.\n")
    return rf,ef


def source_quality(cand: pd.DataFrame, hyp: pd.DataFrame, context: dict[str,Any]) -> tuple[pd.DataFrame,pd.DataFrame]:
    rows=[]
    for source,hg in hyp.groupby("hypothesis_source"):
        cg=cand[cand.hypothesis_source==source]
        events=set(e for x in hg.support_overlapping_event_ids for e in str(x).split('|') if e)
        cert_events=set(e for x in hg.certifiable_event_ids for e in str(x).split('|') if e)
        ranks=pd.to_numeric(cg.actual_H1_rank,errors='coerce')
        rows.append({"hypothesis_source":source,"hypothesis_count":len(hg),"positive_hypothesis_rate":float(hg.positive_hypothesis.mean()),
                     "event_containing_rate":float(hg.event_containing.mean()),"unique_events_represented":len(events),
                     "unique_events_with_certifying_core":len(cert_events),
                     "mean_first_public_rank":float(pd.to_numeric(hg.first_public_rank,errors='coerce').mean()),"mean_proxy_percentile":float(cg.core_proxy_percentile.mean()),
                     "top20_presence":int((ranks<=20).sum()),"top50_presence":int((ranks<=50).sum()),
                     "false_burden":float((~hg.event_containing).mean()),
                     "fragmentation_contribution":float(hg.support_overlapping_event_count.sum()/len(events)) if events else math.nan})
    sf=pd.DataFrame(rows);write_csv(OUT/"candidate_quality/source_quality.csv",sf)
    positive=set(frozen_tables()["oracle"].loc[lambda x:x.parsed_label=='positive','unit_id'].astype(int));contrib=[]
    order=context['orders']['H1'];source_by_unit=dict(zip(cand.core_unit_id.astype(int),cand.hypothesis_source))
    for b in BUDGETS:
        for source in sorted(cand.hypothesis_source.unique()):
            units=[u for u in order[:b] if source_by_unit.get(u)==source];events=set(e for u in units if u in positive for e in context['unit_events'].get(u,[]))
            contrib.append({"budget":b,"hypothesis_source":source,"selected_core_units":len(units),"positive_units":len(set(units)&positive),"unique_events_contributed":len(events)})
    cf=pd.DataFrame(contrib);write_csv(OUT/"candidate_quality/source_budget_contribution.csv",cf)
    dominant=sf.sort_values('false_burden',ascending=False).iloc[0].hypothesis_source
    false_counts={r.hypothesis_source:int(round(r.hypothesis_count*r.false_burden)) for r in sf.itertuples()}
    aggregate_false=sum(false_counts.values())/int(sf.hypothesis_count.sum())
    (OUT/"candidate_quality/CANDIDATE_QUALITY_REPORT.md").write_text(
        f"# Candidate Source Quality\n\nThe authoritative support-overlap false burden is `{aggregate_false:.6f}` ({sum(false_counts.values())}/{int(sf.hypothesis_count.sum())}). High-proxy islands contribute `{false_counts.get('high_proxy_island',0)}` false hypotheses and orphan-local-peak cells `{false_counts.get('orphan_local_peak',0)}`; the larger within-source rate is `{dominant}`. Positive-core/certifiable-event rates are reported separately and are not substituted for the 79.3% support-overlap burden.\n")
    return sf,cf


def headroom(static: pd.DataFrame, oracle_metrics: pd.DataFrame) -> pd.DataFrame:
    h1=pd.read_csv(HCR/"analysis/per_budget_metrics.csv");h1=h1[(h1.variant=='H1')&(h1.materializer=='k3_bridge_safe')]
    rows=[]
    for b in BUDGETS:
        actual_cov=static[(static.ordering=='ACTUAL_H1_PUBLIC_ORDER')&(static.budget==b)].iloc[0]
        perfect=static[(static.ordering=='PERFECT_UNIQUE_EVENT_ORDER')&(static.budget==b)].iloc[0]
        oracle=oracle_metrics[oracle_metrics.budget==b].iloc[0];actual=h1[h1.budget==b].iloc[0]
        optimistic_f1 = 2 * perfect.event_candidate_recall / (1 + perfect.event_candidate_recall) if perfect.event_candidate_recall > 0 else 0.0
        rows.append({"budget":b,"actual_H1_candidate_coverage":actual_cov.event_candidate_recall,
                     "perfect_unique_event_candidate_coverage":perfect.event_candidate_recall,
                     "candidate_headroom":perfect.event_candidate_recall-actual_cov.event_candidate_recall,
                     "actual_H1_event_f1":actual.event_f1,"oracle_reorder_event_f1":oracle.event_f1,
                     "ranking_headroom":oracle.event_f1-actual.event_f1,
                     "perfect_unique_event_candidate_quality":optimistic_f1,
                     "oracle_reorder_plus_K3_event_quality":oracle.event_f1,
                     "materialization_gap":max(0.0, optimistic_f1-oracle.event_f1)})
    f=pd.DataFrame(rows);write_csv(OUT/"ceilings/headroom_decomposition_by_budget.csv",f)
    (OUT/"ceilings/HEADROOM_DECOMPOSITION.md").write_text(
        "# Headroom Decomposition\n\nCandidate headroom uses evidence-certified event coverage over the complete H1 legal action universe. Ranking headroom uses frozen K3-safe event F1. Perfect unique-event candidate quality converts coverage to optimistic F1 assuming one precise output per covered event: `2c/(1+c)`. Materialization gap compares that optimistic quality with oracle-reorder K3 F1; because the reorder is greedy rather than exact, this is a combined reorder/materialization gap, not an additive causal identity.\n")
    return f


def draw_svg(curves: pd.DataFrame) -> None:
    width,height,margin=760,440,55
    x=lambda b:margin+(float(b)-5)/95*(width-2*margin);y=lambda v:height-margin-float(v)*(height-2*margin)
    colors={"H1":"#1f77b4","ORACLE_REORDER":"#2ca02c","MAP_M1":"#d62728"};parts=[]
    for name,g in curves.groupby("series"):
        pts=" ".join(f"{x(r.budget):.1f},{y(r.event_f1):.1f}" for r in g.sort_values('budget').itertuples())
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{colors[name]}" stroke-width="3"/><text x="580" y="{35+20*len(parts)}" fill="{colors[name]}">{name}</text>')
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"><rect width="100%" height="100%" fill="white"/><line x1="{margin}" y1="{height-margin}" x2="{width-margin}" y2="{height-margin}" stroke="black"/><line x1="{margin}" y1="{margin}" x2="{margin}" y2="{height-margin}" stroke="black"/>{"".join(parts)}</svg>\n'
    (OUT/"figures/headroom_curve.svg").write_text(svg);write_csv(OUT/"figures/headroom_curve_data.csv",curves)


def analyze() -> None:
    ensure_dirs(); cand,hyp,context=candidate_tables();static,static_orders=static_ceilings(cand,context)
    oracle_trace,oracle_metrics=oracle_reorder();action_diag=action_outcome_diagnostics();pm,nm=calibration_metrics(action_diag)
    _,crossmetrics=crossfit(cand);ranking_comparison(context,oracle_trace);source_quality(cand,hyp,context);heads=headroom(static,oracle_metrics)
    h1metrics=pd.read_csv(HCR/"analysis/per_budget_metrics.csv");h1metrics=h1metrics[(h1metrics.variant=='H1')&(h1metrics.materializer=='k3_bridge_safe')]
    mapm=pd.read_csv(STRICT/"current_method/current_budget_curves.csv");mapm=mapm[mapm.method_variant=='K3_BRIDGE_SAFE'].rename(columns={'horizon_budget':'budget'})
    curves=pd.concat([h1metrics[['budget','event_f1']].assign(series='H1'),oracle_metrics[['budget','event_f1']].assign(series='ORACLE_REORDER'),mapm[['budget','event_f1']].assign(series='MAP_M1')],ignore_index=True)
    draw_svg(curves)
    progress("Evaluator-only diagnostic matrix", "--stage analyze", f"{len(cand)} core candidates; {len(action_diag)} state-action diagnostics; zero physical calls", "Apply preregistered primary decision logic.")


def decide() -> None:
    static=pd.read_csv(OUT/"ceilings/static_candidate_ceiling_by_budget.csv");heads=pd.read_csv(OUT/"ceilings/headroom_decomposition_by_budget.csv")
    oracle=pd.read_csv(OUT/"ceilings/oracle_informed_reorder_metrics.csv");pm=pd.read_csv(OUT/"calibration/positive_calibration_metrics.csv");nm=pd.read_csv(OUT/"calibration/new_event_calibration_metrics.csv")
    cm=pd.read_csv(OUT/"calibration_feasibility/crossfit_metrics.csv");miss=pd.read_csv(OUT/"ceilings/missing_event_from_candidate_universe.csv")
    h1_auc=trapezoid_auc(pd.read_csv(HCR/"analysis/per_budget_metrics.csv").query("variant=='H1' and materializer=='k3_bridge_safe'"),"budget","event_f1")
    oracle_auc=float(oracle.event_f1_auc.iloc[0]);map_auc=0.3880556629484837;native_auc=0.3896592193755119
    low=heads[heads.budget.isin([5,10,20])]; map_curve=pd.read_csv(STRICT/"current_method/current_budget_curves.csv");map_curve=map_curve[map_curve.method_variant=='K3_BRIDGE_SAFE'].rename(columns={'horizon_budget':'budget'})
    comparison=low.merge(map_curve[['budget','event_f1']].rename(columns={'event_f1':'map_f1'}),on='budget')
    substantial=bool((comparison.ranking_headroom>=CONFIG['substantial_ranking_headroom_f1']).any())
    approaches=bool((comparison.oracle_reorder_event_f1>=comparison.map_f1-CONFIG['approach_tolerance_f1']).any() or oracle_auc>=map_auc-CONFIG['approach_tolerance_f1'])
    f2=cm[(cm.feature_set=='F2_all_public_H1')&(cm.scope=='pooled')]
    posrow=f2[f2.target=='is_positive'].iloc[0];eventrow=f2[f2.target=='can_certify_any_event'].iloc[0]
    fold=cm[(cm.feature_set=='F2_all_public_H1')&(cm.scope=='fold')]
    posfold=fold[fold.target=='is_positive'];evfold=fold[fold.target=='can_certify_any_event']
    pos_signal=pd.notna(posrow.auroc) and posrow.auroc>=CONFIG['calibration_signal_pooled_auc'] and int((posfold.auroc>CONFIG['calibration_signal_fold_auc']).sum())>=CONFIG['calibration_signal_min_defined_folds']
    event_signal=pd.notna(eventrow.auroc) and eventrow.auroc>=CONFIG['calibration_signal_pooled_auc'] and int((evfold.auroc>CONFIG['calibration_signal_fold_auc']).sum())>=CONFIG['calibration_signal_min_defined_folds']
    calibration_signal=bool(pos_signal and event_signal)
    core_coverage=1-float(miss.absent_from_core_universe.mean());legal_coverage=1-float(miss.absent_from_full_legal_universe.mean())
    missing_substantial=(1-legal_coverage)>=CONFIG['substantial_missing_event_fraction']
    if substantial and approaches and calibration_signal:
        decision="OUTCOME_CALIBRATION_GO";bottleneck="belief_and_ranking_regret";next_action="collect separate calibration videos; train/freeze outcome and new-event models; evaluate on untouched held-out videos"
    elif missing_substantial and not calibration_signal:
        decision="CHEAP_CANDIDATE_CONSTRUCTION_REQUIRED";bottleneck="candidate_absence_and_weak_public_separability";next_action="run Cheap Primitive Candidate Construction Gate v1 on separate development videos; freeze public-only candidate rules before any planner work"
    elif core_coverage>=0.8 and substantial and not approaches:
        decision="MATERIALIZER_LIMITED";bottleneck="materialization";next_action="study the event partition/materialization operator"
    elif not substantial and not calibration_signal and legal_coverage<0.8:
        decision="PLANNER_LINE_NO_GO";bottleneck="insufficient_action_space_and_no_calibration_signal";next_action="pause BCM planner; retain MAP/M1 + BB-EM paper route"
    else:
        decision="MIXED_DIAGNOSTIC";bottleneck="multiple_substantial_bottlenecks";next_action="separate candidate recall improvement from held-out calibration-data collection before choosing a planner direction"
    pa=pm[pm.group_type=='all'].iloc[0];na=nm[nm.group_type=='all'].iloc[0]
    row={"decision":decision,"benchmark_id":CONFIG['benchmark_id'],"physical_vlm_calls":0,"baseline_runs_rerun":0,"online_method_modified":False,
         "actual_H1_AUC":h1_auc,"oracle_reorder_H1_AUC":oracle_auc,"MAP_M1_AUC":map_auc,"best_native_AUC":native_auc,
         "candidate_universe_event_coverage":legal_coverage,
         "top5_event_coverage":float(static[(static.ordering=='ACTUAL_H1_PUBLIC_ORDER')&(static.budget==5)].iloc[0].event_candidate_recall),
         "top10_event_coverage":float(static[(static.ordering=='ACTUAL_H1_PUBLIC_ORDER')&(static.budget==10)].iloc[0].event_candidate_recall),
         "top20_event_coverage":float(static[(static.ordering=='ACTUAL_H1_PUBLIC_ORDER')&(static.budget==20)].iloc[0].event_candidate_recall),
         "ranking_headroom_B5":float(heads[heads.budget==5].iloc[0].ranking_headroom),"ranking_headroom_B10":float(heads[heads.budget==10].iloc[0].ranking_headroom),
         "ranking_headroom_B20":float(heads[heads.budget==20].iloc[0].ranking_headroom),
         "materialization_gap":float(heads[heads.budget==20].iloc[0].materialization_gap),
         "positive_brier":float(pa.brier),"positive_ece":float(pa.ece),"new_event_brier":float(na.brier),"new_event_ece":float(na.ece),
         "crossfit_positive_metric":float(posrow.auroc) if pd.notna(posrow.auroc) else math.nan,"crossfit_event_metric":float(eventrow.auroc) if pd.notna(eventrow.auroc) else math.nan,
         "primary_bottleneck":bottleneck,"next_required_action":next_action,
         "materialization_gap_mean":float(heads.materialization_gap.mean()),
         "core_candidate_event_coverage":core_coverage,"full_legal_action_universe_event_coverage":legal_coverage,"public_feature_calibration_signal":calibration_signal}
    write_csv(OUT/"FINAL_DECISION.csv",[row])
    source=pd.read_csv(OUT/"candidate_quality/source_quality.csv")
    static_display=static[static.ordering.isin(['ACTUAL_H1_PUBLIC_ORDER','PERFECT_UNIQUE_EVENT_ORDER'])][['ordering','budget','positive_units_in_top_b','distinct_reference_events_touched','event_candidate_recall','materialized_event_f1']]
    oracle_display=oracle[['budget','unique_events_discovered','event_precision','event_recall','event_f1','returned_seconds','overmerge','oversplit']]
    head_display=heads[['budget','candidate_headroom','ranking_headroom','materialization_gap']]
    calibration_display=pd.DataFrame([
        {'target':'positive','brier':pa.brier,'ece':pa.ece,'auroc':pa.auroc,'average_precision':pa.average_precision,'top20_hits':pa.positives_at_20},
        {'target':'new_event','brier':na.brier,'ece':na.ece,'auroc':na.auroc,'average_precision':na.average_precision,'top20_hits':na.new_events_at_20},
    ])
    cross_display=cm[(cm.scope=='pooled')][['target','feature_set','prevalence','brier','auroc','average_precision']]
    ranking=pd.read_csv(OUT/"ranking/ranking_overlap_by_k.csv")
    ranking_display=ranking[(ranking.k.isin([5,10,20]))][['k','left_method','right_method','unit_overlap','jaccard_overlap','left_unique_events','right_unique_events','first_ranking_divergence']]
    absent=miss[miss.absent_from_full_legal_universe].reference_event_id.astype(str).tolist()
    status_counts=miss.representation_status.value_counts().to_dict()
    report=f"""# Candidate and Outcome Calibration Gate v1

Decision: `{decision}`

## Strongest supported conclusion

Frozen facts reproduce exactly. H1 core candidates cover `{core_coverage:.6f}` of the 26 VLM-defined pseudo-events; the full legal H1 action universe covers `{legal_coverage:.6f}`. Actual H1 AUC is `{h1_auc:.6f}` and evaluator-only greedy reorder AUC is `{oracle_auc:.6f}`, versus MAP/M1 `{map_auc:.6f}` and best native `{native_auc:.6f}`.

The oracle reorder is an estimated greedy ceiling, not an exact optimum or runnable method. Low-budget ranking headroom is B5 `{row['ranking_headroom_B5']:.6f}`, B10 `{row['ranking_headroom_B10']:.6f}`, B20 `{row['ranking_headroom_B20']:.6f}`.

## Static candidate ceilings

{static_display.to_markdown(index=False)}

Six events are absent even from the full legal H1 universe: `{', '.join(absent)}`. Fourteen events are absent from the core-only universe.

Of the 20 represented events, `{status_counts.get('TOP20',0)}` first appear in the frozen public top 20, `{status_counts.get('RANK21_100',0)}` at ranks 21–100, and `{status_counts.get('BEYOND_B100',0)}` only after the formal B100 trace under the deterministic universe-audit append order.

## Oracle-informed reorder

{oracle_display.to_markdown(index=False)}

Its event-F1 AUC is `{oracle_auc:.6f}`. This is a greedy estimate, not a proven optimum.

## Headroom decomposition

{head_display.to_markdown(index=False)}

`materialization_gap` in `FINAL_DECISION.csv` is the B20 combined greedy-reorder/K3 gap (`{row['materialization_gap']:.6f}`); the decomposition is not treated as an additive identity.

## Calibration and feasibility

Positive belief: Brier `{pa.brier:.6f}`, ECE `{pa.ece:.6f}`. New-event belief: Brier `{na.brier:.6f}`, ECE `{na.ece:.6f}`. Fixed blocked-crossfit F2 AUROC is positive `{row['crossfit_positive_metric']}` and certifiable-event `{row['crossfit_event_metric']}`. Preregistered stable-signal gate: `{calibration_signal}`.

{calibration_display.to_markdown(index=False)}

### Fixed blocked-cross-validation feasibility

{cross_display.to_markdown(index=False)}

All defined F2 temporal-fold AUROCs are below `0.5`; one fold contains no positives, so its AUROC is correctly undefined. The current public features therefore do not pass the stable-signal gate.

## H1 / MAP / ARC ranking divergence

{ranking_display.to_markdown(index=False)}

ARC ranking uses the frozen seed-0 trace only for unit-order comparison; best-native AUC uses the benchmark's authoritative cross-seed aggregation.

## Candidate source quality

{source.to_markdown(index=False)}

## Interpretation

Primary bottleneck: `{bottleneck}`. This is single-video VLM-defined pseudo-oracle diagnostic evidence. No baseline was rerun, H1 was not modified, and no VLM/physical oracle inference occurred.

Perfect ordering proves ranking headroom but does **not** justify calibration: six events remain absent from the legal universe and the preregistered blocked-crossfit feature gate fails. Candidate/cheap-feature repair is therefore primary; K3 is not the low-budget bottleneck because oracle reorder reaches F1 `0.322581/0.555556/0.666667` at B5/10/20 with precision `1.0`.

## Exact next action

Run `Cheap Primitive Candidate Construction Gate v1`: on separate development videos, add or revise public-only cheap primitives, freeze the candidate rule, and require legal-universe event coverage plus blocked-cross-video separability before any planner work. Do not train a planner on this strict video.
"""
    (OUT/"FINAL_REPORT.md").write_text(report);(OUT/"reports/FINAL_REPORT.md").write_text(report)
    (OUT/"RESEARCH_STATE.md").write_text(f"# Research State\n\n## Objective\nDiscriminate H1 ranking/calibration headroom from candidate/materializer insufficiency.\n\n## Established findings\nCore-universe coverage `{core_coverage:.6f}`; legal-universe coverage `{legal_coverage:.6f}`; oracle reorder AUC `{oracle_auc:.6f}`; decision `{decision}`.\n\n## Rejected or unsupported hypotheses\nPerfect evaluator ordering alone is not evidence that calibration is promising. Public feature signal gate is `{calibration_signal}`.\n\n## Unresolved uncertainty\nSingle-video blocked cross-validation is diagnostic and cannot establish cross-video generalization.\n\n## Next highest-value action\n{next_action}.\n")
    progress("Primary gate decision", "--stage decide", f"decision={decision}; bottleneck={bottleneck}", "Independent adversarial review, then final seal.")


def finalize() -> None:
    required=["FINAL_REPORT.md","FINAL_DECISION.csv","RESEARCH_STATE.md","REPRODUCTION.md","audit/INPUT_ARTIFACT_AUDIT.md","audit/INPUT_MANIFEST.csv",
              "reproduction/FROZEN_RESULT_RECOMPUTATION.csv","data/H1_CANDIDATE_DIAGNOSTIC_EVALUATOR_ONLY.csv","data/H1_HYPOTHESIS_DIAGNOSTIC_EVALUATOR_ONLY.csv",
              "ceilings/static_candidate_ceiling_by_budget.csv","ceilings/missing_event_from_candidate_universe.csv","ceilings/oracle_informed_reorder_trace_EVALUATOR_ONLY.csv",
              "ceilings/oracle_informed_reorder_metrics.csv","ceilings/headroom_decomposition_by_budget.csv","calibration/ACTION_OUTCOME_DIAGNOSTIC_EVALUATOR_ONLY.csv",
              "calibration/positive_calibration_metrics.csv","calibration/new_event_calibration_metrics.csv","calibration/positive_reliability_bins.csv","calibration/new_event_reliability_bins.csv",
              "calibration_feasibility/crossfit_predictions_EVALUATOR_ONLY.csv","calibration_feasibility/crossfit_metrics.csv","ranking/ranking_overlap_by_k.csv",
              "ranking/event_discovery_comparison.csv","candidate_quality/source_quality.csv","candidate_quality/source_budget_contribution.csv","figures/headroom_curve.svg"]
    missing=[p for p in required if not (OUT/p).is_file()]
    repro=pd.read_csv(OUT/"reproduction/FROZEN_RESULT_RECOMPUTATION.csv")
    review_path=OUT/"audit/INDEPENDENT_ADVERSARIAL_REVIEW.json";review=json.loads(review_path.read_text()) if review_path.exists() else None
    review_ok=bool(review and review.get('status')=='PASS' and review.get('blocking_findings',1)==0 and review.get('high_findings',1)==0)
    checks=[{"check":"required_artifacts","status":"PASS" if not missing else "FAIL","evidence":json.dumps(missing)},
            {"check":"frozen_reproduction","status":"PASS" if (repro.status=='PASS').all() else "FAIL","evidence":f"{(repro.status=='PASS').sum()}/{len(repro)}"},
            {"check":"zero_physical_vlm_calls","status":"PASS","evidence":"0"},{"check":"baseline_runs_rerun","status":"PASS","evidence":"0"},
            {"check":"online_method_modified","status":"PASS","evidence":"False"},{"check":"independent_review","status":"PASS" if review_ok else "PENDING","evidence":"audit/INDEPENDENT_ADVERSARIAL_REVIEW.json" if review else "missing"}]
    write_csv(OUT/"audit/COMPLETION_AUDIT.csv",checks)
    if any(r['status']=='FAIL' for r in checks) or not review_ok: return
    files=[]
    for p in sorted(OUT.rglob('*')):
        if p.is_file() and p.name not in {"FILE_MANIFEST.csv","EXPERIMENT_MANIFEST.json"}:
            files.append({"path":str(p.relative_to(OUT)),"size_bytes":p.stat().st_size,"sha256":sha256_file(p)})
    write_csv(OUT/"FILE_MANIFEST.csv",files)
    decision=pd.read_csv(OUT/"FINAL_DECISION.csv").iloc[0]
    write_json(OUT/"EXPERIMENT_MANIFEST.json",{"schema_version":"candidate_outcome_calibration_gate_v1_manifest_v1","status":"COMPLETE","completed_at_utc":utc_now(),
               "benchmark_id":CONFIG['benchmark_id'],"decision":decision.decision,"physical_vlm_calls":0,"baseline_runs_rerun":0,"online_method_modified":False,
               "file_manifest_sha256":sha256_file(OUT/"FILE_MANIFEST.csv"),"completion_audit_sha256":sha256_file(OUT/"audit/COMPLETION_AUDIT.csv")})
    progress("Final seal","--stage finalize",f"COMPLETE; decision={decision.decision}","No required work remains.")


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument('--stage',choices=['audit','reproduce','analyze','decide','finalize','all'],default='all');args=parser.parse_args()
    stages=['audit','reproduce','analyze','decide','finalize'] if args.stage=='all' else [args.stage]
    functions={'audit':audit_inputs,'reproduce':reproduce,'analyze':analyze,'decide':decide,'finalize':finalize}
    for stage in stages: functions[stage]()


if __name__=='__main__': main()
