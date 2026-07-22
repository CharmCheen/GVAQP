"""E1 execution-only coordinator primitives; no import-time seed generation."""
from __future__ import annotations

import csv, hashlib, json, os, tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .r2 import CapacityMatchingR2, ExactConditionalRollout, ExactPosterior, FixedPeriodicR2, R2Environment, RatioPSVRR2, ScanThenConfirmR2, ShieldedPi0R2, finite_world_library
from .r2_confirmatory import generate_confirmatory_universe_once
from .r2_splits import LEGACY_HELDOUT, LEGACY_HELDOUT_SHA256


METHOD_IDS = ("B0_SCAN_THEN_CONFIRM", "B1_SHIELDED_PI0", "B2_FIXED_PERIODIC_K1", "B2_FIXED_PERIODIC_K2", "B2_FIXED_PERIODIC_K4", "B2_FIXED_PERIODIC_K8", "B3_CAPACITY_MATCHING", "B4_RATIO_PSVR", "M1_EXACT_VISIBLE_HISTORY_ROLLOUT")
LEDGER_STATES = {"PREPARED", "STARTED", "COMMITTED", "FAILED_DETERMINISTIC", "FAILED_INFRASTRUCTURE", "RECOVERY_STARTED", "RECOVERY_COMMITTED", "INVALIDATED_HASH_MISMATCH"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, encoding="utf-8") as out:
        json.dump(value, out, sort_keys=True, separators=(",", ":")); out.write("\n"); tmp = Path(out.name)
    tmp.replace(path)


def append_ledger(path: Path, row: dict) -> None:
    if row["state"] not in LEDGER_STATES: raise ValueError("invalid ledger state")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as out:
        out.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
        out.flush(); os.fsync(out.fileno())


def load_ledger(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def latest_states(rows: list[dict]) -> dict[tuple[str,str], dict]:
    state = {}
    for row in rows: state[(row["episode_public_id"], row["method_id"])] = row
    return state


def precheck(root: Path, r2_freeze: Path, prereg: Path) -> dict:
    freeze=json.loads(r2_freeze.read_text()); mismatches=[]
    repository = r2_freeze.parents[2]
    for row in freeze["files"]:
        p=repository/row["file"]
        if not p.is_file() or sha(p)!=row["sha256"]: mismatches.append(row["file"])
    return {"ok": not root.exists() and not mismatches and (not LEGACY_HELDOUT.exists() or sha(LEGACY_HELDOUT)==LEGACY_HELDOUT_SHA256), "attempt_root_exists":root.exists(), "freeze_mismatches":mismatches, "preregistration_hash":sha(prereg), "legacy_hash":LEGACY_HELDOUT_SHA256}


def initialize_once(root: Path, r2_freeze: Path, prereg: Path) -> dict:
    check=precheck(root,r2_freeze,prereg)
    if not check["ok"]: raise RuntimeError(f"E1 precheck failed: {check}")
    commitment=generate_confirmatory_universe_once(root,512)
    sealed=json.loads((root/"sealed_seed_manifest.json").read_text())
    atomic_json(root/"CONFIRMATORY_SEED_COMMITMENT.json", commitment)
    atomic_json(root/"CONFIRMATORY_SEALED_UNIVERSE_MANIFEST.json", {"commitment_sha256":commitment["commitment_sha256"],"count":512,"algorithm":sealed["algorithm"]})
    ledger=root/"CONFIRMATORY_ATTEMPT_LEDGER.jsonl"
    for i, seed in enumerate(sealed["episode_seeds"]):
        for method in METHOD_IDS:
            append_ledger(ledger,{"episode_public_id":f"confirmatory-{i:04d}","sealed_seed_hash":hashlib.sha256(str(seed).encode()).hexdigest(),"method_id":method,"state":"PREPARED","attempt_ordinal":0,"timestamp":datetime.now(timezone.utc).isoformat(),"raw_trace_path":None,"raw_trace_sha256":None,"failure_class":None,"recovery_status":"NONE"})
    return commitment


def write_trace(root: Path, episode_public_id: str, method_id: str, env: R2Environment, hashes: dict) -> Path:
    path=root/"CONFIRMATORY_RAW_TRACES"/f"{episode_public_id}__{method_id}.json"
    if path.exists(): raise FileExistsError("COMMITTED raw trace cannot be overwritten")
    truth=sorted({token for region in env._world.regions for token in region.event_tokens if token is not None})
    world = env._world
    payload={"episode_public_id":episode_public_id,"method_id":method_id,"visible_history":asdict(env.history),"evaluator_truth_tokens":truth,"evaluator_regime":{"process":world.process,"cost_regime":world.cost_regime,"density_bin":world.density_bin,"cost_variance_bin":world.cost_variance_bin},"trace_metrics":env.metrics(),"completion_state":"COMMITTED","source_config_hashes":hashes}
    atomic_json(path,payload); return path


def run_closed_loop(world, policy) -> R2Environment:
    env=R2Environment(world)
    while not env.visible_state().stopped: env.execute(policy.choose(env.history,env.safe_actions()))
    return env


def m1_policy(): return ExactConditionalRollout(ExactPosterior(finite_world_library()))

def policy_universe() -> dict:
    return {"B0_SCAN_THEN_CONFIRM":ScanThenConfirmR2(),"B1_SHIELDED_PI0":ShieldedPi0R2(),"B2_FIXED_PERIODIC_K1":FixedPeriodicR2(1),"B2_FIXED_PERIODIC_K2":FixedPeriodicR2(2),"B2_FIXED_PERIODIC_K4":FixedPeriodicR2(4),"B2_FIXED_PERIODIC_K8":FixedPeriodicR2(8),"B3_CAPACITY_MATCHING":CapacityMatchingR2(),"B4_RATIO_PSVR":RatioPSVRR2(),"M1_EXACT_VISIBLE_HISTORY_ROLLOUT":m1_policy()}

def world_for_sealed(seed: int, index: int):
    worlds=finite_world_library(); density=index%8
    if index<96: process,variance,cost=0,(seed//3)%4,seed%3
    elif index<192: process,variance,cost=2,(seed//3)%4,seed%3
    elif index<288: process,variance,cost=seed%3,2+((seed//3)%2),(seed//9)%3
    else: process,cost,variance,density=seed%3,(seed//3)%3,(seed//9)%4,(seed//36)%8
    return worlds[process+3*cost+9*density+72*variance]

def execute_identity(root: Path, index: int, seed: int, method_id: str, hashes: dict, recovery: bool=False) -> dict:
    episode=f"confirmatory-{index:04d}"; ledger=root/"CONFIRMATORY_ATTEMPT_LEDGER.jsonl"
    latest=latest_states(load_ledger(ledger)); prior=latest[(episode,method_id)]
    if prior["state"] in {"COMMITTED","RECOVERY_COMMITTED"}: return prior
    trace_path=root/"CONFIRMATORY_RAW_TRACES"/f"{episode}__{method_id}.json"
    # A crash after atomic trace publication but before the ledger append is
    # recoverable without re-execution: bind the already immutable raw trace.
    if trace_path.is_file():
        raw=json.loads(trace_path.read_text(encoding="utf-8"))
        if raw.get("episode_public_id") != episode or raw.get("method_id") != method_id or raw.get("source_config_hashes") != hashes:
            raise RuntimeError("orphan raw trace fails identity/hash reconciliation")
        reconciled={**prior,"state":"RECOVERY_COMMITTED","attempt_ordinal":prior["attempt_ordinal"]+1,"timestamp":datetime.now(timezone.utc).isoformat(),"raw_trace_path":str(trace_path.relative_to(root)),"raw_trace_sha256":sha(trace_path),"failure_class":None,"recovery_status":"RECONCILED_ATOMIC_RAW_TRACE"}
        append_ledger(ledger,reconciled); return reconciled
    state="RECOVERY_STARTED" if recovery else "STARTED"
    append_ledger(ledger,{**prior,"state":state,"attempt_ordinal":prior["attempt_ordinal"]+1,"timestamp":datetime.now(timezone.utc).isoformat(),"recovery_status":"SAME_SEALED_IDENTITY"})
    try:
        env=run_closed_loop(world_for_sealed(seed,index),policy_universe()[method_id])
        trace=write_trace(root,episode,method_id,env,hashes)
        committed={**prior,"state":"RECOVERY_COMMITTED" if recovery else "COMMITTED","attempt_ordinal":prior["attempt_ordinal"]+1,"timestamp":datetime.now(timezone.utc).isoformat(),"raw_trace_path":str(trace.relative_to(root)),"raw_trace_sha256":sha(trace),"failure_class":None,"recovery_status":"COMMITTED"}
        append_ledger(ledger,committed); return committed
    except Exception as exc:
        failed={**prior,"state":"FAILED_INFRASTRUCTURE","attempt_ordinal":prior["attempt_ordinal"]+1,"timestamp":datetime.now(timezone.utc).isoformat(),"failure_class":type(exc).__name__,"recovery_status":"REQUIRES_SAME_IDENTITY"}
        append_ledger(ledger,failed); raise

def derive_raw_results(root: Path) -> list[dict]:
    rows=[]
    for path in sorted((root/"CONFIRMATORY_RAW_TRACES").glob("*.json")):
        raw=json.loads(path.read_text()); rows.append({"episode_public_id":raw["episode_public_id"],"method_id":raw["method_id"],**raw["evaluator_regime"],**raw["trace_metrics"]})
    return rows

def write_csv(path: Path, rows: list[dict]) -> None:
    if path.exists(): raise FileExistsError(f"immutable derived artifact already exists: {path.name}")
    path.parent.mkdir(parents=True,exist_ok=True)
    fields=sorted({key for row in rows for key in row})
    with tempfile.NamedTemporaryFile("w",dir=path.parent,delete=False,encoding="utf-8",newline="") as out:
        writer=csv.DictWriter(out,fieldnames=fields); writer.writeheader(); writer.writerows(rows); tmp=Path(out.name)
    tmp.replace(path)

def export_derived_layer(root: Path) -> dict:
    """Deterministic exports; source of truth remains raw trace JSON."""
    bundle=root/"CONFIRMATORY_DERIVED_BUNDLE"
    if bundle.exists():
        required={"CONFIRMATORY_RAW_RESULTS.csv","CONFIRMATORY_EPISODE_MANIFEST.csv","CONFIRMATORY_EXECUTION_FAILURES.csv","CONFIRMATORY_TASK_RESULTS.csv","CONFIRMATORY_PAIRED_DIFFERENCES.csv","CONFIRMATORY_REGIME_RESULTS.csv","CONFIRMATORY_METRIC_RECOMPUTATION.json"}
        if required == {p.name for p in bundle.iterdir() if p.is_file()}:
            return json.loads((bundle/"CONFIRMATORY_METRIC_RECOMPUTATION.json").read_text(encoding="utf-8"))["counts"]
        raise RuntimeError("incomplete derived bundle is immutable evidence; publication blocked")
    staging=root/f".CONFIRMATORY_DERIVED_BUNDLE.staging-{os.getpid()}"
    staging.mkdir(parents=True,exist_ok=False)
    raw=derive_raw_results(root); write_csv(staging/"CONFIRMATORY_RAW_RESULTS.csv",raw)
    latest=latest_states(load_ledger(root/"CONFIRMATORY_ATTEMPT_LEDGER.jsonl"))
    episodes=[]
    for episode in sorted({r["episode_public_id"] for r in latest.values()}):
        rows=[r for r in raw if r["episode_public_id"]==episode]
        regime=rows[0] if rows else {}
        episodes.append({"episode_public_id":episode,"method_count":len(rows),"process":regime.get("process"),"cost_regime":regime.get("cost_regime"),"density_bin":regime.get("density_bin"),"cost_variance_bin":regime.get("cost_variance_bin")})
    write_csv(staging/"CONFIRMATORY_EPISODE_MANIFEST.csv",episodes)
    failures=[row for row in latest.values() if row["state"] not in {"COMMITTED","RECOVERY_COMMITTED"}]
    write_csv(staging/"CONFIRMATORY_EXECUTION_FAILURES.csv",failures)
    by_episode={}
    for row in raw: by_episode.setdefault(row["episode_public_id"],{})[row["method_id"]]=row
    tasks=[]; paired=[]
    for episode, methods in sorted(by_episode.items()):
        for method,row in sorted(methods.items()): tasks.append({"episode_public_id":episode,"method_id":method,"primary_utility":row["primary_utility"],"AnytimeAUC_F1":row["AnytimeAUC_F1"],"TTFC":row["TTFC"]})
        if "M1_EXACT_VISIBLE_HISTORY_ROLLOUT" in methods:
            for method,row in methods.items():
                if method!="M1_EXACT_VISIBLE_HISTORY_ROLLOUT": paired.append({"episode_public_id":episode,"comparator":method,"M1_minus_comparator":methods["M1_EXACT_VISIBLE_HISTORY_ROLLOUT"]["primary_utility"]-row["primary_utility"]})
    write_csv(staging/"CONFIRMATORY_TASK_RESULTS.csv",tasks); write_csv(staging/"CONFIRMATORY_PAIRED_DIFFERENCES.csv",paired)
    regime=[]
    keys=("process","cost_regime","density_bin","cost_variance_bin","method_id")
    groups={}
    for row in raw: groups.setdefault(tuple(row[k] for k in keys),[]).append(row)
    for values, rows in sorted(groups.items()):
        regime.append({**dict(zip(keys,values)),"n":len(rows),"mean_primary_utility":sum(r["primary_utility"] for r in rows)/len(rows)})
    write_csv(staging/"CONFIRMATORY_REGIME_RESULTS.csv",regime)
    counts={"raw":len(raw),"tasks":len(tasks),"paired":len(paired),"regimes":len(regime),"failures":len(failures)}
    atomic_json(staging/"CONFIRMATORY_METRIC_RECOMPUTATION.json",{"derivation":"COORDINATOR_DERIVED_NOT_INDEPENDENT_VERIFICATION","counts":counts})
    staging.replace(bundle)
    return counts

def publish_decision_bundle(root: Path, verifier: dict, gate: dict, decision: dict) -> dict:
    """Publish formal verifier/Gate/decision records as one immutable bundle."""
    bundle=root/"CONFIRMATORY_DECISION_BUNDLE"
    required={"CONFIRMATORY_INDEPENDENT_VERIFICATION.json","CONFIRMATORY_GATE_EVALUATION.json","CONFIRMATORY_DECISION_BRANCH.json"}
    if bundle.exists():
        if required != {p.name for p in bundle.iterdir() if p.is_file()}:
            raise RuntimeError("incomplete decision bundle is immutable interruption evidence")
        return {name:json.loads((bundle/name).read_text(encoding="utf-8")) for name in required}
    staging=root/f".CONFIRMATORY_DECISION_BUNDLE.staging-{os.getpid()}"
    staging.mkdir(parents=True,exist_ok=False)
    atomic_json(staging/"CONFIRMATORY_INDEPENDENT_VERIFICATION.json",verifier)
    atomic_json(staging/"CONFIRMATORY_GATE_EVALUATION.json",gate)
    atomic_json(staging/"CONFIRMATORY_DECISION_BRANCH.json",decision)
    staging.replace(bundle)
    return {"CONFIRMATORY_INDEPENDENT_VERIFICATION.json":verifier,"CONFIRMATORY_GATE_EVALUATION.json":gate,"CONFIRMATORY_DECISION_BRANCH.json":decision}

def completion_eligible(root: Path) -> bool:
    ledger=latest_states(load_ledger(root/"CONFIRMATORY_ATTEMPT_LEDGER.jsonl"))
    return bool(ledger) and all(row["state"] in {"COMMITTED","RECOVERY_COMMITTED"} for row in ledger.values())
