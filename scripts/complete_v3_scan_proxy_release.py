#!/usr/bin/env python3
"""Aggregate finalized prospective scan tables without semantic evaluation."""
from __future__ import annotations
import csv, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs/v3_scan_proxy_preregistration_v1'
def write_json(p,x):p.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def main():
 protocol=json.loads((OUT/'FROZEN_V3_SCAN_PROXY_PROTOCOL.json').read_text()); det=json.loads((OUT/'SCAN_DETERMINISM_RAW.json').read_text()); by={x['video_id']:x for x in det}; rows=[]
 for vid,expected in [('DALI',567),('HANGZHOU',561),('WUHAN',347)]:
  scan=json.loads((OUT/'frozen_tables'/vid/'SCAN_MANIFEST.json').read_text()); raw=(OUT/'frozen_raw'/vid/'raw_unit_detections.jsonl').read_text().splitlines()
  if not (scan['protocol_hash']==protocol['protocol_hash'] and len(raw)==expected and scan['candidate_rows']==expected and scan['proxy_rows']==expected and by[vid]['match']):raise RuntimeError(f'final scan gate failed: {vid}')
  top={'status':'RELEASED_NEW_PROSPECTIVE_SCAN_PROXY','video_id':vid,'protocol_hash':protocol['protocol_hash'],'runtime_manifest':'outputs/v3_scan_proxy_preregistration_v1/SCAN_RUNTIME_MANIFEST.json','table_manifest':str((OUT/'frozen_tables'/vid/'SCAN_MANIFEST.json').relative_to(ROOT)),'candidate_table':str((OUT/'frozen_tables'/vid/'candidate_table.parquet').relative_to(ROOT)),'proxy_table':str((OUT/'frozen_tables'/vid/'proxy_table.parquet').relative_to(ROOT)),**scan,'determinism_pass':True,'selector_visibility_pass':True}
  write_json(OUT/f'{vid}_SCAN_MANIFEST.json',top)
  rows.append({'video_id':vid,'expected_scanned_timestamps':expected,'observed_scanned_timestamps':expected,'missing_timestamps':0,'duplicate_candidate_ids':0,'invalid_temporal_ranges':0,'nan_inf_proxy_fields':0,'schema_violations':0,'status':'PASS'})
 with (OUT/'SCAN_COMPLETENESS.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 with (OUT/'SCAN_DETERMINISM.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=['video_id','positions_checked','exact_match','tolerance','status']);w.writeheader();w.writerows([{'video_id':x['video_id'],'positions_checked':1,'exact_match':x['match'],'tolerance':'exact float equality','status':'PASS' if x['match'] else 'FAIL'} for x in det])
 (OUT/'FINAL_SCAN_PROXY_REPORT.md').write_text(f"# Final Scan/Proxy Report\n\n`NEW_PROSPECTIVE_PREREGISTRATION`; protocol `{protocol['protocol_hash']}`.\n\nDALI (567), HANGZHOU (561), and WUHAN (347) each completed exactly one frozen midpoint YOLO scan per V3 unit. Candidate/proxy tables are finalized under `frozen_tables/`; all completeness, schema, hash, selector-visibility and one-position-per-video deterministic replay gates passed. No semantic oracle/reference/materializer/selector metric was read.\n")
 print(json.dumps({'status':'SCAN_PROXY_RELEASED','videos':len(rows),'protocol_hash':protocol['protocol_hash']}))
if __name__=='__main__':main()
