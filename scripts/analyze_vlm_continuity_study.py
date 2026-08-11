#!/usr/bin/env python3
"""Post-freeze analysis for the independent blinded VLM continuity study."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"outputs/vlm_continuity_validation_v1"
HUMAN=ROOT/"outputs/human_continuity_validation_v1"
CONV=ROOT/"outputs/research_contribution_convergence_v1"
METHODS=("C0_same_event","C1_same_event","K3_same_event")
NAMES={"C0_same_event":"C0","C1_same_event":"C1_GAP_ONLY","K3_same_event":"K3"}
LABELMAP={"SAME_EVENT":1,"DIFFERENT_EVENTS":0}


def sha(p: Path) -> str:
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""): h.update(b)
    return h.hexdigest()


def write_csv(path: Path, rows: list[dict[str,Any]], fields: list[str]) -> None:
    import io
    b=io.StringIO(newline=""); w=csv.DictWriter(b,fieldnames=fields); w.writeheader(); w.writerows(rows)
    value=b.getvalue()
    if path.exists() and path.read_text(encoding="utf-8") != value: raise RuntimeError(f"immutable output mismatch: {path}")
    path.write_text(value,encoding="utf-8")


def boot(values: np.ndarray, seed: int=20260811, n: int=10000) -> tuple[float,float,float]:
    if not len(values): return float("nan"),float("nan"),float("nan")
    rng=np.random.default_rng(seed); m=len(values); x=np.empty(n)
    for i in range(n): x[i]=values[rng.integers(0,m,m)].mean()
    return float(values.mean()),float(np.quantile(x,.025)),float(np.quantile(x,.975))


def boundary(y: np.ndarray,pred: np.ndarray) -> dict[str,Any]:
    truth=y==0; decision=pred==0
    tp=int((truth&decision).sum()); fp=int((~truth&decision).sum()); fn=int((truth&~decision).sum())
    precision=tp/(tp+fp) if tp+fp else float("nan"); recall=tp/(tp+fn) if tp+fn else float("nan")
    return {"TP":tp,"FP":fp,"FN":fn,"precision":precision,"recall":recall,"F1":2*precision*recall/(precision+recall) if precision+recall else float("nan"),"false_merge":int((~decision&truth).sum()),"false_split":int((decision&~truth).sum())}


def main() -> None:
    protocol=json.loads((OUT/"VLM_JUDGE_PROTOCOL.json").read_text())
    labels_path=OUT/"JUDGE_A_LABELS.csv"
    if not labels_path.exists() or not (OUT/"JUDGE_A_LABELS_HASH.txt").exists(): raise RuntimeError("labels must be frozen before hidden method join")
    labels=pd.read_csv(labels_path)
    hidden=pd.read_csv(HUMAN/"PRIMARY_SAMPLE_MANIFEST.csv")
    if len(labels)!=40 or labels.case_id.nunique()!=40 or set(labels.case_id)!=set(hidden.public_case_id): raise RuntimeError("label identities are not the frozen primary set")
    human_state=json.loads((HUMAN/"HUMAN_CONTINUITY_STATE.json").read_text())
    if human_state.get("human_labels_observed") != 0: raise RuntimeError("human benchmark was unexpectedly modified")
    joined=hidden.merge(labels,left_on="public_case_id",right_on="case_id",validate="one_to_one")
    joined["judge_same"]=joined.label.map(LABELMAP)
    eligible=joined[joined.judge_same.notna()].copy(); eligible["judge_same"]=eligible.judge_same.astype(int)
    result=[]
    for method in METHODS:
        correct=(eligible[method].astype(int)==eligible.judge_same).astype(float)
        result.append({"scope":"TARGETED_PRIMARY","method":NAMES[method],"eligible_cases":len(eligible),"accuracy":float(correct.mean()) if len(correct) else float("nan"),"weighting":"none"})
        result.append({"scope":"POPULATION_WEIGHTED_DESCRIPTIVE","method":NAMES[method],"eligible_cases":len(eligible),"accuracy":float(np.average(correct,weights=eligible.analysis_weight)) if len(correct) else float("nan"),"weighting":"inverse_probability"})
    write_csv(OUT/"VLM_CONTINUITY_METHOD_COMPARISON.csv",result,list(result[0]))
    video=[]
    for video_id,g in joined.groupby("video_id",sort=True):
        e=g[g.judge_same.notna()]; row={"video_id":video_id,"total_cases":len(g),"eligible_cases":len(e),"anchor_invalid":int(g.label.eq("ANCHOR_INVALID").sum()),"uncertain":int(g.label.eq("UNCERTAIN").sum()),"parse_failure_coerced_uncertain":int(g.parse_status.eq("PARSE_FAILURE_COERCED_TO_UNCERTAIN").sum())}
        for m in METHODS: row[NAMES[m]+"_accuracy"]=float((e[m].astype(int)==e.judge_same).mean()) if len(e) else float("nan")
        row["C1_minus_C0"]=row["C1_GAP_ONLY_accuracy"]-row["C0_accuracy"] if len(e) else float("nan"); row["K3_minus_C1"]=row["K3_accuracy"]-row["C1_GAP_ONLY_accuracy"] if len(e) else float("nan")
        video.append(row)
    write_csv(OUT/"VLM_CONTINUITY_BY_VIDEO.csv",video,list(video[0]))
    metrics=[]; errors=[]
    for m in METHODS:
        b=boundary(eligible.judge_same.to_numpy(),eligible[m].astype(int).to_numpy())
        metrics.append({"method":NAMES[m],"eligible_cases":len(eligible),**b})
        errors.append({"method":NAMES[m],"error_type":"FALSE_MERGE","count":b["false_merge"]})
        errors.append({"method":NAMES[m],"error_type":"FALSE_SPLIT","count":b["false_split"]})
    write_csv(OUT/"VLM_BOUNDARY_METRICS.csv",metrics,list(metrics[0])); write_csv(OUT/"VLM_ERROR_TAXONOMY.csv",errors,list(errors[0]))
    patterns=[]
    for pat,g in joined.groupby("prediction_pattern",sort=True):
        e=g[g.judge_same.notna()]; row={"prediction_pattern":pat,"sampled_cases":len(g),"eligible_cases":len(e),"judge_same_rate":float(e.judge_same.mean()) if len(e) else float("nan"),"uncertain":int(g.label.eq("UNCERTAIN").sum())}
        for m in METHODS: row[NAMES[m]+"_accuracy"]=float((e[m].astype(int)==e.judge_same).mean()) if len(e) else float("nan")
        patterns.append(row)
    write_csv(OUT/"VLM_PREDICTION_PATTERN_RESULTS.csv",patterns,list(patterns[0]))
    consensus=[]
    for _,r in labels.iterrows(): consensus.append({"case_id":r.case_id,"consensus_label":r.label,"label_source":"JUDGE_A_SINGLE","eligible_continuity":r.label in LABELMAP,"raw_output_sha256":r.raw_output_sha256})
    write_csv(OUT/"VLM_CONSENSUS_LABELS.csv",consensus,list(consensus[0]))
    agreement=[{"judge_design":"SINGLE","judge_a":"HuggingFaceTB/SmolVLM2-500M-Video-Instruct","judge_b":"NOT_USED","raw_agreement":"NOT_APPLICABLE","cohen_kappa":"NOT_APPLICABLE","note":"No second cached cross-family video-generative judge was available at preregistration."}]
    write_csv(OUT/"JUDGE_AGREEMENT.csv",agreement,list(agreement[0]))
    c1=(eligible.C1_same_event==eligible.judge_same).astype(int).to_numpy()-(eligible.C0_same_event==eligible.judge_same).astype(int).to_numpy()
    k3=(eligible.K3_same_event==eligible.judge_same).astype(int).to_numpy()-(eligible.C1_same_event==eligible.judge_same).astype(int).to_numpy()
    c1mean,c1lo,c1hi=boot(c1); k3mean,k3lo,k3hi=boot(k3,seed=20260812)
    # Frozen protocol says fewer than 28 eligible labels is objectively
    # INCONCLUSIVE, regardless of observed method direction.
    decision="INCONCLUSIVE_VLM" if len(eligible)<28 or (np.isfinite(c1hi-c1lo) and c1hi-c1lo>.40) else "NO_VLM_SUPPORT"
    comparison=f"""# P0 vs Independent VLM Evidence Comparison

P0 V3 has a controlled model-relative result: median K3−K0 Event-F1 is `+0.1457` across 54 same-trace pairs. Its reference EventRelation is K3-constructed from full-grid Qwen outcomes, so it is circularity-qualified.

The present study reused the identical blinded 40-case primary set, but Judge A produced only `{len(eligible)}/40` schema-eligible SAME/DIFFERENT continuity labels. `{int(labels.parse_status.eq('PARSE_FAILURE_COERCED_TO_UNCERTAIN').sum())}/40` outputs could not be mapped to the frozen four-label schema and were conservatively recorded as `UNCERTAIN`; they were not re-run. Therefore its C1−C0 estimate `{c1mean:.4f}` and K3−C1 estimate `{k3mean:.4f}` are descriptive only.

**Answer to the circularity question: `INCONCLUSIVE`.** A cross-family model was blind to K3 and method metadata, but insufficient schema-valid labels prevent it from independently corroborating or refuting the P0 materialization effect. This does not alter the P0 raw result and does not permit promotion of C1 or K3 as human-semantic truth.
"""
    (OUT/"P0_VS_VLM_EVIDENCE_COMPARISON.md").write_text(comparison,encoding="utf-8")
    report=f"""# Independent VLM Event-Continuity Analysis

## Design and completeness

Judge A was the pre-frozen cross-family `HuggingFaceTB/SmolVLM2-500M-Video-Instruct` on all 40 blinded public cases. The original human benchmark remains untouched: `HUMAN_CONTINUITY_VALIDATION = PENDING`, zero human labels.

Raw logs and a 40-row label CSV are hash-frozen. However, only `{len(eligible)}` rows have a frozen schema-valid/recoverable `SAME_EVENT` or `DIFFERENT_EVENTS` label. Label counts are `{labels.label.value_counts().to_dict()}`; parse status counts are `{labels.parse_status.value_counts().to_dict()}`. The majority were explicit parser failures conservatively represented as `UNCERTAIN`, not converted to boundaries.

## Method comparison

On the `{len(eligible)}` eligible rows, C1−C0 accuracy is `{c1mean:.4f}` (paired bootstrap 95% CI `{c1lo:.4f}`, `{c1hi:.4f}`); K3−C1 is `{k3mean:.4f}` (95% CI `{k3lo:.4f}`, `{k3hi:.4f}`). These estimates do not meet the frozen minimum of 28 eligible cases and cannot support a scientific continuity conclusion.

## Decision

`VLM_CONTINUITY_DECISION = {decision}`.

The study is a failed-to-be-informative cross-family sanity probe, not negative semantic evidence against C1/K3. It leaves the reference-circularity risk **UNRESOLVED**, retains `REAL_HUMAN_VALIDATION = PENDING`, and forbids retuning/repeating the same cases to repair the judge output format.
"""
    (OUT/"VLM_CONTINUITY_ANALYSIS.md").write_text(report,encoding="utf-8")
    (OUT/"VLM_CONTINUITY_DECISION.md").write_text(f"# Independent VLM Continuity Decision\n\n`VLM_CONTINUITY_DECISION = {decision}`\n\nReason: only `{len(eligible)}/40` labels are eligible under the frozen schema; `{int(labels.parse_status.eq('PARSE_FAILURE_COERCED_TO_UNCERTAIN').sum())}/40` were parser failures conservatively retained as `UNCERTAIN`. No reserve cases are unlocked because the same judge/schema failure offers no evident information gain.\n",encoding="utf-8")
    reviewer=f"""# Reviewer Attack Matrix After Independent VLM Study

| Risk | Current answer |
|---|---|
| R1: only K3-reference circularity? | **Unresolved.** The blind cross-family judge was not informative enough (`{len(eligible)}/40` eligible) to corroborate/rebut it. |
| R2: gap-only too trivial? | Still a concern. P0 only establishes a conditional reconstruction effect; no independent semantic confirmation was added. |
| R3: independent judge sees false merges? | **Inconclusive**, because parser-valid continuity labels are too few. |
| R4: K3 beyond C1? | **Inconclusive**; do not claim extra K3 value. |
| R5: why query processing rather than smoothing? | Existing framing remains provisional: event-relation materialization affects query results, but independent semantic validation remains required. |
"""
    (OUT/"REVIEWER_ATTACK_MATRIX_AFTER_VLM.md").write_text(reviewer,encoding="utf-8")
    CONV.mkdir(exist_ok=True)
    update=f"""# VLM Validation Update

`VLM_CONTINUITY_DECISION = {decision}`. A frozen single cross-family SmolVLM2 judge was executed on the exact 40 blinded human-primary cases. All 40 raw outputs were retained, but only `{len(eligible)}` met/recovered the frozen SAME/DIFFERENT label schema; `{int(labels.parse_status.eq('PARSE_FAILURE_COERCED_TO_UNCERTAIN').sum())}` were conservatively `UNCERTAIN` parser failures. The protocol's objective minimum (`28`) was not met.

This is neither support nor refutation of the P0 C1/K3 phenomenon. It demonstrates that a small local cross-family VLM cannot be treated as a reliable independent continuity adjudicator under this protocol. The untouched real-human benchmark remains the next decisive evidence source.
"""
    (CONV/"VLM_VALIDATION_UPDATE.md").write_text(update,encoding="utf-8")
    paper=f"""# Paper Mainline Decision After Independent VLM Study

`PAPER_MAINLINE_DECISION_AFTER_VLM = WEAK_CURRENTLY`.

The blinded cross-family VLM study was pre-frozen and method-blind, but it was scientifically **inconclusive**, not confirmatory: only `{len(eligible)}/40` outputs were schema-eligible. Thus it cannot reduce the K3-defined model-reference circularity risk. Existing P0 evidence remains a controlled conditional reconstruction result; it does not establish independent humanlike event continuity. The single decisive next action is the already-frozen real-human 40-case continuity annotation.
"""
    (CONV/"PAPER_MAINLINE_DECISION_AFTER_VLM.md").write_text(paper,encoding="utf-8")
    state=json.loads((OUT/"VLM_CONTINUITY_STATE.json").read_text()); state.update({"status":"ANALYSIS_COMPLETE","analysis_complete":True,"primary_decision":decision,"paper_mainline_after_vlm":"WEAK_CURRENTLY","eligible_continuity_cases":len(eligible),"human_validation_status":"PENDING_UNMODIFIED"})
    (OUT/"VLM_CONTINUITY_STATE.json").write_text(json.dumps(state,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"eligible":len(eligible),"uncertain":int(labels.label.eq('UNCERTAIN').sum()),"c1_c0":c1mean,"k3_c1":k3mean,"decision":decision,"paper":"WEAK_CURRENTLY"},sort_keys=True))

if __name__=="__main__": main()
