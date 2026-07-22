#!/usr/bin/env python3
"""Zero-VLM risk-limiting provisional-prune simulation."""
import hashlib,heapq,json,math,random
from collections import defaultdict
from pathlib import Path
import numpy as np,pandas as pd
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'DARE_AQP_Experiment_v1').is_dir())
OUT=ROOT/'DARE_AQP_Experiment_v1/outputs/risk_limiting_interval_pruning_feasibility_v1'
U=pd.read_csv(ROOT/'Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict/frozen_inputs/units.csv')
E=pd.read_csv(ROOT/'Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict/frozen_inputs/event_reference.csv')
P=pd.read_csv(ROOT/'Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict/benchmark/adapter_units.csv')
N=347; TARGET=.8; DELTA=.05; SEEDS=500
anchors=[]; support={}
for r in E.itertuples():
 m=U[(U.start_time<=r.canonical_anchor_time)&(U.end_time>r.canonical_anchor_time)]; a=int(m.iloc[0].unit_id);anchors.append(a);support[a]=len(str(r.source_unit_ids).split('|'))
A=set(anchors); proxy=dict(zip(P.frame_idx.astype(int),P.proxy_score.astype(float)))
prefix=[0]
for i in range(N):prefix.append(prefix[-1]+int(i in A))
def cnt(x):return prefix[x[1]]-prefix[x[0]]
def split(x):lo,hi=x;m=lo+(hi-lo)//2;return (lo,m),(m,hi)
def pri(x):lo,hi=x;v=[proxy[i] for i in range(lo,hi)];return(max(v),sum(v)/len(v),-(hi-lo),-lo)
nodes=[];stack=[(0,N)]
while stack:
 x=stack.pop()
 if x[1]-x[0]<=1:continue
 for y in split(x):nodes.append(y);stack.append(y)
pos=[x for x in nodes if cnt(x)>0];neg=[x for x in nodes if cnt(x)==0]
def bscore(x):
 aa=[a for a in anchors if x[0]<=a<x[1]];return max([0]+[1/(1+min(a-x[0],x[1]-1-a)) for a in aa])
def lscore(x):return max([0]+[support[a] for a in anchors if x[0]<=a<x[1]])

def deterministic_sets(sens,spec,unk,placement):
 nf=round((1-sens)*len(pos)); npu=round(sens*unk*len(pos)); nnu=round((unk+(1-unk)*(1-spec))*len(neg))
 if placement=='boundary': order=sorted(pos,key=lambda x:(bscore(x),cnt(x),x[1]-x[0]),reverse=True)
 elif placement=='multi_event':order=sorted(pos,key=lambda x:(cnt(x),x[1]-x[0]),reverse=True)
 elif placement=='long_event':order=sorted(pos,key=lambda x:(lscore(x),cnt(x),x[1]-x[0]),reverse=True)
 elif placement=='low_proxy':order=sorted(pos,key=lambda x:(pri(x)[1],-cnt(x)))
 elif placement=='correlated_sibling':order=sorted(pos,key=lambda x:(x[0]//max(1,x[1]-x[0]),cnt(x)),reverse=True)
 elif placement=='correlated_level':order=sorted(pos,key=lambda x:(x[1]-x[0],cnt(x)),reverse=True)
 else:order=sorted(pos,key=lambda x:(cnt(x),x[1]-x[0]),reverse=True)
 fn=set(order[:nf]); unknown=set(order[nf:nf+npu]); unneg=set(sorted(neg,key=lambda x:x[1]-x[0],reverse=True)[:nnu])
 return fn,unknown,unneg

def outcome(sens,spec,unk,placement,seed):
 if placement!='independent':fn,up,un=deterministic_sets(sens,spec,unk,placement)
 else:fn=up=un=None;rng=random.Random(918273+seed)
 pruned=[];queried=[(0,N)];found=set();heap=[]
 def push(x):
  if x[1]-x[0]==1:
   if x[0] in A:found.add(x[0])
  else:
   p=pri(x);heapq.heappush(heap,(tuple(-z for z in p),x))
 push((0,N))
 while heap:
  _,x=heapq.heappop(heap)
  for y in split(x):
   queried.append(y);c=cnt(y)
   if placement=='independent':
    z=rng.random()
    if c and z<1-sens:state='NEG'
    elif c and z<1-sens+sens*unk:state='UNK'
    elif c:state='POS'
    elif z<unk:state='UNK'
    elif z<unk+(1-unk)*spec:state='NEG'
    else:state='POS'
   else:
    state='NEG' if y in fn or (c==0 and y not in un) else 'UNK' if y in up or (c==0 and y in un) else 'POS'
   if state=='NEG':pruned.append(y)
   else:push(y)
 return queried,pruned,found

def serfling_total(values,n,sample,delta):
 Np=len(values)
 if Np==0:return 0.0
 if n==0:return float(sum(x[1]-x[0] for x in values))
 if n==Np:return float(sum(sample))
 b=max(x[1]-x[0] for x in values);mean=float(np.mean(sample))
 radius=b*math.sqrt((1-(n-1)/Np)*math.log(1/delta)/(2*n))
 return min(float(sum(x[1]-x[0] for x in values)),Np*(mean+radius))

def audits(pruned,variant,seed):
 rng=random.Random(77123+seed);Np=len(pruned)
 if Np==0:return {f:([],[],0.0,0.0) for f in fracs}
 if variant=='B2_SRS':
  order=list(range(Np));rng.shuffle(order);out={}
  for frac in fracs:
   n=min(Np,math.ceil(frac*Np));idx=order[:n];vals=[cnt(pruned[i]) for i in idx]
   out[frac]=(idx,vals,serfling_total(pruned,n,vals,DELTA),(Np/n)*sum(vals) if n else 0.0)
  return out
 # Frozen strata: length bucket x public-score median; Bonferroni Serfling.
 scores=[pri(x)[1] for x in pruned];med=float(np.median(scores));groups=defaultdict(list)
 for i,x in enumerate(pruned):
  L=x[1]-x[0];lb='S' if L<=2 else 'M' if L<=8 else 'L';groups[(lb,scores[i]>=med)].append(i)
 for ids in groups.values():rng.shuffle(ids)
 out={};H=len(groups)
 for frac in fracs:
  idx=[];vals=[];upper=0.0;ht=0.0
  for ids in groups.values():
   n=min(len(ids),math.ceil(frac*len(ids)));take=ids[:n];sv=[cnt(pruned[i]) for i in take]
   idx+=take;vals+=sv;upper+=serfling_total([pruned[i] for i in ids],n,sv,DELTA/H);ht+=(len(ids)/n)*sum(sv) if n else 0.0
  out[frac]=(idx,vals,upper,ht)
 return out

sens_grid=[.8,.85,.9,.95,.97,.99,1.0];spec_grid=[.8,.85,.9,.95,.97,.99,1.0];unk_grid=[0,.05,.1,.2];fracs=[0,.05,.1,.2,.3,.4,.5,.7,1.0]
placements=['independent','boundary','multi_event','long_event','low_proxy','adversarial','correlated_sibling','correlated_level']
costs=[('constant',1.0),('alpha_0.95',.95)]
rows=[];placement_diag=[]
for sens in sens_grid:
 for spec in spec_grid:
  for unk in unk_grid:
   for placement in placements:
    acc=defaultdict(lambda:defaultdict(list))
    outcome_seeds=range(SEEDS) if placement=='independent' else [0]
    outs=[outcome(sens,spec,unk,placement,s) for s in outcome_seeds]
    if placement!='independent':outs=outs*SEEDS
    for seed,(queried,pruned,found0) in enumerate(outs):
     actual_total=sum(cnt(x) for x in pruned)
     interval_costs={cname:sum(alpha+(1-alpha)*(x[1]-x[0]) for x in queried) for cname,alpha in costs}
     for variant in ['B2_SRS','B3_STRATIFIED']:
      audit_results=audits(pruned,variant,seed)
      # One frozen random permutation per seed; fractions are nested only in expectation.
      for frac in fracs:
       idx,vals,utotal,ht=audit_results[frac]
       sampled=sum(vals);actual_remaining=actual_total-sampled
       urem=max(0.0,utotal-sampled);D=len(found0)+sampled
       recall=D/26;f1=2*recall/(1+recall) if recall else 0;rlb=D/(D+urem) if D+urem else 1
       audited_units=sum(pruned[i][1]-pruned[i][0] for i in idx)
       for cname,alpha in costs:
        interval_cost=interval_costs[cname]
        total=interval_cost+len(found0)+audited_units
        key=(variant,frac,cname,alpha)
        a=acc[key];a['bias'].append(ht-actual_total)
        a['covered'].append(urem+1e-12>=actual_remaining);a['bound_width'].append(urem)
        a['cost'].append(total);a['recall'].append(recall);a['f1'].append(f1);a['rlb'].append(rlb)
        a['certified'].append(rlb>=TARGET);a['audit_units'].append(audited_units);a['pruned_blocks'].append(len(pruned))
    if placement!='independent':
     q,p,f=outs[0];placement_diag.append({'sensitivity':sens,'specificity':spec,'unknown_rate':unk,'placement':placement,
       'interval_queries':len(q),'pruned_blocks':len(p),'events_found_before_audit':len(f),'events_in_pruned_blocks':sum(cnt(x) for x in p)})
    for key,a in acc.items():
     variant,frac,cname,alpha=key
     rows.append({'sensitivity':sens,'specificity':spec,'unknown_rate':unk,'placement':placement,'variant':variant,
      'audit_fraction':frac,'cost_family':cname,'fixed_fraction':alpha,'seeds':len(a['cost']),
      'ht_bias_mean':float(np.mean(a['bias'])),'ht_error_variance':float(np.var(a['bias'],ddof=1)),
      'empirical_coverage':float(np.mean(a['covered'])),'failure_probability':1-float(np.mean(a['covered'])),'bound_width_mean':float(np.mean(a['bound_width'])),
      'audit_unit_cost_mean':float(np.mean(a['audit_units'])),'total_cost_mean':float(np.mean(a['cost'])),'total_cost_p95':float(np.quantile(a['cost'],.95)),
      'dense_ratio_mean':float(np.mean(a['cost'])/347),'event_recall_mean':float(np.mean(a['recall'])),'event_recall_p05':float(np.quantile(a['recall'],.05)),
      'event_f1_mean':float(np.mean(a['f1'])),'recall_lb_mean':float(np.mean(a['rlb'])),'certify_rate':float(np.mean(a['certified'])),
      'coverage_pass':float(np.mean(a['covered']))>=.94,'recall_pass':float(np.quantile(a['recall'],.05))>=.8,
      'cost_pass':float(np.quantile(a['cost'],.95))/347<.7})
for r in rows:r['joint_pass']=r['coverage_pass'] and r['recall_pass'] and r['cost_pass'] and r['certify_rate']>=.9
for d in ['simulations','estimators','cost','feasible_region','diagnostics']:(OUT/d).mkdir(parents=True,exist_ok=True)
df=pd.DataFrame(rows);df.to_csv(OUT/'simulations/RISK_LIMITING_GRID.csv',index=False)
df[['variant','placement','sensitivity','specificity','unknown_rate','audit_fraction','ht_bias_mean','ht_error_variance','empirical_coverage','failure_probability','bound_width_mean','certify_rate']].to_csv(OUT/'estimators/ESTIMATOR_RESULTS.csv',index=False)
df[['variant','placement','sensitivity','specificity','unknown_rate','audit_fraction','cost_family','total_cost_mean','total_cost_p95','dense_ratio_mean','audit_unit_cost_mean','cost_pass']].to_csv(OUT/'cost/COST_GRID.csv',index=False)
df[df.joint_pass].to_csv(OUT/'feasible_region/RANDOM_FEASIBLE_REGION.csv',index=False)
# Robust means same config passes every required placement.
rob=[]
for keys,g in df.groupby(['sensitivity','specificity','unknown_rate','variant','audit_fraction','cost_family','fixed_fraction']):
 rob.append(dict(zip(['sensitivity','specificity','unknown_rate','variant','audit_fraction','cost_family','fixed_fraction'],keys))|
  {'placements_passed':int(g.joint_pass.sum()),'placements_required':len(placements),'robust_feasible':bool(g.joint_pass.all()),
   'worst_cost_p95':float(g.total_cost_p95.max()),'worst_recall_p05':float(g.event_recall_p05.min()),'worst_coverage':float(g.empirical_coverage.min())})
pd.DataFrame(rob).to_csv(OUT/'feasible_region/ROBUST_FEASIBLE_REGION.csv',index=False)
pd.DataFrame(placement_diag).to_csv(OUT/'diagnostics/ERROR_PLACEMENT_SUMMARY.csv',index=False)
pd.DataFrame([{'variant':'B0_DENSE','cost':347,'dense_ratio':1.0,'eligible':True},
 {'variant':'B1_HARD_ANY','cost':'grid','dense_ratio':'grid','eligible':False},
 {'variant':'B2_SRS','cost':'grid','dense_ratio':'grid','eligible':True},
 {'variant':'B3_STRATIFIED','cost':'grid','dense_ratio':'grid','eligible':True},
 {'variant':'B4_DUAL_COVER','cost':'NOT_RUN','dense_ratio':'NOT_RUN','eligible':False},
 {'variant':'B5_EXACT_ANY','cost':243,'dense_ratio':243/347,'eligible':False}]).to_csv(OUT/'simulations/VARIANT_SUMMARY.csv',index=False)
print(OUT,len(df))
