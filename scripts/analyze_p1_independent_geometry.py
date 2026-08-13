#!/usr/bin/env python3
"""Fail-closed primary P1 analysis against adjudicated human temporal events."""
from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from garc_eval.accelerated_event_query.matching import MatchConfig, match_events, summarize_matches
from garc_eval.accelerated_event_query.types import EventRecord
OUT = ROOT / "outputs/gvaqp_long_horizon_p1_p3_v1"
PROTOCOL = OUT / "P1_ANALYSIS_PROTOCOL.json"
TRACE = OUT / "P1_OUTCOME_BLIND_TRACE_MANIFEST.csv"
HUMAN = OUT / "human_reference_package"
HUMAN_REF = HUMAN / "P1_HUMAN_EVENT_REFERENCE.parquet"
HUMAN_MANIFEST = HUMAN / "P1_HUMAN_REFERENCE_MANIFEST.json"
QWEN = OUT / "qwen32_oracle"
QWEN_TABLE = QWEN / "P1_QWEN32_UNIT_OUTCOMES.parquet"
QWEN_COMPLETE = QWEN / "P1_QWEN32_ORACLE_COMPLETION.json"
V10 = ROOT / "outputs/v10_multiseal_reference_v1/FINAL_UNIT_REFERENCE.parquet"
P1_PROTOCOL = OUT / "P1_PROTOCOL.json"
IMPLEMENTATION = OUT / "P1_ANALYSIS_IMPLEMENTATION_MANIFEST.json"
VIDEOS = ("DALI", "HANGZHOU", "WUHAN")
Q1 = "Q_DRIVER_RESPONSE_V1"
Q2 = "Q_VULNERABLE_ROAD_USER_CONFLICT_V1"
MATCH_COLUMNS = ["video_id", "query_id", "proxy_family", "budget", "verified_positive_count", "traces_in_stratum", "geometry_high", "geometry_low", "geometry_delta", "trace_high", "trace_low", "delta_distinct_human_events_touched", "delta_human_event_coverage", "delta_human_events_with_zero_evidence", "delta_HumanEventRecall_C1", "delta_HumanEventF1_C1"]


def sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""):h.update(b)
    return h.hexdigest()


def require_complete() -> tuple[dict, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    p=json.loads(PROTOCOL.read_text())
    if p["status"] != "FROZEN_BEFORE_SECOND_QUERY_OUTCOMES_AND_HUMAN_REFERENCE": raise RuntimeError("unexpected P1 analysis protocol status")
    for path in (TRACE, HUMAN_REF, HUMAN_MANIFEST, QWEN_TABLE, QWEN_COMPLETE, IMPLEMENTATION):
        if not path.exists(): raise RuntimeError(f"required P1 input unavailable: {path}")
    implementation=json.loads(IMPLEMENTATION.read_text())
    if implementation.get("status") != "FROZEN_BEFORE_SECOND_QUERY_OUTCOMES_AND_HUMAN_REFERENCE": raise RuntimeError("P1 analysis implementation manifest is not frozen")
    for relative,expected_hash in implementation.get("files",{}).items():
        actual=ROOT/relative
        if not actual.exists() or sha(actual) != expected_hash: raise RuntimeError(f"P1 analysis implementation changed after freeze: {relative}")
    if implementation.get("analysis_protocol_sha256") != sha(PROTOCOL) or implementation.get("p1_protocol_sha256") != sha(P1_PROTOCOL): raise RuntimeError("P1 protocol changed after analysis implementation freeze")
    qcomplete=json.loads(QWEN_COMPLETE.read_text())
    if qcomplete.get("status") != "COMPLETE" or qcomplete.get("units") != 1475 or qcomplete.get("table_sha256") != sha(QWEN_TABLE): raise RuntimeError("second-query Qwen table is not complete/verified")
    hmanifest=json.loads(HUMAN_MANIFEST.read_text())
    if hmanifest.get("status") != "FROZEN_COMPLETE_ADJUDICATED_HUMAN_REFERENCE" or hmanifest.get("reference_parquet_sha256") != sha(HUMAN_REF): raise RuntimeError("human reference is not complete/verified")
    trace=pd.read_csv(TRACE)
    if len(trace) != 504 or trace.protocol_hash.nunique()!=1: raise RuntimeError("frozen trace population invalid")
    human=pd.read_parquet(HUMAN_REF)
    expected={(v,q) for v in VIDEOS for q in (Q1,Q2)}
    seen={(r.video_id,r.query_id) for r in human.itertuples()}
    # Empty-event cases are valid; case coverage must be checked from the adjudication CSV.
    adjud=pd.read_csv(HUMAN/"ADJUDICATED_EVENTS.csv",keep_default_na=False)
    if {(r.video_id,r.query_id) for r in adjud.itertuples()} != expected: raise RuntimeError("human reference lacks six adjudicated clusters")
    return p, trace, human, adjud


def load_labels() -> tuple[dict[tuple[str,str], dict[str,dict]], dict[tuple[str,str], int]]:
    old=pd.read_parquet(V10)
    new=pd.read_parquet(QWEN_TABLE)
    if len(old)!=1475 or len(new)!=1475 or set(new.label)-{"relevant","not_relevant","unknown","parse_failure"}: raise RuntimeError("semantic outcome tables invalid")
    labels: dict[tuple[str,str],dict[str,dict]]={}
    counts={}
    for query, frame, unit_col, label_col in ((Q1,old,"unit_id","authoritative_label"),(Q2,new,"unit_id","label")):
        for video,g in frame.groupby("video_id"):
            sub={str(r[unit_col]): {"start":float(r["start_time"]),"end":float(r["end_time"]),"outcome":str(r[label_col])} for _,r in g.iterrows()}
            labels[(str(video),query)]=sub; counts[(str(video),query)]=len(sub)
    if set(labels) != {(v,q) for v in VIDEOS for q in (Q1,Q2)} or set(counts.values()) != {347,561,567}: raise RuntimeError("semantic label/video coverage invalid")
    return labels, counts


def overlaps(a0:float,a1:float,b0:float,b1:float)->bool: return max(a0,b0)<min(a1,b1)


def c1_events(positives:list[dict]) -> list[dict]:
    ordered=sorted(positives,key=lambda x:(x["start"],x["end"],x["unit_id"]))
    groups=[]
    for item in ordered:
        if not groups or item["start"]-groups[-1][-1]["end"]>10.0: groups.append([item])
        else: groups[-1].append(item)
    return [{"start":min(x["start"] for x in g),"end":max(x["end"] for x in g)} for g in groups]


def human_records(video: str, query: str, refs: pd.DataFrame) -> list[EventRecord]:
    return [EventRecord(str(r.event_id), query, video, float(r.start_time), float(r.end_time), 1.0,
                        "HUMAN_ADJUDICATED_EVENT", (), (), "P1_HUMAN_REFERENCE", None)
            for r in refs.itertuples()]


def c1_records(video: str, query: str, positive: list[dict]) -> list[EventRecord]:
    return [EventRecord(f"p1_c1_{video}_{query}_{i:04d}", query, video, event["start"], event["end"], 1.0,
                        "VERIFIED_EVENT", (), (), "C1_gap_limited", None)
            for i,event in enumerate(c1_events(positive), 1)]


def trace_rows(trace:pd.DataFrame,human:pd.DataFrame,labels:dict[tuple[str,str],dict[str,dict]],counts:dict[tuple[str,str],int]) -> pd.DataFrame:
    rows=[]
    for t in trace.itertuples():
        ids=json.loads(t.selected_unit_ids_json)
        for query in (Q1,Q2):
            lm=labels[(t.video_id,query)]
            if any(x not in lm for x in ids): raise RuntimeError("trace/label identity mismatch")
            selected=[{**lm[x],"unit_id":x} for x in ids]
            positive=[x for x in selected if x["outcome"]=="relevant"]
            pos_positions=sorted(int(x["unit_id"].rsplit("u",1)[-1]) for x in positive)
            # Distance in candidate index to already verified evidence; summary after trace is permitted as oracle-observed.
            mindist=0.0 if len(pos_positions)<2 else float(np.mean([min(abs(a-b) for b in pos_positions if b!=a) for a in pos_positions]))
            refs=human[(human.video_id==t.video_id)&(human.query_id==query)]
            touched=sum(any(overlaps(p["start"],p["end"],float(r.start_time),float(r.end_time)) for p in positive) for r in refs.itertuples())
            pred=c1_records(t.video_id,query,positive); reference=human_records(t.video_id,query,refs)
            official=summarize_matches(pred,reference,match_events(pred,reference,MatchConfig(minimum_tiou=0.0,boundary_tolerance_sec=0.0)))
            tp=int(official["matched_events"]); fp=len(pred)-tp; fn=len(reference)-tp
            recall=float(official["32b_operational_oracle_relative_event_recall"])
            f1=float(official["event_f1"])
            centers=np.array([(x["start"]+x["end"])/2 for x in positive])
            rows.append({**t._asdict(),"query_id":query,"verified_positive_count":len(positive),"positive_yield":len(positive)/len(selected),"positive_temporal_dispersion":float(np.std(centers)/(max(x["end"] for x in lm.values()))) if len(centers) else 0.0,"distance_to_existing_verified_evidence":mindist,"human_event_count":len(refs),"distinct_human_events_touched":touched,"human_event_coverage":touched/len(refs) if len(refs) else 1.0,"human_events_with_zero_evidence":len(refs)-touched,"HumanEventRecall_C1":recall,"HumanEventF1_C1":f1,"C1_predicted_event_count":len(pred),"C1_TP":tp,"C1_FP":fp,"C1_FN":fn})
    return pd.DataFrame(rows)


def matched(frame:pd.DataFrame) -> pd.DataFrame:
    out=[]
    for key,g in frame.groupby(["video_id","query_id","proxy_family","budget","verified_positive_count"],sort=True):
        if len(g)<2 or g.number_of_temporal_regions_touched.nunique()<2: continue
        high=g.sort_values(["number_of_temporal_regions_touched","trace_hash"],ascending=[False,True]).iloc[0]
        low=g.sort_values(["number_of_temporal_regions_touched","trace_hash"],ascending=[True,True]).iloc[0]
        r={"video_id":key[0],"query_id":key[1],"proxy_family":key[2],"budget":key[3],"verified_positive_count":key[4],"traces_in_stratum":len(g),"geometry_high":high.number_of_temporal_regions_touched,"geometry_low":low.number_of_temporal_regions_touched,"geometry_delta":high.number_of_temporal_regions_touched-low.number_of_temporal_regions_touched,"trace_high":high.trace_hash,"trace_low":low.trace_hash}
        for col in ("distinct_human_events_touched","human_event_coverage","human_events_with_zero_evidence","HumanEventRecall_C1","HumanEventF1_C1"):
            r[f"delta_{col}"]=float(high[col]-low[col])
        out.append(r)
    return pd.DataFrame(out,columns=MATCH_COLUMNS)


def cluster_level_matches(matches:pd.DataFrame) -> tuple[pd.DataFrame,pd.DataFrame]:
    """Collapse repeated trace strata before any inferential P1 summaries.

    A video-query is the P1 statistical unit.  We retain a proxy-specific
    collapse for the proxy-replication gate, and a proxy-averaged collapse for
    the cross-cluster primary matched effect.  The original stratum table stays
    intact for the prespecified minimum-evidence count and auditability.
    """
    endpoints=("delta_distinct_human_events_touched","delta_human_event_coverage",
               "delta_human_events_with_zero_evidence","delta_HumanEventRecall_C1",
               "delta_HumanEventF1_C1")
    columns=["video_id","query_id","proxy_family","matched_strata",*endpoints]
    if matches.empty:
        proxy=pd.DataFrame(columns=columns)
        return proxy,pd.DataFrame(columns=["video_id","query_id","proxy_clusters",*endpoints])
    proxy=(matches.groupby(["video_id","query_id","proxy_family"],sort=True)
            .agg(matched_strata=("budget","size"),**{col:(col,"median") for col in endpoints})
            .reset_index())
    overall=(proxy.groupby(["video_id","query_id"],sort=True)
               .agg(proxy_clusters=("proxy_family","size"),**{col:(col,"median") for col in endpoints})
               .reset_index())
    return proxy,overall


def cluster_bootstrap(matches:pd.DataFrame) -> tuple[pd.DataFrame,dict]:
    """Resample video-query clusters, retaining all matched strata per draw.

    The bootstrap is a prespecified uncertainty report, not a post-hoc decision
    rule.  Trace rows are never resampled as independent observations.
    """
    metrics=("delta_distinct_human_events_touched","delta_human_event_coverage",
             "delta_human_events_with_zero_evidence","delta_HumanEventRecall_C1",
             "delta_HumanEventF1_C1")
    _,cluster_effects=cluster_level_matches(matches)
    if cluster_effects.empty:
        empty=pd.DataFrame(columns=["replicate","metric","estimate"])
        return empty,{metric:{"n":0,"median":None,"ci95":None} for metric in metrics}
    clusters=[(str(r.video_id),str(r.query_id)) for r in cluster_effects.itertuples()]
    by_cluster={(str(r.video_id),str(r.query_id)):r for r in cluster_effects.itertuples()}
    rng=np.random.default_rng(20260812)
    records=[]
    for replicate in range(10_000):
        sampled=[clusters[int(i)] for i in rng.integers(0,len(clusters),size=len(clusters))]
        for metric in metrics:
            values=[float(getattr(by_cluster[key],metric)) for key in sampled]
            records.append({"replicate":replicate,"metric":metric,"estimate":float(np.median(values))})
    result=pd.DataFrame(records)
    summary={}
    for metric,g in result.groupby("metric",sort=True):
        values=g.estimate.to_numpy()
        summary[metric]={"n":int(len(values)),"median":float(np.median(values)),
                         "ci95":[float(x) for x in np.quantile(values,[0.025,0.975])]} 
    return result,summary


def heldout(frame:pd.DataFrame) -> pd.DataFrame:
    features={"YIELD_ONLY":["positive_yield"],"YIELD_PLUS_POLICY_VISIBLE":["positive_yield","number_of_temporal_regions_touched","temporal_dispersion","coverage_fraction","largest_unqueried_gap_units","query_redundancy"],"YIELD_PLUS_VISIBLE_AND_ORACLE_OBSERVED":["positive_yield","number_of_temporal_regions_touched","temporal_dispersion","coverage_fraction","largest_unqueried_gap_units","query_redundancy","positive_temporal_dispersion","distance_to_existing_verified_evidence"]}
    result=[]
    for split, groups in (("LOVO", [(v,frame.video_id!=v,frame.video_id==v) for v in VIDEOS]),("LOVQO", [(f"{v}::{q}",(frame.video_id!=v)|(frame.query_id!=q),(frame.video_id==v)&(frame.query_id==q)) for v in VIDEOS for q in (Q1,Q2)])):
        for name, cols in features.items():
            scores=[]
            for held,train_mask,test_mask in groups:
                train,test=frame[train_mask],frame[test_mask]
                model=Pipeline([("impute",SimpleImputer(strategy="median")),("scale",StandardScaler()),("ridge",Ridge(alpha=1.0))])
                model.fit(train[cols],train.human_event_coverage); pred=model.predict(test[cols])
                score={"split":split,"heldout":held,"model":name,"n_train":len(train),"n_test":len(test),"MAE":float(mean_absolute_error(test.human_event_coverage,pred)),"R2":float(r2_score(test.human_event_coverage,pred))}
                result.append(score); scores.append(score)
            result.append({"split":split,"heldout":"MACRO_MEAN","model":name,"n_train":np.nan,"n_test":len(frame),"MAE":float(np.mean([x["MAE"] for x in scores])),"R2":float(np.mean([x["R2"] for x in scores]))})
    return pd.DataFrame(result)


def decide(matches:pd.DataFrame,models:pd.DataFrame)->tuple[str,dict]:
    counts=matches.groupby("proxy_family").size().to_dict() if len(matches) else {}
    clusters=matches.groupby(["proxy_family","video_id","query_id"]).size() if len(matches) else pd.Series(dtype=int)
    min_evidence=all(counts.get(p,0)>=12 and int((clusters.loc[p] if p in clusters.index.get_level_values(0) else pd.Series()).size)>=4 for p in ["PROXY_A_YOLOV8N_OBJECT_MOTION","PROXY_B_OPTICAL_FLOW_VISUAL_DYNAMICS"])
    proxy_effects,overall_effects=cluster_level_matches(matches)
    direction_by_cluster=overall_effects.set_index(["video_id","query_id"])["delta_human_event_coverage"] if len(overall_effects) else pd.Series(dtype=float)
    median_coverage=float(overall_effects.delta_human_event_coverage.median()) if len(overall_effects) else 0.0
    median_touched=float(overall_effects.delta_distinct_human_events_touched.median()) if len(overall_effects) else 0.0
    matched_effect=bool(len(overall_effects) and median_coverage>0 and median_touched>0 and int((direction_by_cluster>0).sum())>=4)
    byproxy=proxy_effects.groupby("proxy_family").delta_human_event_coverage.median() if len(proxy_effects) else pd.Series(dtype=float)
    proxy_ok=all(byproxy.get(p,0)>0 for p in ["PROXY_A_YOLOV8N_OBJECT_MOTION","PROXY_B_OPTICAL_FLOW_VISUAL_DYNAMICS"])
    macro=models[models.heldout=="MACRO_MEAN"]
    def get(split,model,col): return float(macro[(macro.split==split)&(macro.model==model)].iloc[0][col])
    y_lovo,y_lovqo=get("LOVO","YIELD_ONLY","R2"),get("LOVQO","YIELD_ONLY","R2")
    pv_lovo,pv_lovqo=get("LOVO","YIELD_PLUS_POLICY_VISIBLE","MAE"),get("LOVQO","YIELD_PLUS_POLICY_VISIBLE","MAE")
    ymae_lovo,ymae_lovqo=get("LOVO","YIELD_ONLY","MAE"),get("LOVQO","YIELD_ONLY","MAE")
    yield_insufficient=(y_lovo<=.5 and y_lovqo<=.5) or (ymae_lovo-pv_lovo>=.05 and ymae_lovqo-pv_lovqo>=.05)
    geometry_lift=ymae_lovo-pv_lovo>=.02 and ymae_lovqo-pv_lovqo>=.02
    passed=all((min_evidence,matched_effect,proxy_ok,yield_insufficient,geometry_lift))
    info={"minimum_evidence":min_evidence,"matched_effect":matched_effect,"proxy_replication":proxy_ok,"yield_only_insufficient":yield_insufficient,"policy_visible_geometry_lift":geometry_lift,"matched_strata_by_proxy":counts,"cluster_statistical_unit":"video-query; within-cluster matched strata are median-collapsed before primary summaries","positive_clusters":int((direction_by_cluster>0).sum()),"median_delta_coverage":median_coverage if len(overall_effects) else None,"median_delta_events_touched":median_touched if len(overall_effects) else None,"yield_r2_lovo":y_lovo,"yield_r2_lovqo":y_lovqo,"mae_lift_lovo":ymae_lovo-pv_lovo,"mae_lift_lovqo":ymae_lovqo-pv_lovqo}
    return ("PASS" if passed else "FAIL"),info


def main()->None:
    final=OUT/"P1_DECISION.md"
    if final.exists(): raise RuntimeError("P1 analysis already finalized")
    protocol,trace,human,_=require_complete(); labels,counts=load_labels()
    frame=trace_rows(trace,human,labels,counts); frame.to_csv(OUT/"P1_TRACE_HUMAN_ENDPOINTS.csv",index=False)
    matches=matched(frame); matches.to_csv(OUT/"P1_EQUAL_YIELD_MATCHED_HUMAN.csv",index=False)
    proxy_clusters,overall_clusters=cluster_level_matches(matches)
    proxy_clusters.to_csv(OUT/"P1_PROXY_VIDEOQUERY_MATCHED_HUMAN.csv",index=False)
    overall_clusters.to_csv(OUT/"P1_VIDEOQUERY_MATCHED_HUMAN.csv",index=False)
    bootstrap,bootstrap_summary=cluster_bootstrap(matches); bootstrap.to_csv(OUT/"P1_CLUSTER_BOOTSTRAP.csv",index=False)
    models=heldout(frame); models.to_csv(OUT/"P1_HELDOUT_GEOMETRY_MODELS.csv",index=False)
    decision,info=decide(matches,models)
    (OUT/"P1_DECISION.json").write_text(json.dumps({"decision":decision,"criteria":info,"cluster_bootstrap":bootstrap_summary,"analysis_protocol_sha256":sha(PROTOCOL),"input_hashes":{"trace":sha(TRACE),"human_reference":sha(HUMAN_REF),"qwen_second_query":sha(QWEN_TABLE),"original_query":sha(V10)}},indent=2,sort_keys=True)+"\n")
    report=f"""# P1 independent geometry replication report

## Decision

`P1_EVENT_EVIDENCE_GEOMETRY = {decision}`

## Prespecified gate audit

```json
{json.dumps(info,indent=2,sort_keys=True)}
```

## Cluster-bootstrap uncertainty report

The prespecified 10,000-replicate video-query-cluster bootstrap resampled whole
video-query clusters and retained their trace strata together. It is descriptive
uncertainty reporting; the preregistered PASS/FAIL gate above is unchanged.

```json
{json.dumps(bootstrap_summary,indent=2,sort_keys=True)}
```

This analysis used the adjudicated independent human temporal-event reference as its primary endpoint. Human event IDs/boundaries were not predictors. C1 was applied unchanged only for its secondary direct-recovery endpoint.

If this is `FAIL`, P2/P3 selector development must not proceed; see `P1_FAILURE_ANALYSIS.md` and `PROJECT_DIRECTION_AFTER_P1.md`.
"""
    (OUT/"P1_FINAL_REPORT.md").write_text(report)
    (OUT/"P1_DECISION.md").write_text(report)
    if decision=="FAIL":
        (OUT/"P1_FAILURE_ANALYSIS.md").write_text("# P1 failure analysis\n\nThe preregistered P1 gate did not establish a cross-cluster, two-natural-proxy independent-human geometry effect. Geometry-aware policy development is stopped. The cached model-relative geometry association remains a qualified descriptive observation only.\n")
        (OUT/"PROJECT_DIRECTION_AFTER_P1.md").write_text("# Project direction after P1\n\n`EVENT_EVIDENCE_POLICY = NO_GO`. The two-stage problem and its careful materialization/provenance artifacts remain useful supporting work, but the present evidence does not support an event-evidence query-policy algorithm. Do not run P2/P3, MAB/RL, or SCAN/VERIFY controller development under this branch.\n")
    print(json.dumps({"status":"COMPLETE","decision":decision,"output":str(OUT)},sort_keys=True))

if __name__=="__main__": main()
