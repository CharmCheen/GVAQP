#!/usr/bin/env python3
"""Prepare and freeze the adjudicated P1 human temporal-event reference."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "outputs/gvaqp_long_horizon_p1_p3_v1/human_reference_package"
RAW = PACKAGE / "HUMAN_EVENT_LABELS.jsonl"
CASES = PACKAGE / "ANNOTATOR_VIEW_CASES.json"
TEMPLATE = PACKAGE / "ADJUDICATION_TEMPLATE.csv"
ADJUDICATED = PACKAGE / "ADJUDICATED_EVENTS.csv"
REFERENCE = PACKAGE / "P1_HUMAN_EVENT_REFERENCE.parquet"
MANIFEST = PACKAGE / "P1_HUMAN_REFERENCE_MANIFEST.json"


def sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""): h.update(b)
    return h.hexdigest()


def latest_complete_annotations() -> tuple[dict, list[dict]]:
    cases={x["case_id"]:x for x in json.loads(CASES.read_text())}
    records=[json.loads(x) for x in RAW.read_text().splitlines() if x.strip()]
    latest={}
    for row in records:
        key=(row.get("annotator_id"),row.get("case_id"))
        if row.get("case_id") not in cases: raise RuntimeError("raw label references unknown case")
        latest[key]=row
    annotators=sorted({k[0] for k in latest})
    if len(annotators) < 2: raise RuntimeError("need two independent annotators before adjudication")
    for a in annotators:
        missing=[c for c in cases if (a,c) not in latest]
        if missing: raise RuntimeError(f"annotator {a} incomplete: {missing}")
    return cases, [latest[k] for k in sorted(latest)]


def prepare() -> None:
    if REFERENCE.exists() or MANIFEST.exists(): raise RuntimeError("human reference already frozen")
    cases, latest = latest_complete_annotations()
    if TEMPLATE.exists(): raise RuntimeError("adjudication template already exists; edit it rather than regenerate")
    by_case={c:[] for c in cases}
    for r in latest: by_case[r["case_id"]].append(r)
    rows=[]
    for case_id, case in cases.items():
        items=by_case[case_id]
        rows.append({"case_id":case_id,"video_id":case["video_id"],"query_id":case["query_id"],"annotator_ids":"|".join(x["annotator_id"] for x in items),"annotator_event_lists_json":json.dumps({x["annotator_id"]:x["events"] for x in items},sort_keys=True),"adjudicator_id":"","event_exists":"","events_json":"","adjudication_rationale":""})
    pd.DataFrame(rows).to_csv(TEMPLATE,index=False)
    print(json.dumps({"status":"ADJUDICATION_TEMPLATE_READY","cases":len(rows),"path":str(TEMPLATE)},sort_keys=True))


def freeze() -> None:
    if REFERENCE.exists() or MANIFEST.exists(): raise RuntimeError("human reference already frozen")
    cases, latest=latest_complete_annotations()
    if not ADJUDICATED.exists(): raise RuntimeError("missing ADJUDICATED_EVENTS.csv; copy/rename the completed template")
    df=pd.read_csv(ADJUDICATED,keep_default_na=False)
    required=["case_id","video_id","query_id","annotator_ids","annotator_event_lists_json","adjudicator_id","event_exists","events_json","adjudication_rationale"]
    if list(df.columns)!=required or len(df)!=len(cases) or set(df.case_id)!=set(cases): raise RuntimeError("invalid adjudication schema/case coverage")
    events=[]
    for row in df.to_dict("records"):
        case=cases[row["case_id"]]
        if row["video_id"]!=case["video_id"] or row["query_id"]!=case["query_id"]: raise RuntimeError("adjudication identity mismatch")
        if not row["adjudicator_id"].strip() or not row["adjudication_rationale"].strip(): raise RuntimeError("missing adjudicator provenance")
        if str(row["event_exists"]).lower() not in {"true","false"}: raise RuntimeError("event_exists must be true/false")
        parsed=json.loads(row["events_json"])
        if not isinstance(parsed,list) or (str(row["event_exists"]).lower()=="true") != bool(parsed): raise RuntimeError("event list/event_exists mismatch")
        for i,e in enumerate(parsed):
            if set(e)!={"start_time","end_time","boundary_ambiguous"}: raise RuntimeError("invalid adjudicated event fields")
            start,end=float(e["start_time"]),float(e["end_time"])
            if not (0 <= start < end <= float(case["duration_sec"])) or not isinstance(e["boundary_ambiguous"],bool): raise RuntimeError("invalid adjudicated interval")
            events.append({"event_id":f"{row['case_id']}::E{i+1:03d}","case_id":row["case_id"],"video_id":row["video_id"],"query_id":row["query_id"],"event_exists":True,"start_time":start,"end_time":end,"boundary_ambiguous":e["boundary_ambiguous"],"adjudicator_id":row["adjudicator_id"]})
    ref=pd.DataFrame(events,columns=["event_id","case_id","video_id","query_id","event_exists","start_time","end_time","boundary_ambiguous","adjudicator_id"])
    ref.to_parquet(REFERENCE,index=False)
    manifest={"status":"FROZEN_COMPLETE_ADJUDICATED_HUMAN_REFERENCE","created_at_utc":datetime.now(timezone.utc).isoformat(),"case_count":len(cases),"event_count":len(ref),"annotators":sorted({r["annotator_id"] for r in latest}),"raw_label_log_sha256":sha(RAW),"adjudication_csv_sha256":sha(ADJUDICATED),"reference_parquet_sha256":sha(REFERENCE),"protocol_sha256":sha(PACKAGE/"HUMAN_REFERENCE_PROTOCOL.json"),"source_video_hashes":json.loads((PACKAGE/"HUMAN_REFERENCE_PROTOCOL.json").read_text())["source_videos"]}
    MANIFEST.write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":"FROZEN","events":len(ref),"manifest":str(MANIFEST)},sort_keys=True))


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("command",choices=("prepare-adjudication","freeze"));a=p.parse_args()
    prepare() if a.command=="prepare-adjudication" else freeze()
