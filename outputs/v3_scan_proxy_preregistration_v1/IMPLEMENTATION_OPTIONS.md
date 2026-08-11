# Implementation Options

| implementation | status | reason |
|---|---|---|
| `src/garc_eval/models/yolo_scorer.py` | maintained but single-class frame scorer | insufficient direct multi-class unit-table finalization alone |
| `scripts/partial_scan_pilot_common.py` | historical maintained | different cut-in query/reference; not promoted |
| `scripts/run_mfrp_previews.py` | historical maintained | different preview study; not promoted |
| `scripts/run_v3_prospective_scan_proxy.py` | selected new prospective wrapper | binds frozen V3 units to simple YOLOv8n midpoint proxy without semantic inputs |

Selection used interface, deterministic identity, cheapness, and causal availability only; no downstream result was read.
