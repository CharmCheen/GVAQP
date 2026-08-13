#!/usr/bin/env python3
"""Freeze VLM-direct shadow reference, then run frozen P1 analyses in isolation."""
from __future__ import annotations

import hashlib, json, math, sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeRegressor

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
from garc_eval.p1b_protocol_v1_2 import assign_positive_units_to_events
from garc_eval.accelerated_event_query.matching import MatchConfig,match_events,summarize_matches
from garc_eval.accelerated_event_query.types import EventRecord

OUT=ROOT/'outputs/p1_shadow_vlm_direct_reference_v1'; P1=ROOT/'outputs/p1_independent_geometry_replication_v1'
TRACE=P1/'TRACE_POPULATION.csv'; PAIRS=P1/'PRIMARY_GEOMETRY_PAIR_MANIFEST_V1_2.csv'; PROXY=P1/'TRACE_PROXY_DEPENDENCE_AUDIT.csv'
Q1=ROOT/'outputs/v10_multiseal_reference_v1/FINAL_UNIT_REFERENCE.parquet'; Q2=ROOT/'outputs/gvaqp_long_horizon_p1_p3_v1/qwen32_oracle/P1_QWEN32_UNIT_OUTCOMES.parquet'
VIDEOS=('DALI','HANGZHOU','WUHAN'); QUERIES=('Q_DRIVER_RESPONSE_V1','Q_VULNERABLE_ROAD_USER_CONFLICT_V1')
PROXIES=('PROXY_A_YOLOV8N_OBJECT_MOTION','PROXY_B_OPTICAL_FLOW_VISUAL_DYNAMICS')
PUBLIC=['positive_yield','number_of_temporal_regions_touched','temporal_dispersion','coverage_fraction','largest_unqueried_gap','median_unqueried_gap','query_redundancy','near_duplicate_query_fraction','queried_temporal_span']

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def dump(p,x): p.write_text(json.dumps(x,indent=2,sort_keys=True,allow_nan=False,ensure_ascii=False)+'\n')
def iou(a,b):
 o=max(0,min(a['end_time'],b['end_time'])-max(a['start_time'],b['start_time'])); u=max(a['end_time'],b['end_time'])-min(a['start_time'],b['start_time']); return o/u if u else 0.
def match(left,right,threshold=0.):
 if not left or not right:return []
 s=np.array([[iou(a,b) for b in right] for a in left]); rr,cc=linear_sum_assignment(-s)
 return [(left[i],right[j],float(s[i,j])) for i,j in zip(rr,cc) if s[i,j]>threshold]

def require_complete():
 protocol=json.loads((OUT/'SHADOW_PROTOCOL.json').read_text()); cases=json.loads((OUT/'BLINDED_CASES.json').read_text())
 expected=sum(math.ceil(float(c['duration_sec'])/float(protocol['windowing']['stride_sec'])) for c in cases)
 streams={}
 for a in ('VLM_A','VLM_B'):
  path=OUT/f'{a}_RAW.jsonl'; rows=[json.loads(x) for x in path.read_text().splitlines() if x.strip()] if path.exists() else []
  # The completed sharded restart bound both streams to the final fallback
  # protocol hash; partial preflight streams were excluded before merge.
  expected_hash=protocol['protocol_hash']
  if len(rows)!=expected or len({x['window_id'] for x in rows})!=expected or any(x['protocol_hash']!=expected_hash or x['annotator_id']!=a or not x['terminal'] for x in rows): raise RuntimeError(f'{a} incomplete/not bound to its frozen shadow protocol: {len(rows)}/{expected}')
  streams[a]=rows
 return protocol,cases,streams,expected

def stitch(rows,annotator):
 events=[]
 for x in rows:
  for e in x['events']:
   events.append({'start_time':float(x['window_start'])+float(e['start_offset_sec']),'end_time':float(x['window_start'])+float(e['end_offset_sec']),'boundary_ambiguous':bool(e['boundary_ambiguous']),'semantic_ambiguous':bool(e['semantic_ambiguous']),'notes':e.get('notes','')})
 events.sort(key=lambda x:(x['start_time'],x['end_time']))
 merged=[]
 for e in events:
  if merged and e['start_time'] < merged[-1]['end_time']:
   merged[-1]['end_time']=max(merged[-1]['end_time'],e['end_time']); merged[-1]['start_time']=min(merged[-1]['start_time'],e['start_time']); merged[-1]['boundary_ambiguous']|=e['boundary_ambiguous']; merged[-1]['semantic_ambiguous']|=e['semantic_ambiguous']; merged[-1]['notes']=(merged[-1]['notes']+' | '+e['notes'])[:1000]
  else: merged.append(e.copy())
 for i,e in enumerate(merged,1):e['event_id']=f'{annotator}::E{i:04d}'
 return merged

def build_reference(protocol,cases,streams):
 ann={}; agreement=[]
 for case in cases:
  cid=case['case_id']; a=stitch([x for x in streams['VLM_A'] if x['case_id']==cid],'VLM_A'); b=stitch([x for x in streams['VLM_B'] if x['case_id']==cid],'VLM_B'); ann[cid]=(a,b)
  raw=match(a,b); row={'case_id':cid,'video_id':case['video_id'],'query_id':case['query_id'],'vlm_a_event_count':len(a),'vlm_b_event_count':len(b),'event_existence_agreement':bool(a)==bool(b),'matched_event_fraction_iou_gt_0':2*len(raw)/(len(a)+len(b)) if a or b else 1.,'median_matched_temporal_iou':float(np.median([x[2] for x in raw])) if raw else np.nan,'median_abs_start_difference':float(np.median([abs(x[0]['start_time']-x[1]['start_time']) for x in raw])) if raw else np.nan,'median_abs_end_difference':float(np.median([abs(x[0]['end_time']-x[1]['end_time']) for x in raw])) if raw else np.nan}
  for t in (.1,.3,.5): row[f'matched_events_iou_ge_{str(t).replace(".","p")}']=len(match(a,b,t-1e-12))
  agreement.append(row)
 agree=pd.DataFrame(agreement); agree.to_csv(OUT/'VLM_AGREEMENT_BY_CASE.csv',index=False)
 refs=[]
 for case in cases:
  a,b=ann[case['case_id']]; matched=match(a,b); useda={id(x[0]) for x in matched}; usedb={id(x[1]) for x in matched}; combined=[]
  for x,y,_ in matched: combined.append({'start_time':min(x['start_time'],y['start_time']),'end_time':max(x['end_time'],y['end_time']),'boundary_ambiguous':x['boundary_ambiguous'] or y['boundary_ambiguous'],'semantic_ambiguous':x['semantic_ambiguous'] or y['semantic_ambiguous'],'source':'MATCHED_UNION'})
  combined += [{**x,'source':'UNMATCHED_VLM_A'} for x in a if id(x) not in useda]; combined += [{**x,'source':'UNMATCHED_VLM_B'} for x in b if id(x) not in usedb]; combined.sort(key=lambda x:(x['start_time'],x['end_time'],x['source']))
  for i,e in enumerate(combined,1): refs.append({'video_id':case['video_id'],'query_id':case['query_id'],'event_id':f'SHADOW::{case["video_id"]}::{case["query_id"]}::E{i:04d}','start_time':e['start_time'],'end_time':e['end_time'],'boundary_ambiguous':e.get('boundary_ambiguous',False),'semantic_ambiguous':e.get('semantic_ambiguous',False),'adjudication_source':e['source'],'reference_type':'VLM_DIRECT_SHADOW','human_reference':False})
 ref=pd.DataFrame(refs); ref.to_csv(OUT/'SHADOW_VLM_EVENT_REFERENCE.csv',index=False)
 summary={'event_existence_agreement':float(agree.event_existence_agreement.mean()),'global_matched_event_fraction_iou_gt_0':float(2*sum(len(match(*ann[c['case_id']])) for c in cases)/sum(len(x) for pair in ann.values() for x in pair)) if sum(len(x) for pair in ann.values() for x in pair) else 1.,'median_matched_temporal_iou':float(agree.median_matched_temporal_iou.median()),'median_abs_start_difference':float(agree.median_abs_start_difference.median()),'median_abs_end_difference':float(agree.median_abs_end_difference.median()),'vlm_a_events':sum(len(x[0]) for x in ann.values()),'vlm_b_events':sum(len(x[1]) for x in ann.values()),'shadow_events':len(ref)}
 (OUT/'VLM_AGREEMENT.md').write_text('# Shadow VLM agreement\n\n```json\n'+json.dumps(summary,indent=2,sort_keys=True)+'\n```\n\nThis is a shadow quality diagnostic, not the formal human-reference gate.\n')
 freeze={'status':'FROZEN_VLM_DIRECT_SHADOW','reference_type':'VLM_DIRECT_SHADOW','human_reference':False,'created_at_utc':datetime.now(timezone.utc).isoformat(),'reference_sha256':sha(OUT/'SHADOW_VLM_EVENT_REFERENCE.csv'),'vlm_a_raw_sha256':sha(OUT/'VLM_A_RAW.jsonl'),'vlm_b_raw_sha256':sha(OUT/'VLM_B_RAW.jsonl'),'protocol_hash':protocol['protocol_hash'],'event_count':len(ref)}; dump(OUT/'SHADOW_REFERENCE_FREEZE.json',freeze)
 return ref,agree,summary,freeze

def labels():
 out={}
 for q,d,col in ((QUERIES[0],pd.read_parquet(Q1),'authoritative_label'),(QUERIES[1],pd.read_parquet(Q2),'label')):
  for v,g in d.groupby('video_id'):out[(str(v),q)]={str(r.unit_id):{'label':str(getattr(r,col)),'start':float(r.start_time),'end':float(r.end_time)} for r in g.itertuples()}
 return out
def c1(pos):
 g=[]
 for x in sorted(pos,key=lambda z:(z['start'],z['end'])):
  if not g or x['start']-g[-1][-1]['end']>10:g.append([x])
  else:g[-1].append(x)
 return [(min(x['start'] for x in z),max(x['end'] for x in z)) for z in g]
def c1metrics(pred,ref,v,q):
 p=[EventRecord(f'p{i}',q,v,a,b,1.,'V',(),(),'C1',None) for i,(a,b) in enumerate(pred)]; r=[EventRecord(f'r{i}',q,v,a,b,1.,'R',(),(),'SHADOW',None) for i,(a,b) in enumerate(ref)]; m=match_events(p,r,MatchConfig(minimum_tiou=0.,boundary_tolerance_sec=0.)); s=summarize_matches(p,r,m); return float(s['32b_operational_oracle_relative_event_precision']),float(s['32b_operational_oracle_relative_event_recall']),float(s['event_f1']),float(np.mean([x.temporal_iou for x in m])) if m else 0.
def endpoints(ref):
 tr=pd.read_csv(TRACE); lm=labels(); rows=[]
 for t in tr.itertuples(index=False):
  pos=[{**lm[(t.video_id,t.query_id)][u],'unit_id':u} for u in json.loads(t.queried_unit_ids) if lm[(t.video_id,t.query_id)][u]['label']=='relevant']; rr=ref[(ref.video_id==t.video_id)&(ref.query_id==t.query_id)]; ev=[{'event_id':r.event_id,'start_time':r.start_time,'end_time':r.end_time} for r in rr.itertuples()]; ac=assign_positive_units_to_events(pos,ev,'ANCHOR_ASSIGNED_EVENT'); oc=assign_positive_units_to_events(pos,ev,'OVERLAP_ANY_EVENT'); touched=sum(x>0 for x in ac.values()); ot=sum(x>0 for x in oc.values()); cov=touched/len(ev) if ev else np.nan; ep=sum(ac.values())/len(pos) if pos else (1. if not ev else 0.); f1=2*ep*cov/(ep+cov) if ev and ep+cov else (0. if ev else np.nan); cp,cr,cf,ci=c1metrics(c1(pos),[(r.start_time,r.end_time) for r in rr.itertuples()],t.video_id,t.query_id)
  rows.append({**t._asdict(),'human_reference_event_count':len(ev),'distinct_events_anchor_assigned':touched,'event_coverage_anchor_assigned':cov,'events_with_zero_anchor_evidence':len(ev)-touched,'events_with_1plus_anchor_evidence':touched,'events_with_2plus_anchor_evidence':sum(x>=2 for x in ac.values()),'distinct_events_overlap_any':ot,'event_coverage_overlap_any':ot/len(ev) if ev else np.nan,'event_recall':cov,'event_F1':f1,'C1_precision':cp,'C1_recall':cr,'C1_F1':cf,'C1_mean_iou':ci})
 return pd.DataFrame(rows)
def pair_results(ep):
 pairs=pd.read_csv(PAIRS); look=ep.set_index('trace_instance_id'); rows=[]
 for p in pairs.itertuples(index=False):
  a=look.loc[p.trace_a_better_geometry]; b=look.loc[p.trace_b_worse_geometry]; r=p._asdict()
  for m in ('distinct_events_anchor_assigned','event_coverage_anchor_assigned','distinct_events_overlap_any','event_coverage_overlap_any','event_recall','event_F1','C1_F1'):r['better_'+m]=float(a[m]);r['worse_'+m]=float(b[m]);r['delta_'+m]=float(a[m]-b[m])
  rows.append(r)
 return pd.DataFrame(rows)
def aggregate(pr):
 dep=pr[pr.trace_a_proxy_dependent|pr.trace_b_proxy_dependent]; shared=pr[~pr.trace_a_proxy_dependent&~pr.trace_b_proxy_dependent].copy(); shared['shared_key']=shared.apply(lambda r:hashlib.sha256('|'.join(map(str,[r.video_id,r.query_id,r.budget,r.verified_positive_count,*sorted([r.trace_a_content_hash,r.trace_b_content_hash])])).encode()).hexdigest(),axis=1); shared=shared.drop_duplicates('shared_key')
 metrics=['delta_distinct_events_anchor_assigned','delta_event_coverage_anchor_assigned','delta_event_coverage_overlap_any','delta_C1_F1']
 px=dep.groupby(['video_id','query_id','proxy_id'],as_index=False).agg(exact_pairs=('budget','size'),**{m:(m,'mean') for m in metrics}); sh=shared.groupby(['video_id','query_id'],as_index=False).agg(shared_pairs=('budget','size'),**{'shared_'+m:(m,'mean') for m in metrics}); cl=px.groupby(['video_id','query_id'],as_index=False).agg(proxy_count=('proxy_id','nunique'),**{m:(m,'mean') for m in metrics}).merge(sh,on=['video_id','query_id'],how='outer')
 for m in metrics:cl[m]=[float(np.mean([z for z in (x,y) if pd.notna(z)])) for x,y in zip(cl[m],cl['shared_'+m])]
 src=cl.groupby('video_id',as_index=False).agg(**{m:(m,'mean') for m in metrics}); return px,cl,src,shared
def models(ep):
 audit=pd.read_csv(PROXY)[['trace_instance_id','trace_content_hash','proxy_dependent']]; d=ep.merge(audit,on='trace_instance_id'); d=pd.concat([d[d.proxy_dependent],d[~d.proxy_dependent].drop_duplicates(['video_id','query_id','trace_content_hash'])]); d=d[d.event_coverage_anchor_assigned.notna()]; reps={'YIELD_ONLY':['positive_yield'],'YIELD_PLUS_PUBLIC_GEOMETRY':PUBLIC,'REFERENCE_DIAGNOSTIC':['positive_yield',*PUBLIC[1:],'human_reference_event_count']}; rows=[]
 for split,held,tr,te in [('LOVO',v,d.video_id!=v,d.video_id==v) for v in VIDEOS]+[('LOVQ',f'{v}::{q}',(d.video_id!=v)|(d.query_id!=q),(d.video_id==v)&(d.query_id==q)) for v in VIDEOS for q in QUERIES]:
  for rep,cols in reps.items():
   for name,est in [('linear',LinearRegression()),('ridge',Ridge(alpha=1.)),('depth2_tree',DecisionTreeRegressor(max_depth=2,min_samples_leaf=12,random_state=0))]:
    pipe=Pipeline([('imp',SimpleImputer(strategy='median')),('scale',StandardScaler()),('model',est)]).fit(d.loc[tr,cols],d.loc[tr,'event_coverage_anchor_assigned']); pred=pipe.predict(d.loc[te,cols]); rows.append({'split':split,'heldout':held,'representation':rep,'model':name,'n_train':int(tr.sum()),'n_test':int(te.sum()),'R2':float(r2_score(d.loc[te,'event_coverage_anchor_assigned'],pred)),'MAE':float(mean_absolute_error(d.loc[te,'event_coverage_anchor_assigned'],pred))})
 out=pd.DataFrame(rows); macro=out.groupby(['split','representation','model'],as_index=False).agg(R2=('R2','mean'),MAE=('MAE','mean'),n_train=('n_train','sum'),n_test=('n_test','sum')); macro['heldout']='MACRO_MEAN'; return pd.concat([out,macro[out.columns]])
def main():
 protocol,cases,streams,expected=require_complete(); ref,agree,ags,freeze=build_reference(protocol,cases,streams)
 ep=endpoints(ref); ep.to_csv(OUT/'MATERIALIZER_INDEPENDENT_TRACE_RESULTS.csv',index=False); pr=pair_results(ep); pr.to_csv(OUT/'EQUAL_YIELD_PRIMARY_RESULTS.csv',index=False); px,cl,src,shared=aggregate(pr); px.to_csv(OUT/'CROSS_PROXY_HUMAN_EVENT_EFFECT.csv',index=False); cl.to_csv(OUT/'CLUSTER_PRIMARY_EFFECTS.csv',index=False); src.to_csv(OUT/'SOURCE_VIDEO_EFFECTS.csv',index=False); shared.to_csv(OUT/'SHARED_CONTROL_EFFECTS.csv',index=False)
 mod=models(ep); mod.to_csv(OUT/'HELDOUT_MODELS.csv',index=False); mod[mod.representation=='YIELD_ONLY'].to_csv(OUT/'YIELD_ONLY_MODEL.csv',index=False); mod[mod.representation=='YIELD_PLUS_PUBLIC_GEOMETRY'].to_csv(OUT/'PUBLIC_GEOMETRY_MODEL.csv',index=False); mod[mod.representation=='REFERENCE_DIAGNOSTIC'].to_csv(OUT/'REFERENCE_DIAGNOSTIC_MODEL.csv',index=False); mod[mod.split=='LOVO'].to_csv(OUT/'LOVO_RESULTS.csv',index=False); mod[mod.split=='LOVQ'].to_csv(OUT/'LOVQ_RESULTS.csv',index=False); ep[['trace_instance_id','video_id','query_id','proxy_id','budget','C1_precision','C1_recall','C1_F1','C1_mean_iou']].to_csv(OUT/'C1_SHADOW_RESULTS.csv',index=False)
 macro=mod[(mod.heldout=='MACRO_MEAN')&(mod.model=='ridge')]; val=lambda rep,col:float(macro[(macro.split=='LOVO')&(macro.representation==rep)].iloc[0][col]); y={'R2':val('YIELD_ONLY','R2'),'MAE':val('YIELD_ONLY','MAE')}; g={'R2':val('YIELD_PLUS_PUBLIC_GEOMETRY','R2'),'MAE':val('YIELD_PLUS_PUBLIC_GEOMETRY','MAE')}; posc=int((cl.delta_event_coverage_anchor_assigned>0).sum()); poss=int((src.delta_event_coverage_anchor_assigned>0).sum()); pfx=px.groupby('proxy_id').delta_event_coverage_anchor_assigned.mean().to_dict(); mean=float(cl.delta_event_coverage_anchor_assigned.mean()); anchor_overlap=bool(np.sign(pr.delta_event_coverage_anchor_assigned.mean())==np.sign(pr.delta_event_coverage_overlap_any.mean())); high=mean>0 and posc>=4 and poss>=2 and all(pfx.get(x,0)>0 for x in PROXIES) and g['MAE']<y['MAE'] and anchor_overlap; low=mean<=0 or poss<=1 or any(pfx.get(x,0)<0 for x in PROXIES); potential='HIGH' if high else 'LOW' if low else 'MEDIUM'; c1_pair=float(cl.delta_C1_F1.mean()); c1dep='NOT_C1_DEPENDENT' if mean>0 else ('C1_ONLY' if c1_pair>0 else 'NO_GEOMETRY_SIGNAL')
 parse_counts={a:pd.Series([x['parse_status'] for x in streams[a]]).value_counts().to_dict() for a in ('VLM_A','VLM_B')}; result={'shadow_p1_potential':potential,'shadow_reference_type':'VLM_DIRECT','vlm_annotators':['Qwen3-VL-8B session A','Qwen3-VL-8B independent session/prompt B'],'vlm_agreement':ags,'parse_status_counts':parse_counts,'shadow_events':len(ref),'exact_yield_pairs':len(pr),'primary_mean_delta_event_coverage':mean,'primary_mean_delta_distinct_events':float(cl.delta_distinct_events_anchor_assigned.mean()),'primary_pair_mean_delta_event_coverage':float(pr.delta_event_coverage_anchor_assigned.mean()),'overlap_any_pair_mean_delta_event_coverage':float(pr.delta_event_coverage_overlap_any.mean()),'positive_clusters':posc,'zero_clusters':int((cl.delta_event_coverage_anchor_assigned==0).sum()),'negative_clusters':int((cl.delta_event_coverage_anchor_assigned<0).sum()),'positive_source_videos':poss,'proxy_effects':pfx,'yield_only_lovo':y,'yield_plus_geometry_lovo':g,'geometry_mae_added_value':y['MAE']-g['MAE'],'c1_pair_mean_delta_f1':c1_pair,'c1_dependence':c1dep,'formal_p1_status':'WAITING_HUMAN_REFERENCE','p2_authorized':False,'controller_reopen':False,'claim_boundary':'VLM-direct ontology feasibility only; not human confirmation'}; dump(OUT/'SHADOW_DECISION.json',result)
 (OUT/'FINAL_SHADOW_REPORT.md').write_text(f'''# GVAQP P1 shadow VLM-direct reference result

## Decision

`SHADOW_P1_POTENTIAL = {potential}`

The frozen 198-pair, anchor-assigned analysis gives macro video-query coverage effect `{mean:+.6f}` and distinct-event effect `{result['primary_mean_delta_distinct_events']:+.6f}`. Only `{posc}/6` clusters are positive (`{result['zero_clusters']}` zero, `{result['negative_clusters']}` negative), although `{poss}/3` source-video coverage means are positive. Proxy directions conflict: YOLO `{pfx.get(PROXIES[0],float('nan')):+.6f}`, optical flow `{pfx.get(PROXIES[1],float('nan')):+.6f}`. The exact-pair anchor coverage mean is `{result['primary_pair_mean_delta_event_coverage']:+.6f}` and overlap-any sensitivity is `{result['overlap_any_pair_mean_delta_event_coverage']:+.6f}`.

Yield-only ridge LOVO is R² `{y['R2']:.6f}`, MAE `{y['MAE']:.6f}`; yield+public-geometry is R² `{g['R2']:.6f}`, MAE `{g['MAE']:.6f}`. Geometry improves MAE by only `{result['geometry_mae_added_value']:.6f}`. Frozen C1's matched-pair F1 effect is `{c1_pair:+.6f}`, so the weak primary positive is not a C1-only artifact; C1 does not corroborate it.

## Reference-quality boundary

The final study uses two isolated sessions/prompts of the same Qwen3-VL-8B checkpoint after the cross-family SmolVLM2 and Qwen32 alternatives failed schema/runtime feasibility. A has `{ags['vlm_a_events']}` events, B `{ags['vlm_b_events']}`; global matched-event fraction is `{ags['global_matched_event_fraction_iou_gt_0']:.3f}`. The deterministic unmatched-event union yields `{len(ref)}` shadow events. This low agreement and same-checkpoint dependence are major confounds. Parse failures were retained as empty uncertain windows, never semantically retried.

## Claim boundary

This is evidence of **low success potential under this VLM-direct shadow ontology**, not a formal P1 failure and not human validation. It does not replace independent annotations, change `P1_EVENT_EVIDENCE_GEOMETRY = WAITING_HUMAN_REFERENCE`, authorize P2, support Claim B, or reopen controller work.

```json
{json.dumps(result,indent=2,sort_keys=True)}
```
''')
 state=json.loads((OUT/'SHADOW_STATE.json').read_text()); state.update({'status':'COMPLETE','shadow_reference_frozen':True,'shadow_p1_potential':potential,'formal_p1_status':'WAITING_HUMAN_REFERENCE','p2_authorized':False});dump(OUT/'SHADOW_STATE.json',state); print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
