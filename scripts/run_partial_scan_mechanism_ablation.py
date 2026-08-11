#!/usr/bin/env python3
"""M0--M9 development-only ablation for geometric guarded marginal scan."""
from __future__ import annotations
import json, math
from pathlib import Path
import sys
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"scripts"))
from partial_scan_pilot_common import atomic_csv, atomic_json, atomic_text, transition  # noqa: E402
IMM=ROOT/"benchmarks/partial_scan_pilot_v1/immutable"; DER=ROOT/"benchmarks/partial_scan_pilot_v1/derived"
DEV=ROOT/"outputs/partial_scan_method_development_v1"; OUT=DEV/"mechanism_ablation"
BUDGET=60.; METHODS=[f"M{i}" for i in range(10)]

def event_map():
    table=pd.read_parquet(DER/"candidate_event_map.parquet"); table=table[table.partition_offset_sec.eq(0)]
    out={}
    for r in table.itertuples(index=False):
        for u in json.loads(r.source_unit_ids): out.setdefault(u,set()).add(r.reference_event_id)
    return out

def features():
    raw=pd.read_csv(DEV/"temporal_cost_audit/unit_observation_features.csv")
    cand=pd.concat([pd.read_parquet(p) for p in sorted((DER/"visible_subset_candidates").glob("*_offset0_full.parquet"))])
    agg=cand.groupby("unit_id").agg(candidate_count=("candidate_id","size"),candidate_score=("candidate_score","sum"),candidate_mid=("candidate_start_sec",lambda x:float(np.mean(x)))).reset_index()
    return raw.merge(agg,on="unit_id",how="left").fillna({"candidate_count":0,"candidate_score":0,"candidate_mid":-1})

def cost(previous, selected, model):
    tr=transition(previous,selected); key=f"{tr['transition_class']}|{tr['same_or_cross_gop']}|CONTROLLED_WARM"
    return float(model["strata"].get(key,{}).get("q90_action_cost_sec",model["fallback_q90_sec"]))

def lg(remaining, scanned, ix):
    if not scanned:return remaining[len(remaining)//2]
    return max(remaining,key=lambda u:(min(abs(ix[u]-ix[s]) for s in scanned),-ix[u]))

def choose(level, units, scanned, previous, remaining_budget, model):
    ix=dict(zip(units.unit_id,units.unit_index)); by=dict((r.unit_id,r) for r in units.itertuples(index=False)); remaining=[str(x) for x in units.unit_id if x not in scanned]
    previous_unit = None if previous is None else str(previous["unit_id"])
    base=lg(remaining,scanned,ix)
    if level==0:return base,"largest_gap"
    # M1: one fixed adjacent refinement after an active observation.
    if previous_unit and by[previous_unit].candidate_count>0:
        neighbors=[u for u in remaining if abs(ix[u]-ix[previous_unit])==1]
        if neighbors:
            if level==1:return min(neighbors,key=lambda u:ix[u]),"fixed_adjacency"
            # M2 directs refinement toward the side containing candidate midpoint.
            prev=by[previous_unit]; direction=1 if prev.candidate_mid>=prev.start_sec+5 else -1
            directed=[u for u in neighbors if ix[u]-ix[previous_unit]==direction]
            local=directed or neighbors
            if level==2:return local[0],"directional_refinement"
            # M3 continues to the first legal local candidate neighbor.
            legal=[u for u in local if by[u].candidate_count>0]
            if level==3 and legal:return legal[0],"first_legal_completion"
            # M4 exits duplicate/empty local scans; candidate score supplies novelty proxy.
            novel=[u for u in local if by[u].candidate_score>0 and by[u].candidate_count>=1]
            if level>=4 and novel:
                candidate=novel[0]
            else: candidate=None
            if candidate and level==4:return candidate,"duplicate_novelty_exit"
            # M5 prefers locally active macro regions (8-unit observable-mass windows).
            if level>=5:
                macro={u:sum(by[v].candidate_score for v in remaining if abs(ix[v]-ix[u])<=4) for u in remaining}
                active=max(remaining,key=lambda u:(macro[u],-ix[u]))
                candidate = candidate if candidate and macro[candidate]>=0.75*macro[active] else active
                if level==5:return candidate,"macro_activity_shrinkage"
                # M6 normalizes observable marginal score by frozen transition cost.
                scored=[]
                for u in remaining:
                    c=cost(previous,by[u]._asdict(),model)
                    dispersion=min(abs(ix[u]-ix[s]) for s in scanned) if scanned else len(units)/2
                    scored.append(((by[u].candidate_score+0.25*dispersion)/c,u))
                candidate=max(scored)[1]
                if level==6:return candidate,"path_cost_normalization"
                # M7 enforces at least 80% of M0's immediate geometric dispersion.
                base_gap=min(abs(ix[base]-ix[s]) for s in scanned) if scanned else len(units)/2
                safe=[u for _,u in scored if (min(abs(ix[u]-ix[s]) for s in scanned) if scanned else len(units)/2)>=.8*base_gap]
                candidate=max(((by[u].candidate_score+0.25*(min(abs(ix[u]-ix[s]) for s in scanned) if scanned else len(units)/2))/cost(previous,by[u]._asdict(),model),u) for u in (safe or [base]))[1]
                if level==7:return candidate,"geometric_guard"
                # M8 keeps a conservative fallback action recoverable after admission.
                c=cost(previous,by[candidate]._asdict(),model); fallback=float(model["fallback_q90_sec"])
                if remaining_budget-c < fallback: candidate=base
                if level==8:return candidate,"recoverability_guard"
                # M9 adds a local P0 trigger bonus only inside the M7 safe set,
                # then reapplies M8 recoverability rather than bypassing either guard.
                candidate=max(safe or [base],key=lambda u:((by[u].candidate_score+0.4*by[u].trigger_count+0.25*(min(abs(ix[u]-ix[s]) for s in scanned) if scanned else len(units)/2))/cost(previous,by[u]._asdict(),model)))
                if remaining_budget-cost(previous,by[candidate]._asdict(),model) < fallback:
                    candidate=base
                return candidate,"optional_local_p0_trigger"
    return base,"largest_gap_fallback"

def run(level, video, units, fmap, model):
    scanned=[]; exposed=set(); prior=None; elapsed=0.; rows=[]; all_events=set().union(*(fmap.get(u,set()) for u in units.unit_id))
    while len(scanned)<len(units):
        u,reason=choose(level,units,scanned,prior, BUDGET-elapsed,model); sel=units[units.unit_id.eq(u)].iloc[0].to_dict(); c=cost(prior,sel,model)
        if elapsed+c>BUDGET:break
        new=fmap.get(u,set())-exposed; exposed|=fmap.get(u,set()); scanned.append(u); elapsed+=c
        idx=units.set_index("unit_id").unit_index; scanned_ix=np.array([idx[x] for x in scanned]); all_ix=units.unit_index.to_numpy()
        rows.append({"video_id":video,"method":f"M{level}","action_index":len(scanned),"unit_id":u,"selection_reason":reason,"estimated_action_cost_sec":c,"cumulative_scan_time_sec":elapsed,"new_exposed_event_count":len(new),"exposed_event_count":len(exposed),"event_exposure_fraction":len(exposed)/max(1,len(all_events)),"max_unscanned_gap_units":max(np.diff(np.sort(scanned_ix)).max(initial=0)-1,int(all_ix.max()-scanned_ix.max())),"nearest_scan_distance":float(np.abs(all_ix[:,None]-scanned_ix[None,:]).min(axis=1).mean())})
        prior=sel
    return rows

def main():
    timeline=pd.read_csv(IMM/"timeline_units.csv"); feat=features(); timeline=timeline.merge(feat[["unit_id","candidate_count","candidate_score","candidate_mid","trigger_count"]],on="unit_id",how="left").fillna(0)
    model=json.loads((DER/"cost_calibration/conservative_cost_model.json").read_text()); fmap=event_map(); rows=[]
    for video,units in timeline.groupby("video_id"):
        units=units.sort_values("unit_index")
        for level in range(10):rows+=run(level,video,units,fmap,model)
    trace=pd.DataFrame(rows); OUT.mkdir(parents=True,exist_ok=True); atomic_csv(OUT/"ablation_action_trace.csv",trace)
    summary=trace.groupby(["video_id","method"]).agg(actions=("action_index","max"),exposure_scan_time_auc=("event_exposure_fraction",lambda x:float(np.trapezoid(x,trace.loc[x.index,"cumulative_scan_time_sec"]))),exposure_end=("event_exposure_fraction","last"),new_events=("new_exposed_event_count","sum"),max_gap=("max_unscanned_gap_units","last"),nearest_distance=("nearest_scan_distance","last"),wallclock=("cumulative_scan_time_sec","last")).reset_index(); atomic_csv(OUT/"ablation_summary.csv",summary)
    delta=summary.pivot(index="method",columns="video_id",values="exposure_scan_time_auc"); atomic_csv(OUT/"ablation_auc_by_video.csv",delta.reset_index())
    atomic_json(OUT/"ablation_manifest.json",{"scope":"DEVELOPMENT_ONLY","sequence":{"M0":"Anytime Largest-Gap","M1":"fixed adjacency refinement","M2":"directional refinement","M3":"first legal candidate completion","M4":"duplicate/novelty exit","M5":"macro-region activity shrinkage","M6":"path-cost normalization","M7":"geometric coverage guard","M8":"recoverability guard","M9":"optional local P0 trigger"},"formal_ranking":"BLOCKED_PENDING_EXTERNAL_RUNTIME_ATTESTATION"})
    atomic_text(OUT/"MECHANISM_ABLATION_REPORT.md","# M0--M9 development mechanism ablation\n\nAll outcomes are relative to the frozen pseudo-reference and for development only. Each M level adds exactly the listed rule to its predecessor; no RL, Bandit, SMDP, or CONFIRM is used.\n")
if __name__=="__main__":main()
