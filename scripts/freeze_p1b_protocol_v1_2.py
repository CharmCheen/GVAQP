#!/usr/bin/env python3
"""Finalize immutable P1-B v1.2 after all pre-annotation validation."""
from __future__ import annotations
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs/p1_independent_geometry_replication_v1'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def main():
 if any(x.strip() for x in (OUT/'HUMAN_EVENT_LABELS.jsonl').read_text().splitlines()): raise SystemExit('human outcome exists; freeze forbidden')
 files=['outputs/p1_independent_geometry_replication_v1/QUERY_DEFINITIONS.md','outputs/p1_independent_geometry_replication_v1/ANNOTATION_GUIDE.md','outputs/p1_independent_geometry_replication_v1/HUMAN_REFERENCE_PROTOCOL.json','outputs/p1_independent_geometry_replication_v1/REFERENCE_QUALITY_GATE.md','outputs/p1_independent_geometry_replication_v1/TEMPORAL_REGION_DEFINITION.md','outputs/p1_independent_geometry_replication_v1/HUMAN_EVENT_ATTRIBUTION_PROTOCOL.md','outputs/p1_independent_geometry_replication_v1/PRIMARY_GEOMETRY_PAIR_MANIFEST_V1_2.csv','outputs/p1_independent_geometry_replication_v1/P1_PROTOCOL.json','outputs/p1_independent_geometry_replication_v1/CROSS_PROXY_ANALYSIS_PROTOCOL.md','outputs/p1_independent_geometry_replication_v1/TRACE_PROXY_DEPENDENCE_AUDIT.csv','outputs/p1_independent_geometry_replication_v1/ANNOTATION_BLINDING_AUDIT.md','scripts/serve_p1_independent_geometry_reference.py','scripts/resume_p1_independent_geometry_replication.py','src/garc_eval/p1b_protocol_v1_2.py']
 freeze={'freeze_id':'GVAQP_P1B_PROTOCOL_V1_2','created_at_utc':datetime.now(timezone.utc).isoformat(),'p1b_protocol_version':'1.2','annotation_protocol_frozen':True,'human_outcome_seen':False,'formal_annotation_start_authorized':True,'primary_geometry_axis':'number_of_temporal_regions_touched','region_definition_hash':sha(OUT/'TEMPORAL_REGION_DEFINITION.md'),'region_implementation_hash':sha(ROOT/'src/garc_eval/p1b_protocol_v1_2.py'),'generalization_primary':'Leave-One-Video-Out','generalization_secondary':'Leave-One-VideoQuery-Out','artifact_hashes':{f:sha(ROOT/f) for f in files}}
 (OUT/'P1B_PROTOCOL_V1_2_FREEZE.json').write_text(json.dumps(freeze,indent=2,sort_keys=True)+'\n')
 state=json.loads((OUT/'RESEARCH_STATE.json').read_text()); state.update({'annotation_protocol_hash':json.loads((OUT/'HUMAN_REFERENCE_PROTOCOL.json').read_text())['protocol_hash'],'protocol_hash':json.loads((OUT/'P1_PROTOCOL.json').read_text())['protocol_hash'],'p1b_protocol_version':'1.2','current_gate':'FORMAL_HUMAN_ANNOTATION','human_outcome_seen':False,'formal_annotation_start_authorized':True,'next_entrypoint':'python scripts/serve_p1_independent_geometry_reference.py','user_input_required':'ANNOTATOR_A and ANNOTATOR_B must independently complete all six cases.'}); (OUT/'RESEARCH_STATE.json').write_text(json.dumps(state,indent=2,sort_keys=True)+'\n')
 print(json.dumps({'status':'FROZEN','version':'1.2','human_outcome_seen':False},sort_keys=True))
if __name__=='__main__':main()
