#!/usr/bin/env python3
"""Pre-annotation P1-B v1.2 hardening and immutable freeze."""
from __future__ import annotations
import hashlib, json
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import sys

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs/p1_independent_geometry_replication_v1'
sys.path.insert(0,str(ROOT/'src'))
from garc_eval.p1b_protocol_v1_2 import canonical_hash, temporal_region_count, trace_proxy_metadata

def sha(p:Path)->str:
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(1<<20),b''): h.update(block)
 return h.hexdigest()
def dump(p:Path,x): p.write_text(json.dumps(x,indent=2,sort_keys=True,allow_nan=False)+'\n')

def main():
 labels=[line for line in (OUT/'HUMAN_EVENT_LABELS.jsonl').read_text().splitlines() if line.strip()]
 if labels:
  (OUT/'P1B_PROTOCOL_REVIEW.md').write_text('# P1-B protocol review\n\n`PROTOCOL_AMENDMENT_TOO_LATE = TRUE`\n')
  raise SystemExit('PROTOCOL_AMENDMENT_TOO_LATE = TRUE')
 trace=pd.read_csv(OUT/'TRACE_POPULATION.csv'); oldpairs=pd.read_csv(OUT/'PRIMARY_GEOMETRY_PAIR_MANIFEST.csv')
 metadata=pd.DataFrame([trace_proxy_metadata(row) for row in trace.to_dict('records')])
 audit=pd.concat([trace[['trace_instance_id','source_trace_instance_id','video_id','query_id','proxy_id','policy_id','generator_family','seed','budget']].reset_index(drop=True),metadata],axis=1)
 audit['cross_proxy_role']=audit.proxy_dependent.map({True:'PROXY_SPECIFIC',False:'SHARED_CONTROL'})
 audit.to_csv(OUT/'TRACE_PROXY_DEPENDENCE_AUDIT.csv',index=False)

 # Recompute the historical axis exactly; never select or change membership.
 lookup=trace.set_index('trace_instance_id'); conflicts=[]; rows=[]
 for row in oldpairs.to_dict('records'):
  a=lookup.loc[row['trace_a_better_geometry']]; b=lookup.loc[row['trace_b_worse_geometry']]
  pa=temporal_region_count([int(x.rsplit('_u',1)[1]) for x in json.loads(a.queried_unit_ids)])
  pb=temporal_region_count([int(x.rsplit('_u',1)[1]) for x in json.loads(b.queried_unit_ids)])
  if pa!=int(row['regions_touched_a']) or pb!=int(row['regions_touched_b']) or pa<=pb: conflicts.append(row)
  am=trace_proxy_metadata(a.to_dict()); bm=trace_proxy_metadata(b.to_dict())
  rows.append(row|{'pair_content_hash':canonical_hash({'a':row['trace_a_better_geometry'],'b':row['trace_b_worse_geometry']}),
   'attribution_mapping':'ANCHOR_ASSIGNED_EVENT','trace_a_content_hash':am['trace_content_hash'],'trace_b_content_hash':bm['trace_content_hash'],
   'trace_a_proxy_dependent':am['proxy_dependent'],'trace_b_proxy_dependent':bm['proxy_dependent'],
   'trace_a_proxy_origin':am['proxy_origin'],'trace_b_proxy_origin':bm['proxy_origin'],'shared_control_weighting':'count once per video-query effect; never an independent proxy replication'})
 if conflicts:
  (OUT/'P1B_PROTOCOL_REVIEW.md').write_text('# P1-B protocol review\n\n`PRIMARY_PAIR_PROTOCOL_CONFLICT = TRUE`\n')
  raise SystemExit('PRIMARY_PAIR_PROTOCOL_CONFLICT')
 v12=pd.DataFrame(rows); v12.to_csv(OUT/'PRIMARY_GEOMETRY_PAIR_MANIFEST_V1_2.csv',index=False)

 region='''# Frozen temporal-region definition — P1-B v1.2

`number_of_temporal_regions_touched` is the number of maximal connected components of queried candidate units on the released V3 candidate lattice. It is not a count of fixed macro-windows.

- Atomic temporal-region width: 10.0 seconds.
- Origin: video time 0.0 seconds.
- Boundary: half-open `[10k,10(k+1))`; the final partial cell ends at video duration.
- Unit assignment: each released unit has frozen `candidate_order=k` and belongs to exactly atomic cell k.
- Partial boundary: the last shortened unit remains one atomic cell.
- Adjacent queried units: consecutive candidate orders belong to one maximal touched region; a missing order splits regions.
- One queried unit cannot touch multiple geometry regions.
- Duplicates, if present, are removed before component counting.
- Implementation: `temporal_region_count` in `src/garc_eval/p1b_protocol_v1_2.py`.

All 198 memberships and orientations reproduce exactly under this definition. Region size/alignment cannot change after annotation begins.
'''; (OUT/'TEMPORAL_REGION_DEFINITION.md').write_text(region)
 attribution='''# Frozen human-event attribution protocol — P1-B v1.2

## Primary: ANCHOR_ASSIGNED_EVENT

Each verified-positive unit credits at most one adjudicated human event. The anchor is a pre-existing unit anchor when supplied; otherwise it is the frozen interval center `(start+end)/2`. Event containment is half-open. If overlapping events contain the anchor, choose maximum unit/event temporal overlap; an exact tie goes to lexically earliest frozen `event_id`. If no event contains the anchor, give no credit.

Primary endpoints are `distinct_human_events_anchor_assigned`, `human_event_coverage_anchor_assigned`, `events_with_zero_anchor_assigned_evidence`, and `events_with_1plus_anchor_assigned_evidence`.

## Secondary: OVERLAP_ANY_EVENT

Every human event with positive temporal overlap receives credit. This mapping may credit multiple events and is sensitivity-only. Report `distinct_human_events_overlap_any` and `human_event_coverage_overlap_any`; it cannot establish the primary claim. Final reporting must state whether primary and sensitivity directions agree.
'''; (OUT/'HUMAN_EVENT_ATTRIBUTION_PROTOCOL.md').write_text(attribution)
 gate='''# Frozen human-reference quality gate — P1-B v1.2

Agreement uses one-to-one maximum-IoU matching and reports IoU>0 plus sensitivities at 0.1, 0.3, and 0.5, event existence, count differences, unmatched fraction, median matched tIoU, start/end disagreement, and boundary/semantic ambiguity.

`HUMAN_REFERENCE_QUALITY=INSUFFICIENT` if any holds: (A) event existence differs in at least 3/6 cases; (B) event-count difference exceeds `max(2, 50% of larger count)` in at least 3/6 cases; (C) global one-to-one matched-event fraction at IoU>0 is below 0.50; (D) blinded semantic review documents systematic different query interpretation in multiple cases. Otherwise it is `ADJUDICATION_ELIGIBLE`.

IoU 0.3/0.5 are boundary diagnostics and do not mechanically fail the reference. Failure prohibits adjudication and requires protocol review plus full six-case reannotation; difficult cases cannot be deleted.
'''; (OUT/'REFERENCE_QUALITY_GATE.md').write_text(gate)
 cross='''# Frozen cross-proxy analysis protocol — P1-B v1.2

Proxy-dependent StaticProxyRank/MMR traces retain their YOLO or optical-flow origin. UniformTemporal, CoverageFirst, and SeededTemporalHash are `SHARED_CONTROL`. Identical shared-control trace content is counted once at the video-query level and cannot be presented as two independent proxy observations.

Pair effects aggregate first within video-query × proxy; shared controls receive one video-query contribution through frozen equal-weight/deduplicated aggregation. Proxy robustness reports YOLO and FLOW effects only where the proxy-dependent endpoint exists. The two proxy dimensions remain within-cluster robustness checks, never independent source samples.
'''; (OUT/'CROSS_PROXY_ANALYSIS_PROTOCOL.md').write_text(cross)

 p=json.loads((OUT/'P1_PROTOCOL.json').read_text()); p['protocol_id']='GVAQP_P1_INDEPENDENT_EVENT_EVIDENCE_GEOMETRY_REPLICATION_V1_2'; p['version']='1.2'
 p['primary_endpoints']={'distinct_human_events_anchor_assigned':'primary one-unit-at-most-one-event endpoint','human_event_coverage_anchor_assigned':'primary coverage endpoint','overlap_any':'secondary sensitivity only','C1_EventF1':'secondary materializer endpoint only'}
 p['inference']={'primary_unit':'video-query cluster (6)','source_robustness':'source video (3)','aggregation_order':['pairs within video-query × proxy','proxies/shared-control-deduplicated within video-query','macro across 6 video-query clusters','direction across 3 source videos'],'cell_level_p_value_cannot_drive_pass':True,'generalization_primary':'Leave-One-Video-Out','generalization_secondary':'Leave-One-VideoQuery-Out','lovq_cannot_rescue_negative_lovo':True,'bootstrap':'10000 whole video-query cluster resamples, seed 20260813','models':['linear','ridge primary diagnostic','depth-2 small tree']}
 p['p1_final_gate_operationalization']['public_geometry_lift']='yield-only minus public-geometry MAE >=0.02 in primary LOVO; LOVQO is secondary and cannot rescue negative LOVO'
 p.pop('protocol_hash',None); p['protocol_hash']=canonical_hash(p); dump(OUT/'P1_PROTOCOL.json',p)
 hp=json.loads((OUT/'HUMAN_REFERENCE_PROTOCOL.json').read_text()); hp.update({'protocol_id':'P1_INDEPENDENT_HUMAN_EVENT_REFERENCE_V1_2','version':'1.2','reference_quality_gate':{'hard_failure_A':'event existence differs in >=3/6 cases','hard_failure_B':'count difference >max(2,50% larger count) in >=3/6 cases','hard_failure_C':'global matched-event fraction at IoU>0 <0.50','hard_failure_D':'systematic semantic misunderstanding in multiple cases','otherwise':'ADJUDICATION_ELIGIBLE'},'primary_attribution':'ANCHOR_ASSIGNED_EVENT','secondary_attribution':'OVERLAP_ANY_EVENT'})
 hp.pop('protocol_hash',None); hp['protocol_hash']=canonical_hash(hp); dump(OUT/'HUMAN_REFERENCE_PROTOCOL.json',hp)
 status=json.loads((OUT/'ANNOTATION_STATUS.json').read_text()); status.update({'annotation_protocol_hash':hp['protocol_hash'],'protocol_version':'1.2','status':'WAITING_HUMAN_REFERENCE','agreement_status':'NOT_RUN','adjudication_status':'NOT_STARTED'}); dump(OUT/'ANNOTATION_STATUS.json',status)
 schema=json.loads((OUT/'ANNOTATION_EXPORT_SCHEMA.json').read_text()); schema['schema_id']='P1B_ANNOTATION_EXPORT_V1_2'; schema['protocol_hash']=hp['protocol_hash']; dump(OUT/'ANNOTATION_EXPORT_SCHEMA.json',schema)
 oldfreeze=json.loads((OUT/'P1B_FREEZE_MANIFEST.json').read_text()); oldfreeze.update({'primary_geometry_axis':'number_of_temporal_regions_touched','region_definition_hash':sha(OUT/'TEMPORAL_REGION_DEFINITION.md'),'region_implementation_hash':sha(ROOT/'src/garc_eval/p1b_protocol_v1_2.py'),'superseded_by':'P1B_PROTOCOL_V1_2_FREEZE.json'}); dump(OUT/'P1B_FREEZE_MANIFEST.json',oldfreeze)

 summary=audit.groupby(['cross_proxy_role']).size().to_dict(); unique_shared=audit[audit.cross_proxy_role=='SHARED_CONTROL'].trace_content_hash.nunique(); unique_dep=audit[audit.cross_proxy_role=='PROXY_SPECIFIC'].trace_content_hash.nunique()
 (OUT/'CROSS_PROXY_ANALYSIS_PROTOCOL.md').write_text(cross+f"\nAudit totals: {unique_dep} unique proxy-dependent trace contents; {unique_shared} unique shared-control trace contents.\n")
 review='''# P1-B protocol review

## PASS

- Zero formal annotations and no human outcome seen.
- Historical region implementation was reconstructed and all 198 orientations reproduced.
- Anchor attribution, quantitative reference gate, source-level inference, primary LOVO, shared-control deduplication, and fail-closed state transitions are explicit.

## REQUIRES_AMENDMENT

- Pre-annotation v1.1 used overlap-any as primary attribution and did not fully specify the historical connected-component region semantics.
- Its reference gate omitted the requested count rule and IoU>0 matching fraction; LOVO and LOVQO were not ordered.
- Generic static serving required an allowlist privacy hardening.

These issues are amended in v1.2 before the first formal annotation.

## BLOCKING_ISSUES

None after v1.2 validation. Pair membership did not change.
'''; (OUT/'P1B_PROTOCOL_REVIEW.md').write_text(review)
 print(json.dumps({'status':'HARDENED_PRE_FREEZE','pairs':len(v12),'conflicts':0,'unique_proxy_dependent':unique_dep,'unique_shared_control':unique_shared,'human_outcome_seen':False},sort_keys=True))
if __name__=='__main__': main()
