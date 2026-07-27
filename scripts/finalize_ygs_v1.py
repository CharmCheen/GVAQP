#!/usr/bin/env python3
"""Finalize reports and artifact manifest for the YOLO-guided SCAN loop."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs/scan_innovation_agentic_loop_v1'; REPORTS=OUT/'reports'

def sha256(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        while chunk:=f.read(1<<20): h.update(chunk)
    return h.hexdigest()
def write(path:Path,text:str)->None:
    path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(path.suffix+'.tmp'); tmp.write_text(text.rstrip()+'\n'); tmp.replace(path)
def json_write(path:Path,value:object)->None:
    tmp=path.with_suffix(path.suffix+'.tmp'); tmp.write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n'); tmp.replace(path)

def main()->None:
    h0=json.loads((OUT/'hypotheses/YGS-H000.json').read_text()); h1=json.loads((OUT/'hypotheses/YGS-H001.json').read_text())
    h2=json.loads((OUT/'hypotheses/YGS-H002.json').read_text()); h3=json.loads((OUT/'hypotheses/YGS-H003.json').read_text())
    winner=pd.DataFrame(h0['observed_winners']).set_index('video_id'); q1={x['video_id']:x for x in h1['recomputed_metrics']}; q2={x['video_id']:x for x in h2['metrics']}; q3={x['video_id']:x for x in h3['metrics']}
    short,long='PSP_V0_SHORT','PSP_V1_LONG'
    decision={
      'final_state':'SAFE_COVERAGE_BASELINE_REMAINS_STRONGEST','selected_new_yolo_guided_algorithm':False,
      'scheduler_layer':'PROHIBITED_STATIC_OBSERVABILITY_GATE_FAILED','physical_candidate_validation':'NOT_RUN_BY_CONTRACT',
      'runnable_fallback':{'class':'garc_eval.scan_scheduler.SafeCoveragePolicy','config':'configs/safe_coverage_scan.yaml','cli':'scripts/run_safe_coverage_scan.py'},
      'strongest_supported_conclusion':'Large offline scheduling headroom exists, but tested causal YOLO/motion previews cannot identify it robustly after preview cost.',
      'claim_scope':'two design videos; frozen full-context Oracle pseudo-reference; controlled-warm hardware evidence; no cross-video generalization claim',
      'hypotheses':{'YGS-H000':h0['status'],'YGS-H001':h1['status'],'YGS-H002':h2['status'],'YGS-H003':h3['status']},
    }
    json_write(OUT/'final_decision.json',decision)
    report=f'''# SCAN Innovation Research Report

## Final answer

The defensible final state is `SAFE_COVERAGE_BASELINE_REMAINS_STRONGEST`.
There is substantial *offline* SCAN scheduling headroom, but this study did
not establish a causal, cost-effective YOLO-guided signal that can exploit it
on both videos. Therefore no region-value scheduler, batching rule, novelty
exit, or new physical candidate was admitted.

This is not a conclusion that SCAN cannot be optimized. It is the narrower
conclusion that the tested policy-visible signals do not identify the
headroom reliably enough to justify an adaptive scheduler.

## Decisive evidence

| Evidence | Short video | Long video | Meaning |
|---|---:|---:|---|
| Best causal full-horizon AUC | {winner.loc[short].full_horizon_auc:.3f} ({winner.loc[short].full_horizon_winner}) | {winner.loc[long].full_horizon_auc:.3f} ({winner.loc[long].full_horizon_winner}) | simple coverage order matters |
| Offline oracle AUC | {winner.loc[short].offline_oracle_full_auc:.3f} | {winner.loc[long].offline_oracle_full_auc:.3f} | large noncausal upper headroom remains |
| Q1-L Recall@20 / AUC | {q1[short]['recall_at_20']:.3f} / {q1[short]['ranking_event_recall_auc']:.3f} | {q1[long]['recall_at_20']:.3f} / {q1[long]['ranking_event_recall_auc']:.3f} | stable weak detection signal |
| Q2 high-rate YOLO Recall@20 / AUC | {q2[short]['recall_at_20']:.3f} / {q2[short]['ranking_event_recall_auc']:.3f} | {q2[long]['recall_at_20']:.3f} / {q2[long]['ranking_event_recall_auc']:.3f} | more detections do not resolve ambiguity |
| Q3 directional motion Recall@20 / AUC | {q3[short]['recall_at_20']:.3f} / {q3[short]['ranking_event_recall_auc']:.3f} | {q3[long]['recall_at_20']:.3f} / {q3[long]['ranking_event_recall_auc']:.3f} | small long-only effect, not robust |
| Q1/Q2/Q3 cost ratio | {h1['actual_preview_cost_ratio']:.3f} / {h2['combined_preview_cost_ratio']:.3f} / {h3['combined_preview_cost_ratio']:.3f} | same joint accounting | all legal, so rejection is not caused by cost-cap violation |

The frozen static Gate required Recall@20 >= 0.40 on both videos, strict
improvement over Q1-L on both, nonnegative primary net yield on both, and a
common budget with positive gain on both. Q2 and Q3 failed these conditions.
At 20% total cost Q2 changed event count by -3/+7 (short/long); Q3 by -5/+1.
This is video-unstable and preview cost removes the apparent low-budget gain.

## What the experiments imply

Observed: coverage winners vary with video and horizon. At physical 60 seconds
the tested winners are Sequential on the short video and Uniform-prefix on the
long video. At the full replay horizon they are Anytime Largest-Gap and Macro
Largest-Gap. Thus there is no evidence for one universal ordering winner.

Derived: detection sampling density is not the dominant bottleneck. Q2 used
ten-times the Q1 sampling rate on the uncertainty-selected subset yet did not
improve short-video ranking and degraded the long-video primary recall.

Working hypothesis rejected: directional local motion alone is enough to turn
Q1 into a cross-video value estimator. Q3 improves only the long video by
about 0.005 Recall@20 and leaves the short video unchanged.

Main competing explanation: the pseudo-reference event value depends on
longer temporal/interaction semantics not captured by sparse detection or
short-window flow. Another possibility is that two design videos are too few
to identify a stable mapping. Neither explanation licenses a scheduler now.

## Innovation status and scheduler design

The intended innovation was an uncertainty-escalated residual-value scheduler:
global low-rate YOLO, selective higher-fidelity sensing near the allocation
boundary, explicit competition between predicted new-event value and coverage
opportunity cost, and a recoverable one-step deviation. This would be a real
mechanistic contribution, not merely “YOLO + Largest-Gap”.

It was not implemented as a selected method because its prerequisite value
signal failed. If a future independent asset set passes the static Gate, the
next legal scheduler is:

1. produce `u_C`, the best global coverage action;
2. produce `u_R`, the best region action by `(p_new + lambda*uncertainty)/cost`;
3. execute `u_R` only if it beats the nonzero coverage opportunity utility by
   a frozen margin, preserves the maximum-gap bound, and leaves enough budget
   for coverage-only recovery;
4. otherwise execute `u_C`;
5. only after replay acceptance, test 1/2/4 contiguous units and novelty exits
   of 1/2 no-new-cluster actions.

Rejection trigger: any future signal that fails >=0.40 Recall@20 on either
complete held-out video, loses after actual preview cost, or improves only one
video must again fall back to coverage.
'''
    write(REPORTS/'SCAN_INNOVATION_REPORT.md',report)
    method='''# Safe Coverage SCAN — Method Specification

```text
FINAL_STATE = SAFE_COVERAGE_BASELINE_REMAINS_STRONGEST
DEFAULT_RUNNABLE_POLICY = ANYTIME_LARGEST_GAP
YOLO_GUIDANCE = DISABLED_BY_FAILED_STATIC_GATE
POLICY_INPUT = PublicScanState only
TRAINING = NONE
REFERENCE_ACCESS = PROHIBITED
```

`SafeCoveragePolicy` is a thin audited package over the frozen Sequential,
Uniform-prefix, Anytime Largest-Gap, and Macro Largest-Gap implementations.
The default is Anytime Largest-Gap because it has an anytime geometric
coverage invariant and was the short-video full-horizon winner. The evidence
does not justify silently choosing a policy from video identity, so alternative
modes must be selected explicitly.

Evidence-specific choices: Sequential was strongest on the short video's
physical 60-second horizon; Uniform-prefix on the long video's physical
60-second horizon; Anytime Largest-Gap on the short full replay horizon; Macro
Largest-Gap on the long full replay horizon. These are development findings,
not general routing rules.
'''
    write(REPORTS/'METHOD_SPEC.md',method)
    usage='''# Usage

Generate a public-state-only order:

```bash
python scripts/run_safe_coverage_scan.py \\
  --video-id PSP_V0_SHORT \\
  --max-actions 20 \\
  --output /tmp/scan_order.csv
```

Choose another frozen coverage mechanism explicitly:

```bash
python scripts/run_safe_coverage_scan.py \\
  --video-id PSP_V1_LONG \\
  --policy MACRO_REGION_LARGEST_GAP \\
  --max-actions 20
```

Inspect frozen evidence:

```bash
python scripts/benchmark_safe_coverage_scan.py
```

Python API:

```python
from garc_eval.scan_scheduler import SafeCoverageConfig, SafeCoveragePolicy
policy = SafeCoveragePolicy(SafeCoverageConfig("ANYTIME_LARGEST_GAP", 3))
unit_id = policy.choose_next_unit(public_state)
```

The CLI generates a causal order. Integration with the physical executor must
pass the evolving `PublicScanState` after each completed action and retain the
executor's deadline/admission logic.
'''
    write(REPORTS/'USAGE.md',usage)
    failure='''# Failure Analysis

Q1-L was deterministic and cheap but missed the Recall@20 threshold on both
videos. Q2 falsified the “insufficient detection sampling” explanation: its
selected high-rate YOLO features did not strictly improve Q1 on either video.
Q3 tested a materially different signal; directional residual flow produced a
small long-video-only improvement and no short-video improvement.

The strongest negative evidence is cost-adjusted: Q2 at 20% total budget was
-3/+7 events and Q3 was -5/+1. A macro average could hide the short-video
failure, so both were rejected. No scheduler replay or new physical runs were
performed because doing so after the static Gate failed would test a mechanism
whose input value is not established.

Unresolved: only two design videos exist, event truth is a frozen Oracle
pseudo-reference, and no independent validation/test videos exist. A future
branch should begin with additional complete videos or a new preregistered
longer-context observable, not more tuning of Q2/Q3.
'''
    write(REPORTS/'FAILURE_ANALYSIS.md',failure)
    final='''# Final Algorithm Decision

```text
FINAL_STATE = SAFE_COVERAGE_BASELINE_REMAINS_STRONGEST
SELECTED_YOLO_GUIDED_SCAN_ALGORITHM = NONE
RUNNABLE_FALLBACK = garc_eval.scan_scheduler.SafeCoveragePolicy
SCHEDULER_LAYER = PROHIBITED
NEW_PHYSICAL_VALIDATION = NOT_ALLOWED_AFTER_STATIC_GATE_FAILURE
```

The runnable fallback is delivered and tested. It is not presented as a new
YOLO-guided innovation. The experimental contribution is a falsified design:
low-rate YOLO has ranking signal, but selective high-rate detection and
directional motion do not make that signal robust or cost-effective enough to
control SCAN on both videos.
'''
    write(REPORTS/'FINAL_ALGORITHM_DECISION.md',final)
    # Hash every final artifact except the manifest itself.
    manifest={}
    for path in sorted(OUT.rglob('*')):
        if path.is_file() and path.name!='artifact_hash_manifest.json' and not path.name.endswith('.tmp'):
            manifest[str(path.relative_to(OUT))]={'sha256':sha256(path),'bytes':path.stat().st_size}
    json_write(OUT/'artifact_hash_manifest.json',{'artifact_count':len(manifest),'artifacts':manifest})
    print(json.dumps(decision,indent=2))

if __name__=='__main__': main()
