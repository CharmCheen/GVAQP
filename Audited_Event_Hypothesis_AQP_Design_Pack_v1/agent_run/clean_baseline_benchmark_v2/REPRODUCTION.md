# Reproduction

Run from `/qiuyeqing/llama_prl/G-ARC` in the environment recorded in `environment.json`.

```bash
source /qiuyeqing/tools/miniconda3/bin/activate garc
ffprobe -v error -show_entries format=duration:stream=duration,avg_frame_rate -of json data/realcam/long_video_data/long_video_dataset3.mp4
python /qiuyeqing/llama_prl/G-ARC/Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2/scripts/build_v2_oracle.py --stage prepare
python /qiuyeqing/llama_prl/G-ARC/Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2/scripts/build_v2_oracle.py --stage infer
python /qiuyeqing/llama_prl/G-ARC/Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2/scripts/build_v2_oracle.py --stage finalize
python /qiuyeqing/llama_prl/G-ARC/Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2/scripts/build_v2_run_plan.py
python /qiuyeqing/llama_prl/G-ARC/Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2/scripts/run_clean_benchmark_v2.py --stage freeze
python /qiuyeqing/llama_prl/G-ARC/Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2/scripts/pre_execution_audit.py
python /qiuyeqing/llama_prl/G-ARC/Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2/scripts/run_clean_benchmark_v2.py --stage baselines
python /qiuyeqing/llama_prl/G-ARC/Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2/scripts/run_clean_benchmark_v2.py --stage current
python /qiuyeqing/llama_prl/G-ARC/Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2/scripts/run_clean_benchmark_v2.py --stage aggregate
python /qiuyeqing/llama_prl/G-ARC/Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2/scripts/run_clean_benchmark_v2.py --stage compare
python /qiuyeqing/llama_prl/G-ARC/Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2/scripts/finalize_v2_audits.py
python /qiuyeqing/llama_prl/G-ARC/Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2/scripts/validate_benchmark_compatibility.py --new-manifest /qiuyeqing/llama_prl/G-ARC/Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2/BENCHMARK_MANIFEST.json --new-run-id self_check
python - <<'PY'
import csv,hashlib,pathlib
p=pathlib.Path('/qiuyeqing/llama_prl/G-ARC/Audited_Event_Hypothesis_AQP_Design_Pack_v1/agent_run/clean_baseline_benchmark_v2')
for r in csv.DictReader((p/'FILE_MANIFEST.csv').open()):
    assert hashlib.sha256((p/r['path']).read_bytes()).hexdigest()==r['sha256']
print('FILE_MANIFEST PASS')
PY
```

Authoritative extraction is OpenCV at source fps 30 with target 2 fps and integer `frame_count % int(video_fps/2)==0`; unit 346 indices are recorded in `oracle/input_identities.jsonl`. Exact prompt/model/processor/video-processor/generation/parser/sampling hashes are in `oracle/oracle_configuration.json`. Environment, start/end, peak GPU memory, logical/physical calls, and wall time are in `environment.json`.
