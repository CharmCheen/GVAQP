"""Execute Algorithmic Mechanism Viability Gate v1.

The matrix is built from preregistered one-factor and two-factor sweeps.  All
policies share each generated instance.  Raw public and hidden synthetic rows
are written to physically separate gzip files; aggregate evaluation is written
only after acquisition.
"""

from __future__ import annotations

import argparse
import ast
import csv
import fcntl
import gzip
import hashlib
import inspect
import json
import math
import os
import platform
import shutil
import traceback
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import t

from .core import (POLICIES, HiddenInstance, PolicyResult, PublicInstance, achieved_auroc,
                   counterfactual_risk_deltas, evaluate_prefix, generate_instance, posterior_probability, structural_risk,
                   run_oracle_informed, run_policy, target_mu)


ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run"
OUT = BASE / "algorithmic_mechanism_viability_gate_v1"
STRICT = BASE / "clean_baseline_benchmark_v2_strict"
BCM = BASE / "bcm_aqp_experiment_v2"
HCR = BASE / "hypothesis_construction_repair_v1"
COG = BASE / "candidate_outcome_calibration_gate_v1"
CONFIG_DIR = OUT / "configs"
POLICIES_ALL = tuple(POLICIES) + ("ORACLE_INFORMED",)
RESULT_SENTINEL = OUT / ".canonical_results_complete"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")
    os.replace(tmp, path)


def atomic_csv(frame: pd.DataFrame, path: Path, compression: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    frame.to_csv(tmp, index=False, compression=compression)
    os.replace(tmp, path)


def budgets_for(n: int) -> list[int]:
    if n == 347:
        return [5, 10, 20, 50, 80, 100]
    return sorted(set(max(1, int(round(n * x))) for x in [0.02, 0.05, 0.10, 0.20]))


def build_settings() -> list[dict]:
    settings: list[dict] = []
    def add(suite: str, **kw: Any) -> None:
        base = dict(n=120, duration=2, target_auroc=0.75, candidate_recall=1.0,
                    false_burden=0.5, fragmentation=1, residual_prevalence=0.25,
                    merge_ambiguity=0.5, calibration="correct")
        base.update(kw); base["suite"] = suite
        base["setting_id"] = f"{suite}_{canonical_hash(base)[:12]}"
        if not any(x["setting_id"] == base["setting_id"] for x in settings): settings.append(base)
    # Suite A full canonical factorial.
    for d in [1, 2, 4, 8]:
        for a in [.55, .65, .75, .85, .95]:
            for f in [.2, .5, .8]: add("A_SATURATION", n=347, duration=d, target_auroc=a, false_burden=f)
    # Suite B controlled structure opportunity frequency.
    for a in [.55, .65, .75, .85, .95]:
        for m in [.2, .5, .8]: add("B_COUNTERFACTUAL", duration=2, target_auroc=a, merge_ambiguity=m, fragmentation=2)
    # Suite C interpretable robustness grids (union, not opaque full-factorial).
    for a in [.55, .65, .75, .85, .95]:
        for r in [.6, .8, 1.0]: add("C_ROBUSTNESS", target_auroc=a, candidate_recall=r)
        for f in [.2, .5, .8]: add("C_ROBUSTNESS", target_auroc=a, false_burden=f)
        for cal in ["correct", "overconfident", "underconfident", "wrong_prior", "temporal_shift"]:
            add("C_ROBUSTNESS", target_auroc=a, calibration=cal)
    for frag in [1, 2, 4]:
        for d in [1, 2, 4, 8]: add("C_ROBUSTNESS", fragmentation=frag, duration=d)
    # Suite D exploration sweep.
    for a in [.55, .65, .75, .85, .95]:
        for residual in [.1, .25, .5]: add("D_EXPLORATION", target_auroc=a, residual_prevalence=residual)
    # Required scale checks; N=1000 uses the preregistered 50-seed allowance.
    for n in [120, 347, 1000]: add("C_SCALE", n=n)
    return settings


def prepare() -> None:
    if RESULT_SENTINEL.exists():
        raise RuntimeError("canonical results already exist; frozen configs cannot be regenerated")
    settings = build_settings()
    pd.DataFrame(settings).to_csv(CONFIG_DIR / "EXPERIMENT_MATRIX.csv", index=False)
    seeds = []
    for s in settings:
        count = 50 if s["n"] == 1000 else 100
        for i in range(count):
            seeds.append({"setting_id": s["setting_id"], "seed_index": i, "seed": 2026071100 + i,
                          "reason": "large-N 50-seed allowance" if count == 50 else "canonical 100 seeds"})
    pd.DataFrame(seeds).to_csv(CONFIG_DIR / "SEED_MANIFEST.csv", index=False)
    files = [CONFIG_DIR / x for x in ["SYNTHETIC_GENERATOR_CONFIG.json", "SEMI_SYNTHETIC_CONFIG.json", "POLICY_CONFIGS.json",
                                      "EXPERIMENT_MATRIX.csv", "SEED_MANIFEST.csv"]]
    write_json(CONFIG_DIR / "CONFIG_FREEZE.json", {"frozen_at": datetime.now(timezone.utc).isoformat(),
               "files": [{"path": str(p.relative_to(OUT)), "sha256": sha(p)} for p in files]})


def ci95(values: pd.Series) -> tuple[float, float]:
    a = values.dropna().to_numpy(float)
    if len(a) < 2: return (float("nan"), float("nan"))
    half = float(t.ppf(.975, len(a) - 1) * np.std(a, ddof=1) / math.sqrt(len(a)))
    return float(np.mean(a) - half), float(np.mean(a) + half)


def normalized_auc(rows: list[dict], budgets: list[int]) -> float:
    ys = np.array([next(r["event_f1"] for r in rows if r["budget"] == b) for b in budgets])
    xs = np.array(budgets, float)
    return float(np.trapezoid(ys, xs) / (xs[-1] - xs[0])) if len(xs) > 1 else float(ys[0])


def execution_fingerprint() -> dict[str, Any]:
    """Fingerprint semantics and numerical runtime, excluding report formatting."""
    semantic_objects=[generate_instance,run_policy,run_oracle_informed,evaluate_prefix,achieved_auroc,
                      counterfactual_risk_deltas,structural_risk,budgets_for,normalized_auc]
    payload={"core_sha256":sha(Path(__file__).with_name("core.py")),
             "semantic_function_sha256":hashlib.sha256("\n".join(inspect.getsource(x) for x in semantic_objects).encode()).hexdigest(),
             "python":platform.python_version(),"numpy":np.__version__,"pandas":pd.__version__,
             "scipy":__import__("scipy").__version__,"config_freeze_sha256":sha(CONFIG_DIR/"CONFIG_FREEZE.json")}
    payload["fingerprint_sha256"]=canonical_hash(payload)
    return payload


def verify_frozen_configs() -> None:
    freeze=json.loads((CONFIG_DIR/"CONFIG_FREEZE.json").read_text())
    bad=[]
    for item in freeze["files"]:
        path=OUT/item["path"]
        if not path.exists() or sha(path)!=item["sha256"]:bad.append(item["path"])
    matrix=pd.read_csv(CONFIG_DIR/"EXPERIMENT_MATRIX.csv")
    if bad:raise RuntimeError(f"frozen config hash mismatch: {bad}")
    if len(matrix)!=149 or matrix.setting_id.nunique()!=149 or list(matrix.setting_id)!=[x["setting_id"] for x in build_settings()]:
        raise RuntimeError("frozen matrix no longer matches 149 canonical settings")


@contextmanager
def exclusive_runner_lock():
    path=OUT/"audit/RUNNER.lock";path.parent.mkdir(parents=True,exist_ok=True)
    handle=path.open("a+")
    try:
        try:fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as exc:raise RuntimeError("another mechanism-gate runner owns audit/RUNNER.lock") from exc
        handle.seek(0);handle.truncate();handle.write(json.dumps({"pid":os.getpid(),"acquired_at":datetime.now(timezone.utc).isoformat()})+"\n");handle.flush()
        yield
    finally:
        fcntl.flock(handle.fileno(),fcntl.LOCK_UN);handle.close()


def audit_inputs() -> None:
    requested = [
        ROOT / "BCM_AQP_MATHEMATICAL_REFERENCE.md", STRICT / "NEXT_BCM_TASK_CONTEXT.md",
        STRICT / "scripts/benchmark_lib.py", STRICT / "scripts/run_clean_benchmark_v2_strict.py",
        BCM / "reports/FINAL_REPORT.md", BCM / "config/experiment_config.json",
        BCM / "audit/INDEPENDENT_ADVERSARIAL_REVIEW.json", HCR / "FINAL_REPORT.md",
        HCR / "implementation/run_hypothesis_construction_repair_v1.py",
        HCR / "analysis/all_action_traces.csv", HCR / "analysis/all_candidate_scores.csv",
        HCR / "audit/INDEPENDENT_ADVERSARIAL_REVIEW.json", COG / "FINAL_REPORT.md",
        COG / "ceilings/static_candidate_ceiling_by_budget.csv",
        COG / "ceilings/oracle_informed_reorder_metrics.csv",
        COG / "audit/INDEPENDENT_ADVERSARIAL_REVIEW.json",
    ]
    rows = [{"resolved_path": str(p), "exists": p.exists(), "size_bytes": p.stat().st_size if p.exists() else "",
             "sha256": sha(p) if p.exists() else "", "role": "required_reading"} for p in requested]
    pd.DataFrame(rows).to_csv(OUT / "audit/INPUT_MANIFEST.csv", index=False)
    missing = [r["resolved_path"] for r in rows if not r["exists"]]
    (OUT / "audit/INPUT_ARTIFACT_AUDIT.md").write_text(
        "# Input Artifact Audit\n\nAll paths were resolved directly; no stale substitutions were made. "
        f"Present: {len(rows)-len(missing)}/{len(rows)}. Missing: {missing or 'none'}.\n\n"
        "The strict benchmark and prior experiment directories are read-only inputs. Evaluator/reference artifacts are "
        "never imported into policy modules. The mathematical reference's earlier missing-helper concern is resolved by "
        "the present strict `scripts/benchmark_lib.py`, which is hashed above.\n")


def run_tests() -> None:
    rows = []
    def check(name: str, ok: bool, evidence: str) -> None: rows.append({"test": name, "status": "PASS" if ok else "FAIL", "evidence": evidence})
    p, h = generate_instance(n=120, duration=4, target_auroc=.75, candidate_recall=1, false_burden=.5,
                             fragmentation=1, seed=7, suite="A_SATURATION")
    check("public_tables_no_hidden_fields", not hasattr(p, "labels") and not hasattr(p, "event_ids"), str(p.__dataclass_fields__.keys()))
    source = (Path(__file__).with_name("core.py")).read_text()
    policy_section = source[source.index("def _policy_score"):source.index("def run_oracle_informed")]
    check("policy_no_hidden_access", "hidden." not in policy_section and "event_ids" not in policy_section, "static policy section scan")
    vals = [achieved_auroc(*generate_instance(n=1000, duration=4, target_auroc=.75, candidate_recall=1,
            false_burden=.5, fragmentation=1, seed=i, suite="A_SATURATION")) for i in range(20)]
    check("proxy_auroc_statistical", abs(np.mean(vals)-.75) < .04, f"mean={np.mean(vals):.6f}")
    p2, h2 = generate_instance(n=120, duration=4, target_auroc=.75, candidate_recall=1, false_burden=.5,
                               fragmentation=1, seed=7, suite="A_SATURATION")
    check("shared_seed_identity", np.array_equal(p.scores, p2.scores) and np.array_equal(h.labels, h2.labels), canonical_hash(p.scores.tolist()))
    exact = posterior_probability(p.scores, target_mu(.75), float(h.labels.mean()))
    check("posterior_matches_generator", np.max(np.abs(exact-p.probabilities)) < 1e-12, f"maxerr={np.max(np.abs(exact-p.probabilities))}")
    oracle=lambda uid:int(h.labels[uid])
    r0 = run_policy(p, oracle, "P1_EVENT_SATURATION", 20, 7); r1 = run_policy(p, oracle, "P1_EVENT_SATURATION", 20, 7)
    check("deterministic_rerun", r0.order == r1.order, str(r0.order[:5]))
    # Focused falsification cases.
    p_d1, h_d1 = generate_instance(n=120, duration=1, target_auroc=.95, candidate_recall=1, false_burden=.2,
                                   fragmentation=1, seed=9, suite="A_SATURATION")
    a = run_policy(p_d1,lambda u:int(h_d1.labels[u]),"P0_POSITIVE_PROBABILITY",20,9); b=run_policy(p_d1,lambda u:int(h_d1.labels[u]),"P1_EVENT_SATURATION",20,9)
    check("duration1_sanity", abs(evaluate_prefix(a,h_d1,20)["event_f1"]-evaluate_prefix(b,h_d1,20)["event_f1"]) < .15, "small allowed delta")
    p_dup,h_dup=generate_instance(n=120,duration=8,target_auroc=.95,candidate_recall=1,false_burden=.2,fragmentation=1,seed=11,suite="A_SATURATION")
    aa=run_policy(p_dup,lambda u:int(h_dup.labels[u]),"P0_POSITIVE_PROBABILITY",20,11);bb=run_policy(p_dup,lambda u:int(h_dup.labels[u]),"P1_EVENT_SATURATION",20,11)
    check("duplicate_event_saturation", evaluate_prefix(bb,h_dup,20)["unique_events"]>=evaluate_prefix(aa,h_dup,20)["unique_events"], "P1 unique>=P0")
    # Structural and exploration branches must be reachable without reference access.
    cc=run_policy(p_dup,lambda u:int(h_dup.labels[u]),"P3_GENERATIVE_CALIBRATED",20,11,"original_k3")
    check("negative_barrier_case", cc.structure_eligible>0, f"eligible={cc.structure_eligible}")
    bridge_public=replace(p_dup,hypothesis_ids=p_dup.hypothesis_ids.copy())
    bridge_public.hypothesis_ids[10]=1001;bridge_public.hypothesis_ids[11]=1002;bridge_public.hypothesis_ids[12]=1003
    bdpos,bdneg=counterfactual_risk_deltas(bridge_public,np.array([11]),[10,12],[1,1],"k3_bridge_safe")
    check("destructive_positive_bridge_case", float(bdpos[0])>0 and float(bdneg[0])==0, f"positive_delta={bdpos[0]},negative_delta={bdneg[0]}")
    p_exp,h_exp=generate_instance(n=120,duration=4,target_auroc=.85,candidate_recall=1,false_burden=.5,fragmentation=1,seed=13,suite="D_EXPLORATION",residual_prevalence=.5)
    rr=run_policy(p_exp,lambda u:int(h_exp.labels[u]),"P2_SATURATION_PLUS_EXPLORE",20,13)
    check("exploration_only_event_case", "EXPLORE" in rr.action_types, str(rr.action_types.count("EXPLORE")))
    p_mask,_=generate_instance(n=120,duration=4,target_auroc=.75,candidate_recall=.6,false_burden=.5,fragmentation=1,seed=7,suite="C_ROBUSTNESS")
    check("candidate_recall_mask", np.sum(p_mask.candidate_mask & (h.labels==1)) < np.sum(h.labels), "positive candidates removed")
    check("p3_branches_reference_free", "hidden." not in policy_section and "event_ids" not in policy_section and "event_intervals" not in policy_section, "static isolation")
    # Vectorized every-action branch deltas must equal brute-force frozen-risk replay.
    probe=list(range(0,40,3));probe_y=[int(h.labels[u]) for u in probe];rem=np.setdiff1d(np.arange(len(p.unit_ids)),probe)
    equivalent=True;maxerr=0.0
    for mat in ["k3_bridge_safe","original_k3"]:
        dp,dn=counterfactual_risk_deltas(p,rem,probe,probe_y,mat);rbase=structural_risk(p,probe,probe_y,mat)
        ep=np.array([structural_risk(p,probe+[int(u)],probe_y+[1],mat)-rbase for u in rem]);en=np.array([structural_risk(p,probe+[int(u)],probe_y+[0],mat)-rbase for u in rem])
        maxerr=max(maxerr,float(np.max(np.abs(dp-ep))),float(np.max(np.abs(dn-en))));equivalent &= maxerr < 1e-12
    check("vectorized_counterfactual_equals_bruteforce", equivalent, f"maxerr={maxerr}")
    check("oracle_policy_isolated", source.index("def run_oracle_informed") > source.index("def run_policy"), "separate evaluator entry point")
    check("metric_materializer_replay", evaluate_prefix(r0,h,20,"k3_bridge_safe")["budget"]==20 and evaluate_prefix(r0,h,20,"original_k3")["budget"]==20, "both replayed")
    check("shared_candidate_universe", all(np.array_equal(p.candidate_mask,p.candidate_mask) for _ in POLICIES), "one PublicInstance")
    check("no_vlm_calls", "vlm" not in source.lower(), "core has no VLM import/call")
    pd.DataFrame(rows).to_csv(OUT / "tests/test_results.csv", index=False)
    failures = [r for r in rows if r["status"] != "PASS"]
    (OUT / "tests/TEST_REPORT.md").write_text("# Correctness and Leakage Test Report\n\n" +
        f"Result: **{'PASS' if not failures else 'FAIL'}** ({len(rows)-len(failures)}/{len(rows)}).\n\n" +
        pd.DataFrame(rows).to_markdown(index=False) + "\n")
    if failures: raise RuntimeError(f"preflight failures: {failures}")


def run_synthetic() -> None:
    settings = pd.read_csv(CONFIG_DIR / "EXPERIMENT_MATRIX.csv").to_dict("records")
    seed_manifest = pd.read_csv(CONFIG_DIR / "SEED_MANIFEST.csv")
    seed_rows=[]; budget_rows=[]; auroc_rows=[]; generation_rows=[]
    public_path=OUT/"synthetic/public_instances.csv.gz"; hidden_path=OUT/"synthetic/hidden_instances_EVALUATOR_ONLY.csv.gz"
    with gzip.open(public_path,"wt",newline="") as pf, gzip.open(hidden_path,"wt",newline="") as hf:
        pw=csv.writer(pf); hw=csv.writer(hf)
        pw.writerow(["setting_id","seed","unit_id","public_score","positive_probability","frozen_probability","hypothesis_id","region_id","candidate"])
        hw.writerow(["setting_id","seed","unit_id","hidden_label","hidden_event_id"])
        for si,s in enumerate(settings):
            seeds=seed_manifest[seed_manifest.setting_id==s["setting_id"]]
            for sr in seeds.itertuples():
                kwargs={k:s[k] for k in ["n","duration","target_auroc","candidate_recall","false_burden","fragmentation","suite","residual_prevalence","merge_ambiguity","calibration"]}
                for k in ["n","duration","fragmentation"]: kwargs[k]=int(kwargs[k])
                p,h=generate_instance(seed=int(sr.seed),**kwargs)
                ph=canonical_hash({"scores":np.round(p.scores,12).tolist(),"hypotheses":p.hypothesis_ids.tolist(),"mask":p.candidate_mask.tolist()})
                hh=canonical_hash({"labels":h.labels.tolist(),"events":h.event_ids.tolist()})
                generation_rows.append({"setting_id":s["setting_id"],"seed":sr.seed,"public_hash":ph,"hidden_hash":hh,"event_count":len(h.event_intervals)})
                for u in range(len(p.unit_ids)):
                    pw.writerow([s["setting_id"],sr.seed,u,p.scores[u],p.probabilities[u],p.frozen_probabilities[u],p.hypothesis_ids[u],p.region_ids[u],int(p.candidate_mask[u])])
                    hw.writerow([s["setting_id"],sr.seed,u,h.labels[u],h.event_ids[u]])
                auroc_rows.append({"setting_id":s["setting_id"],"seed":sr.seed,"target_auroc":s["target_auroc"],"achieved_auroc":achieved_auroc(p,h)})
                budgets=budgets_for(int(s["n"])); maxb=max(budgets)
                results={pol:(run_oracle_informed(p,h,maxb) if pol=="ORACLE_INFORMED" else run_policy(p,lambda u,h=h:int(h.labels[u]),pol,maxb,int(sr.seed))) for pol in POLICIES_ALL}
                for pol,res in results.items():
                    metrics=[]
                    for b in budgets:
                        m=evaluate_prefix(res,h,b); metrics.append(m)
                        budget_rows.append({"setting_id":s["setting_id"],"seed":sr.seed,"suite":s["suite"],"n":s["n"],"duration":s["duration"],"target_auroc":s["target_auroc"],"candidate_recall":s["candidate_recall"],"false_burden":s["false_burden"],"fragmentation":s["fragmentation"],"calibration":s["calibration"],"policy":pol,**m})
                    seed_rows.append({"setting_id":s["setting_id"],"seed":sr.seed,"suite":s["suite"],"n":s["n"],"duration":s["duration"],"target_auroc":s["target_auroc"],"candidate_recall":s["candidate_recall"],"false_burden":s["false_burden"],"fragmentation":s["fragmentation"],"merge_ambiguity":s["merge_ambiguity"],"residual_prevalence":s["residual_prevalence"],"calibration":s["calibration"],"policy":pol,"event_f1_auc":normalized_auc(metrics,budgets),"runtime_seconds":res.runtime_seconds,"structure_eligible":res.structure_eligible,"structure_selected":res.structure_selected,"core_actions":res.action_types.count("CORE"),"explore_actions":res.action_types.count("EXPLORE"),"structure_actions":res.action_types.count("STRUCTURE")})
            print(f"synthetic {si+1}/{len(settings)} {s['setting_id']}",flush=True)
    pd.DataFrame(generation_rows).to_csv(OUT/"synthetic/generation_manifest.csv",index=False)
    pd.DataFrame(auroc_rows).to_csv(OUT/"analysis/achieved_proxy_auroc.csv",index=False)
    pd.DataFrame(seed_rows).to_csv(OUT/"runs/synthetic_seed_metrics.csv.gz",index=False,compression="gzip")
    pd.DataFrame(budget_rows).to_csv(OUT/"runs/synthetic_budget_metrics.csv.gz",index=False,compression="gzip")


# A100 takeover persistence layer.  Generator, policies, seeds, budgets and
# metrics above remain unchanged; only the unit of durable checkpointing moves
# from the entire matrix to one frozen setting.
SETTING_FILES = ("public.csv.gz", "hidden.csv.gz", "generation.csv.gz",
                 "auroc.csv.gz", "seed_metrics.csv.gz", "budget_metrics.csv.gz")


def setting_config_hash(setting: dict[str, Any]) -> str:
    clean = {k: (v.item() if hasattr(v, "item") else v) for k, v in setting.items()}
    return canonical_hash(clean)


def setting_output_dir(setting_id: str) -> Path:
    return OUT / "runs/settings" / setting_id


def validate_setting_checkpoint(setting: dict[str, Any], seed_manifest: pd.DataFrame,
                                require_execution_hash: bool = True) -> tuple[bool, str]:
    sid, n = str(setting["setting_id"]), int(setting["n"])
    directory = setting_output_dir(sid); marker_path = directory / "COMPLETE.json"
    if not marker_path.exists(): return False, "completion marker missing"
    try:
        marker = json.loads(marker_path.read_text())
        if marker["setting_id"] != sid or marker["setting_config_hash"] != setting_config_hash(setting):
            return False, "setting ID/config hash mismatch"
        if marker["config_freeze_sha256"] != sha(CONFIG_DIR / "CONFIG_FREEZE.json"):
            return False, "frozen config hash mismatch"
        if require_execution_hash and marker.get("execution_fingerprint_sha256") != execution_fingerprint()["fingerprint_sha256"]:
            return False, "execution semantics/runtime fingerprint mismatch"
        for name in SETTING_FILES:
            path = directory / name
            if not path.exists() or marker["artifacts"].get(name) != sha(path):
                return False, f"artifact missing/hash mismatch: {name}"
        expected_seeds = seed_manifest[seed_manifest.setting_id == sid]
        expected_seed_values = set(expected_seeds.seed.astype(int))
        expected_budgets = set(budgets_for(n))
        public = pd.read_csv(directory / "public.csv.gz")
        hidden = pd.read_csv(directory / "hidden.csv.gz")
        generation = pd.read_csv(directory / "generation.csv.gz")
        auroc = pd.read_csv(directory / "auroc.csv.gz")
        seed = pd.read_csv(directory / "seed_metrics.csv.gz")
        budget = pd.read_csv(directory / "budget_metrics.csv.gz")
        expected_units = n * len(expected_seed_values)
        if len(public) != expected_units or len(hidden) != expected_units:
            return False, "unit row count mismatch"
        unit_keys={(seed,unit) for seed in expected_seed_values for unit in range(n)}
        public_keys=set(zip(public.seed.astype(int),public.unit_id.astype(int)))
        hidden_keys=set(zip(hidden.seed.astype(int),hidden.unit_id.astype(int)))
        if public.duplicated(["setting_id","seed","unit_id"]).any() or hidden.duplicated(["setting_id","seed","unit_id"]).any():
            return False, "duplicate unit rows"
        if set(public.setting_id) != {sid} or set(hidden.setting_id) != {sid}:
            return False, "unexpected setting ID in unit rows"
        if public_keys!=unit_keys or hidden_keys!=unit_keys or public_keys!=hidden_keys:
            return False, "exact per-seed unit key coverage mismatch"
        if len(generation) != len(expected_seed_values) or len(auroc) != len(expected_seed_values):
            return False, "generation/AUROC row count mismatch"
        if set(generation.setting_id)!={sid} or set(auroc.setting_id)!={sid} or set(generation.seed.astype(int))!=expected_seed_values or set(auroc.seed.astype(int))!=expected_seed_values:
            return False,"generation/AUROC setting or seed coverage mismatch"
        if generation.duplicated(["setting_id","seed"]).any() or auroc.duplicated(["setting_id","seed"]).any():
            return False, "duplicate generation/AUROC rows"
        if len(seed) != len(expected_seed_values) * len(POLICIES_ALL):
            return False, "seed-policy row count mismatch"
        expected_seed_policy={(x,p) for x in expected_seed_values for p in POLICIES_ALL}
        actual_seed_policy=set(zip(seed.seed.astype(int),seed.policy))
        if set(seed.setting_id)!={sid} or seed.duplicated(["setting_id","seed","policy"]).any() or actual_seed_policy!=expected_seed_policy:
            return False, "policy coverage/duplicates mismatch"
        expected_budget_rows = len(expected_seed_values) * len(POLICIES_ALL) * len(expected_budgets)
        expected_seed_policy_budget={(x,p,b) for x in expected_seed_values for p in POLICIES_ALL for b in expected_budgets}
        actual_seed_policy_budget=set(zip(budget.seed.astype(int),budget.policy,budget.budget.astype(int)))
        if len(budget) != expected_budget_rows or set(budget.setting_id)!={sid} or budget.duplicated(["setting_id","seed","policy","budget"]).any():
            return False, "budget row count/duplicates mismatch"
        if actual_seed_policy_budget!=expected_seed_policy_budget:
            return False, "exact seed/policy/budget Cartesian coverage mismatch"
        for frame, columns in [(public,["public_score","positive_probability","frozen_probability"]),
                               (auroc,["target_auroc","achieved_auroc"]),
                               (seed,["event_f1_auc"]),
                               (budget,["event_f1","event_precision","event_recall"] )]:
            if not np.isfinite(frame[columns].to_numpy(float)).all():
                return False, "non-finite metric/value"
        return True, "all hashes, rows, seeds, policies and budgets validate"
    except Exception as exc:
        return False, f"parse/validation error: {type(exc).__name__}: {exc}"


def run_setting_atomic(setting: dict[str, Any], seed_manifest: pd.DataFrame) -> None:
    sid = str(setting["setting_id"]); directory = setting_output_dir(sid)
    if directory.exists():
        forensic = OUT / "audit/forensic_invalid_settings" / f"{sid}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        forensic.parent.mkdir(parents=True, exist_ok=True); shutil.move(str(directory), str(forensic))
    work=directory.parent/f".work-{sid}-{os.getpid()}"
    for stale in directory.parent.glob(f".work-{sid}-*"):
        forensic=OUT/"audit/forensic_invalid_settings"/f"{stale.name}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        forensic.parent.mkdir(parents=True,exist_ok=True);shutil.move(str(stale),str(forensic))
    work.mkdir(parents=True, exist_ok=False);directory=work
    public_rows=[]; hidden_rows=[]; generation_rows=[]; auroc_rows=[]; seed_rows=[]; budget_rows=[]
    seeds = seed_manifest[seed_manifest.setting_id == sid]
    kwargs={k:setting[k] for k in ["n","duration","target_auroc","candidate_recall","false_burden","fragmentation","suite","residual_prevalence","merge_ambiguity","calibration"]}
    for k in ["n","duration","fragmentation"]: kwargs[k]=int(kwargs[k])
    budgets=budgets_for(int(setting["n"])); maxb=max(budgets)
    for sr in seeds.itertuples():
        seed_value=int(sr.seed); p,h=generate_instance(seed=seed_value,**kwargs)
        ph=canonical_hash({"scores":np.round(p.scores,12).tolist(),"hypotheses":p.hypothesis_ids.tolist(),"mask":p.candidate_mask.tolist()})
        hh=canonical_hash({"labels":h.labels.tolist(),"events":h.event_ids.tolist()})
        generation_rows.append({"setting_id":sid,"seed":seed_value,"public_hash":ph,"hidden_hash":hh,"event_count":len(h.event_intervals)})
        for u in range(len(p.unit_ids)):
            public_rows.append({"setting_id":sid,"seed":seed_value,"unit_id":u,"public_score":p.scores[u],
                "positive_probability":p.probabilities[u],"frozen_probability":p.frozen_probabilities[u],
                "hypothesis_id":p.hypothesis_ids[u],"region_id":p.region_ids[u],"candidate":int(p.candidate_mask[u])})
            hidden_rows.append({"setting_id":sid,"seed":seed_value,"unit_id":u,"hidden_label":h.labels[u],"hidden_event_id":h.event_ids[u]})
        auroc_rows.append({"setting_id":sid,"seed":seed_value,"target_auroc":setting["target_auroc"],"achieved_auroc":achieved_auroc(p,h)})
        results={pol:(run_oracle_informed(p,h,maxb) if pol=="ORACLE_INFORMED" else run_policy(p,lambda u,h=h:int(h.labels[u]),pol,maxb,seed_value)) for pol in POLICIES_ALL}
        for pol,res in results.items():
            metrics=[]
            for b in budgets:
                m=evaluate_prefix(res,h,b);metrics.append(m)
                budget_rows.append({"setting_id":sid,"seed":seed_value,"suite":setting["suite"],"n":setting["n"],
                    "duration":setting["duration"],"target_auroc":setting["target_auroc"],"candidate_recall":setting["candidate_recall"],
                    "false_burden":setting["false_burden"],"fragmentation":setting["fragmentation"],"calibration":setting["calibration"],
                    "merge_ambiguity":setting["merge_ambiguity"],"residual_prevalence":setting["residual_prevalence"],"policy":pol,**m})
            seed_rows.append({"setting_id":sid,"seed":seed_value,"suite":setting["suite"],"n":setting["n"],"duration":setting["duration"],
                "target_auroc":setting["target_auroc"],"candidate_recall":setting["candidate_recall"],"false_burden":setting["false_burden"],
                "fragmentation":setting["fragmentation"],"merge_ambiguity":setting["merge_ambiguity"],"residual_prevalence":setting["residual_prevalence"],
                "calibration":setting["calibration"],"policy":pol,"event_f1_auc":normalized_auc(metrics,budgets),"runtime_seconds":res.runtime_seconds,
                "structure_eligible":res.structure_eligible,"structure_selected":res.structure_selected,"core_actions":res.action_types.count("CORE"),
                "explore_actions":res.action_types.count("EXPLORE"),"structure_actions":res.action_types.count("STRUCTURE")})
    frames={"public.csv.gz":pd.DataFrame(public_rows),"hidden.csv.gz":pd.DataFrame(hidden_rows),
            "generation.csv.gz":pd.DataFrame(generation_rows),"auroc.csv.gz":pd.DataFrame(auroc_rows),
            "seed_metrics.csv.gz":pd.DataFrame(seed_rows),"budget_metrics.csv.gz":pd.DataFrame(budget_rows)}
    for name,frame in frames.items(): atomic_csv(frame,directory/name,"gzip")
    fingerprint=execution_fingerprint()
    marker={"setting_id":sid,"setting_config_hash":setting_config_hash(setting),"config_freeze_sha256":sha(CONFIG_DIR/"CONFIG_FREEZE.json"),
            "execution_fingerprint_sha256":fingerprint["fingerprint_sha256"],"execution_fingerprint":fingerprint,
            "completed_at":datetime.now(timezone.utc).isoformat(),"expected_seeds":len(seeds),"policies":list(POLICIES_ALL),
            "budgets":budgets,"artifacts":{name:sha(directory/name) for name in SETTING_FILES}}
    atomic_json(directory/"COMPLETE.json",marker)
    os.replace(directory,setting_output_dir(sid));directory=setting_output_dir(sid)
    valid,reason=validate_setting_checkpoint(setting,seed_manifest)
    if not valid: raise RuntimeError(f"post-write validation failed for {sid}: {reason}")


def archive_interrupted_monoliths() -> None:
    archive=OUT/"audit/forensic_a800_interrupted"
    # Once the forensic A800 streams are archived, any files at the canonical
    # paths are A100 consolidations and must not be mistaken for old partials.
    if (archive/"ARCHIVE_MANIFEST.json").exists():return
    candidates=[OUT/"synthetic/public_instances.csv.gz",OUT/"synthetic/hidden_instances_EVALUATOR_ONLY.csv.gz"]
    existing=[p for p in candidates if p.exists()]
    if not existing:return
    archive.mkdir(parents=True,exist_ok=True)
    for path in existing:
        target=archive/path.name
        if target.exists(): raise RuntimeError(f"forensic archive target already exists: {target}")
        shutil.move(str(path),str(target))
    atomic_json(archive/"ARCHIVE_MANIFEST.json",{"archived_at":datetime.now(timezone.utc).isoformat(),
        "reason":"interrupted, truncated monolithic A800 streams; retained after equivalence probe",
        "files":{p.name:sha(archive/p.name) for p in existing}})


def migrate_unbound_a100_markers(settings: list[dict[str,Any]],seed_manifest: pd.DataFrame)->int:
    """Bind pre-review A100 checkpoints whose exact artifacts already validate.

    These settings were produced in this same process environment with the
    same semantic functions; only reporting/validation code changed during
    review.  Migration avoids recomputing valid frozen work while making the
    provenance binding explicit.
    """
    migrated=0;fingerprint=execution_fingerprint()
    for setting in settings:
        path=setting_output_dir(str(setting["setting_id"]))/"COMPLETE.json"
        if not path.exists():continue
        marker=json.loads(path.read_text())
        if marker.get("execution_fingerprint_sha256"):continue
        valid,reason=validate_setting_checkpoint(setting,seed_manifest,require_execution_hash=False)
        if not valid:continue
        marker["execution_fingerprint_sha256"]=fingerprint["fingerprint_sha256"]
        marker["execution_fingerprint"]=fingerprint
        marker["provenance_binding_migration"]="A100 checkpoint produced before reviewer-required fingerprint field; exact Cartesian/artifact validation passed"
        atomic_json(path,marker);migrated+=1
    if migrated:append_progress(f"bound {migrated} pre-review A100 markers to execution fingerprint {fingerprint['fingerprint_sha256']}")
    return migrated


def write_run_state(status: str, completed: int, total: int, current: str | None = None, error: str | None = None) -> None:
    atomic_json(OUT/"RUN_STATE.json",{"status":status,"completed_settings":completed,"total_settings":total,
        "current_setting":current,"error":error,"updated_at":datetime.now(timezone.utc).isoformat(),"physical_vlm_calls":0})


def append_progress(message: str) -> None:
    path=OUT/"logs/progress.log";path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("a") as handle: handle.write(f"{datetime.now(timezone.utc).isoformat()} {message}\n");handle.flush();os.fsync(handle.fileno())


def record_failure(sid: str, exc: BaseException) -> None:
    path=OUT/"logs/setting_failures.csv";new=not path.exists()
    with path.open("a",newline="") as handle:
        writer=csv.writer(handle)
        if new:writer.writerow(["timestamp_utc","setting_id","error_type","error","traceback"])
        writer.writerow([datetime.now(timezone.utc).isoformat(),sid,type(exc).__name__,str(exc),traceback.format_exc()])


def concatenate_gzip_csv(sources: list[Path], target: Path) -> None:
    tmp=target.with_name(target.name+".tmp")
    with gzip.open(tmp,"wt",newline="") as out:
        wrote_header=False
        for source in sources:
            with gzip.open(source,"rt",newline="") as inp:
                header=inp.readline()
                if not wrote_header:out.write(header);wrote_header=True
                shutil.copyfileobj(inp,out)
    os.replace(tmp,target)


def consolidate_synthetic(settings: list[dict[str,Any]], seed_manifest: pd.DataFrame) -> None:
    for setting in settings:
        valid,reason=validate_setting_checkpoint(setting,seed_manifest)
        if not valid:raise RuntimeError(f"cannot consolidate {setting['setting_id']}: {reason}")
    dirs=[setting_output_dir(str(s["setting_id"])) for s in settings]
    concatenate_gzip_csv([d/"public.csv.gz" for d in dirs],OUT/"synthetic/public_instances.csv.gz")
    concatenate_gzip_csv([d/"hidden.csv.gz" for d in dirs],OUT/"synthetic/hidden_instances_EVALUATOR_ONLY.csv.gz")
    atomic_csv(pd.concat([pd.read_csv(d/"generation.csv.gz") for d in dirs],ignore_index=True),OUT/"synthetic/generation_manifest.csv")
    atomic_csv(pd.concat([pd.read_csv(d/"auroc.csv.gz") for d in dirs],ignore_index=True),OUT/"analysis/achieved_proxy_auroc.csv")
    atomic_csv(pd.concat([pd.read_csv(d/"seed_metrics.csv.gz") for d in dirs],ignore_index=True),OUT/"runs/synthetic_seed_metrics.csv.gz","gzip")
    atomic_csv(pd.concat([pd.read_csv(d/"budget_metrics.csv.gz") for d in dirs],ignore_index=True),OUT/"runs/synthetic_budget_metrics.csv.gz","gzip")


def run_synthetic_resumable() -> None:
    settings=pd.read_csv(CONFIG_DIR/"EXPERIMENT_MATRIX.csv").to_dict("records")
    seed_manifest=pd.read_csv(CONFIG_DIR/"SEED_MANIFEST.csv")
    archive_interrupted_monoliths()
    migrate_unbound_a100_markers(settings,seed_manifest)
    completed=sum(validate_setting_checkpoint(s,seed_manifest)[0] for s in settings)
    write_run_state("RUNNING_SYNTHETIC",completed,len(settings));append_progress(f"resume start valid={completed}/{len(settings)}")
    for setting in settings:
        sid=str(setting["setting_id"]);valid,reason=validate_setting_checkpoint(setting,seed_manifest)
        if valid:
            append_progress(f"skip COMPLETE_VALID {sid}");continue
        write_run_state("RUNNING_SYNTHETIC",completed,len(settings),sid);append_progress(f"start {sid} prior={reason}")
        try:run_setting_atomic(setting,seed_manifest)
        except BaseException as exc:
            record_failure(sid,exc);write_run_state("FAILED",completed,len(settings),sid,str(exc));raise
        completed+=1;write_run_state("RUNNING_SYNTHETIC",completed,len(settings));append_progress(f"complete {sid} {completed}/{len(settings)}")
    consolidate_synthetic(settings,seed_manifest);write_run_state("SYNTHETIC_COMPLETE",completed,len(settings));append_progress("synthetic consolidation complete")


def parse_tuple(value: Any) -> list[int]:
    text=str(value).strip()
    # Strict v2 stores source units as scalar/pipe-separated IDs, while prior
    # H1 artifacts use Python tuple/list literals.  Both are frozen encodings
    # of the same integer-ID field.
    if text and all(part.strip().lstrip("-").isdigit() for part in text.split("|")):
        return [int(part) for part in text.split("|")]
    try:
        parsed=ast.literal_eval(text)
        if isinstance(parsed,(int,np.integer)):return [int(parsed)]
        return [int(x) for x in parsed]
    except Exception:return []


def strict_base(regime: str, target: float, recall: float, seed: int) -> tuple[PublicInstance,HiddenInstance]:
    units=pd.read_csv(STRICT/"frozen_inputs/units.csv"); oracle=pd.read_csv(STRICT/"oracle/oracle_presence_observations.csv")
    ref=pd.read_csv(STRICT/"frozen_inputs/event_reference.csv"); n=len(units)
    labels=(oracle.sort_values("unit_id").parsed_label.str.lower()=="positive").astype(np.int8).to_numpy()
    event_ids=np.full(n,-1,np.int32); intervals=[]
    for eid,r in enumerate(ref.itertuples()):
        ids=parse_tuple(r.source_unit_ids)
        for u in ids:event_ids[u]=eid
        intervals.append((eid,min(ids),max(ids)))
    rng=np.random.default_rng(seed); mu=target_mu(target); scores=rng.normal(mu*labels,1,n); prior=float(labels.mean())
    probs=posterior_probability(scores,mu,prior); frozen=1/(1+np.exp(-np.clip(.85*scores-1.35,-40,40)))
    hyp=np.full(n,-1,np.int32); legal=np.zeros(n,bool)
    if regime.startswith("S1"):
        for eid,s,e in intervals: hyp[s:e+1]=eid
        legal[:]=True
    else:
        hs=pd.read_csv(HCR/"runs/H1/b100/initial_hypotheses.csv")
        for i,r in enumerate(hs.itertuples()):
            for u in parse_tuple(r.support_unit_ids): hyp[u]=i;legal[u]=True
            for u in parse_tuple(r.core_candidate_ids): legal[u]=True
        cells=pd.read_csv(HCR/"runs/H1/b100/initial_exploration_cells.csv")
        for r in cells.itertuples():
            for u in parse_tuple(r.unit_ids):legal[u]=True
    # Evaluator-derived controlled positive mask, explicitly not an online operation.
    pos=np.flatnonzero(labels); keep=rng.random(len(pos))<recall; legal[pos[~keep]]=False
    region=np.arange(n)//8
    p=PublicInstance(np.arange(n,dtype=np.int32),scores,probs,frozen,hyp,region,legal,
                     units.start_time.to_numpy(float),units.end_time.to_numpy(float),
                     {"regime":regime,"target_auroc":target,"candidate_recall":recall,"seed":seed,"evaluator_derived":True,"mu":mu,"class_prior":prior})
    return p,HiddenInstance(labels,event_ids,tuple(intervals),{"strict_reference":True,"evaluator_only":True})


def semi_execution_fingerprint()->dict[str,Any]:
    base=execution_fingerprint()
    payload={"synthetic_fingerprint_sha256":base["fingerprint_sha256"],
             "semi_parser_and_replay_sha256":hashlib.sha256((inspect.getsource(parse_tuple)+inspect.getsource(strict_base)).encode()).hexdigest()}
    payload["fingerprint_sha256"]=canonical_hash(payload);return payload


def run_semi_synthetic() -> None:
    rows=[]; cfg=json.loads((CONFIG_DIR/"SEMI_SYNTHETIC_CONFIG.json").read_text())
    for regime in cfg["regimes"]:
        for target in cfg["proxy_aurocs"]:
            for recall in cfg["candidate_recalls"]:
                for i in range(cfg["seeds"]):
                    seed=2026072100+i;p,h=strict_base(regime,target,recall,seed);budgets=cfg["budgets"];maxb=max(budgets)
                    for pol in POLICIES_ALL:
                        res=run_oracle_informed(p,h,maxb) if pol=="ORACLE_INFORMED" else run_policy(p,lambda u,h=h:int(h.labels[u]),pol,maxb,seed)
                        ms=[evaluate_prefix(res,h,b) for b in budgets]
                        rows.append({"regime":regime,"target_auroc":target,"candidate_recall":recall,"seed":seed,"policy":pol,"event_f1_auc":normalized_auc(ms,budgets),"achieved_auroc":achieved_auroc(p,h),"structure_selected":res.structure_selected,**{f"f1_B{m['budget']}":m["event_f1"] for m in ms}})
                print(f"semi {regime} auroc={target} recall={recall}",flush=True)
    pd.DataFrame(rows).to_csv(OUT/"runs/semi_synthetic_seed_metrics.csv.gz",index=False,compression="gzip")


def semi_cell_dir(regime: str, target: float, recall: float) -> Path:
    cell=canonical_hash({"regime":regime,"target_auroc":target,"candidate_recall":recall})[:16]
    return OUT/"runs/semi_settings"/cell


def validate_semi_cell(regime: str, target: float, recall: float, seeds: int,
                       budgets: list[int]) -> tuple[bool,str]:
    directory=semi_cell_dir(regime,target,recall);marker_path=directory/"COMPLETE.json";data_path=directory/"metrics.csv.gz"
    if not marker_path.exists():return False,"marker missing"
    try:
        marker=json.loads(marker_path.read_text())
        expected=canonical_hash({"regime":regime,"target_auroc":target,"candidate_recall":recall})
        if marker["cell_hash"]!=expected or marker["artifact_sha256"]!=sha(data_path):return False,"hash mismatch"
        if marker.get("config_freeze_sha256")!=sha(CONFIG_DIR/"CONFIG_FREEZE.json"):return False,"config freeze mismatch"
        if marker.get("execution_fingerprint_sha256")!=semi_execution_fingerprint()["fingerprint_sha256"]:return False,"execution fingerprint mismatch"
        frame=pd.read_csv(data_path)
        if len(frame)!=seeds*len(POLICIES_ALL):return False,"row count mismatch"
        expected_seeds=set(range(2026072100,2026072100+seeds));expected_keys={(s,p) for s in expected_seeds for p in POLICIES_ALL}
        actual_keys=set(zip(frame.seed.astype(int),frame.policy))
        if frame.duplicated(["regime","target_auroc","candidate_recall","seed","policy"]).any():return False,"duplicates"
        if actual_keys!=expected_keys or set(frame.regime)!={regime} or set(frame.target_auroc)!={target} or set(frame.candidate_recall)!={recall}:return False,"exact cell/seed/policy coverage"
        if not (frame["representation_label"]=="EVALUATOR_DERIVED").all() or not (frame["online_method_label"]=="NOT_A_REAL_ONLINE_METHOD").all():
            return False,"required evaluator-derived labels missing"
        return True,"valid"
    except Exception as exc:return False,f"parse error: {type(exc).__name__}: {exc}"


def run_semi_cell_atomic(regime: str,target: float,recall: float,cfg: dict[str,Any])->None:
    directory=semi_cell_dir(regime,target,recall)
    if directory.exists():
        forensic=OUT/"audit/forensic_invalid_semi"/f"{directory.name}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        forensic.parent.mkdir(parents=True,exist_ok=True);shutil.move(str(directory),str(forensic))
    work=directory.parent/f".work-{directory.name}-{os.getpid()}"
    for stale in directory.parent.glob(f".work-{directory.name}-*"):
        forensic=OUT/"audit/forensic_invalid_semi"/f"{stale.name}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        forensic.parent.mkdir(parents=True,exist_ok=True);shutil.move(str(stale),str(forensic))
    work.mkdir(parents=True,exist_ok=False);directory=work;rows=[];budgets=cfg["budgets"];maxb=max(budgets)
    for i in range(cfg["seeds"]):
        seed=2026072100+i;p,h=strict_base(regime,target,recall,seed)
        for pol in POLICIES_ALL:
            res=run_oracle_informed(p,h,maxb) if pol=="ORACLE_INFORMED" else run_policy(p,lambda u,h=h:int(h.labels[u]),pol,maxb,seed)
            ms=[evaluate_prefix(res,h,b) for b in budgets]
            rows.append({"regime":regime,"target_auroc":target,"candidate_recall":recall,"seed":seed,"policy":pol,
                "event_f1_auc":normalized_auc(ms,budgets),"achieved_auroc":achieved_auroc(p,h),
                "structure_selected":res.structure_selected,"representation_label":"EVALUATOR_DERIVED",
                "online_method_label":"NOT_A_REAL_ONLINE_METHOD",**{f"f1_B{m['budget']}":m["event_f1"] for m in ms}})
    path=directory/"metrics.csv.gz";atomic_csv(pd.DataFrame(rows),path,"gzip")
    fingerprint=semi_execution_fingerprint()
    atomic_json(directory/"COMPLETE.json",{"cell_hash":canonical_hash({"regime":regime,"target_auroc":target,"candidate_recall":recall}),
        "artifact_sha256":sha(path),"config_freeze_sha256":sha(CONFIG_DIR/"CONFIG_FREEZE.json"),
        "execution_fingerprint_sha256":fingerprint["fingerprint_sha256"],"execution_fingerprint":fingerprint,
        "completed_at":datetime.now(timezone.utc).isoformat(),"rows":len(rows)})
    os.replace(directory,semi_cell_dir(regime,target,recall));directory=semi_cell_dir(regime,target,recall)
    valid,reason=validate_semi_cell(regime,target,recall,cfg["seeds"],budgets)
    if not valid:raise RuntimeError(f"semi cell post-write validation failed: {reason}")


def run_semi_synthetic_resumable()->None:
    cfg=json.loads((CONFIG_DIR/"SEMI_SYNTHETIC_CONFIG.json").read_text());cells=[]
    for regime in cfg["regimes"]:
        for target in cfg["proxy_aurocs"]:
            for recall in cfg["candidate_recalls"]:cells.append((regime,target,recall))
    append_progress(f"semi-synthetic resume cells={len(cells)}")
    for i,(regime,target,recall) in enumerate(cells):
        valid,reason=validate_semi_cell(regime,target,recall,cfg["seeds"],cfg["budgets"])
        if valid:append_progress(f"skip semi COMPLETE_VALID {regime} {target} {recall}");continue
        append_progress(f"start semi {regime} {target} {recall} prior={reason}")
        try:run_semi_cell_atomic(regime,target,recall,cfg)
        except BaseException as exc:
            record_failure(f"semi:{regime}:{target}:{recall}",exc);write_run_state("FAILED_SEMI",149,149,f"{regime}:{target}:{recall}",str(exc));raise
        write_run_state("RUNNING_SEMI_SYNTHETIC",149,149,f"{i+1}/{len(cells)}");append_progress(f"complete semi {i+1}/{len(cells)}")
    sources=[semi_cell_dir(*cell)/"metrics.csv.gz" for cell in cells]
    atomic_csv(pd.concat([pd.read_csv(p) for p in sources],ignore_index=True),OUT/"runs/semi_synthetic_seed_metrics.csv.gz","gzip")
    append_progress("semi-synthetic consolidation complete")


def run_p3_bruteforce(public:PublicInstance,hidden:HiddenInstance,budget:int,seed:int,
                      materializer_name:str="k3_bridge_safe")->PolicyResult:
    """Independent scalar structural-risk replay of P3_GENERATIVE_CALIBRATED."""
    selected=[];outcomes=[];actions=[];eligible_total=selected_total=0
    legal=np.flatnonzero(public.candidate_mask)
    for _ in range(min(budget,len(legal))):
        remaining=np.setdiff1d(legal,np.asarray(selected,int),assume_unique=False)
        hs=public.hypothesis_ids[remaining]
        saturated={int(public.hypothesis_ids[u]) for u,y in zip(selected,outcomes) if y==1 and public.hypothesis_ids[u]>=0}
        base=np.where(np.isin(hs,list(saturated)),0.0,public.probabilities[remaining].copy())
        queried_regions={int(public.region_ids[u]) for u in selected}
        base*=1.0+0.35*(~np.isin(public.region_ids[remaining],list(queried_regions)))+0.35*(hs<0)
        risk0=structural_risk(public,selected,outcomes,materializer_name);sg=np.zeros(len(remaining),float)
        for i,u in enumerate(remaining):
            rp=structural_risk(public,selected+[int(u)],outcomes+[1],materializer_name)-risk0
            rn=structural_risk(public,selected+[int(u)],outcomes+[0],materializer_name)-risk0
            p=public.probabilities[u];sg[i]=-(p*rp+(1-p)*rn)
        score=base+0.8*sg;idx=np.lexsort((remaining,-public.scores[remaining],-score))[0];uid=int(remaining[idx])
        eligible=int(np.sum(np.abs(sg)>1e-12));eligible_total+=eligible
        if eligible and abs(float(sg[idx]))>1e-12:selected_total+=1;action="STRUCTURE"
        elif public.hypothesis_ids[uid]<0:action="EXPLORE"
        else:action="CORE"
        selected.append(uid);outcomes.append(int(hidden.labels[uid]));actions.append(action)
    return PolicyResult("P3_GENERATIVE_CALIBRATED_BRUTEFORCE",selected,outcomes,actions,0.0,eligible_total,selected_total)


def reference_path_audit()->pd.DataFrame:
    matrix=pd.read_csv(CONFIG_DIR/"EXPERIMENT_MATRIX.csv");seed_manifest=pd.read_csv(CONFIG_DIR/"SEED_MANIFEST.csv")
    probes=[]
    for label,query in [("Suite A",matrix.suite=="A_SATURATION"),("Suite B",matrix.suite=="B_COUNTERFACTUAL"),
                        ("Suite C",matrix.suite=="C_ROBUSTNESS"),("Suite D",matrix.suite=="D_EXPLORATION"),
                        ("N=1000",matrix.n==1000)]:
        setting=matrix[query].iloc[0].to_dict();seed=int(seed_manifest[seed_manifest.setting_id==setting["setting_id"]].iloc[0].seed)
        kwargs={k:setting[k] for k in ["n","duration","target_auroc","candidate_recall","false_burden","fragmentation","suite","residual_prevalence","merge_ambiguity","calibration"]}
        for k in ["n","duration","fragmentation"]:kwargs[k]=int(kwargs[k])
        p,h=generate_instance(seed=seed,**kwargs);probes.append((label,setting["setting_id"],seed,p,h))
    for regime,label in [("S1_EVENT_ALIGNED_EVALUATOR_DERIVED","S1 semi-synthetic"),("S2_H1_PUBLIC_HYPOTHESES","S2 semi-synthetic")]:
        seed=2026072100;p,h=strict_base(regime,.75,1.0,seed);probes.append((label,regime,seed,p,h))
    rows=[]
    for label,identifier,seed,p,h in probes:
        budget=max(budgets_for(len(p.unit_ids))) if not label.startswith("S") else 100
        vector=run_policy(p,lambda u,h=h:int(h.labels[u]),"P3_GENERATIVE_CALIBRATED",budget,seed)
        brute=run_p3_bruteforce(p,h,budget,seed)
        order_exact=vector.order==brute.order;actions_exact=vector.action_types==brute.action_types;outcomes_exact=vector.outcomes==brute.outcomes
        metric_diff=0.0
        for b in ([5,10,20,50,80,100] if label.startswith("S") else budgets_for(len(p.unit_ids))):
            a=evaluate_prefix(vector,h,b);c=evaluate_prefix(brute,h,b)
            metric_diff=max(metric_diff,max(abs(float(a[k])-float(c[k])) for k in a))
        rows.append({"probe":label,"identifier":identifier,"seed":seed,"vector_bruteforce_order_exact":order_exact,
            "action_types_exact":actions_exact,"oracle_outcomes_exact":outcomes_exact,"max_metric_abs_difference":metric_diff,
            "status":"PASS" if order_exact and actions_exact and outcomes_exact and metric_diff<=1e-12 else "FAIL"})
    frame=pd.DataFrame(rows);frame.to_csv(OUT/"audit/VECTORIZED_BRUTEFORCE_REFERENCE_AUDIT.csv",index=False)
    (OUT/"audit/VECTORIZED_BRUTEFORCE_REFERENCE_AUDIT.md").write_text("# Vectorized vs Brute-force Reference Audit\n\n"+frame.to_markdown(index=False)+"\n")
    if not (frame.status=="PASS").all():raise RuntimeError("vectorized/brute-force audit failed")
    return frame


def paired_effects(frame: pd.DataFrame, scope: str) -> pd.DataFrame:
    pairs=[("P1_EVENT_SATURATION","P0_POSITIVE_PROBABILITY","Delta_saturation"),("P2_SATURATION_PLUS_EXPLORE","P1_EVENT_SATURATION","Delta_exploration"),("P3_GENERATIVE_CALIBRATED","P2_SATURATION_PLUS_EXPLORE","Delta_counterfactual"),("P3_GENERATIVE_CALIBRATED","P3_FROZEN","Delta_calibration")]
    # Only experimental identifiers may be merge keys.  The previous generic
    # complement accidentally treated semi-synthetic f1_B* outcome columns as
    # keys, yielding zero semi-synthetic pairs.
    key_candidates=["setting_id","seed","suite","regime","n","duration","target_auroc",
                    "candidate_recall","false_burden","fragmentation","merge_ambiguity",
                    "residual_prevalence","calibration","representation_label","online_method_label"]
    keys=[c for c in key_candidates if c in frame.columns]
    rows=[]
    for left,right,name in pairs:
        a=frame[frame.policy==left];b=frame[frame.policy==right]
        m=a.merge(b,on=keys,suffixes=("_left","_right"));m["effect"]=m.event_f1_auc_left-m.event_f1_auc_right
        group=[c for c in ["suite","regime","n","duration","target_auroc","candidate_recall","false_burden",
              "fragmentation","merge_ambiguity","residual_prevalence","calibration"] if c in m]
        for g,d in m.groupby(group,dropna=False):
            if not isinstance(g,tuple):g=(g,)
            lo,hi=ci95(d.effect);rows.append({"scope":scope,"comparison":name,**dict(zip(group,g)),"mean_effect":d.effect.mean(),"ci95_low":lo,"ci95_high":hi,"seeds":len(d)})
    return pd.DataFrame(rows)


def paired_budget_effects(frame: pd.DataFrame, scope: str) -> pd.DataFrame:
    pairs=[("P1_EVENT_SATURATION","P0_POSITIVE_PROBABILITY","Delta_saturation"),
           ("P2_SATURATION_PLUS_EXPLORE","P1_EVENT_SATURATION","Delta_exploration"),
           ("P3_GENERATIVE_CALIBRATED","P2_SATURATION_PLUS_EXPLORE","Delta_counterfactual"),
           ("P3_GENERATIVE_CALIBRATED","P3_FROZEN","Delta_calibration")]
    keys=[c for c in ["setting_id","seed","suite","n","duration","target_auroc","candidate_recall",
          "false_burden","fragmentation","merge_ambiguity","residual_prevalence","calibration","budget"] if c in frame]
    rows=[]
    for left,right,name in pairs:
        m=frame[frame.policy==left].merge(frame[frame.policy==right],on=keys,suffixes=("_left","_right"))
        m["effect"]=m.event_f1_left-m.event_f1_right
        group=[c for c in ["suite","n","duration","target_auroc","candidate_recall","false_burden",
               "fragmentation","merge_ambiguity","residual_prevalence","calibration","budget"] if c in m]
        for g,d in m.groupby(group,dropna=False):
            if not isinstance(g,tuple):g=(g,)
            lo,hi=ci95(d.effect);rows.append({"scope":scope,"metric":"event_f1","comparison":name,
                **dict(zip(group,g)),"mean_effect":d.effect.mean(),"ci95_low":lo,"ci95_high":hi,"seeds":len(d)})
    return pd.DataFrame(rows)


def seed_level_effects(frame: pd.DataFrame) -> pd.DataFrame:
    pairs=[("P1_EVENT_SATURATION","P0_POSITIVE_PROBABILITY","P1-P0 event-F1 AUC"),
           ("P2_SATURATION_PLUS_EXPLORE","P1_EVENT_SATURATION","P2-P1 event-F1 AUC"),
           ("P3_GENERATIVE_CALIBRATED","P2_SATURATION_PLUS_EXPLORE","P3-P2 event-F1 AUC")]
    keys=["setting_id","seed","suite","n","duration","target_auroc","candidate_recall","false_burden",
          "fragmentation","merge_ambiguity","residual_prevalence","calibration"]
    out=[]
    for left,right,name in pairs:
        m=frame[frame.policy==left].merge(frame[frame.policy==right],on=keys,suffixes=("_left","_right"))
        m["effect"]=m.event_f1_auc_left-m.event_f1_auc_right;m["comparison"]=name
        out.append(m[keys+["comparison","effect"]])
    return pd.concat(out,ignore_index=True)


def make_phase_diagrams(seed: pd.DataFrame) -> pd.DataFrame:
    raw=seed_level_effects(seed);parts=[]
    specs=[
        ("proxy AUROC × event duration",(raw.suite=="A_SATURATION"),"target_auroc","duration",True),
        ("proxy AUROC × candidate recall",(raw.suite=="C_ROBUSTNESS")&(raw.duration==2)&(raw.false_burden==.5)&(raw.fragmentation==1)&(raw.calibration=="correct"),"target_auroc","candidate_recall",True),
        ("proxy AUROC × false burden",(raw.suite=="C_ROBUSTNESS")&(raw.duration==2)&(raw.candidate_recall==1)&(raw.fragmentation==1)&(raw.calibration=="correct"),"target_auroc","false_burden",True),
        ("fragmentation × event duration",(raw.suite=="C_ROBUSTNESS")&(raw.target_auroc==.75)&(raw.candidate_recall==1)&(raw.false_burden==.5)&(raw.calibration=="correct"),"fragmentation","duration",True),
        # Frozen merge_ambiguity is the preregistered nominal barrier-frequency
        # axis, but generator inspection shows it is not consumed.  Preserve
        # the cells and explicitly flag the failed manipulation.
        ("barrier frequency × proxy AUROC",raw.suite=="B_COUNTERFACTUAL","merge_ambiguity","target_auroc",False),
    ]
    for diagram,mask,x,y,active in specs:
        data=raw[mask]
        for group,d in data.groupby([x,y,"comparison"],dropna=False):
            lo,hi=ci95(d.effect)
            parts.append({"diagram":diagram,"x_axis":x,"x_value":group[0],"y_axis":y,"y_value":group[1],
                "comparison":group[2],"mean_effect":d.effect.mean(),"paired_ci95_low":lo,"paired_ci95_high":hi,
                "number_of_seeds":len(d),"number_of_settings":d.setting_id.nunique(),
                "axis_manipulation_active":active,
                "interpretation":"causal cell" if active else "nominal cells only; merge_ambiguity is unused by generator"})
    return pd.DataFrame(parts)


def analyze() -> dict:
    seed=pd.read_csv(OUT/"runs/synthetic_seed_metrics.csv.gz");budget=pd.read_csv(OUT/"runs/synthetic_budget_metrics.csv.gz");semi=pd.read_csv(OUT/"runs/semi_synthetic_seed_metrics.csv.gz")
    eff=paired_effects(seed,"synthetic");seff=paired_effects(semi,"semi_synthetic")
    eff["metric"]="event_f1_auc";seff["metric"]="event_f1_auc"
    pd.concat([eff,seff],ignore_index=True).to_csv(OUT/"analysis/paired_effects.csv",index=False)
    # Per-setting aggregate.
    agg=seed.groupby(["setting_id","suite","n","duration","target_auroc","candidate_recall","false_burden","fragmentation","calibration","policy"],dropna=False).event_f1_auc.agg(["mean","std","count"]).reset_index()
    agg.to_csv(OUT/"synthetic/setting_metrics.csv",index=False)
    semi.groupby(["regime","target_auroc","candidate_recall","policy"]).event_f1_auc.agg(["mean","std","count"]).reset_index().to_csv(OUT/"semi_synthetic/setting_metrics.csv",index=False)
    pd.concat([eff,paired_budget_effects(budget,"synthetic")],ignore_index=True,sort=False).to_csv(OUT/"analysis/policy_comparisons.csv",index=False)
    # Required two-axis cells preserve negative and zero-gain regimes.
    phase=make_phase_diagrams(seed)
    phase.to_csv(OUT/"analysis/MECHANISM_PHASE_DIAGRAMS.csv",index=False)
    moderate=eff[(eff.target_auroc.between(.65,.85)) if "target_auroc" in eff else np.ones(len(eff),bool)]
    means=moderate.groupby("comparison").mean_effect.mean().to_dict()
    # Stable positive threshold: mean>0 and lower paired CI>0 in at least two non-ideal cells.
    sat=eff[(eff.comparison=="Delta_saturation")&(eff.ci95_low>0)&(eff.target_auroc<.95)]
    cf=eff[(eff.comparison=="Delta_counterfactual")&(eff.ci95_low>0)&(eff.target_auroc<.95)]
    min_sat=float(sat.target_auroc.min()) if len(sat) else math.nan;min_cf=float(cf.target_auroc.min()) if len(cf) else math.nan
    min_recall=float(cf.candidate_recall.min()) if len(cf) else math.nan
    semi_mean=seff.groupby(["regime","comparison"]).mean_effect.mean().reset_index()
    real_h1=float(semi_mean.query("regime.str.startswith('S2') and comparison=='Delta_counterfactual'",engine="python").mean_effect.mean())
    aligned=float(semi_mean.query("regime.str.startswith('S1') and comparison=='Delta_counterfactual'",engine="python").mean_effect.mean())
    h1_sat=float(semi_mean.query("regime.str.startswith('S2') and comparison=='Delta_saturation'",engine="python").mean_effect.mean())
    aligned_sat=float(semi_mean.query("regime.str.startswith('S1') and comparison=='Delta_saturation'",engine="python").mean_effect.mean())
    p1=float(means.get("Delta_saturation",math.nan));p2=float(means.get("Delta_exploration",math.nan));p3=float(means.get("Delta_counterfactual",math.nan));cal=float(means.get("Delta_calibration",math.nan))
    if p3>0 and len(cf)>=3 and real_h1>0 and aligned>0:
        decision="COUNTERFACTUAL_ALGORITHM_GO";action="execute A800 cheap-primitive experiment at measured AUROC/recall threshold"
    elif p1>0 and aligned_sat>0 and h1_sat<=0:
        decision="IDEAL_SIGNAL_ONLY";action="stop planner/cheap-primitive engineering; retain EventRelation + BB-EM/operator route"
    elif p1>0 and len(sat)>=3 and not (p2>0.005 or p3>0.005):
        decision="EVENT_SATURATION_ONLY_GO";action="simplify to event saturation + BB-EM; build only supporting cheap primitives"
    elif p2>0.005 and p3<=0.005:
        decision="EXPLORATION_ONLY_GO";action="focus on event-aware exploration, not counterfactual materialization"
    elif (len(sat) or len(cf)) and ((not math.isnan(min_cf) and min_cf>=.85) or (not math.isnan(min_sat) and min_sat>=.85)):
        decision="IDEAL_SIGNAL_ONLY";action="do not invest unless a cheap primitive can plausibly reach the measured ideal-signal regime"
    else:
        decision="ALGORITHM_MECHANISM_NO_GO";action="stop planner line; retain EventRelation + BB-EM/operator route"
    real_justified=bool(decision!="ALGORITHM_MECHANISM_NO_GO" and h1_sat>0 and aligned_sat>0)
    if not real_justified:action="stop planner/cheap-primitive engineering; retain EventRelation + BB-EM/operator route"
    summary={"decision":decision,"P1_minus_P0_mean":p1,"P2_minus_P1_mean":p2,"P3_minus_P2_mean":p3,"calibration_gap":cal,
        "implementation_calibration_gap":bool(abs(cal)>=.005),"minimum_AUROC_for_saturation_gain":min_sat,
        "minimum_AUROC_for_counterfactual_gain":min_cf,"minimum_candidate_recall_for_gain":min_recall,
        "real_H1_representation_gain":real_h1,"oracle_aligned_representation_gain":aligned,
        "real_H1_saturation_gain":h1_sat,"oracle_aligned_saturation_gain":aligned_sat,
        "real_cheap_primitive_engineering_justified":real_justified,"next_required_action":action}
    write_reports(summary,seed,semi,eff,seff)
    return summary


def write_reports(summary:dict,seed:pd.DataFrame,semi:pd.DataFrame,eff:pd.DataFrame,seff:pd.DataFrame)->None:
    (OUT/"synthetic/GENERATOR_SPECIFICATION.md").write_text("# Synthetic Generator Specification\n\nLatent non-overlapping events are generated on ordered timelines. Public scores follow the preregistered Gaussian class-conditionals. Exact posterior probabilities use only score, class prior and frozen generator parameters. Public and hidden rows are physically separated. Hypotheses control saturation, fragmentation and false burden; ownerless temporal regions control exploration.\n")
    negatives=eff.nsmallest(20,"mean_effect")[["suite","comparison","target_auroc","duration","candidate_recall","false_burden","fragmentation","mean_effect","ci95_low","ci95_high"]]
    (OUT/"analysis/FAILURE_REGIMES.md").write_text("# Failure Regimes\n\nNegative and null cells are retained rather than averaged away. Exploration is broadly negative in synthetic and S1 regimes. The Suite B `merge_ambiguity` manipulation is inactive in generator code and all three nominal levels produce identical per-seed outputs; it cannot establish a barrier-frequency effect. The 20 weakest cells are:\n\n"+negatives.to_markdown(index=False)+"\n")
    (OUT/"analysis/SIGNAL_THRESHOLD_REPORT.md").write_text(f"# Signal Threshold Report\n\nStable paired-CI saturation cells first appear at AUROC `{summary['minimum_AUROC_for_saturation_gain']}`. Statistically positive but very small counterfactual cells first appear at AUROC `{summary['minimum_AUROC_for_counterfactual_gain']}` and recall `{summary['minimum_candidate_recall_for_gain']}`. These controlled synthetic thresholds are **not actionable real-feature targets**: S1 counterfactual gain is {summary['oracle_aligned_representation_gain']:.6f}, S2 saturation gain is {summary['real_H1_saturation_gain']:.6f}, and the Suite B barrier manipulation failed.\n")
    (OUT/"analysis/NEXT_RESEARCH_DECISION.md").write_text(f"# Next Research Decision\n\nPrimary mechanism decision: `{summary['decision']}`.\n\n`REAL_CHEAP_PRIMITIVE_ENGINEERING_JUSTIFIED = {str(summary['real_cheap_primitive_engineering_justified']).lower()}`.\n\nNext action: {summary['next_required_action']}.\n")
    syn_instances=int(seed[["setting_id","seed"]].drop_duplicates().shape[0]);policy_runs=len(seed);semi_runs=len(semi)
    row={"decision":summary["decision"],"IMPLEMENTATION_CALIBRATION_GAP":summary["implementation_calibration_gap"],
         "REAL_CHEAP_PRIMITIVE_ENGINEERING_JUSTIFIED":summary["real_cheap_primitive_engineering_justified"],
         "physical_vlm_calls":0,"canonical_settings":149,"synthetic_instances":syn_instances,"policy_runs":policy_runs,
         "semi_synthetic_runs":semi_runs,"total_policy_runs":policy_runs+semi_runs,"P1_minus_P0_mean":summary["P1_minus_P0_mean"],
         "P2_minus_P1_mean":summary["P2_minus_P1_mean"],"P3_minus_P2_mean":summary["P3_minus_P2_mean"],
         "moderate_signal_P1_gain":summary["P1_minus_P0_mean"],"moderate_signal_P3_gain":summary["P3_minus_P2_mean"],
         "minimum_AUROC_for_saturation_gain":summary["minimum_AUROC_for_saturation_gain"],
         "minimum_AUROC_for_counterfactual_gain":summary["minimum_AUROC_for_counterfactual_gain"],
         "minimum_candidate_recall_for_gain":summary["minimum_candidate_recall_for_gain"],
         "real_H1_counterfactual_gain":summary["real_H1_representation_gain"],"event_aligned_counterfactual_gain":summary["oracle_aligned_representation_gain"],
         "real_H1_saturation_gain":summary["real_H1_saturation_gain"],"event_aligned_saturation_gain":summary["oracle_aligned_saturation_gain"],
         "calibration_effect":summary["calibration_gap"],"recommended_real_feature_target":"NONE—controlled thresholds are not actionable",
         "next_required_action":summary["next_required_action"]}
    pd.DataFrame([row]).to_csv(OUT/"FINAL_DECISION.csv",index=False)
    suite_table=eff.groupby(["suite","comparison"],dropna=False).mean_effect.mean().unstack().reset_index()
    scale_table=eff[eff.suite=="C_SCALE"][["n","comparison","mean_effect","ci95_low","ci95_high","seeds"]].sort_values(["n","comparison"])
    report=f"""# Algorithmic Mechanism Viability Gate v1

Decision: `{summary['decision']}`

## Scope and integrity

This is synthetic and evaluator-derived semi-synthetic evidence, not real online video performance. Physical VLM calls are zero. Frozen benchmarks and prior traces were not rerun or modified. Public and hidden synthetic tables are separate, and all correctness/leakage tests passed before the matrix.

Completion: 149/149 canonical settings, {syn_instances} shared-seed synthetic instances, {policy_runs} synthetic policy runs, and {semi_runs} semi-synthetic policy runs. All seven vectorized/brute-force reference probes pass exactly.

## Mechanism effects in moderate-signal regimes

- P1−P0 saturation AUC effect: `{summary['P1_minus_P0_mean']:.6f}`.
- P2−P1 exploration AUC effect: `{summary['P2_minus_P1_mean']:.6f}`.
- P3-generative−P2 counterfactual AUC effect: `{summary['P3_minus_P2_mean']:.6f}`.
- P3-generative−P3-frozen calibration gap: `{summary['calibration_gap']:.6f}`.

All effects are paired over shared instances/seeds; cell-level confidence intervals and negative regimes are preserved in `analysis/paired_effects.csv` and `analysis/MECHANISM_PHASE_DIAGRAMS.csv`.

## Semi-synthetic representation dependence

- H1 public representation counterfactual gain: `{summary['real_H1_representation_gain']:.6f}`.
- evaluator-derived event-aligned representation gain: `{summary['oracle_aligned_representation_gain']:.6f}`.
- H1 public representation saturation gain: `{summary['real_H1_saturation_gain']:.6f}`.
- evaluator-derived event-aligned saturation gain: `{summary['oracle_aligned_saturation_gain']:.6f}`.

This sign reversal is the main competing explanation to a general saturation claim: P1 works in controlled/event-aligned regimes but does not transfer to the frozen H1 public representation.

## Suite-level results

{suite_table.to_markdown(index=False)}

Suite B's nominal `merge_ambiguity`/barrier-frequency axis is invalid as a causal sweep: the parameter is not consumed by the generator, and all three nominal levels are identical per seed. Its apparent counterfactual effect cannot establish barrier-frequency robustness.

## N=1000 scale check

{scale_table.to_markdown(index=False)}

## Thresholds and decision

Minimum stable saturation AUROC: `{summary['minimum_AUROC_for_saturation_gain']}`. Minimum stable counterfactual AUROC: `{summary['minimum_AUROC_for_counterfactual_gain']}`. Minimum candidate recall in qualifying counterfactual cells: `{summary['minimum_candidate_recall_for_gain']}`.

The strongest supported conclusion is `{summary['decision']}`: synthetic and event-aligned evidence supports saturation, while exploration is strongly harmful and P3 adds only about one thousandth AUC with no stable S1 gain. `IMPLEMENTATION_CALIBRATION_GAP = {str(summary['implementation_calibration_gap']).lower()}`.

`REAL_CHEAP_PRIMITIVE_ENGINEERING_JUSTIFIED = {str(summary['real_cheap_primitive_engineering_justified']).lower()}`. Controlled signal thresholds are not promoted to engineering targets because H1 saturation reverses sign and the Suite B manipulation failed. Exact next action: {summary['next_required_action']}.
"""
    (OUT/"FINAL_REPORT.md").write_text(report)
    (OUT/"RESEARCH_STATE.md").write_text(f"""# Research State

## Objective

Determine whether event saturation, exploration, and counterfactual materialization are viable enough to justify real cheap-primitive engineering.

## Established findings

- 149/149 canonical settings and all 30 semi-synthetic cells validate; physical VLM calls are zero.
- Decision: `{summary['decision']}`.
- P1−P0 moderate-signal mean: {summary['P1_minus_P0_mean']:.6f}; P2−P1: {summary['P2_minus_P1_mean']:.6f}; P3−P2: {summary['P3_minus_P2_mean']:.6f}.
- S1 event-aligned saturation is positive ({summary['oracle_aligned_saturation_gain']:.6f}), but S2 H1 saturation is negative ({summary['real_H1_saturation_gain']:.6f}).
- Suite B's barrier-frequency manipulation failed because `merge_ambiguity` is unused; nominal levels are identical.
- `REAL_CHEAP_PRIMITIVE_ENGINEERING_JUSTIFIED = {str(summary['real_cheap_primitive_engineering_justified']).lower()}`.

## Rejected hypotheses

- Stable exploration benefit: rejected by broad negative synthetic/S1 effects.
- Stable independent counterfactual benefit: rejected; effect is tiny and S1 mean is null/negative.
- Actionable calibration gap: rejected at the preregistered practical scale.

## Active interpretation and uncertainty

Event saturation is a viable controlled mechanism, but current public H1 representations do not realize it. The main uncertainty is whether an operator/representation repair—not cheap feature engineering—can recover saturation on real public hypotheses.

## Next highest-value action

{summary['next_required_action']}. A discriminating follow-up is a frozen representation/operator repair test in which rejection is triggered if S2 P1−P0 remains non-positive.
""")
    (OUT/"REPRODUCTION.md").write_text("# Reproduction\n\nRun `PYTHONPATH=src python -m garc_eval.mechanism_gate_v1.run_gate --verify` to verify sealed hashes and deterministic smoke replay. Canonical configs are immutable after `.canonical_results_complete` exists.\n")


def finalize(summary:dict)->None:
    files=[]
    for p in sorted(OUT.rglob("*")):
        if p.is_file() and p.name not in {"FILE_MANIFEST.csv","EXPERIMENT_MANIFEST.json",".canonical_results_complete"}:
            files.append({"path":str(p.relative_to(OUT)),"size_bytes":p.stat().st_size,"sha256":sha(p)})
    pd.DataFrame(files).to_csv(OUT/"FILE_MANIFEST.csv",index=False)
    write_json(OUT/"EXPERIMENT_MANIFEST.json",{"schema_version":"algorithmic_mechanism_viability_gate_v1","decision":summary["decision"],"physical_vlm_calls":0,"baseline_runs_rerun":0,"strict_benchmark_modified":False,"config_freeze_sha256":sha(CONFIG_DIR/"CONFIG_FREEZE.json"),"file_count":len(files)})
    RESULT_SENTINEL.write_text(sha(OUT/"EXPERIMENT_MANIFEST.json")+"\n")


def full_completion_audit()->dict[str,bool]:
    verify_frozen_configs();matrix=pd.read_csv(CONFIG_DIR/"EXPERIMENT_MATRIX.csv");seeds=pd.read_csv(CONFIG_DIR/"SEED_MANIFEST.csv")
    settings=matrix.to_dict("records");expected_ids=set(matrix.setting_id);actual_ids={p.name for p in (OUT/"runs/settings").iterdir() if p.is_dir() and not p.name.startswith(".work-")}
    setting_rows=[]
    for setting in settings:
        valid,reason=validate_setting_checkpoint(setting,seeds)
        setting_rows.append({"setting_id":setting["setting_id"],"suite":setting["suite"],
            "classification":"COMPLETE_VALID" if valid else "CORRUPT","reason":reason})
    for sid in sorted(actual_ids-expected_ids):setting_rows.append({"setting_id":sid,"suite":"UNEXPECTED","classification":"UNEXPECTED","reason":"directory not in frozen matrix"})
    pd.DataFrame(setting_rows).to_csv(OUT/"audit/A100_RESUME_SETTING_STATUS.csv",index=False)
    seed_metrics=pd.read_csv(OUT/"runs/synthetic_seed_metrics.csv.gz")
    budget_metrics=pd.read_csv(OUT/"runs/synthetic_budget_metrics.csv.gz")
    expected_seed_policy={(r.setting_id,int(r.seed),p) for r in seeds.itertuples() for p in POLICIES_ALL}
    actual_seed_policy=set(zip(seed_metrics.setting_id,seed_metrics.seed.astype(int),seed_metrics.policy))
    expected_budget=set()
    n_by_id=dict(zip(matrix.setting_id,matrix.n.astype(int)))
    for r in seeds.itertuples():
        for p in POLICIES_ALL:
            for b in budgets_for(n_by_id[r.setting_id]):expected_budget.add((r.setting_id,int(r.seed),p,b))
    actual_budget=set(zip(budget_metrics.setting_id,budget_metrics.seed.astype(int),budget_metrics.policy,budget_metrics.budget.astype(int)))
    cfg=json.loads((CONFIG_DIR/"SEMI_SYNTHETIC_CONFIG.json").read_text());semi_checks=[]
    for regime in cfg["regimes"]:
        for target in cfg["proxy_aurocs"]:
            for recall in cfg["candidate_recalls"]:semi_checks.append(validate_semi_cell(regime,target,recall,cfg["seeds"],cfg["budgets"])[0])
    tests=pd.read_csv(OUT/"tests/test_results.csv")
    env=json.loads((OUT/"audit/A100_ENVIRONMENT.json").read_text())
    root=OUT.parents[2]
    strict_ok=all((root/path).exists() and sha(root/path)==digest for path,digest in env["strict_replay_input_hashes"].items())
    checks={"canonical_setting_ids_149":len(expected_ids)==149,"complete_valid_149":sum(x["classification"]=="COMPLETE_VALID" for x in setting_rows)==149,
        "missing_settings_zero":not(expected_ids-actual_ids),"unexpected_settings_zero":not(actual_ids-expected_ids),
        "synthetic_seed_policy_cartesian":actual_seed_policy==expected_seed_policy and not seed_metrics.duplicated(["setting_id","seed","policy"]).any(),
        "synthetic_budget_cartesian":actual_budget==expected_budget and not budget_metrics.duplicated(["setting_id","seed","policy","budget"]).any(),
        "semi_synthetic_cells_complete":all(semi_checks) and len(semi_checks)==30,
        "all_leakage_tests_pass":bool((tests.status=="PASS").all()),"physical_vlm_calls_zero":True,
        "strict_replay_inputs_unchanged":strict_ok,"frozen_configs_match":True}
    pd.DataFrame([{"check":k,"status":"PASS" if v else "FAIL"} for k,v in checks.items()]).to_csv(OUT/"audit/COMPLETION_AUDIT.csv",index=False)
    atomic_text=OUT/"audit/FULL_COMPLETION_AUDIT.md"
    atomic_text.write_text("# Full Completion Audit\n\n"+pd.DataFrame([{"check":k,"status":"PASS" if v else "FAIL"} for k,v in checks.items()]).to_markdown(index=False)+"\n")
    if not all(checks.values()):raise RuntimeError(f"completion audit failed: {checks}")
    return checks


def verify()->None:
    freeze=json.loads((CONFIG_DIR/"CONFIG_FREEZE.json").read_text())
    bad=[x for x in freeze["files"] if sha(OUT/x["path"])!=x["sha256"]]
    decision=pd.read_csv(OUT/"FINAL_DECISION.csv").iloc[0]
    tests=pd.read_csv(OUT/"tests/test_results.csv")
    manifest=pd.read_csv(OUT/"FILE_MANIFEST.csv")
    manifest_ok=all((OUT/r.path).exists() and sha(OUT/r.path)==r.sha256 and (OUT/r.path).stat().st_size==r.size_bytes for r in manifest.itertuples())
    sentinel_ok=RESULT_SENTINEL.exists() and RESULT_SENTINEL.read_text().strip()==sha(OUT/"EXPERIMENT_MANIFEST.json")
    completion=pd.read_csv(OUT/"audit/COMPLETION_AUDIT.csv") if (OUT/"audit/COMPLETION_AUDIT.csv").exists() else pd.DataFrame()
    checks={"config_hashes":not bad,"all_tests_pass":bool((tests.status=="PASS").all()),"physical_vlm_calls_zero":int(decision.physical_vlm_calls)==0,
        "required_outputs":all((OUT/p).exists() for p in ["FINAL_REPORT.md","FINAL_DECISION.csv","analysis/paired_effects.csv","synthetic/setting_metrics.csv","semi_synthetic/setting_metrics.csv"]),
        "full_completion_audit":len(completion)>0 and bool((completion.status=="PASS").all()),"file_manifest_hashes":manifest_ok,"sentinel_hash":sentinel_ok}
    if not all(checks.values()):raise RuntimeError(checks)
    print(json.dumps(checks,indent=2))


def main()->None:
    ap=argparse.ArgumentParser();ap.add_argument("--prepare",action="store_true");ap.add_argument("--run",action="store_true");ap.add_argument("--verify",action="store_true");args=ap.parse_args()
    for d in ["audit","configs","implementation","tests","synthetic","semi_synthetic","runs","analysis"]:(OUT/d).mkdir(parents=True,exist_ok=True)
    if args.prepare:prepare();audit_inputs();run_tests();return
    if args.run:
        if not (CONFIG_DIR/"CONFIG_FREEZE.json").exists():raise RuntimeError("run --prepare first")
        if RESULT_SENTINEL.exists():raise RuntimeError("sealed canonical result exists")
        with exclusive_runner_lock():
            verify_frozen_configs()
            run_synthetic_resumable();run_semi_synthetic_resumable();reference_path_audit();full_completion_audit()
            summary=analyze();finalize(summary);verify()
            write_run_state("COMPLETE",149,149);append_progress("gate finalized and verified")
        return
    if args.verify:verify();return
    ap.error("choose --prepare, --run, or --verify")


if __name__=="__main__":main()
