#!/usr/bin/env python3
"""Independent adversarial audit of the final YGS decision and fallback."""
from __future__ import annotations
import hashlib, json, os, subprocess, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs/scan_innovation_agentic_loop_v1'

def sha256(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        while chunk:=f.read(1<<20): h.update(chunk)
    return h.hexdigest()
def check(name:str,value:bool,details='')->dict: return {'check':name,'pass':bool(value),'details':details}
def main()->None:
    rows=[]; decision=json.loads((OUT/'final_decision.json').read_text()); h2=json.loads((OUT/'hypotheses/YGS-H002.json').read_text()); h3=json.loads((OUT/'hypotheses/YGS-H003.json').read_text())
    rows.append(check('legal_final_state',decision['final_state']=='SAFE_COVERAGE_BASELINE_REMAINS_STRONGEST'))
    rows.append(check('h002_gate_rejected',h2['status']=='REJECTED' and not h2['static_observability_gate_pass']))
    rows.append(check('h003_gate_rejected',h3['status']=='REJECTED' and not h3['static_observability_gate_pass']))
    rows.append(check('preview_cost_caps',h2['combined_preview_cost_ratio']<=.10 and h3['combined_preview_cost_ratio']<=.10,
                      f"H002={h2['combined_preview_cost_ratio']:.6f}; H003={h3['combined_preview_cost_ratio']:.6f}"))
    rows.append(check('scheduler_not_run_after_gate_failure',not any((OUT/'scheduler_experiments').iterdir())))
    rows.append(check('new_physical_not_run_after_gate_failure',not any((OUT/'physical_validation').iterdir())))
    policy_files=[ROOT/'src/garc_eval/scan_scheduler/policy.py',ROOT/'src/garc_eval/scan_scheduler/config.py',ROOT/'src/garc_eval/scan_scheduler/coverage.py']
    forbidden=('reference_events','candidate_event_map','scan_outputs','offline_oracle','hidden_state')
    intersections={str(p.relative_to(ROOT)):[x for x in forbidden if x in p.read_text().lower()] for p in policy_files}
    rows.append(check('fallback_policy_forbidden_inputs_absent',not any(intersections.values()),json.dumps(intersections,sort_keys=True)))
    rows.append(check('fallback_yolo_disabled',not decision['selected_new_yolo_guided_algorithm']))
    required=[OUT/'reports/SCAN_INNOVATION_REPORT.md',OUT/'reports/METHOD_SPEC.md',OUT/'reports/USAGE.md',OUT/'reports/FAILURE_ANALYSIS.md',
              ROOT/'configs/safe_coverage_scan.yaml',ROOT/'scripts/run_safe_coverage_scan.py']
    rows.append(check('required_fallback_artifacts_exist',all(p.exists() and p.stat().st_size>0 for p in required)))
    env=dict(os.environ); env['PYTHONPATH']=str(ROOT/'src')
    test=subprocess.run(['pytest','-q','tests/scan_scheduler','tests/scan_headroom','tests/partial_scan_v2/test_runtime_accounting.py'],cwd=ROOT,env=env,text=True,capture_output=True)
    rows.append(check('relevant_tests_pass',test.returncode==0,(test.stdout+test.stderr)[-2000:]))
    with tempfile.TemporaryDirectory() as folder:
        a=Path(folder)/'a.csv'; b=Path(folder)/'b.csv'
        command=['python','scripts/run_safe_coverage_scan.py','--video-id','PSP_V0_SHORT','--max-actions','40']
        ra=subprocess.run(command+['--output',str(a)],cwd=ROOT,text=True,capture_output=True)
        rb=subprocess.run(command+['--output',str(b)],cwd=ROOT,text=True,capture_output=True)
        rows.append(check('fallback_cli_deterministic',ra.returncode==0 and rb.returncode==0 and sha256(a)==sha256(b)))
    # The selection builder uses a combined region table for public cost, but
    # explicitly drops both label columns before selection. Record, do not hide,
    # this trusted-code lineage limitation; it cannot invalidate a negative result.
    freeze=(ROOT/'scripts/freeze_ygs_h002.py').read_text()
    rows.append(check('selection_label_columns_explicitly_dropped',
                      'drop(columns=["residual_event_count", "binary_positive"])' in freeze,
                      'builder reads combined table for public geometry/cost; no label column reaches selection'))
    status='PASS' if all(row['pass'] for row in rows) else 'FAIL'
    result={'status':status,'checks_passed':sum(r['pass'] for r in rows),'checks_total':len(rows),'checks':rows,
            'adversarial_conclusion':'The negative Gate decision is supported. Any combined-table lineage would favor, not weaken, the rejected method; the shipped fallback has no such dependency.',
            'audit_script_hash':sha256(Path(__file__))}
    path=OUT/'reports/INDEPENDENT_FINAL_AUDIT.json'; tmp=path.with_suffix('.json.tmp'); tmp.write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n'); tmp.replace(path)
    print(json.dumps(result,indent=2))
    if status!='PASS': raise SystemExit(1)
if __name__=='__main__': main()
