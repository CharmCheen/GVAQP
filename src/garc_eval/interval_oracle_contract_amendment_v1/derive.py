#!/usr/bin/env python3
"""Reference-only synthetic ANY error injection; never loads a VLM or response."""

import csv, hashlib, heapq, math, random
from pathlib import Path
import pandas as pd

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "DARE_AQP_Experiment_v1").is_dir())
OUT = ROOT / "DARE_AQP_Experiment_v1/outputs/gate_c0_interval_contract_amendment_v1"
UNITS = ROOT / "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict/frozen_inputs/units.csv"
EVENTS = ROOT / "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict/frozen_inputs/event_reference.csv"
PROXY = ROOT / "Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2_strict/benchmark/adapter_units.csv"
N, TARGET, DENSE = 347, 21, 347.0

units, events, proxy_df = pd.read_csv(UNITS), pd.read_csv(EVENTS), pd.read_csv(PROXY)
anchors=[]
for r in events.itertuples():
    m=units[(units.start_time <= r.canonical_anchor_time) & (units.end_time > r.canonical_anchor_time)]
    anchors.append(int(m.iloc[0].unit_id))
anchor_set=set(anchors); proxy=dict(zip(proxy_df.frame_idx.astype(int),proxy_df.proxy_score.astype(float)))
prefix=[0]
for i in range(N): prefix.append(prefix[-1]+int(i in anchor_set))
def count(lo,hi): return prefix[hi]-prefix[lo]
def split(lo,hi):
    m=lo+(hi-lo)//2; return (lo,m),(m,hi)
def priority(lo,hi):
    v=[proxy[i] for i in range(lo,hi)]; return (max(v),sum(v)/len(v),-(hi-lo),-lo)

# All binary-tree children eligible for ANY; used to freeze adversarial placement.
nodes=[]; stack=[(0,N)]
while stack:
    lo,hi=stack.pop()
    if hi-lo<=1: continue
    for child in split(lo,hi):
        nodes.append(child)
        if child[1]-child[0]>1: stack.append(child)
positive=[x for x in nodes if count(*x)>0]; negative=[x for x in nodes if count(*x)==0]
def boundary_score(x):
    lo,hi=x; a=[z for z in anchors if lo<=z<hi]
    return max([count(lo,hi)*1000]+[100-max(z-lo,hi-1-z) for z in a])

def chosen_sets(sens,spec,unknown,placement,seed):
    eff_spec=spec*(1-unknown)
    nf=round((1-sens)*len(positive)); nu=round((1-eff_spec)*len(negative))
    if placement=="independent":
        rng=random.Random(seed); fn=set(rng.sample(positive,min(nf,len(positive)))); un=set(rng.sample(negative,min(nu,len(negative))))
    elif placement=="adversarial_multi":
        fn=set(sorted(positive,key=lambda x:(count(*x),x[1]-x[0]),reverse=True)[:nf]); un=set(sorted(negative,key=lambda x:x[1]-x[0],reverse=True)[:nu])
    else:
        fn=set(sorted(positive,key=boundary_score,reverse=True)[:nf]); un=set(sorted(negative,key=lambda x:x[1]-x[0],reverse=True)[:nu])
    return fn,un

def replay(sens,spec,unknown,placement,seed,alpha):
    fn,un=chosen_sets(sens,spec,unknown,placement,seed)
    found=set(); heap=[]; queried=[]; false_pruned=0
    def push(x):
        lo,hi=x
        if hi-lo==1:
            if lo in anchor_set: found.add(lo)
            return
        p=priority(lo,hi); heapq.heappush(heap,(tuple(-v for v in p),lo,hi))
    push((0,N))
    while len(found)<TARGET and heap:
        _,lo,hi=heapq.heappop(heap)
        for child in split(lo,hi):
            queried.append(child); c=count(*child)
            if c>0 and child in fn:
                false_pruned += c
            elif c==0 and child not in un:
                pass
            else: push(child)
    calls=1+len(queried) # frozen root COUNT plus ANY children
    cost=1.25*(alpha+(1-alpha)*N)+sum(alpha+(1-alpha)*(hi-lo) for lo,hi in queried)+len(found)
    return {"events_found":len(found),"event_recall":len(found)/26,"event_f1":2*len(found)/(len(found)+26),
            "logical_interval_calls":calls,"certifications":len(found),"total_cost":cost,"dense_ratio":cost/DENSE,
            "false_pruned_event_multiplicity":false_pruned,"fallback_extra_calls":len(un),"pass_recall":len(found)/26>=.8,
            "pass_cost":cost/DENSE<.7,"joint_pass":len(found)/26>=.8 and cost/DENSE<.7}

sens_grid=[.8,.85,.9,.925,.95,.975,.99,1.0]; spec_grid=[.8,.9,.95,.975,.99,1.0]; unknown_grid=[0,.05,.1,.2]
rows=[]
for sens in sens_grid:
 for spec in spec_grid:
  for unknown in unknown_grid:
   for placement in ["independent","adversarial_multi","adversarial_boundary"]:
    seeds=range(25) if placement=="independent" else [0]
    for alpha,label in [(1.0,"registered_constant_optimistic"),(.95,"registered_grid_0.95")]:
     values=[replay(sens,spec,unknown,placement,s,alpha) for s in seeds]
     row={"effective_sensitivity":sens,"effective_specificity":spec,"unknown_rate":unknown,
          "placement":placement,"cost_assumption":label,"fixed_fraction":alpha,"replicates":len(values)}
     lower_worse={"events_found","event_recall","event_f1","pass_recall","pass_cost","joint_pass"}
     upper_worse={"logical_interval_calls","certifications","total_cost","dense_ratio","false_pruned_event_multiplicity","fallback_extra_calls"}
     for k in lower_worse: row[k+"_worst"]=min(v[k] for v in values)
     for k in upper_worse: row[k+"_worst"]=max(v[k] for v in values)
     row["joint_pass_all_replicates"]=all(v["joint_pass"] for v in values)
     rows.append(row)
OUT.joinpath("derivation").mkdir(parents=True,exist_ok=True)
pd.DataFrame(rows).to_csv(OUT/"derivation/ANY_ERROR_INJECTION_GRID.csv",index=False)

# Conservative region: all three placements pass under a cost assumption.
d=pd.DataFrame(rows)
region=[]
for keys,g in d.groupby(["effective_sensitivity","effective_specificity","unknown_rate","cost_assumption","fixed_fraction"]):
    region.append(dict(zip(["effective_sensitivity","effective_specificity","unknown_rate","cost_assumption","fixed_fraction"],keys)) |
                  {"all_placements_pass":bool(g.joint_pass_all_replicates.all()),
                   "worst_event_recall":float(g.event_recall_worst.min()),"worst_dense_ratio":float(g.dense_ratio_worst.max()),
                   "worst_false_pruned_event_multiplicity":int(g.false_pruned_event_multiplicity_worst.max())})
pd.DataFrame(region).to_csv(OUT/"derivation/ANY_FEASIBLE_REGION.csv",index=False)

# COUNT priority-only synthetic usefulness table. It never changes recall; a
# conservative inversion penalty maps errors to lost ordering benefit.
count_rows=[]
for exact in [.5,.7,.8,.9,.95,1.0]:
 for mae in [0,.25,.5,1,2]:
  for under in [0,.05,.1,.2,.4]:
   for unknown in [0,.1,.2]:
    inversion=min(1.0,(1-exact)+mae/4+under+unknown/2)
    # Interpolate from perfect count-guided 85 calls to safe ANY 201 calls.
    calls=85+116*inversion; cost=1.25*calls+21
    count_rows.append({"exact_count_accuracy":exact,"mae":mae,"undercount_rate":under,"unknown_count_rate":unknown,
      "adversarial_inversion_index":inversion,"event_recall":21/26,"calls_equivalent":calls,"constant_cost":cost,
      "dense_ratio":cost/347,"improves_over_any_only":calls<201,"joint_pass":21/26>=.8 and cost/347<.7})
pd.DataFrame(count_rows).to_csv(OUT/"derivation/COUNT_ERROR_INJECTION_GRID.csv",index=False)
pd.DataFrame([r for r in count_rows if r["joint_pass"]]).to_csv(OUT/"derivation/COUNT_FEASIBLE_REGION.csv",index=False)
print(OUT)
