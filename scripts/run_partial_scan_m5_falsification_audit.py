#!/usr/bin/env python3
"""Online-only M5 falsification audit; pseudo-reference is evaluator-only."""
from __future__ import annotations
import json, random
from pathlib import Path
import sys
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'scripts'))
from partial_scan_pilot_common import atomic_csv,atomic_json,atomic_text,transition  # noqa
IMM=ROOT/'benchmarks/partial_scan_pilot_v1/immutable'; DER=ROOT/'benchmarks/partial_scan_pilot_v1/derived'; DEV1=ROOT/'outputs/partial_scan_method_development_v1'; OUT=ROOT/'outputs/partial_scan_method_development_v2/m5_falsification_audit'
REGION=8; BUDGET=60.; RHO=2.

def fmap():
 t=pd.read_parquet(DER/'candidate_event_map.parquet'); out={}
 for r in t[t.partition_offset_sec.eq(0)].itertuples(index=False):
  for u in json.loads(r.source_unit_ids):out.setdefault(u,set()).add(r.reference_event_id)
 return out
def q90(prev,sel,m):
 tr=transition(prev,sel); return float(m['strata'].get(f"{tr['transition_class']}|{tr['same_or_cross_gop']}|CONTROLLED_WARM",{}).get('q90_action_cost_sec',m['fallback_q90_sec']))
def run(kind, units, events, model, blocked_region=None):
 ix=dict(zip(units.unit_id,units.unit_index)); by={r.unit_id:r for r in units.itertuples(index=False)}; scanned=[]; prior=None; elapsed=0.; exposed=set(); rows=[]
 vals={u:np.array([by[u].detection_count,by[u].track_count,by[u].trigger_count,by[u].motion_activity]) for u in ix}
 rng=random.Random(20260724); shuffled=list(vals.values());rng.shuffle(shuffled); shuffled=dict(zip(vals,shuffled))
 components={'DETECTION':[0],'TRACK':[1],'TRIGGER':[2],'MOTION':[3],'COMBINED':[0,1,2,3]}
 while len(scanned)<len(units):
  rem=[u for u in ix if u not in scanned]; lg=rem[len(rem)//2] if not scanned else max(rem,key=lambda u:(min(abs(ix[u]-ix[s]) for s in scanned),-ix[u]))
  observed={u for u in scanned}; scores={}
  for reg in sorted({ix[u]//REGION for u in ix}):
   seen=[u for u in observed if ix[u]//REGION==reg]
   source=shuffled if kind=='SHUFFLED_ACTIVITY' else vals
   vec=np.mean([source[u] for u in seen],axis=0) if seen else np.zeros(4)
   active=float(vec[components.get(kind,components['COMBINED'])].sum())
   scores[reg]=active if kind=='NO_SHRINKAGE' else active*len(seen)/(len(seen)+RHO)
  if kind=='TIME_INDEX_ONLY':scores={r:float(r) for r in scores}
  target=max(scores,key=scores.get); candidates=[u for u in rem if ix[u]//REGION==target and ix[u]//REGION!=blocked_region]
  # Region exploitation is allowed only after positive online support; otherwise LG.
  selected=lg
  if candidates and any(ix[s]//REGION==target for s in scanned) and scores[target]>0:
   selected=max(candidates,key=lambda u:(min(abs(ix[u]-ix[s]) for s in scanned) if scanned else len(units),-ix[u]))
  sel=by[selected]._asdict(); c=q90(prior,sel,model)
  if elapsed+c>BUDGET:break
  new=events.get(selected,set())-exposed;exposed|=events.get(selected,set());scanned.append(selected);elapsed+=c
  rows.append({'method':kind,'unit_id':selected,'region':ix[selected]//REGION,'action_index':len(scanned),'time':elapsed,'new_events':len(new),'exposure':len(exposed),'region_score':scores.get(target,0.)});prior=sel
 return rows
def main():
 tl=pd.read_csv(IMM/'timeline_units.csv'); feat=pd.read_csv(DEV1/'temporal_cost_audit/unit_observation_features.csv'); cand=pd.concat([pd.read_parquet(p) for p in (DER/'visible_subset_candidates').glob('*_offset0_full.parquet')])
 motion=cand.groupby('unit_id').path_directed_lateral_motion.mean().rename('motion_activity').reset_index(); tl=tl.merge(feat[['unit_id','detection_count','track_count','trigger_count']],on='unit_id').merge(motion,on='unit_id',how='left').fillna(0)
 model=json.loads((DER/'cost_calibration/conservative_cost_model.json').read_text()); events=fmap(); allrows=[]
 kinds=['COMBINED','SHUFFLED_ACTIVITY','TIME_INDEX_ONLY','NO_SHRINKAGE','DETECTION','TRACK','TRIGGER','MOTION']
 for video,u in tl.groupby('video_id'):
  u=u.sort_values('unit_index'); base=run('COMBINED',u,events,model); best=pd.DataFrame(base).groupby('region').new_events.sum().idxmax() if base else None
  for kind in kinds:
   for r in run(kind,u,events,model):r['video_id']=video;allrows.append(r)
  for r in run('LEAVE_BEST_REGION_OUT',u,events,model,best):r['video_id']=video;allrows.append(r)
 trace=pd.DataFrame(allrows); OUT.mkdir(parents=True,exist_ok=True);atomic_csv(OUT/'m5_audit_trace.csv',trace)
 summary=trace.groupby(['video_id','method']).agg(actions=('action_index','max'),exposure_end=('exposure','last'),auc=('exposure',lambda x:float(np.trapezoid(x,trace.loc[x.index,'time']))),region_concentration=('region',lambda x:float(x.value_counts(normalize=True).iloc[0]))).reset_index();atomic_csv(OUT/'m5_falsification_summary.csv',summary)
 atomic_json(OUT/'audit_manifest.json',{'scope':'MECHANISM_PILOT_ONLINE_OBSERVATIONS_ONLY','negative_controls':['SHUFFLED_ACTIVITY','TIME_INDEX_ONLY','NO_SHRINKAGE','LEAVE_BEST_REGION_OUT'],'components':['DETECTION','TRACK','TRIGGER','MOTION','COMBINED'],'region_units':REGION,'shrinkage_rho':RHO})
 atomic_text(OUT/'M5_FALSIFICATION_REPORT.md','# M5 falsification audit\n\nAll macro scores use completed units only. Pseudo-reference events are evaluator-side metrics only.\n')
if __name__=='__main__':main()
