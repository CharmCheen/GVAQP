# 06 Boundary REFINE Audit

## Findings

- P1 boundary degeneracy is real: all 5 P1 positives were 0.0-0.7.
- Full scan boundary degeneracy remains: 39/40 positives are exactly 0.0-0.7 and positive `event_end` has one unique value.
- Stage 1 video metadata/raw_fps smoke was executed but did not solve the template issue.
- Contact-sheet smoke was executed and produced more varied boundaries, but label stability dropped.
- Post-hoc boundary Scheme C was only partially executed; the failure log says 3/5 completed.
- No dataset3 post-hoc boundary full run exists.
- The no-new-VLM REFINE replay under `test_vlm/outputs/event_native_aqp_p1_refine_gate_v1` is on V13.8, not dataset3, and is based on existing stitched labels rather than new boundary observations.

## Can Boundary Fields Support Event IoU?

No for dataset3. The full scan boundary fields are templated and should not be used for event-IoU claims or REFINE evaluation.

## REFINE Decision

`BOUNDARY_ORACLE_REDESIGN_REQUIRED`

REFINE should be downgraded to limitation/future work. It is not supported as a core innovation in the current dataset3 output.
