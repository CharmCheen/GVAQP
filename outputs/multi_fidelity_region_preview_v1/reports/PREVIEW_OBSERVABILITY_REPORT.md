# Preview Observability Report

All four frozen configurations cover all 229 regions and were independently repeated twice.

| Config | Conservative cost (s) | Full-SCAN ratio | Deterministic | Missing cells |
|---|---:|---:|---|---:|
| P0 | 55.700 | 0.0290 | True | 0 |
| P1_L | 62.757 | 0.0327 | True | 0 |
| P1_M | 57.939 | 0.0302 | True | 0 |
| P2 | 153.401 | 0.0800 | True | 0 |

Cost is the sum of the slower per-video observation across the two repeats, frozen before label analysis. P1 uses frozen YOLOv8n detection only; P2 uses sparse frame differences without optical flow. All configurations pass the 10% cost ceiling.
