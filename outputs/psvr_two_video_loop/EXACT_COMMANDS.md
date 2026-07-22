# Exact commands

```bash
python scripts/audit_psvr_two_video_inputs.py
python scripts/freeze_psvr_two_video_queries.py
python scripts/preregister_psvr_two_video_proxy.py
python scripts/build_psvr_two_video_references.py prepare
python scripts/build_psvr_two_video_references.py infer
python scripts/build_psvr_two_video_references.py finalize
python scripts/build_psvr_two_video_references.py verify
python scripts/run_psvr_two_video_proxy.py freeze-implementation
python scripts/freeze_psvr_two_video_deadlines.py profile
python scripts/freeze_psvr_two_video_deadlines.py freeze
python scripts/run_psvr_two_video_proxy.py smoke --family Y8 --video V0 --unit 0
python scripts/run_psvr_two_video_proxy.py smoke --family YP640 --video V0 --unit 0
python scripts/run_psvr_two_video_proxy.py smoke --family YP320 --video V0 --unit 0
python scripts/run_psvr_two_video_proxy.py profile --family Y8
python scripts/run_psvr_two_video_proxy.py profile --family YP640
python scripts/run_psvr_two_video_proxy.py profile --family YP320
python scripts/run_psvr_two_video_proxy.py extract --family Y8 --video V0
python scripts/run_psvr_two_video_proxy.py extract --family Y8 --video V1
python scripts/run_psvr_two_video_proxy.py extract --family YP640 --video V0
python scripts/run_psvr_two_video_proxy.py extract --family YP640 --video V1
python scripts/run_psvr_two_video_proxy.py extract --family YP320 --video V0
python scripts/run_psvr_two_video_proxy.py extract --family YP320 --video V1
python scripts/run_psvr_two_video_proxy.py evaluate
python scripts/run_psvr_two_video_physical.py freeze-pilot-candidates
python scripts/run_psvr_two_video_physical.py proxy-pilot-smoke
python scripts/run_psvr_two_video_physical.py proxy-pilot-smoke-gate
python scripts/run_psvr_two_video_physical.py proxy-pilot
python scripts/evaluate_psvr_two_video_physical.py proxy-pilot
python scripts/evaluate_psvr_two_video_physical.py select-proxy
python scripts/run_psvr_two_video_physical.py preregister-expose
python scripts/run_psvr_two_video_physical.py expose-smoke
python scripts/run_psvr_two_video_physical.py expose-smoke-gate
python scripts/run_psvr_two_video_physical.py expose-formal
python scripts/evaluate_psvr_two_video_physical.py expose
python scripts/run_psvr_two_video_physical.py expose-revision --revision-method exposure_temporal_nms
python scripts/evaluate_psvr_two_video_physical.py expose-revision --revision-method exposure_temporal_nms
python scripts/finalize_psvr_two_video_loop.py
```
