# P0 V3 Materializer Mechanism Decomposition

Protocol: `bde64b325942b66575595d5213fb0436caa01cffb245bd412969153f84611cb9`. This is an outcome-preserving cached replay of the already frozen 54 P0 traces.  It uses no oracle calls, no selector change, no threshold sweep and no new materializer proposal. It maps historical Stage-0 C0→C3 natural lineage to current V3 units, then compares current K3.

| Mechanism increment | Mean ΔF1 | Median ΔF1 | + / = / - cells |
|---|---:|---:|---:|
| gap constraint | 0.1738 | 0.1377 | 40 / 14 / 0 |
| duration cap | 0.0072 | 0.0000 | 10 / 44 / 0 |
| queried-negative barrier | 0.0034 | 0.0000 | 5 / 49 / 0 |
| current-V3 unknown/parse/exact semantics | -0.0003 | 0.0000 | 0 / 50 / 4 |

Interpretation rule: an increment is evidence for that exact constraint only when it changes output on the same trace.  A zero does not say the constraint is invalid; it says the frozen sparse traces did not expose a case in which it changed the primary overlap-any event metric.  Because the reference event relation is full-grid K3-defined, all event-level attribution remains model-relative/circularity-qualified.
