"""Development-only H1B execution harness; deliberately no confirmatory API."""
from __future__ import annotations
import hashlib, json, os, time
from dataclasses import asdict, dataclass
from pathlib import Path
from .approximate_rollout import ApproximatePlanner, PlannerConfig
from .types import ActionView, VisibleDecisionState
from .error_operators import ErrorContext, perturb_probability, perturb_duration
from garc_eval.psvr_rollout_toy.r2 import ActionR2, R2Environment, finite_world_library

METHODS=("B1_SHIELDED_PI0","APPROX_NO_FALLBACK","APPROX_POINT_ESTIMATE_FALLBACK","APPROX_LCB_FALLBACK","APPROX_PLANNING_ADMISSION_LCB")
STATES=("PREPARED","STARTED","COMMITTED","FAILED_DETERMINISTIC","FAILED_INFRASTRUCTURE","RECOVERY_STARTED","RECOVERY_COMMITTED","INVALIDATED_HASH_MISMATCH")
PUBLIC_SEEDS=(-10001,-10002,-10003,-10004,-10005,-10006)

def sha(path: Path)->str: return hashlib.sha256(path.read_bytes()).hexdigest()
def atomic_json(path: Path, payload: dict)->None:
    """Durably publish an immutable raw trace only after its full contents exist."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    if temporary.exists():
        raise FileExistsError('unresolved partial development trace')
    with temporary.open('x',encoding='utf-8') as f:
        f.write(json.dumps(payload,sort_keys=True)+'\n'); f.flush(); os.fsync(f.fileno())
    os.replace(temporary,path)
def append(path:Path,row:dict)->None:
    if row['state'] not in STATES: raise ValueError('ledger state')
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a',encoding='utf-8') as f: f.write(json.dumps(row,sort_keys=True)+'\n'); f.flush(); os.fsync(f.fileno())
def latest(path:Path)->dict:
    out={}
    for line in path.read_text().splitlines():
        row=json.loads(line); out[(row['development_episode_id'],row['configuration_id'],row['method_id'])]=row
    return out
@dataclass(frozen=True)
class DevModel:
    seed:int
    error_target:str
    error_form:str="systematic_optimism"
    magnitude:float=.05
    def paired_returns(self,state,action,base,worlds,trajectories):
        # deterministic debug-only paired values, not an evaluator environment.
        delta=(sum(map(ord,action.identifier))-sum(map(ord,base.identifier))+self.seed)%7-3
        # All perturbations remain planner-only.  JOINT_CORNER deterministically
        # composes every frozen target, rather than merely setting its LCB margin.
        targets=(self.error_target,) if self.error_target!='JOINT_CORNER' else ('scan_candidate_yield','confirm_positive_probability','novelty_duplicate_probability','grouping_transition','action_duration','materialization_success')
        for target in targets:
            context=ErrorContext(self.seed,state.decision_index,target,self.error_form,0,action.identifier,0,action.score_bin,action.score_bin)
            if target=='action_duration': delta -= perturb_duration(2,self.magnitude,138,context)-2
            else: delta += int(perturb_probability(.5,self.magnitude,context)*2)-1
        return tuple(float(100+delta+i%2) for i in range(worlds*trajectories)),tuple(float(100+i%2) for i in range(worlds*trajectories))
def base(state):
    confirms=[a for a in state.ordered_actions() if a.kind=='CONFIRM']
    return confirms[0] if confirms else state.ordered_actions()[0] if state.legal_actions else None
def visible(env:R2Environment,cost:int)->VisibleDecisionState:
    safe=env.safe_actions(); state=env.visible_state()
    actions=tuple(ActionView(a.identifier,a.kind,region_id=a.region_id,hypothesis_id=a.hypothesis_id,witness_id=a.witness_id,minimum_remaining_ticks=0) for a in safe)
    frontier=tuple(ActionView(f'CONFIRM::{c.hypothesis_id}:{c.witness_id}','CONFIRM',c.score_bin,c.hypothesis_id,c.witness_id) for c in state.frontier)
    return VisibleDecisionState(env.history.digest,len(env.history.actions),state.remaining_ticks,actions,frontier)
def actual(action:ActionView, env:R2Environment)->ActionR2:
    return next(a for a in env.safe_actions() if a.identifier==action.identifier)
def execute(row:dict,root:Path,hashes:dict)->dict:
    seed=PUBLIC_SEEDS[int(row['development_episode_id'].rsplit('-',1)[1])]; cost=int(row['planning_cost_id'].split('-')[1]); method=row['method_id']
    env=R2Environment(finite_world_library()[abs(seed)%len(finite_world_library())])
    state=visible(env,cost)
    if method=='B1_SHIELDED_PI0':
        selected=base(state); trace={'visible_history_hash':state.history_hash,'base_action':selected.identifier,'selected_action':selected.identifier,'planning_admitted':False,'planning_time':0,'paired_advantages':{},'lcbs':{},'fallback_reason':'BASELINE','post_planning_remaining_time':state.remaining_ticks,'post_planning_feasibility':True}
    else:
        mode={'APPROX_NO_FALLBACK':'UNGATED','APPROX_POINT_ESTIMATE_FALLBACK':'POINT','APPROX_LCB_FALLBACK':'LCB','APPROX_PLANNING_ADMISSION_LCB':'LCB'}[method]
        condition='JOINT_CORNER' if row['error_target_id']=='JOINT_CORNER' else 'STANDARD'
        worlds,trajectories=(int(x) for x in row['budget_id'].removeprefix('b-').split('x'))
        model=DevModel(seed,row['error_target_id'],row.get('error_form','systematic_optimism'),float(row.get('error_magnitude',.05))); selected,pt=ApproximatePlanner(base,model,PlannerConfig(worlds,trajectories,cost,mode,condition)).decide(state); trace=pt.to_dict()
        base_action=base(state)
        # Store every candidate sample vector.  This is raw evidence for the
        # independent verifier, including candidates rejected by fallback.
        sample_vectors={}
        by_identifier={a.identifier:a for a in state.ordered_actions()}
        for identifier in trace['paired_advantages']:
            values,base_values=model.paired_returns(state,by_identifier[identifier],base_action,worlds,trajectories)
            sample_vectors[identifier]={'action_returns':values,'base_returns':base_values}
        trace['paired_sample_vectors']=sample_vectors
        if trace['planning_admitted']: env._elapsed += cost
    if selected.identifier in {a.identifier for a in env.safe_actions()}:
        obs=env.execute(actual(selected,env))
    else: obs=env.execute(ActionR2.stop())
    if not env.visible_state().stopped: env.execute(ActionR2.stop())
    elapsed=env.visible_state().elapsed_ticks; utility=(1600-elapsed) if obs.outcome=='NEW_COMMIT' else 0
    payload={'label':'DEBUG_ONLY_NOT_FOR_SCIENTIFIC_USE','non_confirmatory':True,'identity':row,'trace':trace,'committed_event_timeline':[{'tick':elapsed,'outcome':obs.outcome}],'utility_timeline':[{'tick':0,'utility':0},{'tick':elapsed,'utility':utility}],'stop_time':elapsed,'completion_state':'COMMITTED','source_config_hashes':hashes}
    path=root/'DEVELOPMENT_RAW_TRACES'/f"{row['development_episode_id']}__{row['configuration_id']}__{method}.json"; path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists(): raise FileExistsError('immutable development trace')
    atomic_json(path,payload)
    return {'path':str(path.relative_to(root)),'sha256':sha(path),'trace':trace}
