# External Label Mapping

Mapping status:

```text
LOOSE_APPROXIMATION / AUDIT_UNRELIABLE
```

Nexar-derived labels must not be treated as equivalent to O_enter_ego_path_v0.

Subsequent recall/certificate results are Nexar-derived-boundary-relative unless a new adjudicated benchmark is created.

## Basis

The bounded VLM micro-audit imported from v1 completed 100 / 100 planned calls using Qwen3-VL-32B-Instruct on NVIDIA H20-3e. It found:

- positive agreement: 0.160
- random-negative estimated miss rate: 0.020
- abstain rate: 0.000
- EXTERNAL_LABEL_AUDIT_RESULT: UNRELIABLE

The dominant mismatch is on the positive side: Nexar collision / alert positives do not reliably match the O_enter_ego_path_v0 predicate. Therefore, v2 candidate and certificate results may be used only as Nexar-derived-boundary-relative evidence under single-dataset scope.
