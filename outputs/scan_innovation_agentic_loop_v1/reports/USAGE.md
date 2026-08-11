# Usage

Generate a public-state-only order:

```bash
python scripts/run_safe_coverage_scan.py \
  --video-id PSP_V0_SHORT \
  --max-actions 20 \
  --output /tmp/scan_order.csv
```

Choose another frozen coverage mechanism explicitly:

```bash
python scripts/run_safe_coverage_scan.py \
  --video-id PSP_V1_LONG \
  --policy MACRO_REGION_LARGEST_GAP \
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
