#!/usr/bin/env python3
"""Post-P0, no-tuning mechanism decomposition on frozen P0 V3 traces.

The variants are the pre-existing Stage-0 C0--C3 materialization lineage,
expressed over V3 unit records.  This is a cached, same-trace explanatory
ablation, not a new selector or a replacement for the frozen P0 primary test.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from garc_eval.accelerated_event_query.matching import MatchConfig  # noqa: E402
from garc_eval.accelerated_event_query.model_relative_labels import ModelRelativeUnitLabel  # noqa: E402
from garc_eval.accelerated_event_query.types import EventRecord  # noqa: E402

P0 = ROOT / "outputs/p0_materializer_validation_v3"
OUT = ROOT / "outputs/p0_materializer_mechanism_ablation_v1"
V10 = ROOT / "outputs/v10_multiseal_reference_v1"
P0_RUNNER = ROOT / "scripts/run_p0_v3_materializer_validation.py"
QUERY = "Q_DRIVER_RESPONSE_V1"
VARIANTS = ("C0_naive_all_positive_span", "C1_gap_limited", "C2_gap_duration", "C3_gap_duration_negative_barrier", "K3_current_v3")


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canon(v: Any) -> str:
    return hashlib.sha256(json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def once_json(path: Path, v: Any) -> None:
    text = json.dumps(v, indent=2, sort_keys=True) + "\n"
    if path.exists():
        if path.read_text() != text: raise RuntimeError(f"immutable mismatch: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text)


def once_csv(path: Path, rows: list[dict]) -> None:
    import io
    fields = list(rows[0])
    s = io.StringIO(newline=""); w = csv.DictWriter(s, fieldnames=fields); w.writeheader(); w.writerows(rows)
    if path.exists():
        if path.read_text() != s.getvalue(): raise RuntimeError(f"immutable mismatch: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(s.getvalue())


def p0_module():
    spec = importlib.util.spec_from_file_location("p0_runner", P0_RUNNER)
    if spec is None or spec.loader is None: raise RuntimeError("cannot import frozen P0 runner")
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
    return module


def protocol() -> dict:
    p0 = read(P0 / "EXPERIMENT_PROTOCOL.json")
    if not (P0 / "pooled_summary.json").exists(): raise RuntimeError("P0 V3 result absent")
    stage = ROOT / "scripts/stage0_6_materializer_ablation.py"
    raw = {
        "protocol_id": "P0_V3_MECHANISM_DECOMPOSITION_V1",
        "status": "FROZEN_BEFORE_MECHANISM_REPLAY",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "analysis_kind": "POST_P0_EXPLANATORY_CACHED_REPLAY",
        "not_a_new_algorithm": True,
        "reason": "The long-horizon research objective pre-specified tests of negative evidence and allowed C0/gap/duration/negative-barrier lineage ablations. No thresholds or source semantics are tuned here.",
        "input_p0_protocol_hash": p0["protocol_hash"],
        "input_files": {str(x.relative_to(ROOT)): sha(x) for x in [P0 / "controlled_pairs.csv", P0 / "event_metrics.csv", V10 / "FINAL_UNIT_REFERENCE.parquet", V10 / "K3_MODEL_RELATIVE_EVENT_RELATION.parquet", P0_RUNNER, stage]},
        "same_trace_rule": "Each C0/C1/C2/C3/K3 row consumes the exact P0 queried unit ids, query order and terminal outcomes for that video/selector/budget trace.",
        "variants": {
            "C0_naive_all_positive_span": "Historical Stage-0 C0: all queried relevant anchors become one min-to-max span.",
            "C1_gap_limited": "Historical Stage-0 C1 natural lineage: merge consecutive queried relevant anchors only when temporal gap <= 10 seconds; no duration cap or negative barrier.",
            "C2_gap_duration": "Historical Stage-0 C2 natural lineage: C1 plus 40-second maximum core span.",
            "C3_gap_duration_negative_barrier": "Historical Stage-0 C3 natural lineage: C2 plus any queried not_relevant unit fully between adjacent anchors blocks their merge.",
            "K3_current_v3": "Frozen current V3 K3 adapter, including unknown/parse semantics and exact configuration.",
        },
        "matching": read(P0 / "EXPERIMENT_PROTOCOL.json")["primary_matcher"],
        "model_relative_circularity": "QUALIFIED_BUT_VALID; this decomposition cannot independently validate human event boundaries.",
    }
    raw["protocol_hash"] = canon({k:v for k,v in raw.items() if k not in {"created_at_utc","protocol_hash"}})
    return raw


def freeze() -> None:
    if OUT.exists() and any(OUT.iterdir()): raise RuntimeError(f"refuse overwrite {OUT}")
    p = protocol(); OUT.mkdir(parents=True); once_json(OUT / "MECHANISM_PROTOCOL.json", p); (OUT / "PROTOCOL_HASH.txt").write_text(p["protocol_hash"] + "\n")
    print(json.dumps({"status":"FROZEN","protocol_hash":p["protocol_hash"]}))


def load_protocol() -> dict:
    p = read(OUT / "MECHANISM_PROTOCOL.json")
    actual = canon({k:v for k,v in p.items() if k not in {"created_at_utc","protocol_hash"}})
    if p["protocol_hash"] != actual or (OUT / "PROTOCOL_HASH.txt").read_text().strip() != actual: raise RuntimeError("protocol hash failed")
    if sha(P0_RUNNER) != p["input_files"][str(P0_RUNNER.relative_to(ROOT))]: raise RuntimeError("P0 runner changed after mechanism freeze")
    return p


def generic_events(video: str, units: Sequence[ModelRelativeUnitLabel], variant: str) -> list[EventRecord]:
    pos = sorted([x for x in units if x.outcome == "relevant"], key=lambda x:(x.start_time,x.end_time,x.unit_id))
    if not pos: return []
    if variant == "C0_naive_all_positive_span": groups = [pos]
    else:
        groups = [[pos[0]]]
        for right in pos[1:]:
            left = groups[-1][-1]
            gap = max(0., right.start_time-left.end_time)
            proposed_start, proposed_end = groups[-1][0].start_time, right.end_time
            merge = gap <= 10.0
            if variant in {"C2_gap_duration","C3_gap_duration_negative_barrier"}:
                merge = merge and proposed_end-proposed_start <= 40.0
            if variant == "C3_gap_duration_negative_barrier":
                barriers = [x for x in units if x.outcome == "not_relevant" and x.start_time >= left.end_time and x.end_time <= right.start_time and x.end_time > left.end_time and x.start_time < right.start_time]
                merge = merge and not barriers
            if merge: groups[-1].append(right)
            else: groups.append([right])
    out=[]
    for i, group in enumerate(groups):
        src=tuple(x.unit_id for x in group); token=canon({"v":variant,"video":video,"src":src})[:16]
        out.append(EventRecord(f"mech_{variant}_{token}",QUERY,video,min(x.start_time for x in group),max(x.end_time for x in group),1.,"VERIFIED_EVENT",src,(),variant,None))
    return out


def run() -> None:
    p=load_protocol(); runner=p0_module()
    labels, candidates, refs=runner.load_data(); config,_,_=runner.frozen_k3_config()
    pairs=pd.read_csv(P0 / "controlled_pairs.csv"); pairs=pairs[pairs.materializer=="K0"].copy()
    rows=[]
    for item in pairs.to_dict(orient="records"):
        ids=json.loads(item["queried_unit_ids"]); units=[labels[x] for x in ids]
        for variant in VARIANTS:
            events=runner.k3_materialize(units,config) if variant=="K3_current_v3" else generic_events(item["video_id"],units,variant)
            metrics=runner.metric_row(events,refs[item["video_id"]],MatchConfig(minimum_tiou=0.,boundary_tolerance_sec=0.))
            diag=runner.diagnostics(events,refs[item["video_id"]],units)
            rows.append({"video_id":item["video_id"],"query_id":item["query_id"],"selector":item["selector"],"budget":int(item["budget"]),"seed":int(item["seed"]),"variant":variant,"trace_hash":item["trace_hash"],"oracle_calls":int(item["oracle_calls"]),**metrics,**diag})
    once_csv(OUT / "mechanism_metrics.csv",rows)
    frame=pd.DataFrame(rows); pivot=frame.pivot(index=["video_id","query_id","selector","budget","seed"],columns="variant",values="F1")
    effect_rows=[]
    for index,x in pivot.iterrows():
        for left,right,mechanism in [("C1_gap_limited","C0_naive_all_positive_span","gap constraint"),("C2_gap_duration","C1_gap_limited","duration cap"),("C3_gap_duration_negative_barrier","C2_gap_duration","queried-negative barrier"),("K3_current_v3","C3_gap_duration_negative_barrier","current-V3 unknown/parse/exact semantics")]:
            effect_rows.append({"video_id":index[0],"query_id":index[1],"selector":index[2],"budget":index[3],"seed":index[4],"mechanism":mechanism,"from_variant":right,"to_variant":left,"F1_from":float(x[right]),"F1_to":float(x[left]),"Delta_F1":float(x[left]-x[right])})
    once_csv(OUT / "mechanism_effects.csv",effect_rows)
    summary=[]
    for mech,g in pd.DataFrame(effect_rows).groupby("mechanism",sort=False):
        vals=g.Delta_F1.to_numpy(float); summary.append({"mechanism":mech,"cells":len(vals),"mean_Delta_F1":float(vals.mean()),"median_Delta_F1":float(np.median(vals)),"positive":int((vals>1e-12).sum()),"equal":int((abs(vals)<=1e-12).sum()),"negative":int((vals<-1e-12).sum())})
    once_csv(OUT / "mechanism_summary.csv",summary)
    summary_map={x["mechanism"]:x for x in summary}
    report=f"""# P0 V3 Materializer Mechanism Decomposition

Protocol: `{p['protocol_hash']}`. This is an outcome-preserving cached replay of the already frozen 54 P0 traces.  It uses no oracle calls, no selector change, no threshold sweep and no new materializer proposal. It maps historical Stage-0 C0→C3 natural lineage to current V3 units, then compares current K3.

| Mechanism increment | Mean ΔF1 | Median ΔF1 | + / = / - cells |
|---|---:|---:|---:|
"""+"\n".join(f"| {x['mechanism']} | {x['mean_Delta_F1']:.4f} | {x['median_Delta_F1']:.4f} | {x['positive']} / {x['equal']} / {x['negative']} |" for x in summary)+"""

Interpretation rule: an increment is evidence for that exact constraint only when it changes output on the same trace.  A zero does not say the constraint is invalid; it says the frozen sparse traces did not expose a case in which it changed the primary overlap-any event metric.  Because the reference event relation is full-grid K3-defined, all event-level attribution remains model-relative/circularity-qualified.
"""
    (OUT / "MECHANISM_REPORT.md").write_text(report)
    print(json.dumps({"status":"COMPLETE","protocol_hash":p["protocol_hash"],"summary":summary}))


def main() -> None:
    ap=argparse.ArgumentParser(); ap.add_argument("action",choices=["freeze","run"]); a=ap.parse_args()
    freeze() if a.action=="freeze" else run()
if __name__=="__main__": main()
