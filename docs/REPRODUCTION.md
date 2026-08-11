# Reproduction

From a clean checkout:

```bash
python -m pip install -e '.[test]'
python -m compileall -q src scripts
pytest -q
python scripts/verify_release.py
python scripts/run_safe_coverage_scan.py --video-manifest examples/example_video_manifest.json --max-actions 20 --output /tmp/scan.json
python scripts/run_fixed_ratio_controller.py --video-manifest examples/example_video_manifest.json --query-config configs/example_query.yaml --budget-sec 120 --config configs/fixed_ratio_25_75.yaml --output-dir /tmp/garc-controller
```

The first three commands verify syntax, unit/determinism/differential/deadline/leakage/Frontier/CLI/provenance behavior, dependency closure, large files, media, weights, secrets, and absolute runtime paths. The examples are replay-only and make zero new Oracle calls.
