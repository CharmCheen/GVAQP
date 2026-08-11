#!/usr/bin/env python3
"""Nested static value experiment and frozen Gate for H003 motion preview."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from evaluate_ygs_h002_static import CONFIGS, fit_predict, evaluate, choose, selected_prefix, sha256, atomic_json
from run_mfrp_univariate import score_metrics
from run_mrpo_univariate import geometry_order_scores

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'outputs/multi_fidelity_region_preview_v1'; OUT=ROOT/'outputs/scan_innovation_agentic_loop_v1'; EXP=OUT/'preview_experiments/YGS-H003'

def family(column:str)->str:
    if any(x in column for x in ('selected','pair_count','missingness')): return 'q3_support'
    if any(x in column for x in ('horizontal','vertical','lateral','signed')): return 'q3_direction'
    if any(x in column for x in ('divergence','radial_expansion')): return 'q3_expansion'
    if any(x in column for x in ('center_residual','lower_center')): return 'q3_spatial'
    if 'frame_difference' in column: return 'q3_difference'
    if any(x in column for x in ('residual_magnitude','residual_active')): return 'q3_residual_motion'
    raise KeyError(column)

def select_features(train:pd.DataFrame)->list[str]:
    rows=[]
    for col in [c for c in train if c.startswith('q3__')]:
        values=train[col].to_numpy(float)
        if np.std(values)<=1e-12: continue
        corr=spearmanr(values,train.residual_event_count.to_numpy(float)).statistic; orientation=1 if not np.isfinite(corr) or corr>=0 else -1
        metric=score_metrics(train,orientation*values)
        rows.append({'feature':col,'family':family(col),'recall20':metric['recall_at_20'],'auc':metric['ranking_event_recall_auc']})
    selected=[]
    for _,group in pd.DataFrame(rows).groupby('family',sort=True):
        selected+=group.sort_values(['recall20','auc','feature'],ascending=[False,False,True]).head(2).feature.tolist()
    return sorted(selected)

def main()->None:
    a=EXP/'region_features_run1.parquet'; b=EXP/'region_features_run2.parquet'
    if sha256(a)!=sha256(b): raise AssertionError('Q3 byte determinism failed')
    truth=pd.read_parquet(PARENT/'labels/region_table.parquet'); q1=pd.read_parquet(PARENT/'features/region_features.parquet'); q3=pd.read_parquet(a)
    keys=['video_id','region_id','region_index','start_sec','end_sec','actual_duration_sec']
    data=truth.merge(q1,on=keys,validate='one_to_one').merge(q3,on=keys,how='left',validate='one_to_one')
    q3cols=[c for c in q3 if c.startswith('q3__')]; data[q3cols]=data[q3cols].fillna(0.0); data=data.sort_values(['video_id','region_index']).reset_index(drop=True)
    q1_features=json.loads((PARENT/'experiments/models/nested_feature_selections.json').read_text())
    metric_rows=[]; prediction_rows=[]; fold_features={}
    for test_video in sorted(data.video_id.unique()):
        train=data.query('video_id != @test_video').reset_index(drop=True); test=data.query('video_id == @test_video').reset_index(drop=True)
        q1cols=q1_features[f'test={test_video}|preview=P1_L']['features']; q3selected=select_features(train); columns=q1cols+q3selected
        fold_features[test_video]={'q1':q1cols,'q3':q3selected,'all':columns}
        for config in CONFIGS:
            ts,tp,tc=fit_predict(config,train,train,columns); vs,vp,vc=fit_predict(config,train,test,columns)
            tm=evaluate(train,ts,tp,tc); vm=evaluate(test,vs,vp,vc)
            metric_rows.append({'test_video_id':test_video,'config_id':config['id'].replace('H002','H003'),'family':config['family'],
                                'train_recall20':tm['recall_at_20'],'train_auc':tm['ranking_event_recall_auc'],**{f'test_{k}':v for k,v in vm.items()}})
            cid=config['id'].replace('H002','H003')
            prediction_rows += [{'test_video_id':test_video,'config_id':cid,'region_id':rid,'score':float(s),'binary_probability':float(p),'count_prediction':float(c)}
                                for rid,s,p,c in zip(test.region_id,vs,vp,vc)]
    all_metrics=pd.DataFrame(metric_rows); all_predictions=pd.DataFrame(prediction_rows)
    selections=pd.DataFrame([choose(g).to_dict() for _,g in all_metrics.groupby('test_video_id',sort=True)])
    nested=pd.concat([all_predictions.query('test_video_id == @r.test_video_id and config_id == @r.config_id') for r in selections.itertuples()],ignore_index=True)
    final_rows=[]
    for video_id,frame in data.groupby('video_id',sort=True):
        frame=frame.sort_values('region_index').reset_index(drop=True); chosen=selections.query('test_video_id == @video_id').iloc[0]
        pred=nested.query('test_video_id == @video_id').set_index('region_id').loc[frame.region_id]
        final_rows.append({'video_id':video_id,'selected_config_id':chosen.config_id,'selected_family':chosen.family,
                           **evaluate(frame,pred.score.to_numpy(),pred.binary_probability.to_numpy(),pred.count_prediction.to_numpy())})
    final=pd.DataFrame(final_rows)
    random_mean=pd.read_csv(PARENT/'experiments/controls/B0_RANDOM_COST_MATCHED_100_SEEDS.csv').groupby('video_id').recall_at_20.mean().to_dict()
    p1=pd.read_csv(PARENT/'metrics/nested_branch_per_video_metrics.csv').query("preview == 'P1_L'").set_index('video_id')
    p0=json.loads((PARENT/'preview/p0/inheritance_manifest.json').read_text())['frozen_nested_lovo_recall_at_20']
    controls=pd.read_csv(PARENT/'experiments/controls/static_control_metrics.csv'); time_macro=float(controls[controls.control.str.startswith('B3_TIME_INDEX')].groupby('control').recall_at_20.mean().max())
    shuffled_rows=[]
    for video_id,frame in data.groupby('video_id',sort=True):
        frame=frame.sort_values('region_index').reset_index(drop=True); score=nested.query('test_video_id == @video_id').set_index('region_id').loc[frame.region_id].score.to_numpy()
        shuffled_rows += [{'video_id':video_id,'seed':seed,**score_metrics(frame,np.random.default_rng(seed).permutation(score))} for seed in range(100)]
    shuffled=pd.DataFrame(shuffled_rows); shuffled_mean=shuffled.groupby('video_id').recall_at_20.mean().to_dict()
    parent_cost=json.loads((PARENT/'audits/preview_cost_audit.json').read_text()); q1cost=parent_cost['configs']['P1_L']['conservative_per_video_cost_sec']
    runtime=pd.concat([pd.read_csv(EXP/f'runtime_run{i}.csv') for i in (1,2)]); q3cost=runtime.groupby('video_id').total_wallclock_sec.max().to_dict()
    totalcost={v:float(q1cost[v]+q3cost[v]) for v in q1cost}; ratio=sum(totalcost.values())/float(data.full_scan_cost_sec.sum())
    budget_rows=[]
    for video_id,frame in data.groupby('video_id',sort=True):
        frame=frame.sort_values('region_index').reset_index(drop=True); score=nested.query('test_video_id == @video_id').set_index('region_id').loc[frame.region_id].score.to_numpy(); geometry=geometry_order_scores(frame); full=float(frame.full_scan_cost_sec.sum())
        for bid,total in [('WALLCLOCK_60S',60.0),('FULL_SCAN_COST_20PCT',.2*full),('FULL_SCAN_COST_30PCT',.3*full)]:
            remain=total-totalcost[video_id]
            if remain<0: budget_rows.append({'video_id':video_id,'budget_id':bid,'budget_cell':'INFEASIBLE_PREVIEW_COST','total_budget_sec':total,'preview_cost_sec':totalcost[video_id]}); continue
            ps=selected_prefix(frame,score,remain); cs=selected_prefix(frame,geometry,total); pe=int(frame.iloc[ps].residual_event_count.sum()) if ps else 0; ce=int(frame.iloc[cs].residual_event_count.sum()) if cs else 0
            budget_rows.append({'video_id':video_id,'budget_id':bid,'budget_cell':'FEASIBLE','total_budget_sec':total,'preview_cost_sec':totalcost[video_id],
                                'remaining_scan_budget_sec':remain,'preview_event_count':pe,'coverage_event_count':ce,'delta_event_count':pe-ce})
    budget=pd.DataFrame(budget_rows)
    per_video={}
    for row in final.itertuples():
        per_video[row.video_id]={'recall20_ge_0p40':bool(row.recall_at_20>=.40),'auc_gt_0p55':bool(row.ranking_event_recall_auc>.55),
          'enrichment_gt_1p5':bool(row.recall_at_20/random_mean[row.video_id]>1.5),'beats_p0':bool(row.recall_at_20>p0[row.video_id]+1e-12),
          'beats_p1l':bool(row.recall_at_20>p1.loc[row.video_id].recall_at_20+1e-12),'beats_shuffled':bool(row.recall_at_20>shuffled_mean[row.video_id]+1e-12),
          'leave_best_nonnegative_vs_p1l':bool(row.leave_best_region_out_recall_at_20>=p1.loc[row.video_id].leave_best_region_out_recall_at_20-1e-12),
          'best_region_contribution_lt_0p50':bool(row.best_region_contribution_ratio_at_20<.50)}
    primary=budget.query("budget_id == 'FULL_SCAN_COST_20PCT'")
    common=any(len((x:=budget.query('budget_id == @bid')))==2 and x.budget_cell.eq('FEASIBLE').all() and x.delta_event_count.gt(0).all() for bid in ['WALLCLOCK_60S','FULL_SCAN_COST_20PCT','FULL_SCAN_COST_30PCT'])
    global_checks={'all_per_video_checks':all(all(v.values()) for v in per_video.values()),'beats_time_index_macro':bool(final.recall_at_20.mean()>time_macro),
                   'total_preview_cost_ratio_le_0p10':ratio<=.10,'net_yield_primary_nonnegative_both':bool(primary.budget_cell.eq('FEASIBLE').all() and primary.delta_event_count.ge(0).all()),
                   'one_common_budget_positive_both':common}
    passed=all(global_checks.values())
    all_metrics.to_parquet(EXP/'all_config_nested_metrics.parquet',index=False); all_predictions.to_parquet(EXP/'all_config_nested_predictions.parquet',index=False); nested.to_parquet(EXP/'nested_predictions.parquet',index=False)
    final.to_csv(EXP/'per_video_metrics.csv',index=False); selections.to_csv(EXP/'nested_selected_configs.csv',index=False); shuffled.to_csv(EXP/'shuffled_score_100_seeds.csv',index=False); budget.to_csv(EXP/'net_event_yield_budget_grid.csv',index=False); atomic_json(EXP/'nested_feature_selections.json',fold_features)
    result={'hypothesis_id':'YGS-H003','status':'ACCEPTED' if passed else 'REJECTED','static_observability_gate_pass':passed,'per_video_checks':per_video,'global_checks':global_checks,
            'metrics':final.to_dict('records'),'q1_costs_sec':q1cost,'q3_costs_sec':q3cost,'combined_preview_costs_sec':totalcost,'combined_preview_cost_ratio':ratio,
            'shuffled_mean_recall20':shuffled_mean,'random_mean_recall20':random_mean,'time_index_macro_recall20':time_macro,'implementation_hash':sha256(Path(__file__)),
            'contract_hash':sha256(OUT/'contracts/YGS-H003.json'),'decision':'ALLOW_ONE_STEP_SCHEDULER' if passed else 'PROHIBIT_SCHEDULER_AND_FREEZE_SAFE_COVERAGE'}
    atomic_json(OUT/'hypotheses/YGS-H003.json',result); atomic_json(EXP/'static_gate.json',result); print((OUT/'hypotheses/YGS-H003.json').read_text(),end='')

if __name__=='__main__': main()
