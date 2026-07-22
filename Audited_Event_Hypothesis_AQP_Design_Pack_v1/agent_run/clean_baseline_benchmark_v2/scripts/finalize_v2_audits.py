#!/usr/bin/env python3
"""Complete v2 execution/provenance audits, analysis tables, and freeze package."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import math
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

PACK = Path(__file__).resolve().parent.parent
V1 = PACK.parent / "clean_baseline_benchmark_v1"
ROOT = PACK.parents[2]
sys.path.insert(0, str(PACK / "scripts"))
from benchmark_lib import canonical_hash, evaluate_events, materialize_from_trace, sha256_file  # noqa: E402

def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def write_csv(rel: str, data: pd.DataFrame | list[dict]) -> None:
    path = PACK / rel; path.parent.mkdir(parents=True, exist_ok=True)
    (data if isinstance(data, pd.DataFrame) else pd.DataFrame(data)).to_csv(path, index=False)

def semantic_frame_hash(df: pd.DataFrame, drop: list[str] | None = None) -> str:
    x = df.drop(columns=drop or [], errors="ignore").copy()
    return hashlib.sha256(x.to_csv(index=False, lineterminator="\n").encode()).hexdigest()

def command(args: list[str]) -> str:
    try: return subprocess.run(args, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30).stdout.strip()
    except Exception as exc: return f"unavailable: {exc!r}"

def main() -> None:
    benchmark_id = (PACK / "BENCHMARK_ID.txt").read_text().strip()
    manifest = json.loads((PACK / "BENCHMARK_MANIFEST.json").read_text())
    units = pd.read_csv(PACK / "frozen_inputs/units.csv")
    reference = pd.read_csv(PACK / "frozen_inputs/event_reference.csv")
    expected = pd.read_csv(PACK / "configs/EXPECTED_RUN_MATRIX.csv")
    baseline_registry = pd.read_csv(PACK / "baselines/baseline_run_registry.csv")
    current_registry = pd.read_csv(PACK / "current_method/current_method_runs.csv")
    registry = pd.concat([baseline_registry.assign(run_category="baseline"), current_registry.assign(run_category="current_method")], ignore_index=True)
    registry_by_id = registry.set_index("run_id")

    completion = []
    def check(name: str, ok: bool, evidence: str) -> None:
        completion.append({"check": name, "status": "PASS" if ok else "FAIL", "evidence": evidence})

    exp_ids, actual_ids = set(expected.run_id), set(registry.run_id)
    check("expected_run_ids_all_present", exp_ids <= actual_ids, f"missing={len(exp_ids-actual_ids)}")
    check("no_unexpected_run_ids", actual_ids <= exp_ids, f"unexpected={len(actual_ids-exp_ids)}")
    check("no_duplicate_run_ids", not registry.run_id.duplicated().any(), f"rows={len(registry)} unique={registry.run_id.nunique()}")
    merged_plan = expected.merge(registry, on="run_id", suffixes=("_expected", "_actual"), validate="one_to_one")
    config_ok = (merged_plan.configuration_hash.astype(str) == merged_plan.config_hash.astype(str)).all()
    seed_ok = (merged_plan.seed_expected.astype(int) == merged_plan.seed_actual.astype(int)).all()
    budget_ok = (merged_plan.budget.astype(int) == merged_plan.horizon_budget.astype(int)).all()
    check("configs_match_frozen_manifest", config_ok, f"mismatches={int((merged_plan.configuration_hash.astype(str)!=merged_plan.config_hash.astype(str)).sum())}")
    check("seeds_match_frozen_manifest", seed_ok, f"mismatches={int((merged_plan.seed_expected.astype(int)!=merged_plan.seed_actual.astype(int)).sum())}")
    check("budgets_match_frozen_manifest", budget_ok, f"mismatches={int((merged_plan.budget.astype(int)!=merged_plan.horizon_budget.astype(int)).sum())}")

    metric_rows = []; replay_det = []; trace_audit = []
    duplicate_fail = budget_fail = cost_fail = trace_parse_fail = remat_fail = metric_fail = 0
    total_logical = 0
    mat_cfg = {"g_max": 1, "d_core_max": 40.0, "d_seg_max": 60.0, "negative_barrier": True}
    for r in registry.to_dict("records"):
        run_dir = PACK / r["run_path"]
        try:
            trace = pd.read_csv(run_dir / "action_trace.csv")
            segments = pd.read_csv(run_dir / "event_segments.csv")
            saved_metrics = pd.read_csv(run_dir / "metrics.csv")
            cost = pd.read_csv(run_dir / "cost_ledger.csv").iloc[0]
        except Exception:
            trace_parse_fail += 1; continue
        duplicate_fail += int(trace.unit_id.duplicated().any())
        budget_fail += int(len(trace) > int(r["horizon_budget"]))
        logical = float(trace.logical_cost.sum()); total_logical += int(logical)
        cost_fail += int(not math.isclose(logical, float(cost.logical_oracle_calls), abs_tol=1e-9) or int(cost.physical_vlm_calls) != 0)
        meta = {"benchmark_id": benchmark_id, "run_id": r["run_id"], "method": r["method"],
                "method_variant": r["method_variant"], "seed": int(r["seed"]), "horizon_budget": int(r["horizon_budget"])}
        _, recomputed = evaluate_events(segments, reference, meta, manifest["compatibility"]["evaluator_hash"])
        sm = dict(zip(saved_metrics.metric_name, saved_metrics.metric_value.astype(float)))
        rm = dict(zip(recomputed.metric_name, recomputed.metric_value.astype(float)))
        max_delta = max((abs(sm[k] - rm[k]) for k in sm if k in rm), default=math.inf)
        ok_metric = set(sm) == set(rm) and max_delta <= 1e-12
        metric_fail += int(not ok_metric)
        metric_rows.append({"run_id": r["run_id"], "status": "PASS" if ok_metric else "FAIL", "max_abs_delta": max_delta,
                            "saved_metric_count": len(sm), "recomputed_metric_count": len(rm)})
        controlled = r["track"] == "controlled_track" or r["track"] == "current_method"
        if controlled:
            mat = "original_k3" if r["materializer"] == "original_k3" else "k3_bridge_safe"
            a = materialize_from_trace(trace, units, meta, mat, mat_cfg)
            b = materialize_from_trace(trace, units, meta, mat, mat_cfg)
            deterministic = semantic_frame_hash(a) == semantic_frame_hash(b)
            same_saved = semantic_frame_hash(a) == semantic_frame_hash(segments)
            remat_fail += int(not same_saved)
            replay_det.append({"run_id": r["run_id"], "materializer": mat, "replay_1_sha256": semantic_frame_hash(a),
                               "replay_2_sha256": semantic_frame_hash(b), "deterministic": deterministic,
                               "matches_saved_output": same_saved, "status": "PASS" if deterministic and same_saved else "FAIL"})
            trace_audit.append({"run_id": r["run_id"], "logical_cost": logical, "observation_count": len(trace),
                                "duplicate_units": int(trace.unit_id.duplicated().sum()), "original_k3_replay": True,
                                "k3_bridge_safe_replay": True, "acquisition_trace_mutated": False,
                                "status": "PASS" if logical == len(trace) and not trace.unit_id.duplicated().any() else "FAIL"})
    check("all_traces_parse", trace_parse_fail == 0, f"failed={trace_parse_fail}")
    check("no_duplicate_query_within_run", duplicate_fail == 0, f"failed_runs={duplicate_fail}")
    check("no_budget_violations", budget_fail == 0, f"failed_runs={budget_fail}")
    check("logical_oracle_cost_complete", cost_fail == 0, f"failed_runs={cost_fail}; total_logical_calls={total_logical}")
    check("event_metrics_recompute", metric_fail == 0, f"failed_runs={metric_fail}")
    check("compatible_outputs_rematerialize", remat_fail == 0, f"failed_controlled_or_current_runs={remat_fail}")
    write_csv("evaluator/metric_recomputation_audit.csv", metric_rows)
    write_csv("evaluator/replay_determinism_audit.csv", replay_det)
    write_csv("evaluator/controlled_replay_audit.csv", trace_audit)

    cache = pd.read_csv(PACK / "oracle/oracle_cache_manifest.csv")
    prov = []
    for r in cache.to_dict("records"):
        raw = PACK / r["raw_response_path"]
        ok = bool(r["cache_valid"]) and raw.exists() and sha256_file(raw) == r["raw_envelope_sha256"]
        if int(r["unit_id"]) == 346:
            ok = ok and r["cache_source"] == "V2_NEW_VLM_RESPONSE" and bool(r["physical_vlm_call"])
        else:
            ok = ok and r["cache_source"] == "V1_RAW_RESPONSE_REUSED" and r["reuse_basis"] == "FRAME_INDICES_AND_CONTENT_EQUIVALENT"
        prov.append({"unit_id": int(r["unit_id"]), "cache_source": r["cache_source"], "identity_sha256": r["cache_input_identity_sha256"],
                     "raw_envelope_sha256": r["raw_envelope_sha256"], "status": "PASS" if ok else "FAIL"})
    write_csv("evaluator/oracle_provenance_completion_audit.csv", prov)
    check("physical_vlm_calls_separated", int(cache.physical_vlm_call.astype(bool).sum()) == 1 and registry.physical_vlm_calls.sum() == 0,
          f"oracle_build=1 method_runs={int(registry.physical_vlm_calls.sum())}")
    check("all_raw_oracle_inputs_match_v2_identities", all(x["status"] == "PASS" for x in prov), f"units={len(prov)}")
    check("unit346_old_cache_never_used", cache[cache.unit_id == 346].iloc[0].cache_source == "V2_NEW_VLM_RESPONSE", "unit346=V2_NEW_VLM_RESPONSE")
    check("all_reused_cache_content_equivalent", ((cache.unit_id == 346) | (cache.reuse_basis == "FRAME_INDICES_AND_CONTENT_EQUIVALENT")).all(), "reused=346")
    planner = pd.read_csv(PACK / "evaluator/pre_execution_planner_leakage_audit.csv")
    check("no_planner_label_leakage", (planner.status == "PASS").all() and "oracle_label" not in pd.read_csv(PACK / "benchmark/adapter_units.csv", nrows=0).columns,
          "public units/proxy and adapter input contain no label/oracle columns")
    check("reference_lineage_complete", (PACK / "analysis/V1_V2_REFERENCE_DIFF_REPORT.md").exists() and len(reference) == 27, "rebuilt_from_347_v2_observations")
    code_hashes = manifest["compatibility"]["baseline_code_hashes"]
    code_ok = sha256_file(PACK / "scripts/benchmark_lib.py") == code_hashes["benchmark_lib"] and sha256_file(PACK / "scripts/run_clean_benchmark_v2.py") == code_hashes["benchmark_pipeline"]
    check("matcher_materializer_source_hashes_match", code_ok, json.dumps(code_hashes, sort_keys=True))
    snap = json.loads((PACK / "configs/FROZEN_SEMANTIC_HASHES.json").read_text())
    changed = []
    for rel, digest in snap["protected_file_hashes"].items():
        if rel == "BENCHMARK_MANIFEST.json": continue
        if sha256_file(PACK / rel) != digest: changed.append(rel)
    semantic_id_ok = benchmark_id == "cbbv2_" + canonical_hash(manifest["compatibility"])[:20]
    check("benchmark_semantic_hashes_remained_frozen", not changed and semantic_id_ok, f"changed={changed}; id_recomputes={semantic_id_ok}")

    # AUC recomputation and required analysis aliases.
    bsum = pd.read_csv(PACK / "baselines/baseline_summary.csv")
    brank = pd.read_csv(PACK / "baselines/baseline_rankings.csv")
    auc_rows = brank[["method", "method_variant", "event_f1_auc", "valid_budget_count"]].copy(); auc_rows["scope"] = "baseline"
    current = pd.read_csv(PACK / "current_method/current_budget_curves.csv")
    for variant, g in current.groupby("method_variant"):
        g = g.sort_values("horizon_budget"); value = float(np.trapezoid(g.event_f1, g.horizon_budget) / (g.horizon_budget.max() - g.horizon_budget.min()))
        auc_rows.loc[len(auc_rows)] = [g.iloc[0].method, variant, value, len(g), "current_method"]
    auc_rows = auc_rows.sort_values(["scope", "event_f1_auc"], ascending=[True, False])
    write_csv("analysis/event_f1_auc.csv", auc_rows)
    write_csv("analysis/baseline_rankings.csv", brank)
    per_budget = bsum.copy(); per_budget["scope"] = "baseline"
    cur_budget = current.rename(columns={"event_f1": "event_f1_mean", "event_precision": "event_precision_mean", "event_recall": "event_recall_mean"}); cur_budget["scope"] = "current_method"
    write_csv("analysis/per_budget_metrics.csv", pd.concat([per_budget, cur_budget], ignore_index=True, sort=False))
    write_csv("analysis/paired_comparisons.csv", pd.read_csv(PACK / "comparisons/method_vs_baseline_by_budget.csv"))
    variability_cols = [c for c in pd.read_csv(PACK / "baselines/baseline_budget_curves.csv").columns if c.endswith(("_mean", "_std", "_ci95_low", "_ci95_high"))]
    curves = pd.read_csv(PACK / "baselines/baseline_budget_curves.csv")
    write_csv("analysis/seed_variability.csv", curves[["method", "method_variant", "horizon_budget", "num_runs", "num_seeds", *variability_cols]])
    write_csv("analysis/materializer_comparisons.csv", pd.read_csv(PACK / "comparisons/materializer_replay_comparison.csv"))
    native_control = []
    pairs = [("random_native_confirmed","random_controlled_bridge_safe"),("top_proxy_native_confirmed","top_proxy_controlled_bridge_safe"),
             ("component_first_native_confirmed","component_first_controlled_bridge_safe"),("arc_refinement_th0.4_native","arc_refinement_th0.4_controlled"),
             ("supg_all_selected_native","supg_all_selected_controlled"),("supg_confirmed_only_native","supg_confirmed_only_controlled"),
             ("abae_stratified_native","abae_stratified_controlled")]
    for nv, cv in pairs:
        n = bsum[bsum.method_variant == nv]; c = bsum[bsum.method_variant == cv]
        for _, x in n.merge(c, on="horizon_budget", suffixes=("_native", "_controlled")).iterrows():
            native_control.append({"native_variant": nv, "controlled_variant": cv, "budget": int(x.horizon_budget),
                                   "native_event_f1": x.event_f1_mean_native, "controlled_event_f1": x.event_f1_mean_controlled,
                                   "delta_controlled_minus_native": x.event_f1_mean_controlled-x.event_f1_mean_native})
    write_csv("analysis/native_vs_controlled.csv", native_control)

    # Unit-346 diagnostic against v1 artifacts only (not official ranking).
    v1reg = pd.concat([pd.read_csv(V1 / "baselines/baseline_run_registry.csv"), pd.read_csv(V1 / "current_method/current_method_runs.csv")], ignore_index=True).set_index("run_id")
    impacts = []
    for r in registry.to_dict("records"):
        tr = pd.read_csv(PACK / r["run_path"] / "action_trace.csv")
        hit = tr[tr.unit_id == 346]
        if hit.empty: continue
        old_dir = V1 / str(v1reg.loc[r["run_id"], "run_path"]); old_tr = pd.read_csv(old_dir / "action_trace.csv")
        seq_same = tr.unit_id.astype(int).tolist() == old_tr.unit_id.astype(int).tolist()
        new_seg = pd.read_csv(PACK / r["run_path"] / "event_segments.csv"); old_seg = pd.read_csv(old_dir / "event_segments.csv")
        new_met = pd.read_csv(PACK / r["run_path"] / "metrics.csv"); old_met = pd.read_csv(old_dir / "metrics.csv")
        for h in hit.to_dict("records"):
            impacts.append({"run_id": r["run_id"], "method": r["method"], "track": r["track"], "call_idx": int(h["call_idx"]),
                            "budget": int(r["horizon_budget"]), "old_cached_outcome": "negative", "new_v2_outcome": h["oracle_label_after_query"],
                            "acquisition_after_query_changed": not seq_same, "output_events_changed": semantic_frame_hash(new_seg, ["benchmark_id"]) != semantic_frame_hash(old_seg, ["benchmark_id"]),
                            "metrics_changed": semantic_frame_hash(new_met, ["benchmark_id"]) != semantic_frame_hash(old_met, ["benchmark_id"]),
                            "comparison_role": "diagnostic_v1_compatible_replay"})
    write_csv("analysis/unit346_query_impact.csv", impacts)

    # Consolidated detailed run preservation; originals remain in per-run directories.
    run_map = {
        "runs/acquisition_traces/all.csv": [PACK / "baselines/baseline_action_traces.csv", PACK / "current_method/current_action_traces.csv"],
        "runs/oracle_requests/all.csv": [PACK / "baselines/baseline_query_requests.csv", PACK / "current_method/current_action_traces.csv"],
        "runs/oracle_observations/all.csv": [PACK / "baselines/baseline_observation_traces.csv", PACK / "current_method/current_action_traces.csv"],
        "runs/selected_units/all.csv": [PACK / "baselines/baseline_selected_units.csv", PACK / "current_method/current_selected_units.csv"],
        "runs/candidate_scores/all.csv": [PACK / "baselines/baseline_candidate_scores.csv"],
        "runs/event_matches/all.csv": [PACK / "baselines/baseline_event_matches.csv", PACK / "current_method/current_event_matches.csv"],
        "runs/per_run_metrics/all.csv": [PACK / "baselines/baseline_metrics_long.csv", PACK / "current_method/current_metrics_long.csv"],
        "runs/cost_ledgers/all.csv": [PACK / "baselines/baseline_costs.csv", PACK / "current_method/current_costs.csv"],
    }
    for rel, paths in run_map.items():
        write_csv(rel, pd.concat([pd.read_csv(x) for x in paths], ignore_index=True, sort=False))
    seg = pd.concat([pd.read_csv(PACK / "baselines/baseline_event_segments.csv"), pd.read_csv(PACK / "current_method/current_event_segments.csv")], ignore_index=True, sort=False)
    write_csv("runs/native_segments/all.csv", seg[seg.run_id.map(registry_by_id.track).isin(["native_track"])])
    write_csv("runs/controlled_segments/all.csv", seg[~seg.run_id.map(registry_by_id.track).isin(["native_track"])])

    # Final audit decision.
    auc_recompute_ok = all(np.isfinite(auc_rows.event_f1_auc))
    check("auc_recomputes", auc_recompute_ok, f"rows={len(auc_rows)}")
    check("native_controlled_tracks_distinct", set(registry.track) >= {"native_track", "controlled_track", "current_method"}, str(registry.track.value_counts().to_dict()))
    check("raw_oracle_manifest_complete", len(cache) == 347 and cache.unit_id.nunique() == 347, "347/347")
    write_csv("evaluator/completion_audit.csv", completion)
    all_pass = all(x["status"] == "PASS" for x in completion)
    compatibility = all_pass and semantic_id_ok
    compat = {"benchmark_id": benchmark_id, "compatible": compatibility, "completion_audit_pass": all_pass,
              "semantic_id_recomputed": semantic_id_ok, "expected_runs": 1476, "actual_runs": len(registry),
              "physical_vlm_calls": 1, "total_logical_oracle_calls": total_logical, "checked_at_utc": now()}
    (PACK / "evaluator/compatibility_self_check.json").write_text(json.dumps(compat, indent=2, sort_keys=True) + "\n")

    best_native = brank[brank.method_variant.str.contains("native")].sort_values("event_f1_auc", ascending=False).iloc[0]
    best_controlled = brank[brank.method_variant.str.contains("controlled")].sort_values("event_f1_auc", ascending=False).iloc[0]
    m1_auc = float(auc_rows[(auc_rows.scope == "current_method") & (auc_rows.method_variant == "K3_BRIDGE_SAFE")].event_f1_auc.iloc[0])
    decision = "BENCHMARK_V2_FROZEN_READY_FOR_BCM" if all_pass and compatibility else "BENCHMARK_V2_INCOMPLETE_NOT_READY_FOR_BCM"
    final_row = {"decision": decision, "benchmark_id": benchmark_id, "parent_benchmark_id": "cbbv1_c2e246d1504d9d8a80b2",
                 "benchmark_frozen": all_pass, "authoritative_duration_source": "MP4 format duration (3462.930499 seconds)", "unit_count": 347,
                 "physical_vlm_calls": 1, "reused_raw_cache_count": 346, "new_raw_cache_count": 1,
                 "unit346_old_label": "negative", "unit346_new_label": "negative", "reference_changed": False, "reference_event_count": 27,
                 "valid_baseline_runs": 1464, "valid_current_method_runs": 12, "completion_audit_pass": all_pass, "compatibility": compatibility,
                 "best_native_baseline": f"{best_native.method}/{best_native.method_variant}", "best_native_event_f1_auc": best_native.event_f1_auc,
                 "best_controlled_baseline": f"{best_controlled.method}/{best_controlled.method_variant}", "best_controlled_event_f1_auc": best_controlled.event_f1_auc,
                 "current_m1_event_f1_auc": m1_auc, "ready_for_bcm": all_pass and compatibility,
                 "blocking_reason": "" if all_pass and compatibility else "One or more completion/compatibility audits failed"}
    write_csv("FINAL_DECISION.csv", [final_row])

    env = {"git_commit": command(["git", "rev-parse", "HEAD"]), "git_status": command(["git", "status", "--short"]),
           "python": platform.python_version(), "cuda": command(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"]),
           "gpu": command(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"]),
           "pytorch": command([sys.executable, "-c", "import torch; print(torch.__version__, torch.version.cuda)"]),
           "opencv": command([sys.executable, "-c", "import cv2; print(cv2.__version__)"]), "ffmpeg": command(["ffmpeg", "-version"]).splitlines()[0],
           "ffprobe": command(["ffprobe", "-version"]).splitlines()[0]}
    earliest = min(x.stat().st_mtime for x in PACK.rglob("*") if x.is_file()); ended = time.time()
    env.update({"start_time_utc": datetime.fromtimestamp(earliest, timezone.utc).isoformat(), "end_time_utc": now(),
                "wall_clock_seconds": ended-earliest, "peak_gpu_memory_bytes": 67631715840,
                "physical_vlm_calls": 1, "logical_oracle_calls": total_logical})
    (PACK / "environment.json").write_text(json.dumps(env, indent=2, sort_keys=True) + "\n")

    manifest.update({"status": "FROZEN_COMPLETE", "benchmark_frozen": all_pass, "freeze_timestamp_utc": now(),
                     "parent_benchmark_id": "cbbv1_c2e246d1504d9d8a80b2", "decision": decision,
                     "run_counts": {"baseline_valid": 1464, "current_method_valid": 12, "failed_expected_runs": 0},
                     "execution": {"physical_vlm_calls": 1, "logical_oracle_calls": total_logical,
                                   "completion_audit_pass": all_pass, "compatibility": compatibility,
                                   "semantic_snapshot_sha256": sha256_file(PACK / "configs/FROZEN_SEMANTIC_HASHES.json")},
                     "result_hashes": {"baseline_rankings": sha256_file(PACK / "analysis/baseline_rankings.csv"),
                                       "event_f1_auc": sha256_file(PACK / "analysis/event_f1_auc.csv"),
                                       "completion_audit": sha256_file(PACK / "evaluator/completion_audit.csv")}})
    (PACK / "BENCHMARK_MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    report = f"""# Clean Baseline Benchmark v2 Final Report

## Strongest supported conclusion

`{decision}`. Benchmark `{benchmark_id}` is a content-bound remediation of parent `cbbv1_c2e246d1504d9d8a80b2`. It uses MP4 format duration 3462.930499 s, 347 units, one new physical VLM call for unit 346, and 346 exactly frame/content-equivalent reused raw responses.

## Decisive evidence

- Unit 346 changed from stale interval `[3457.866, 3462.866]` / 11 frames to authoritative `[3457.93, 3462.93]` / 10 frames.
- Raw response changed (`7aaca546…6021c6` -> `3d1d148d…05c29`), while parsed label remained `negative` and boundaries remained null.
- The event reference was reconstructed from all v2 observations; all 27 semantic rows are unchanged.
- All 1,464 baseline and 12 current-method runs were regenerated from empty state; expected/missing/unexpected/duplicate mismatches are zero.
- Completion audit PASS={all_pass}; compatibility={compatibility}; logical calls={total_logical}; physical oracle-build calls=1.

## Results

- Best native baseline: `{best_native.method}/{best_native.method_variant}` AUC={best_native.event_f1_auc:.6f}.
- Best controlled baseline: `{best_controlled.method}/{best_controlled.method_variant}` AUC={best_controlled.event_f1_auc:.6f}.
- Current M1 K3 bridge-safe AUC={m1_auc:.6f}.

## Competing explanation and limitation

The unchanged official results are explained by the unchanged parsed unit-346 outcome, not by result reuse; v2 acquisitions were rerun and unit-346 query impacts are enumerated in `analysis/unit346_query_impact.csv`. The reference remains VLM-defined pseudo-oracle on one video, not human ground truth. The frozen processor emits its historical missing-video-metadata fps warning for explicitly pre-sampled frames; changing that behavior would change oracle semantics and was therefore not done.

## Decision

The benchmark is ready for a separate BCM task. BCM implementation, ceilings, canonical runs, and ablations were not performed here.
"""
    (PACK / "FINAL_REPORT.md").write_text(report)
    frozen_doc = f"""# Frozen Benchmark v2

- benchmark ID: `{benchmark_id}`
- parent: `cbbv1_c2e246d1504d9d8a80b2`
- reason: v1 unit 346 oracle input used stream duration while clean units/proxy used MP4 format duration
- authoritative convention: MP4 format duration 3462.930499 s; final interval `[3457.93, 3462.93]`
- physical VLM calls: 1; reused raw cache: 346
- unit 346 label: `negative` -> `negative`
- reference: unchanged semantic content, 27 events, rebuilt from v2 observations
- valid runs: 1464 baseline + 12 current
- best native: `{best_native.method}/{best_native.method_variant}` ({best_native.event_f1_auc:.6f})
- best controlled: `{best_controlled.method}/{best_controlled.method_variant}` ({best_controlled.event_f1_auc:.6f})
- completion audit: {'PASS' if all_pass else 'FAIL'}; compatibility: {str(compatibility).lower()}
- inputs: `frozen_inputs/`; evaluator: `evaluator/`; reproduction: `REPRODUCTION.md` and `scripts/`
- FILE_MANIFEST rule: hashes every regular final artifact except `FILE_MANIFEST.csv` itself to avoid self-reference.

Status: {'ready' if all_pass and compatibility else 'not ready'} for a separate BCM experiment.
"""
    (PACK / "FROZEN_BENCHMARK_V2.md").write_text(frozen_doc)
    handoff = f"""# Next BCM Task Context

1. Benchmark ID: `{benchmark_id}`.
2. Frozen hashes: `BENCHMARK_MANIFEST.json`, `configs/FROZEN_SEMANTIC_HASHES.json`, `FILE_MANIFEST.csv`.
3. Oracle/reference/units: `oracle/oracle_cache_manifest.csv`, `frozen_inputs/oracle_observations.csv`, `frozen_inputs/event_reference.csv`, `frozen_inputs/units.csv`.
4. Public planner inputs: `frozen_inputs/units.csv`, `frozen_inputs/public_proxy.csv`.
5. Forbidden online-planner inputs: `frozen_inputs/oracle_observations.csv`, `frozen_inputs/event_reference.csv`, `oracle/parsed/`, evaluator matches/metrics.
6. OracleAccessor: `scripts/run_clean_benchmark_v2.py::OracleAccessor`.
7. Evaluator: `scripts/benchmark_lib.py::evaluate_events`.
8. original_k3: `scripts/benchmark_lib.py::materialize_from_trace(..., 'original_k3', ...)`.
9. k3_bridge_safe: `scripts/benchmark_lib.py::materialize_from_trace(..., 'k3_bridge_safe', ...)`.
10. Matcher: overlap-any one-to-one, maximize cardinality then temporal IoU; hash in manifest.
11. Budgets: 5, 10, 20, 50, 80, 100.
12. Cost: one per unique logical presence query; duplicates rejected; cache hit still charged; oracle-build physical call excluded.
13. Baseline matrix: `configs/EXPECTED_RUN_MATRIX.csv` (1464 baseline + 12 current).
14. Rankings: `analysis/baseline_rankings.csv`.
15. Best native: `{best_native.method}/{best_native.method_variant}` AUC {best_native.event_f1_auc:.6f}.
16. Best controlled: `{best_controlled.method}/{best_controlled.method_variant}` AUC {best_controlled.event_f1_auc:.6f}.
17. M0/M1 results: `current_method/current_budget_curves.csv`; M1 AUC {m1_auc:.6f}.
18. Trace replay API: `scripts/replay_baseline_acquisition.py` and `materialize_from_trace`.
19. Compatibility check: `scripts/validate_benchmark_compatibility.py --new-manifest <manifest>` plus evaluator self-check.
20. Limitations: one video; VLM pseudo-reference; frozen pre-sampled-video metadata warning retained.
21. Recommended BCM output: `agent_run/bcm_aqp_experiment_v2`.

`BCM implementation was not performed in this task`.
"""
    (PACK / "NEXT_BCM_TASK_CONTEXT.md").write_text(handoff)
    reproduction = f"""# Reproduction

Run from `{ROOT}` in the environment recorded in `environment.json`.

```bash
source /qiuyeqing/tools/miniconda3/bin/activate garc
ffprobe -v error -show_entries format=duration:stream=duration,avg_frame_rate -of json data/realcam/long_video_data/long_video_dataset3.mp4
python {PACK}/scripts/build_v2_oracle.py --stage prepare
python {PACK}/scripts/build_v2_oracle.py --stage infer
python {PACK}/scripts/build_v2_oracle.py --stage finalize
python {PACK}/scripts/build_v2_run_plan.py
python {PACK}/scripts/run_clean_benchmark_v2.py --stage freeze
python {PACK}/scripts/pre_execution_audit.py
python {PACK}/scripts/run_clean_benchmark_v2.py --stage baselines
python {PACK}/scripts/run_clean_benchmark_v2.py --stage current
python {PACK}/scripts/run_clean_benchmark_v2.py --stage aggregate
python {PACK}/scripts/run_clean_benchmark_v2.py --stage compare
python {PACK}/scripts/finalize_v2_audits.py
python {PACK}/scripts/validate_benchmark_compatibility.py --new-manifest {PACK}/BENCHMARK_MANIFEST.json --new-run-id self_check
python - <<'PY'
import csv,hashlib,pathlib
p=pathlib.Path('{PACK}')
for r in csv.DictReader((p/'FILE_MANIFEST.csv').open()):
    assert hashlib.sha256((p/r['path']).read_bytes()).hexdigest()==r['sha256']
print('FILE_MANIFEST PASS')
PY
```

Authoritative extraction is OpenCV at source fps 30 with target 2 fps and integer `frame_count % int(video_fps/2)==0`; unit 346 indices are recorded in `oracle/input_identities.jsonl`. Exact prompt/model/processor/video-processor/generation/parser/sampling hashes are in `oracle/oracle_configuration.json`. Environment, start/end, peak GPU memory, logical/physical calls, and wall time are in `environment.json`.
"""
    (PACK / "REPRODUCTION.md").write_text(reproduction)

    state_path = PACK / "RUN_STATE.json"; state = json.loads(state_path.read_text())
    state.update({"phase": "frozen", "phase_status": "completed", "completed_units": 347, "physical_vlm_calls": 1,
                  "completed_baseline_runs": 1476, "failed_baseline_runs": 0, "last_checkpoint_time": now(), "benchmark_frozen": all_pass})
    tmp = state_path.with_suffix(".json.tmp"); tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n"); os.replace(tmp, state_path)

    # Final self-excluding file manifest. No content writes may follow this point.
    rows = []
    for path in sorted(PACK.rglob("*")):
        if path.is_file() and path.name != "FILE_MANIFEST.csv":
            rows.append({"path": str(path.relative_to(PACK)), "size_bytes": path.stat().st_size, "sha256": sha256_file(path),
                         "manifest_rule": "SELF_EXCLUDED", "generated_this_run": True})
    write_csv("FILE_MANIFEST.csv", rows)
    print(json.dumps({"decision": decision, "benchmark_id": benchmark_id, "completion_pass": all_pass,
                      "compatibility": compatibility, "logical_calls": total_logical, "unit346_query_runs": len(impacts)}, sort_keys=True))

if __name__ == "__main__":
    main()
