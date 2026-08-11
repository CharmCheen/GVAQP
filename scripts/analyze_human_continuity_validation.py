#!/usr/bin/env python3
"""Analyze only the frozen primary human-continuity labels.

This is deliberately a post-freeze entrypoint.  It refuses JSONL progress
records and joins the blinded labels with hidden C0/C1/K3 metadata only after
the server has created the immutable primary CSV.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"outputs/human_continuity_validation_v1"
LABELS={"SAME_EVENT":1,"DIFFERENT_EVENTS":0}
METHODS=("C0_same_event","C1_same_event","K3_same_event")
PRETTY={"C0_same_event":"C0","C1_same_event":"C1_GAP_ONLY","K3_same_event":"K3"}


def sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""): h.update(b)
    return h.hexdigest()


def write_csv(path: Path, rows: list[dict[str,Any]], fields: list[str]) -> None:
    import io
    b=io.StringIO(newline=""); w=csv.DictWriter(b,fieldnames=fields); w.writeheader(); w.writerows(rows)
    text=b.getvalue()
    if path.exists() and path.read_text(encoding="utf-8") != text:
        raise RuntimeError(f"refusing to overwrite non-identical analysis artifact: {path}")
    path.write_text(text,encoding="utf-8")


def bootstrap(delta: np.ndarray, seed: int, n_boot: int) -> tuple[float,float,float]:
    if len(delta)==0: return float("nan"),float("nan"),float("nan")
    rng=np.random.default_rng(seed); n=len(delta)
    values=np.empty(n_boot)
    for i in range(n_boot): values[i]=delta[rng.integers(0,n,n)].mean()
    return float(delta.mean()),float(np.quantile(values,.025)),float(np.quantile(values,.975))


def boundary(y: np.ndarray, prediction: np.ndarray) -> dict[str,float|int]:
    # A human DIFFERENT_EVENTS judgement is a boundary (0); a method split is
    # likewise a boundary.  Invalid/uncertain cases are excluded upstream.
    truth=(y==0); pred=(prediction==0)
    tp=int((truth&pred).sum()); fp=int((~truth&pred).sum()); fn=int((truth&~pred).sum())
    p=tp/(tp+fp) if tp+fp else float("nan")
    r=tp/(tp+fn) if tp+fn else float("nan")
    f=2*p*r/(p+r) if p+r else float("nan")
    return {"TP":tp,"FP":fp,"FN":fn,"precision":p,"recall":r,"F1":f,
            "false_merge":int((~pred&truth).sum()),"false_split":int((pred&~truth).sum())}


def decision(eligible: pd.DataFrame, ci_width: float) -> tuple[str,dict[str,Any]]:
    r2=json.loads((OUT/"HUMAN_CONTINUITY_PROTOCOL_AMENDMENT_R2.json").read_text())
    rules=r2["analysis_contract"]
    c01=eligible[eligible.C0_same_event.ne(eligible.C1_same_event)]
    c1delta=(eligible.C1_same_event==eligible.human_same).astype(int)-(eligible.C0_same_event==eligible.human_same).astype(int)
    k3delta=(eligible.K3_same_event==eligible.human_same).astype(int)-(eligible.C1_same_event==eligible.human_same).astype(int)
    diag={"eligible_primary_cases":len(eligible),"eligible_C0_C1_disagreement_cases":len(c01),"ci_width":ci_width,
          "C1_minus_C0_raw_accuracy":float(c1delta.mean()) if len(eligible) else float("nan"),
          "K3_minus_C1_raw_accuracy":float(k3delta.mean()) if len(eligible) else float("nan")}
    inconclusive=(len(eligible)<28 or len(c01)<8 or ci_width>.40)
    video_c1=[]; video_k3=[]
    for _,g in eligible.groupby("video_id"):
        if len(g)>=5:
            video_c1.append(float(((g.C1_same_event==g.human_same).astype(int)-(g.C0_same_event==g.human_same).astype(int)).mean())>0)
            video_k3.append(float(((g.K3_same_event==g.human_same).astype(int)-(g.C1_same_event==g.human_same).astype(int)).mean())>0)
    if inconclusive: return "INCONCLUSIVE_PRIMARY",diag
    if diag["K3_minus_C1_raw_accuracy"]>=.10 and sum(video_k3)>=2: return "HUMAN_SUPPORTS_FULL_K3",diag
    if diag["C1_minus_C0_raw_accuracy"]>=.10 and sum(video_c1)>=2 and diag["K3_minus_C1_raw_accuracy"]<.10: return "HUMAN_SUPPORTS_GAP_ONLY",diag
    return "NO_HUMAN_SUPPORT",diag


def main() -> None:
    global OUT
    ap=argparse.ArgumentParser(); ap.add_argument("--package",type=Path,default=OUT); args=ap.parse_args(); OUT=args.package.resolve()
    frozen=OUT/"HUMAN_LABELS_PRIMARY_FROZEN.csv"
    if not frozen.exists():
        raise SystemExit("WAITING_FOR_FROZEN_PRIMARY_LABELS: start the local annotation server; JSONL progress is intentionally not analyzed.")
    state=json.loads((OUT/"HUMAN_CONTINUITY_STATE.json").read_text())
    if state.get("human_labels_observed")!=40: raise RuntimeError("frozen label/state count is not 40")
    hidden=pd.read_csv(OUT/"PRIMARY_SAMPLE_MANIFEST.csv")
    human=pd.read_csv(frozen)
    if len(human)!=40 or human.case_id.nunique()!=40 or set(human.case_id)!=set(hidden.public_case_id): raise RuntimeError("frozen human-label identities do not match primary blinded manifest")
    joined=hidden.merge(human,left_on="public_case_id",right_on="case_id",validate="one_to_one")
    joined["human_same"]=joined.label.map(LABELS)
    eligible=joined[joined.human_same.notna()].copy(); eligible["human_same"]=eligible.human_same.astype(int)
    r2=json.loads((OUT/"HUMAN_CONTINUITY_PROTOCOL_AMENDMENT_R2.json").read_text()); rules=r2["analysis_contract"]
    result=[]
    for method in METHODS:
        correct=(eligible[method].astype(int)==eligible.human_same).astype(float)
        result.append({"scope":"PRIMARY_RAW","method":PRETTY[method],"eligible_cases":len(eligible),"accuracy":float(correct.mean()) if len(correct) else float("nan"),"weighting":"none"})
        result.append({"scope":"PRIMARY_POPULATION_WEIGHTED","method":PRETTY[method],"eligible_cases":len(eligible),"accuracy":float(np.average(correct,weights=eligible.analysis_weight)) if len(correct) else float("nan"),"weighting":"inverse_probability"})
    write_csv(OUT/"human_continuity_results.csv",result,list(result[0]))
    video_rows=[]
    for video,g in joined.groupby("video_id",sort=True):
        ge=g[g.human_same.notna()].copy(); row={"video_id":video,"total_cases":len(g),"eligible_cases":len(ge),"anchor_invalid":int(g.label.eq("ANCHOR_INVALID").sum()),"uncertain":int(g.label.eq("UNCERTAIN").sum())}
        for method in METHODS: row[PRETTY[method]+"_accuracy"]=float((ge[method].astype(int)==ge.human_same).mean()) if len(ge) else float("nan")
        row["C1_minus_C0"]=row["C1_GAP_ONLY_accuracy"]-row["C0_accuracy"] if len(ge) else float("nan"); row["K3_minus_C1"]=row["K3_accuracy"]-row["C1_GAP_ONLY_accuracy"] if len(ge) else float("nan")
        video_rows.append(row)
    write_csv(OUT/"human_continuity_by_video.csv",video_rows,list(video_rows[0]))
    pattern=[]
    for pat,g in joined.groupby("prediction_pattern",sort=True):
        ge=g[g.human_same.notna()]; row={"prediction_pattern":pat,"sampled_cases":len(g),"eligible_cases":len(ge),"human_same_rate":float(ge.human_same.mean()) if len(ge) else float("nan")}
        for m in METHODS: row[PRETTY[m]+"_accuracy"]=float((ge[m].astype(int)==ge.human_same).mean()) if len(ge) else float("nan")
        pattern.append(row)
    write_csv(OUT/"prediction_pattern_results.csv",pattern,list(pattern[0]))
    b_rows=[]
    for method in METHODS:
        b_rows.append({"method":PRETTY[method],**boundary(eligible.human_same.to_numpy(),eligible[method].astype(int).to_numpy()),"eligible_cases":len(eligible)})
    write_csv(OUT/"boundary_metrics.csv",b_rows,list(b_rows[0]))
    av=[]
    for v,g in list(joined.groupby("video_id",sort=True))+[("POOLED",joined)]: av.append({"video_id":v,"total_cases":len(g),"anchor_invalid":int(g.label.eq("ANCHOR_INVALID").sum()),"uncertain":int(g.label.eq("UNCERTAIN").sum()),"eligible":int(g.human_same.notna().sum())})
    write_csv(OUT/"anchor_validity.csv",av,list(av[0]))
    c1=(eligible.C1_same_event==eligible.human_same).astype(int).to_numpy()-(eligible.C0_same_event==eligible.human_same).astype(int).to_numpy()
    k3=(eligible.K3_same_event==eligible.human_same).astype(int).to_numpy()-(eligible.C1_same_event==eligible.human_same).astype(int).to_numpy()
    c1mean,c1lo,c1hi=bootstrap(c1,int(rules["analysis_seed"]),int(rules["paired_bootstrap_resamples"])); k3mean,k3lo,k3hi=bootstrap(k3,int(rules["analysis_seed"])+1,int(rules["paired_bootstrap_resamples"])); dec,diag=decision(eligible,c1hi-c1lo)
    summary={"label_hash":sha(frozen),"eligible_cases":len(eligible),"anchor_invalid":int(joined.label.eq("ANCHOR_INVALID").sum()),"uncertain":int(joined.label.eq("UNCERTAIN").sum()),"C1_minus_C0":{"point":c1mean,"ci95":[c1lo,c1hi]},"K3_minus_C1":{"point":k3mean,"ci95":[k3lo,k3hi]},"primary_decision":dec,"decision_diagnostics":diag}
    (OUT/"HUMAN_CONTINUITY_ANALYSIS_SUMMARY.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    report=f"""# Human Continuity Analysis\n\nFrozen-label hash: `{summary['label_hash']}`.  Eligible continuity cases: `{len(eligible)}/40`; anchor-invalid: `{summary['anchor_invalid']}`; uncertain: `{summary['uncertain']}`.\n\n- C1−C0 human-continuity accuracy: `{c1mean:.4f}` (paired bootstrap 95% CI `{c1lo:.4f}`, `{c1hi:.4f}`).\n- K3−C1 human-continuity accuracy: `{k3mean:.4f}` (paired bootstrap 95% CI `{k3lo:.4f}`, `{k3hi:.4f}`).\n- Primary decision under frozen R2 rules: **`{dec}`**.\n\nResults are a small blinded sanity study, with both raw targeted and inverse-probability population-weighted descriptive estimates in `human_continuity_results.csv`.  Invalid and uncertain anchors are reported rather than coerced into human boundaries.\n"""
    (OUT/"HUMAN_CONTINUITY_ANALYSIS.md").write_text(report,encoding="utf-8")
    (OUT/"HUMAN_CONTINUITY_DECISION.md").write_text(f"# Human Continuity Decision\n\n`PRIMARY_DECISION = {dec}`\n\nSee `HUMAN_CONTINUITY_ANALYSIS.md` and `HUMAN_CONTINUITY_ANALYSIS_SUMMARY.json`.\n",encoding="utf-8")
    state.update({"status":"ANALYSIS_COMPLETE","analysis_performed":True,"primary_decision":dec,"human_label_hash":sha(frozen)})
    (OUT/"HUMAN_CONTINUITY_STATE.json").write_text(json.dumps(state,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(summary,sort_keys=True))

if __name__=="__main__": main()
