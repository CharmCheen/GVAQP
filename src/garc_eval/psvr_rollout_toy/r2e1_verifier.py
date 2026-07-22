"""Independent raw-JSON verification for E1; no coordinator imports."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from .r2 import finite_world_library

METHOD_IDS = ("B0_SCAN_THEN_CONFIRM", "B1_SHIELDED_PI0", "B2_FIXED_PERIODIC_K1", "B2_FIXED_PERIODIC_K2", "B2_FIXED_PERIODIC_K4", "B2_FIXED_PERIODIC_K8", "B3_CAPACITY_MATCHING", "B4_RATIO_PSVR", "M1_EXACT_VISIBLE_HISTORY_ROLLOUT")
REPOSITORY = Path(__file__).resolve().parents[3]

def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def _world_for_sealed(seed: int, index: int):
    """Independent spelling of the frozen 512-cell R2 stratification."""
    density=index % 8
    if index < 96:
        process, variance, cost=0,(seed//3)%4,seed%3
    elif index < 192:
        process, variance, cost=2,(seed//3)%4,seed%3
    elif index < 288:
        process, variance, cost=seed%3,2+((seed//3)%2),(seed//9)%3
    else:
        process,cost,variance,density=seed%3,(seed//3)%3,(seed//9)%4,(seed//36)%8
    return finite_world_library()[process+3*cost+9*density+72*variance]

def recompute(path: Path) -> dict:
    raw=json.loads(path.read_text()); observations=raw["visible_history"]["observations"]
    horizon=raw["visible_history"]["horizon_ticks"]; truth=set(raw["evaluator_truth_tokens"])
    elapsed=0; committed=set(); primary=0; auc=0.0; previous=0; f1=0.0; ttfc=horizon; duplicates=0
    for obs in observations:
        elapsed += obs["duration_ticks"]
        if obs["outcome"]=="DUPLICATE": duplicates+=1
        if obs["outcome"]=="NEW_COMMIT" and obs["committed_token"] is not None:
            auc += f1*(elapsed-previous); previous=elapsed
            token=obs["committed_token"]
            if token not in committed:
                committed.add(token); primary += horizon-elapsed; ttfc=min(ttfc,elapsed)
            recall=len(committed)/len(truth) if truth else 1.0; f1=recall
    auc += f1*(horizon-previous)
    return {"episode_public_id":raw["episode_public_id"],"method_id":raw["method_id"],**raw.get("evaluator_regime",{}),"primary_utility":primary,"AnytimeAUC_F1":auc/horizon,"TTFC":ttfc,"TTFC_no_commit":ttfc==horizon,"unique_committed_events_at_T":len(committed),"event_precision_at_T":1.0,"event_recall_at_T":len(committed)/len(truth) if truth else 1.0,"duplicate_CONFIRM_count":duplicates}

def _load_ledger(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

def _latest(rows: list[dict]) -> dict[tuple[str, str], dict]:
    latest = {}
    for row in rows:
        latest[(row["episode_public_id"], row["method_id"])] = row
    return latest

def verify_attempt(root: Path, *, allow_fixture: bool = False) -> dict:
    """Verify only ledger and raw traces; derived coordinator outputs are ignored."""
    ledger_path = root / "CONFIRMATORY_ATTEMPT_LEDGER.jsonl"
    if not ledger_path.is_file():
        return {"status":"FAIL","reason":"missing ledger","raw_layer_only":True}
    rows = _load_ledger(ledger_path)
    latest = _latest(rows)
    errors=[]; metrics=[]; seen_paths=set()
    sealed_path=root / "sealed_seed_manifest.json"
    public_commitment_path=root / "CONFIRMATORY_SEED_COMMITMENT.json"
    sealed_seeds=None
    if sealed_path.is_file() and public_commitment_path.is_file():
        sealed=json.loads(sealed_path.read_text(encoding="utf-8")); public=json.loads(public_commitment_path.read_text(encoding="utf-8"))
        material=b"".join(int(seed).to_bytes(8,"big") for seed in sealed.get("episode_seeds",[]))
        commitment=hashlib.sha256(material).hexdigest()
        if sealed.get("count") != 512 or len(sealed.get("episode_seeds",[])) != 512:
            errors.append({"reason":"sealed universe count mismatch"})
        if commitment != sealed.get("commitment_sha256") or commitment != public.get("commitment_sha256"):
            errors.append({"reason":"seed commitment mismatch"})
        expected_count=512*len(METHOD_IDS)
        if len(latest) != expected_count:
            errors.append({"reason":"identity count does not match sealed universe","expected":expected_count,"observed":len(latest)})
        sealed_seeds=sealed["episode_seeds"]
    elif sealed_path.exists() or public_commitment_path.exists():
        errors.append({"reason":"incomplete seed commitment layer"})
    elif not allow_fixture:
        errors.append({"reason":"confirmatory verification requires sealed/public commitment artifacts"})
    for identity, row in sorted(latest.items()):
        if row["state"] not in {"COMMITTED", "RECOVERY_COMMITTED"}:
            errors.append({"identity":identity,"reason":"noncommitted latest state","state":row["state"]}); continue
        rel=row.get("raw_trace_path")
        if not rel:
            errors.append({"identity":identity,"reason":"missing raw trace path"}); continue
        path=root/rel
        if rel in seen_paths:
            errors.append({"identity":identity,"reason":"duplicate raw trace path"}); continue
        seen_paths.add(rel)
        if not path.is_file():
            errors.append({"identity":identity,"reason":"raw trace absent"}); continue
        if _sha(path)!=row.get("raw_trace_sha256"):
            errors.append({"identity":identity,"reason":"raw trace hash mismatch"}); continue
        raw=json.loads(path.read_text(encoding="utf-8"))
        if (raw.get("episode_public_id"),raw.get("method_id"))!=identity:
            errors.append({"identity":identity,"reason":"raw identity mismatch"}); continue
        measured=recompute(path)
        if sealed_seeds is not None:
            source_hashes=raw.get("source_config_hashes",{})
            expected_hashes={"r2_freeze":_sha(REPOSITORY/"outputs/psvr_rollout_r2/R2_FREEZE_MANIFEST.json"),"preregistration":_sha(REPOSITORY/"outputs/psvr_rollout_r2/H_ROLLOUT1A_R2_PREREGISTRATION.json"),"e1_freeze":_sha(REPOSITORY/"outputs/psvr_rollout_r2e1/E1_FREEZE_MANIFEST.json"),"e1_protocol_amendment":_sha(REPOSITORY/"outputs/psvr_rollout_r2e1/E1_PROTOCOL_AMENDMENT.json")}
            if source_hashes != expected_hashes:
                errors.append({"identity":identity,"reason":"raw trace source/config hashes are not frozen bindings"}); continue
        if sealed_seeds is not None:
            index=int(identity[0].rsplit("-",1)[1])
            seed=sealed_seeds[index] if 0 <= index < len(sealed_seeds) else None
            if seed is None or hashlib.sha256(str(seed).encode()).hexdigest()!=row.get("sealed_seed_hash"):
                errors.append({"identity":identity,"reason":"ledger sealed-seed binding mismatch"}); continue
            world=_world_for_sealed(seed,index)
            expected_regime={"process":world.process,"cost_regime":world.cost_regime,"density_bin":world.density_bin,"cost_variance_bin":world.cost_variance_bin}
            expected_truth=sorted({token for region in world.regions for token in region.event_tokens if token is not None})
            if raw.get("evaluator_regime") != expected_regime or raw.get("evaluator_truth_tokens") != expected_truth:
                errors.append({"identity":identity,"reason":"raw evaluator truth/regime does not bind to sealed seed"}); continue
        recorded=raw.get("trace_metrics",{})
        for key in ("primary_utility","AnytimeAUC_F1","TTFC","TTFC_no_commit","unique_committed_events_at_T","event_recall_at_T","duplicate_CONFIRM_count"):
            if key not in recorded or recorded[key] != measured[key]:
                errors.append({"identity":identity,"reason":"coordinator metric disagrees with independent recomputation","metric":key}); break
        metrics.append(measured)
    expected = {(episode, method) for episode, method in latest}
    method_errors=[{"episode_public_id":episode,"methods":sorted(method for ep,method in expected if ep==episode)} for episode in sorted({ep for ep,_ in expected}) if {method for ep,method in expected if ep==episode} != set(METHOD_IDS)]
    if method_errors: errors.extend({"reason":"method universe mismatch",**item} for item in method_errors)
    return {"status":"PASS" if not errors else "FAIL","ledger_row_count":len(rows),"latest_identity_count":len(latest),"committed_identity_count":len(metrics),"error_count":len(errors),"errors":errors,"recomputed_metrics":metrics,"raw_layer_only":True,"derived_outputs_read":False}
