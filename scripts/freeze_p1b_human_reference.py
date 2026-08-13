#!/usr/bin/env python3
"""One-time pre-annotation P1-B protocol audit and freeze."""
from __future__ import annotations
import hashlib, json
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs/p1_independent_geometry_replication_v1'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def chash(x): return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def dump(p,x): p.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')

def main():
 raw=OUT/'HUMAN_EVENT_LABELS.jsonl'
 if any(line.strip() for line in raw.read_text().splitlines()): raise RuntimeError('formal annotation already exists; amendment forbidden')
 existing=OUT/'P1B_FREEZE_MANIFEST.json'
 if existing.exists():
  manifest=json.loads(existing.read_text())
  for name in manifest['artifact_hashes']:
   manifest['artifact_hashes'][name]=sha(OUT/name)
  manifest['c1']['sha256']=sha(ROOT/'scripts/resume_p1_independent_geometry_replication.py')
  manifest['annotation_ui']={'source':'scripts/serve_p1_independent_geometry_reference.py','sha256':sha(ROOT/'scripts/serve_p1_independent_geometry_reference.py'),'default_port':8767}
  manifest['preannotation_engineering_refresh_at_utc']=datetime.now(timezone.utc).isoformat()
  dump(existing,manifest)
  print(json.dumps({'status':'P1B_FROZEN_WAITING_HUMANS','refresh':'preannotation engineering hashes only','human_label_records':0},sort_keys=True))
  return
 q='''# Frozen P1-B query definitions — version 1.1

These definitions are semantic and continuous-time. They never refer to units, fixed gaps, proxy scores, traces, C1/K3, or algorithm output.

## Q_DRIVER_RESPONSE_V1 — Driver response required

**Definition/inclusion.** A maximal continuous episode in which visible conditions require an attentive ego driver to noticeably brake, slow, yield, or change path. Qualifying causes include a road user entering or threatening the ego path, a suddenly slowing/stopped lead vehicle, traffic control requiring a marked response, or a visible obstacle/road condition requiring marked speed/path change.

**Exclusion.** Exclude normal steady driving, ordinary following without marked response, distant/non-actionable hazards, and responses completed before the visible episode.

**Boundaries.** Start at the first visible, actionable onset requiring the response. End when the constraint clears and normal progress can resume. A brief occlusion or momentary easing remains inside one event when the same cause and response obligation persist. Split adjacent occurrences only after the first obligation clearly ends and a new actionable cause/obligation begins. Simultaneous actors/causes form one event when they create one inseparable response episode; overlapping but independently actionable obligations may be separate events and may temporally overlap.

## Q_VULNERABLE_ROAD_USER_CONFLICT_V1 — Vulnerable-road-user conflict

**Definition/inclusion.** A maximal continuous episode in which a pedestrian, cyclist, motorcyclist, or scooter rider enters, crosses, or occupies the ego vehicle's immediate travel path such that the ego driver must yield, brake, slow markedly, or steer to avoid conflict.

**Exclusion.** Exclude road users clearly separated from the ego path, ordinary adjacent traffic, and conflicts completed before the displayed episode.

**Boundaries.** Start when path conflict first becomes visible and actionable. End when the road user clears the immediate path or the ego vehicle safely passes and the conflict no longer constrains motion. A brief occlusion remains inside one event if the same conflict plausibly continues. Split only after one conflict resolves and a new conflict begins. Multiple actors form one event when they jointly create an inseparable conflict episode; independently actionable overlapping conflicts may be separate, overlapping events.

## Rules common to both queries

- **No-event:** submit an explicit empty event list and `event_exists=false`.
- **Boundary ambiguity:** mark `boundary_ambiguous=true` when either best boundary could reasonably shift by more than two seconds; retain the best estimates.
- **Semantic ambiguity:** mark `semantic_ambiguity=true` when whether the occurrence satisfies the query remains genuinely uncertain after full-video review; retain the best decision and explain briefly.
- Uncertainty is recorded, never resolved by consulting algorithmic artifacts or by snapping boundaries to fixed time grids.
'''
 guide='''# Frozen P1-B independent annotation guide — version 1.1

Watch each full raw video and annotate maximal semantic temporal events under the frozen query. You may seek and replay freely. The interface and annotators must never access proxy/detection/flow scores, candidate units, VERIFY outcomes, trace/policy identities, C0/C1/K3 events, pseudo-reference, geometry, matched pairs, EventF1, or model predictions.

For every event record start/end seconds, boundary ambiguity, semantic ambiguity, and an optional note. Events may overlap when they are independently actionable semantic occurrences. Do not merge or split by elapsed gap length. Submit an explicit empty event list for a no-event case.

ANNOTATOR_A and ANNOTATOR_B each complete all six cases independently using stable distinct IDs. Neither may inspect or discuss the other's event locations until both submissions are complete. Saves are append-only revisions; the latest revision is used only after completeness validation. Adjudication starts only after both complete exports pass validation and remains blinded to all algorithmic artifacts.

Agreement is computed before adjudication using one-to-one maximum-IoU matching at IoU thresholds 0.1, 0.3, and 0.5, plus raw best-overlap tIoU, boundary disagreement, unmatched counts, and ambiguity rates. Difficult cases are never deleted.
'''
 (OUT/'QUERY_DEFINITIONS.md').write_text(q); (OUT/'ANNOTATION_GUIDE.md').write_text(guide)
 old=json.loads((OUT/'HUMAN_REFERENCE_PROTOCOL.json').read_text())
 amendment={'amendment_id':'P1B_PROTOCOL_AMENDMENT_001','reason':'Pre-annotation audit found temporary-interruption, adjacent/overlapping occurrence, semantic-ambiguity, and explicit no-event rules were not fully machine-bound. Zero formal labels existed.','prior_protocol_hash':old['protocol_hash'],'labels_before_amendment':0,'changes':['semantic continuous-time interruption/split/multiple-actor/overlap rules','semantic_ambiguity field','explicit no-event record','agreement IoU sensitivities 0.1/0.3/0.5'],'created_before_first_annotation':True}
 amendment['amendment_hash']=chash(amendment); dump(OUT/'P1B_PROTOCOL_AMENDMENT.json',amendment)
 proto=old|{'protocol_id':'P1_INDEPENDENT_HUMAN_EVENT_REFERENCE_V1_1','version':'1.1','status':'ANNOTATION_PROTOCOL_FROZEN','annotation_protocol_frozen':True,'amendment_hash':amendment['amendment_hash'],'required_event_fields':['annotation_id','annotator_id','video_id','query_id','event_index','start_time','end_time','boundary_ambiguous','semantic_ambiguity','optional_note','adjudication_status'],'agreement_iou_sensitivity':[0.1,0.3,0.5],'semantic_rules_independent_of_fixed_temporal_gap':True}
 proto.pop('protocol_hash',None); proto['protocol_hash']=chash(proto); dump(OUT/'HUMAN_REFERENCE_PROTOCOL.json',proto)
 pairs=pd.read_csv(OUT/'TRACE_PAIR_MANIFEST.csv'); primary=pairs[(pairs.match_type=='EXACT_YIELD')&(pairs.better_regions>pairs.worse_regions)].copy()
 primary=primary.rename(columns={'better_geometry_trace_id':'trace_a_better_geometry','worse_geometry_trace_id':'trace_b_worse_geometry','better_regions':'regions_touched_a','worse_regions':'regions_touched_b'})
 primary['primary_geometry_axis']='number_of_temporal_regions_touched'; primary['frozen_before_human_labels']=True
 if len(primary) != 198: raise RuntimeError(f'expected 198 exact-yield primary pairs, found {len(primary)}')
 primary.to_csv(OUT/'PRIMARY_GEOMETRY_PAIR_MANIFEST.csv',index=False)
 schema={'schema_id':'P1B_ANNOTATION_EXPORT_V1_1','case_fields':['annotator_id','case_id','video_id','query_id','event_exists','events','saved_at_utc','protocol_hash'],'event_fields':['annotation_id','annotator_id','video_id','query_id','event_index','start_time','end_time','boundary_ambiguous','semantic_ambiguity','optional_note','adjudication_status'],'explicit_no_event':{'event_exists':False,'events':[]},'append_only':True,'latest_revision_per_annotator_case':True}
 dump(OUT/'ANNOTATION_EXPORT_SCHEMA.json',schema)
 (OUT/'ANNOTATION_PACKAGE_README.md').write_text('''# P1-B blinded human-reference package

1. From the repository root run `python scripts/serve_p1_independent_geometry_reference.py` and open `http://127.0.0.1:8767/`.
2. ANNOTATOR_A completes all six cases. ANNOTATOR_B independently completes the same six using the frozen guide. Do not exchange event locations.
3. Each case must be saved, including an explicit empty event list for no-event. Saves append revisions and never overwrite the raw log.
4. After both finish, run `python scripts/resume_p1_independent_geometry_replication.py --check`, then run it without flags. This validates all 12 case submissions and computes agreement only; it does not open method outcomes.
5. Only if the preregistered reference-quality gate passes, fill the generated `ADJUDICATION_TEMPLATE.csv` as `ADJUDICATED_EVENTS.csv`. The adjudicator remains blinded to all algorithmic artifacts. Run the resume script again to freeze the reference and execute P1.

Normal annotation mode must expose only raw video, query text, clock, guide, and annotation controls.
''')
 status={'status':'WAITING_HUMAN_REFERENCE','annotation_protocol_frozen':True,'annotation_protocol_hash':proto['protocol_hash'],'completed_cases':{'ANNOTATOR_A':0,'ANNOTATOR_B':0},'required_cases_per_annotator':6,'agreement_status':'NOT_RUN','adjudication_status':'NOT_STARTED','second_independent_annotator_required':True,'partial_annotations_must_not_be_analyzed':True}
 dump(OUT/'ANNOTATION_STATUS.json',status)
 artifacts=['SOURCE_OF_TRUTH.md','P1_PROTOCOL.json','TRACE_POPULATION.csv','TRACE_GEOMETRY_FEATURES.csv','TRACE_PAIR_MANIFEST.csv','MATCHED_EQUAL_YIELD_STRATA.csv','P1_TRACE_FEASIBILITY.md','P1_DESIGN_DECISION.md','PRIMARY_GEOMETRY_PAIR_MANIFEST.csv','QUERY_DEFINITIONS.md','ANNOTATION_GUIDE.md','HUMAN_REFERENCE_PROTOCOL.json','ANNOTATION_EXPORT_SCHEMA.json','ANNOTATION_PACKAGE_README.md']
 manifest={'freeze_id':'GVAQP_P1B_PREANNOTATION_FREEZE_V1','created_at_utc':datetime.now(timezone.utc).isoformat(),'human_label_records':0,'primary_geometry_axis':'number_of_temporal_regions_touched','primary_pairs':len(primary),'artifact_hashes':{x:sha(OUT/x) for x in artifacts},'evaluator':{'source':'src/garc_eval/accelerated_event_query/matching.py','sha256':sha(ROOT/'src/garc_eval/accelerated_event_query/matching.py')},'c1':{'definition':'GAP-ONLY merge consecutive positive evidence iff temporal gap <=10 seconds; secondary only','implementation_source':'scripts/resume_p1_independent_geometry_replication.py','sha256':sha(ROOT/'scripts/resume_p1_independent_geometry_replication.py')},'unit_semantics':'released V3 one-candidate-per-10-second unit','query_budget_semantics':'cached semantic invocation count; not wall clock','proxy_identities':['PROXY_A_YOLOV8N_OBJECT_MOTION','PROXY_B_OPTICAL_FLOW_VISUAL_DYNAMICS'],'primary_analysis':'exact yield; primary regions axis; materializer-independent human event touch/coverage; video-query inference','secondary_analysis':'near-yield, multivariate geometry, frozen C1 human reference, LOVO/LOVQO models','reference_quality_triage_gate':{'event_existence_agreement_min_clusters':4,'event_count_difference_le_1_min_clusters':4,'event_correspondence_fraction_iou_ge_0p1_min':0.5,'failure_action':'protocol amendment plus full six-case reannotation; no case deletion or outcome analysis'},'final_gate_note':'PASS/PARTIAL/FAIL follows frozen P1_PROTOCOL plus >=2/3 positive source videos and >=2 positive budgets; PARTIAL never authorizes P2'}
 dump(OUT/'P1B_FREEZE_MANIFEST.json',manifest)
 state=json.loads((OUT/'RESEARCH_STATE.json').read_text()); state.update({'annotation_protocol_hash':proto['protocol_hash'],'human_protocol_hash':proto['protocol_hash'],'p1a_trace_hash':sha(OUT/'TRACE_POPULATION.csv'),'primary_pair_manifest_hash':sha(OUT/'PRIMARY_GEOMETRY_PAIR_MANIFEST.csv'),'completed_cases':{'ANNOTATOR_A':0,'ANNOTATOR_B':0},'agreement_status':'NOT_RUN','adjudication_status':'NOT_STARTED','current_gate':'HUMAN_REFERENCE_REQUIRED','top_findings':['P1-A trace feasibility PASS','198 primary exact-yield pairs frozen on number_of_temporal_regions_touched','No formal human labels; second independent annotator required']}); dump(OUT/'RESEARCH_STATE.json',state)
 print(json.dumps({'status':'P1B_FROZEN_WAITING_HUMANS','primary_pairs':len(primary),'protocol_hash':proto['protocol_hash']},sort_keys=True))
if __name__=='__main__': main()
